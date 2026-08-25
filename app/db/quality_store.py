"""PostgreSQL store for Data Quality Results."""

from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import (
    Conflict,
    DataQualityResult,
    DuplicateResult,
    FieldValidation,
)


class QualityResultStore:
    """Persists DataQualityResult records to PostgreSQL."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, result: DataQualityResult) -> DataQualityResult:
        """Insert a DataQualityResult."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO quality_results
                       (quality_result_id, lead_id, research_job_id, original_lead,
                        cleaned_lead, validation_results, duplicate_result,
                        issues, conflicts, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (quality_result_id) DO UPDATE SET
                        original_lead = EXCLUDED.original_lead,
                        cleaned_lead = EXCLUDED.cleaned_lead,
                        validation_results = EXCLUDED.validation_results,
                        duplicate_result = EXCLUDED.duplicate_result,
                        issues = EXCLUDED.issues,
                        conflicts = EXCLUDED.conflicts""",
                    (
                        result.quality_result_id,
                        result.lead_id,
                        result.research_job_id,
                        psycopg2.extras.Json(result.original_lead),
                        psycopg2.extras.Json(result.cleaned_lead),
                        psycopg2.extras.Json([
                            {"field": v.field, "value": v.value, "status": v.status, "issues": v.issues}
                            for v in result.validation
                        ]),
                        psycopg2.extras.Json({
                            "is_duplicate": result.duplicate_result.is_duplicate,
                            "duplicate_type": result.duplicate_result.duplicate_type,
                            "matched_lead_id": result.duplicate_result.matched_lead_id,
                            "match_reason": result.duplicate_result.match_reason,
                        }),
                        psycopg2.extras.Json(result.issues),
                        psycopg2.extras.Json([{"field": c.field, "values": c.values} for c in result.conflicts]),
                        result.created_at,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return result

    def get_by_id(self, quality_result_id: str) -> DataQualityResult | None:
        """Retrieve a DataQualityResult by ID."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM quality_results WHERE quality_result_id = %s",
                    (quality_result_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_result(row)
        finally:
            conn.close()

    def get_by_lead_id(self, lead_id: str) -> DataQualityResult | None:
        """Retrieve a DataQualityResult by lead_id."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM quality_results WHERE lead_id = %s ORDER BY created_at DESC LIMIT 1",
                    (lead_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_result(row)
        finally:
            conn.close()

    def _row_to_result(self, row: dict) -> DataQualityResult:
        """Convert a DB row to a DataQualityResult."""
        val_data = row["validation_results"] if isinstance(row["validation_results"], list) else json.loads(row["validation_results"])
        dup_data = row["duplicate_result"] if isinstance(row["duplicate_result"], dict) else json.loads(row["duplicate_result"])
        conflict_data = row["conflicts"] if isinstance(row["conflicts"], list) else json.loads(row["conflicts"])

        return DataQualityResult(
            quality_result_id=row["quality_result_id"],
            lead_id=row["lead_id"],
            research_job_id=row["research_job_id"],
            original_lead=row["original_lead"] if isinstance(row["original_lead"], dict) else json.loads(row["original_lead"]),
            cleaned_lead=row["cleaned_lead"] if isinstance(row["cleaned_lead"], dict) else json.loads(row["cleaned_lead"]),
            validation=[
                FieldValidation(
                    field=v["field"], value=v["value"],
                    status=v["status"], issues=v.get("issues", []),
                )
                for v in val_data
            ],
            duplicate_result=DuplicateResult(
                is_duplicate=dup_data.get("is_duplicate", False),
                duplicate_type=dup_data.get("duplicate_type"),
                matched_lead_id=dup_data.get("matched_lead_id"),
                match_reason=dup_data.get("match_reason"),
            ),
            issues=row["issues"] if isinstance(row["issues"], list) else json.loads(row["issues"]),
            conflicts=[
                Conflict(field=c["field"], values=c["values"])
                for c in conflict_data
            ],
            created_at=str(row["created_at"]),
        )

    def count(self) -> int:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM quality_results")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quality_results")
            conn.commit()
        finally:
            conn.close()
