"""Activity store backed by PostgreSQL (Supabase)."""

from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import Activity


class ActivityStore:
    """PostgreSQL-backed Activity store (append-only audit trail)."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def log(self, activity: Activity) -> Activity:
        """Append an activity record."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title,
                        description, metadata, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (activity.activity_id, activity.master_id, activity.activity_type,
                     activity.performed_by, activity.title, activity.description,
                     psycopg2.extras.Json(activity.metadata), activity.created_at),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return activity

    def get_for_lead(self, master_id: str, limit: int = 50, offset: int = 0) -> list[Activity]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM lead_activities WHERE master_id = %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (master_id, limit, offset),
                )
                return [self._row_to_activity(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Activity]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM lead_activities ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                return [self._row_to_activity(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM lead_activities")
            conn.commit()
        finally:
            conn.close()

    def _row_to_activity(self, row: dict) -> Activity:
        def _json(val):
            if val is None:
                return {}
            if isinstance(val, dict):
                return val
            return json.loads(val)

        return Activity(
            activity_id=str(row["activity_id"]),
            master_id=row["master_id"],
            activity_type=row["activity_type"],
            performed_by=str(row["performed_by"]) if row.get("performed_by") else None,
            title=row["title"],
            description=row.get("description"),
            metadata=_json(row.get("metadata")),
            created_at=str(row["created_at"]),
        )
