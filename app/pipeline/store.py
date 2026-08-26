"""Pipeline store backed by PostgreSQL (Supabase)."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import PipelineTransition


class PipelineStore:
    """PostgreSQL-backed Pipeline store."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add_transition(self, transition: PipelineTransition) -> PipelineTransition:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lead_pipeline_history
                       (transition_id, master_id, from_stage, to_stage, changed_by, reason, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (transition.transition_id, transition.master_id, transition.from_stage,
                     transition.to_stage, transition.changed_by, transition.reason,
                     transition.created_at),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return transition

    def get_history(self, master_id: str) -> list[PipelineTransition]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM lead_pipeline_history WHERE master_id = %s ORDER BY created_at DESC",
                    (master_id,),
                )
                return [self._row_to_transition(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lead_pipeline_history")
            conn.commit()
        finally:
            conn.close()

    def _row_to_transition(self, row: dict) -> PipelineTransition:
        return PipelineTransition(
            transition_id=str(row["transition_id"]),
            master_id=row["master_id"],
            from_stage=row.get("from_stage"),
            to_stage=row["to_stage"],
            changed_by=str(row["changed_by"]) if row.get("changed_by") else None,
            reason=row.get("reason"),
            created_at=str(row["created_at"]),
        )
