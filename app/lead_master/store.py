"""Lead Master store backed by PostgreSQL (Supabase)."""

from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import LeadMaster


class LeadMasterStore:
    """PostgreSQL-backed Lead Master store."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, record: LeadMaster) -> LeadMaster:
        """Insert or replace a Lead Master record."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lead_master
                       (master_id, lead_id, research_job_id, company_name, website,
                        industry, category, segment, founded, revenue, city_country,
                        ceo_founder_name, ceo_linkedin, marketing_head_name,
                        marketing_head_linkedin, contact_email, confidence_score,
                        confidence_level, confidence_result_id, quality_result_id,
                        data_quality_issues, evidence_refs, raw_evidence_refs,
                        review_id, source_lead_json, status, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (master_id) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        website = EXCLUDED.website,
                        industry = EXCLUDED.industry,
                        confidence_score = EXCLUDED.confidence_score,
                        confidence_level = EXCLUDED.confidence_level,
                        confidence_result_id = EXCLUDED.confidence_result_id,
                        quality_result_id = EXCLUDED.quality_result_id,
                        data_quality_issues = EXCLUDED.data_quality_issues,
                        evidence_refs = EXCLUDED.evidence_refs,
                        review_id = EXCLUDED.review_id,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at""",
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
                        psycopg2.extras.Json(record.data_quality_issues),
                        psycopg2.extras.Json(record.evidence_refs),
                        psycopg2.extras.Json(record.raw_evidence_refs),
                        record.review_id,
                        psycopg2.extras.Json(record.source_lead_json),
                        record.status,
                        record.created_at,
                        record.updated_at,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return record

    def get_by_id(self, master_id: str) -> LeadMaster | None:
        """Retrieve a Lead Master record by master_id."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s", (master_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_record(row)
        finally:
            conn.close()

    def get_by_lead_id(self, lead_id: str) -> LeadMaster | None:
        """Retrieve a Lead Master record by original lead_id."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE lead_id = %s", (lead_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_record(row)
        finally:
            conn.close()

    def get_all(self) -> list[LeadMaster]:
        """Retrieve all Lead Master records."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master ORDER BY created_at DESC")
                return [self._row_to_record(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM lead_master")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def to_list(self) -> list[dict[str, Any]]:
        """Export all records as dicts."""
        return [r.to_dict() for r in self.get_all()]

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lead_master")
            conn.commit()
        finally:
            conn.close()

    def _row_to_record(self, row: dict) -> LeadMaster:
        """Convert a DB row to a LeadMaster."""
        def _json(val):
            if val is None:
                return [] if isinstance(val, list) else {}
            if isinstance(val, (list, dict)):
                return val
            return json.loads(val)

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
            data_quality_issues=_json(row["data_quality_issues"]),
            evidence_refs=_json(row["evidence_refs"]),
            raw_evidence_refs=_json(row["raw_evidence_refs"]),
            review_id=row["review_id"],
            source_lead_json=_json(row["source_lead_json"]),
            status=row["status"] or "accepted",
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
