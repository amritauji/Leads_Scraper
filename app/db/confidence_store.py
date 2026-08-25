"""SQLite store for Confidence Results."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_connection
from app.models import Conflict, ConfidenceResult


class ConfidenceResultStore:
    """Persists ConfidenceResult records to SQLite."""

    def __init__(self, db_path: str | None = None):
        self._conn = get_connection(db_path)

    def add(self, result: ConfidenceResult) -> ConfidenceResult:
        """Insert a ConfidenceResult."""
        self._conn.execute(
            """INSERT OR REPLACE INTO confidence_results
               (confidence_result_id, lead_id, research_job_id, quality_result_id,
                score, level, positive_factors, negative_factors, conflicts, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.confidence_result_id,
                result.lead_id,
                result.research_job_id,
                result.quality_result_id,
                result.score,
                result.level,
                json.dumps(result.positive_factors, default=str),
                json.dumps(result.negative_factors, default=str),
                json.dumps([{"field": c.field, "values": c.values} for c in result.conflicts], default=str),
                result.created_at,
            ),
        )
        self._conn.commit()
        return result

    def get_by_id(self, confidence_result_id: str) -> ConfidenceResult | None:
        """Retrieve a ConfidenceResult by ID."""
        row = self._conn.execute(
            "SELECT * FROM confidence_results WHERE confidence_result_id = ?",
            (confidence_result_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def get_by_lead_id(self, lead_id: str) -> ConfidenceResult | None:
        """Retrieve a ConfidenceResult by lead_id."""
        row = self._conn.execute(
            "SELECT * FROM confidence_results WHERE lead_id = ? ORDER BY created_at DESC LIMIT 1",
            (lead_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def _row_to_result(self, row: sqlite3.Row) -> ConfidenceResult:
        """Convert a DB row to a ConfidenceResult."""
        conflict_data = json.loads(row["conflicts"])

        return ConfidenceResult(
            confidence_result_id=row["confidence_result_id"],
            lead_id=row["lead_id"],
            research_job_id=row["research_job_id"],
            quality_result_id=row["quality_result_id"],
            score=row["score"],
            level=row["level"],
            positive_factors=json.loads(row["positive_factors"]),
            negative_factors=json.loads(row["negative_factors"]),
            conflicts=[
                Conflict(field=c["field"], values=c["values"])
                for c in conflict_data
            ],
            created_at=row["created_at"],
        )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM confidence_results").fetchone()[0]

    def clear(self):
        self._conn.execute("DELETE FROM confidence_results")
        self._conn.commit()
