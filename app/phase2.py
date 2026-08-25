"""Phase 2 Pipeline — connects Data Quality → Confidence → Review → Lead Master.

This module orchestrates the post-research workflow:
    Standard Lead JSON
        → Cleaning
        → Validation
        → Duplicate Detection
        → Confidence Scoring
        → Routing (high/low/conflict)
        → Review Queue (if needed)
        → Lead Master
"""

from __future__ import annotations

import uuid
from typing import Any

from app.models import (
    ConfidenceResult,
    DataQualityResult,
    LeadMaster,
    ReviewItem,
)
from app.quality.engine import run_quality_check
from app.quality.confidence import calculate_confidence
from app.review.queue import ReviewQueue
from app.lead_master.store import LeadMasterStore


# Confidence thresholds
HIGH_CONFIDENCE_THRESHOLD = 70
LOW_CONFIDENCE_THRESHOLD = 40


class Phase2Pipeline:
    """Orchestrates the Data Quality → Lead Master pipeline."""

    def __init__(
        self,
        review_queue: ReviewQueue | None = None,
        lead_master: LeadMasterStore | None = None,
    ):
        self.review_queue = review_queue or ReviewQueue()
        self.lead_master = lead_master or LeadMasterStore()
        self._stats = {
            "total": 0,
            "high_confidence": 0,
            "low_confidence": 0,
            "routed_to_review": 0,
            "added_to_master": 0,
            "duplicates_skipped": 0,
        }

    def process_leads(
        self,
        leads: list[dict[str, Any]],
        research_job_id: str | None = None,
    ) -> dict[str, Any]:
        """Process a batch of Standard Lead JSONs through the full pipeline.

        Args:
            leads: List of Standard Lead JSON dicts.
            research_job_id: Optional job ID for traceability.

        Returns:
            Summary of processing results.
        """
        self._stats = {
            "total": len(leads),
            "high_confidence": 0,
            "low_confidence": 0,
            "routed_to_review": 0,
            "added_to_master": 0,
            "duplicates_skipped": 0,
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
        """Process a single Standard Lead JSON through the full pipeline.

        Returns:
            Dict with dq_result, confidence, routing decision, and any created records.
        """
        lead_id = lead.get("LeadId", f"lead_{uuid.uuid4().hex[:8]}")

        # Step 1: Data Quality Engine
        existing = self.lead_master.to_list()
        dq_result = run_quality_check(lead, existing_leads=existing)

        # Step 2: Confidence Engine
        confidence = calculate_confidence(dq_result, all_leads=existing)

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

        # Skip duplicates
        if dq_result.duplicate_result.is_duplicate:
            self._stats["duplicates_skipped"] += 1
            return {
                "action": "duplicate_skipped",
                "matched_lead_id": dq_result.duplicate_result.matched_lead_id,
                "match_reason": dq_result.duplicate_result.match_reason,
            }

        # High confidence → direct to Lead Master
        if confidence.level == "high":
            self._stats["high_confidence"] += 1
            master = self._create_master_record(
                dq_result, confidence, original_lead, research_job_id, review_id=None
            )
            self._stats["added_to_master"] += 1
            return {
                "action": "added_to_master",
                "master_id": master.master_id,
                "confidence_score": confidence.score,
            }

        # Low or conflict → Review Queue
        self._stats["low_confidence"] += 1
        review_item = self._add_to_review(
            lead_id, dq_result, confidence, original_lead
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
            data_quality_issues=dq_result.issues,
            evidence_refs=cleaned.get("evidence_refs", []),
            raw_evidence_refs=dq_result.original_lead.get("evidence_refs", []),
            quality_result_id=None,
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
        """Add a lead to the review queue."""
        # Determine primary reason
        reason = "low_confidence"
        if dq_result.conflicts:
            reason = "conflict"
        elif dq_result.duplicate_result.is_duplicate:
            reason = "duplicate"
        elif dq_result.issues:
            invalid_issues = [i for i in dq_result.issues if "invalid" in i.lower()]
            if invalid_issues:
                reason = "invalid_fields"
            else:
                reason = "missing_fields"

        item = ReviewItem(
            lead_id=lead_id,
            reason=reason,
            lead_data=original_lead,
            confidence=confidence.to_dict(),
            issues=dq_result.issues,
            conflicts=[{"field": c.field, "values": c.values} for c in dq_result.conflicts],
            evidence_refs=original_lead.get("evidence_refs", []),
        )

        return self.review_queue.add(item)

    def approve_review(self, review_id: str) -> dict[str, Any] | None:
        """Approve a review item and move it to Lead Master.

        Returns:
            The created LeadMaster dict, or None if not found.
        """
        item = self.review_queue.approve(review_id)
        if not item:
            return None

        # Run quality + confidence on the lead data
        dq_result = run_quality_check(item.lead_data)
        confidence = calculate_confidence(dq_result)

        # Create master record
        master = self._create_master_record(
            dq_result, confidence, item.lead_data,
            research_job_id=None, review_id=review_id,
        )

        return master.to_dict()

    def get_stats(self) -> dict[str, int]:
        return dict(self._stats)
