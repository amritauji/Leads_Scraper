"""Lead Master store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_connection
from app.models import LeadMaster


class LeadMasterStore:
    """SQLite-backed Lead Master store."""

    def __init__(self, db_path: str | None = None):
        self._conn = get_connection(db_path)

    def add(self, record: LeadMaster) -> LeadMaster:
        """Insert or replace a Lead Master record."""
        self._conn.execute(
            """INSERT OR REPLACE INTO lead_master
               (master_id, lead_id, research_job_id, company_name, website,
                industry, category, segment, founded, revenue, city_country,
                ceo_founder_name, ceo_linkedin, marketing_head_name,
                marketing_head_linkedin, contact_email, confidence_score,
                confidence_level, confidence_result_id, quality_result_id,
                data_quality_issues, evidence_refs, raw_evidence_refs,
                review_id, source_lead_json, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.master_id,
                record.lead_id,
                record.research_job_id,
                record.company_name,
                record.website,
                record.industry,
                record.category,
                record.segment,
                record.founded,
                record.revenue,
                record.city_country,
                record.ceo_founder_name,
                record.ceo_linkedin,
                record.marketing_head_name,
                record.marketing_head_linkedin,
                record.contact_email,
                record.confidence_score,
                record.confidence_level,
                record.confidence_result_id,
                record.quality_result_id,
                json.dumps(record.data_quality_issues, default=str),
                json.dumps(record.evidence_refs, default=str),
                json.dumps(record.raw_evidence_refs, default=str),
                record.review_id,
                json.dumps(record.source_lead_json, default=str),
                record.status,
                record.created_at,
                record.updated_at,
            ),
        )
        self._conn.commit()
        return record

    def get_by_id(self, master_id: str) -> LeadMaster | None:
        """Retrieve a Lead Master record by master_id."""
        row = self._conn.execute(
            "SELECT * FROM lead_master WHERE master_id = ?", (master_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def get_by_lead_id(self, lead_id: str) -> LeadMaster | None:
        """Retrieve a Lead Master record by original lead_id."""
        row = self._conn.execute(
            "SELECT * FROM lead_master WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def get_all(self) -> list[LeadMaster]:
        """Retrieve all Lead Master records."""
        rows = self._conn.execute(
            "SELECT * FROM lead_master ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM lead_master").fetchone()[0]

    def to_list(self) -> list[dict[str, Any]]:
        """Export all records as dicts."""
        return [r.to_dict() for r in self.get_all()]

    def clear(self):
        self._conn.execute("DELETE FROM lead_master")
        self._conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> LeadMaster:
        """Convert a DB row to a LeadMaster."""
        return LeadMaster(
            master_id=row["master_id"],
            lead_id=row["lead_id"],
            research_job_id=row["research_job_id"],
            company_name=row["company_name"],
            website=row["website"],
            industry=row["industry"],
            category=row["category"],
            segment=row["segment"],
            founded=row["founded"],
            revenue=row["revenue"],
            city_country=row["city_country"],
            ceo_founder_name=row["ceo_founder_name"],
            ceo_linkedin=row["ceo_linkedin"],
            marketing_head_name=row["marketing_head_name"],
            marketing_head_linkedin=row["marketing_head_linkedin"],
            contact_email=row["contact_email"],
            confidence_score=row["confidence_score"] or 0,
            confidence_level=row["confidence_level"] or "low",
            confidence_result_id=row["confidence_result_id"],
            quality_result_id=row["quality_result_id"],
            data_quality_issues=json.loads(row["data_quality_issues"] or "[]"),
            evidence_refs=json.loads(row["evidence_refs"] or "[]"),
            raw_evidence_refs=json.loads(row["raw_evidence_refs"] or "[]"),
            review_id=row["review_id"],
            source_lead_json=json.loads(row["source_lead_json"] or "{}"),
            status=row["status"] or "accepted",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
