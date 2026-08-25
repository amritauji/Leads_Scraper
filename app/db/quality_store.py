"""SQLite store for Data Quality Results."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_connection
from app.models import (
    Conflict,
    DataQualityResult,
    DuplicateResult,
    FieldValidation,
)


class QualityResultStore:
    """Persists DataQualityResult records to SQLite."""

    def __init__(self, db_path: str | None = None):
        self._conn = get_connection(db_path)

    def add(self, result: DataQualityResult) -> DataQualityResult:
        """Insert a DataQualityResult."""
        self._conn.execute(
            """INSERT OR REPLACE INTO quality_results
               (quality_result_id, lead_id, research_job_id, original_lead,
                cleaned_lead, validation_results, duplicate_result,
                issues, conflicts, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.quality_result_id,
                result.lead_id,
                result.research_job_id,
                json.dumps(result.original_lead, default=str),
                json.dumps(result.cleaned_lead, default=str),
                json.dumps([
                    {"field": v.field, "value": v.value, "status": v.status, "issues": v.issues}
                    for v in result.validation
                ], default=str),
                json.dumps({
                    "is_duplicate": result.duplicate_result.is_duplicate,
                    "duplicate_type": result.duplicate_result.duplicate_type,
                    "matched_lead_id": result.duplicate_result.matched_lead_id,
                    "match_reason": result.duplicate_result.match_reason,
                }, default=str),
                json.dumps(result.issues, default=str),
                json.dumps([{"field": c.field, "values": c.values} for c in result.conflicts], default=str),
                result.created_at,
            ),
        )
        self._conn.commit()
        return result

    def get_by_id(self, quality_result_id: str) -> DataQualityResult | None:
        """Retrieve a DataQualityResult by ID."""
        row = self._conn.execute(
            "SELECT * FROM quality_results WHERE quality_result_id = ?",
            (quality_result_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def get_by_lead_id(self, lead_id: str) -> DataQualityResult | None:
        """Retrieve a DataQualityResult by lead_id."""
        row = self._conn.execute(
            "SELECT * FROM quality_results WHERE lead_id = ? ORDER BY created_at DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def _row_to_result(self, row: sqlite3.Row) -> DataQualityResult:
        """Convert a DB row to a DataQualityResult."""
        val_data = json.loads(row["validation_results"])
        dup_data = json.loads(row["duplicate_result"])
        conflict_data = json.loads(row["conflicts"])

        return DataQualityResult(
            quality_result_id=row["quality_result_id"],
            lead_id=row["lead_id"],
            research_job_id=row["research_job_id"],
            original_lead=json.loads(row["original_lead"]),
            cleaned_lead=json.loads(row["cleaned_lead"]),
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
            issues=json.loads(row["issues"]),
            conflicts=[
                Conflict(field=c["field"], values=c["values"])
                for c in conflict_data
            ],
            created_at=row["created_at"],
        )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM quality_results").fetchone()[0]

    def clear(self):
        self._conn.execute("DELETE FROM quality_results")
        self._conn.commit()
