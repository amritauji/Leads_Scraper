"""Phase 2 Pipeline -- connects Data Quality -> Confidence -> Review -> Lead Master.

This module orchestrates the post-research workflow:
    Standard Lead JSON
        -> Cleaning
        -> Validation
        -> Duplicate Detection
        -> Confidence Scoring
        -> Routing (high/low/conflict)
        -> Review Queue (if needed)
        -> Lead Master

All intermediate results are persisted to SQLite for full lineage.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.models import (
    ConfidenceResult,
    DataQualityResult,
    DuplicateEvent,
    LeadMaster,
    ReviewItem,
)
from app.quality.engine import run_quality_check
from app.quality.confidence import calculate_confidence
from app.db.quality_store import QualityResultStore
from app.db.confidence_store import ConfidenceResultStore
from app.db.duplicate_store import DuplicateEventStore
from app.lead_master.store import LeadMasterStore
from app.review.queue import ReviewQueue


# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 70
LOW_CONFIDENCE_THRESHOLD = 40


class Phase2Pipeline:
    """Orchestrates the Data Quality -> Lead Master pipeline with full persistence."""

    def __init__(
        self,
        db_path: str | None = None,
        lead_master: LeadMasterStore | None = None,
        review_queue: ReviewQueue | None = None,
        quality_store: QualityResultStore | None = None,
        confidence_store: ConfidenceResultStore | None = None,
        duplicate_store: DuplicateEventStore | None = None,
    ):
        self.lead_master = lead_master or LeadMasterStore(db_path)
        self.review_queue = review_queue or ReviewQueue(db_path)
        self.quality_store = quality_store or QualityResultStore(db_path)
        self.confidence_store = confidence_store or ConfidenceResultStore(db_path)
        self.duplicate_store = duplicate_store or DuplicateEventStore(db_path)
        self._stats = {
            "total": 0,
            "high_confidence": 0,
            "low_confidence": 0,
            "routed_to_review": 0,
            "added_to_master": 0,
            "duplicates_skipped": 0,
            "duplicate_events_recorded": 0,
        }

    def process_leads(
        self,
        leads: list[dict[str, Any]],
        research_job_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a batch of Standard Lead JSONs through the full pipeline."""
        self._stats = {
            "total": len(leads),
            "high_confidence": 0,
            "low_confidence": 0,
            "routed_to_review": 0,
            "added_to_master": 0,
            "duplicates_skipped": 0,
            "duplicate_events_recorded": 0,
        }

        results: list[dict[str, Any]] = []
        for lead in leads:
            result = self.process_single_lead(lead, research_job_id)
            results.append(result)

        return {
            "stats": self._stats,
            "results": results,
        }

    def process_single_lead(
        self,
        lead: dict[str, Any],
        research_job_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a single Standard Lead JSON through the full pipeline."""
        lead_id = lead.get("LeadId", f"lead_{uuid.uuid4().hex[:8]}")

        # Step 1: Data Quality Engine
        existing = self.lead_master.to_list()
        dq_result = run_quality_check(
            lead, existing_leads=existing, lead_id=lead_id, research_job_id=research_job_id,
        )

        # Persist Data Quality Result
        self.quality_store.add(dq_result)

        # Step 2: Confidence Engine
        confidence = calculate_confidence(dq_result, all_leads=existing)

        # Persist Confidence Result
        self.confidence_store.add(confidence)

        # Step 3: Routing
        routing = self._route(lead_id, dq_result, confidence, lead, research_job_id)

        return {
            "lead_id": lead_id,
            "dq_result": dq_result,
            "confidence": confidence,
            "routing": routing,
        }

    def _route(
        self,
        lead_id: str,
        dq_result: DataQualityResult,
        confidence: ConfidenceResult,
        original_lead: dict[str, Any],
        research_job_id: str | None,
    ) -> dict[str, Any]:
        """Route lead based on confidence level and duplicate status."""

        # Duplicates: record event and skip
        if dq_result.duplicate_result.is_duplicate:
            self._stats["duplicates_skipped"] += 1
            dup_event = DuplicateEvent(
                incoming_lead_id=lead_id,
                matched_master_id=dq_result.duplicate_result.matched_lead_id,
                match_type=dq_result.duplicate_result.duplicate_type or "exact",
                match_reason=dq_result.duplicate_result.match_reason or "unknown",
                quality_result_id=dq_result.quality_result_id,
                research_job_id=research_job_id,
            )
            self.duplicate_store.add(dup_event)
            self._stats["duplicate_events_recorded"] += 1
            return {
                "action": "duplicate_skipped",
                "duplicate_event_id": dup_event.duplicate_event_id,
                "matched_lead_id": dq_result.duplicate_result.matched_lead_id,
                "match_reason": dq_result.duplicate_result.match_reason,
            }

        # High confidence -> direct to Lead Master
        if confidence.level == "high":
            self._stats["high_confidence"] += 1
            master = self._create_master_record(
                dq_result, confidence, original_lead, research_job_id, review_id=None,
            )
            self._stats["added_to_master"] += 1
            return {
                "action": "added_to_master",
                "master_id": master.master_id,
                "confidence_score": confidence.score,
            }

        # Medium or low confidence -> Review Queue
        self._stats["low_confidence"] += 1
        review_item = self._add_to_review(
            lead_id, dq_result, confidence, original_lead,
        )
        self._stats["routed_to_review"] += 1

        return {
            "action": "sent_to_review",
            "review_id": review_item.review_id,
            "reason": review_item.reason,
            "confidence_score": confidence.score,
        }

    def _create_master_record(
        self,
        dq_result: DataQualityResult,
        confidence: ConfidenceResult,
        original_lead: dict[str, Any],
        research_job_id: str | None,
        review_id: str | None,
    ) -> LeadMaster:
        """Create a Lead Master record from a high-confidence lead."""
        cleaned = dq_result.cleaned_lead

        master = LeadMaster(
            lead_id=original_lead.get("LeadId", ""),
            research_job_id=research_job_id,
            company_name=cleaned.get("company_name"),
            website=cleaned.get("website"),
            industry=cleaned.get("industry"),
            category=cleaned.get("category"),
            segment=cleaned.get("segment"),
            founded=cleaned.get("founded"),
            revenue=cleaned.get("revenue"),
            city_country=cleaned.get("city_country"),
            ceo_founder_name=cleaned.get("ceo_founder_name"),
            ceo_linkedin=cleaned.get("ceo_linkedin"),
            marketing_head_name=cleaned.get("marketing_head_name"),
            marketing_head_linkedin=cleaned.get("marketing_head_linkedin"),
            contact_email=cleaned.get("contact_email"),
            confidence_score=confidence.score,
            confidence_level=confidence.level,
            confidence_result_id=confidence.confidence_result_id,
            quality_result_id=dq_result.quality_result_id,
            data_quality_issues=dq_result.issues,
            evidence_refs=cleaned.get("evidence_refs", []),
            raw_evidence_refs=dq_result.original_lead.get("evidence_refs", []),
            review_id=review_id,
            source_lead_json=original_lead,
            status="accepted",
        )

        return self.lead_master.add(master)

    def _add_to_review(
        self,
        lead_id: str,
        dq_result: DataQualityResult,
        confidence: ConfidenceResult,
        original_lead: dict[str, Any],
    ) -> ReviewItem:
        """Add a lead to the review queue with full metadata."""
        reason = self._determine_review_reason(dq_result, confidence)

        item = ReviewItem(
            lead_id=lead_id,
            reason=reason,
            lead_data=original_lead,
            confidence_score=confidence.score,
            confidence_level=confidence.level,
            confidence_result_id=confidence.confidence_result_id,
            quality_result_id=dq_result.quality_result_id,
            issues=dq_result.issues,
            conflicts=[{"field": c.field, "values": c.values} for c in dq_result.conflicts],
            evidence_refs=original_lead.get("evidence_refs", []),
        )

        return self.review_queue.add(item)

    def _determine_review_reason(
        self, dq_result: DataQualityResult, confidence: ConfidenceResult,
    ) -> str:
        """Determine the primary reason a lead needs review."""
        if dq_result.conflicts:
            return "conflict"
        if dq_result.issues:
            invalid_issues = [i for i in dq_result.issues if "invalid" in i.lower()]
            if invalid_issues:
                return "validation_failure"
            return "low_confidence" if confidence.level == "low" else "medium_confidence"
        return "medium_confidence" if confidence.level == "medium" else "low_confidence"

    def approve_review(self, review_id: str) -> dict[str, Any] | None:
        """Approve a review item and move it to Lead Master."""
        item = self.review_queue.approve(review_id)
        if not item:
            return None

        # Re-run quality + confidence on the (possibly edited) lead data
        dq_result = run_quality_check(item.lead_data)
        self.quality_store.add(dq_result)

        confidence = calculate_confidence(dq_result)
        self.confidence_store.add(confidence)

        master = self._create_master_record(
            dq_result, confidence, item.lead_data,
            research_job_id=None, review_id=review_id,
        )

        return master.to_dict()

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)
