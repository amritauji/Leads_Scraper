"""Lead Master — authoritative accepted lead record store."""

from __future__ import annotations

import json
import os
from typing import Any

from app.models import LeadMaster


class LeadMasterStore:
    """In-memory Lead Master with file persistence."""

    def __init__(self, storage_path: str = "output/lead_master.json"):
        self._records: list[LeadMaster] = []
        self._storage_path = storage_path
        self._load()

    def _load(self):
        """Load existing records from disk."""
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for rec in data:
                    record = LeadMaster(
                        master_id=rec.get("master_id", ""),
                        lead_id=rec.get("lead_id", ""),
                        research_job_id=rec.get("research_job_id"),
                        company_name=rec.get("company_name"),
                        website=rec.get("website"),
                        industry=rec.get("industry"),
                        category=rec.get("category"),
                        segment=rec.get("segment"),
                        founded=rec.get("founded"),
                        revenue=rec.get("revenue"),
                        city_country=rec.get("city_country"),
                        ceo_founder_name=rec.get("ceo_founder_name"),
                        ceo_linkedin=rec.get("ceo_linkedin"),
                        marketing_head_name=rec.get("marketing_head_name"),
                        marketing_head_linkedin=rec.get("marketing_head_linkedin"),
                        contact_email=rec.get("contact_email"),
                        confidence_score=rec.get("confidence_score", 0),
                        confidence_level=rec.get("confidence_level", "low"),
                        data_quality_issues=rec.get("data_quality_issues", []),
                        evidence_refs=rec.get("evidence_refs", []),
                        raw_evidence_refs=rec.get("raw_evidence_refs", []),
                        quality_result_id=rec.get("quality_result_id"),
                        review_id=rec.get("review_id"),
                        source_lead_json=rec.get("source_lead_json", {}),
                        status=rec.get("status", "accepted"),
                        created_at=rec.get("created_at", ""),
                        updated_at=rec.get("updated_at", ""),
                    )
                    self._records.append(record)
            except (json.JSONDecodeError, KeyError):
                self._records = []

    def _save(self):
        """Persist records to disk."""
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        data = [r.to_dict() for r in self._records]
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def add(self, record: LeadMaster) -> LeadMaster:
        """Add a record to Lead Master."""
        self._records.append(record)
        self._save()
        return record

    def get_all(self) -> list[LeadMaster]:
        """Get all records."""
        return list(self._records)

    def get_by_id(self, master_id: str) -> LeadMaster | None:
        """Get a record by master_id."""
        return next((r for r in self._records if r.master_id == master_id), None)

    def get_by_lead_id(self, lead_id: str) -> LeadMaster | None:
        """Get a record by original lead_id."""
        return next((r for r in self._records if r.lead_id == lead_id), None)

    def count(self) -> int:
        """Return total records."""
        return len(self._records)

    def to_list(self) -> list[dict[str, Any]]:
        """Export all records as dicts."""
        return [r.to_dict() for r in self._records]

    def clear(self):
        """Clear all records."""
        self._records.clear()
        self._save()
