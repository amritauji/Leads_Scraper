"""Assignment store backed by PostgreSQL (Supabase)."""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import AssignmentRecord


class AssignmentStore:
    """PostgreSQL-backed Assignment store."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, record: AssignmentRecord) -> AssignmentRecord:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lead_assignments
                       (assignment_id, master_id, assigned_to, assigned_by, action, reason, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (record.assignment_id, record.master_id, record.assigned_to,
                     record.assigned_by, record.action, record.reason, record.created_at),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return record

    def get_history(self, master_id: str) -> list[AssignmentRecord]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM lead_assignments WHERE master_id = %s ORDER BY created_at DESC",
                    (master_id,),
                )
                return [self._row_to_record(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lead_assignments")
            conn.commit()
        finally:
            conn.close()

    def _row_to_record(self, row: dict) -> AssignmentRecord:
        return AssignmentRecord(
            assignment_id=str(row["assignment_id"]),
            master_id=row["master_id"],
            assigned_to=str(row["assigned_to"]),
            assigned_by=str(row["assigned_by"]),
            action=row["action"],
            reason=row.get("reason"),
            created_at=str(row["created_at"]),
        )
