"""PostgreSQL store for Confidence Results."""

from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import Conflict, ConfidenceResult


class ConfidenceResultStore:
    """Persists ConfidenceResult records to PostgreSQL."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, result: ConfidenceResult) -> ConfidenceResult:
        """Insert a ConfidenceResult."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO confidence_results
                       (confidence_result_id, lead_id, research_job_id, quality_result_id,
                        score, level, positive_factors, negative_factors, conflicts, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (confidence_result_id) DO UPDATE SET
                        score = EXCLUDED.score,
                        level = EXCLUDED.level,
                        positive_factors = EXCLUDED.positive_factors,
                        negative_factors = EXCLUDED.negative_factors,
                        conflicts = EXCLUDED.conflicts""",
                    (
                        result.confidence_result_id,
                        result.lead_id,
                        result.research_job_id,
                        result.quality_result_id,
                        result.score,
                        result.level,
                        psycopg2.extras.Json(result.positive_factors),
                        psycopg2.extras.Json(result.negative_factors),
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

    def get_by_id(self, confidence_result_id: str) -> ConfidenceResult | None:
        """Retrieve a ConfidenceResult by ID."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM confidence_results WHERE confidence_result_id = %s",
                    (confidence_result_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_result(row)
        finally:
            conn.close()

    def get_by_lead_id(self, lead_id: str) -> ConfidenceResult | None:
        """Retrieve a ConfidenceResult by lead_id."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM confidence_results WHERE lead_id = %s ORDER BY created_at DESC LIMIT 1",
                    (lead_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_result(row)
        finally:
            conn.close()

    def _row_to_result(self, row: dict) -> ConfidenceResult:
        """Convert a DB row to a ConfidenceResult."""
        conflict_data = row["conflicts"] if isinstance(row["conflicts"], list) else json.loads(row["conflicts"])

        return ConfidenceResult(
            confidence_result_id=row["confidence_result_id"],
            lead_id=row["lead_id"],
            research_job_id=row["research_job_id"],
            quality_result_id=row["quality_result_id"],
            score=row["score"],
            level=row["level"],
            positive_factors=row["positive_factors"] if isinstance(row["positive_factors"], list) else json.loads(row["positive_factors"]),
            negative_factors=row["negative_factors"] if isinstance(row["negative_factors"], list) else json.loads(row["negative_factors"]),
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
                cur.execute("SELECT COUNT(*) FROM confidence_results")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM confidence_results")
            conn.commit()
        finally:
            conn.close()
