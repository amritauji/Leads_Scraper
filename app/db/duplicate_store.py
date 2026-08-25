"""PostgreSQL store for Duplicate Events."""

from __future__ import annotations

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import DuplicateEvent


class DuplicateEventStore:
    """Persists DuplicateEvent records to PostgreSQL."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, event: DuplicateEvent) -> DuplicateEvent:
        """Insert a DuplicateEvent."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO duplicate_events
                       (duplicate_event_id, incoming_lead_id, matched_master_id,
                        match_type, match_reason, quality_result_id,
                        research_job_id, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (duplicate_event_id) DO UPDATE SET
                        matched_master_id = EXCLUDED.matched_master_id,
                        match_type = EXCLUDED.match_type,
                        match_reason = EXCLUDED.match_reason""",
                    (
                        event.duplicate_event_id,
                        event.incoming_lead_id,
                        event.matched_master_id,
                        event.match_type,
                        event.match_reason,
                        event.quality_result_id,
                        event.research_job_id,
                        event.created_at,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return event

    def get_by_id(self, duplicate_event_id: str) -> DuplicateEvent | None:
        """Retrieve a DuplicateEvent by ID."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM duplicate_events WHERE duplicate_event_id = %s",
                    (duplicate_event_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_event(row)
        finally:
            conn.close()

    def get_all(self) -> list[DuplicateEvent]:
        """Retrieve all duplicate events."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM duplicate_events ORDER BY created_at DESC")
                return [self._row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_by_incoming_lead_id(self, lead_id: str) -> list[DuplicateEvent]:
        """Retrieve duplicate events for an incoming lead."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM duplicate_events WHERE incoming_lead_id = %s ORDER BY created_at DESC",
                    (lead_id,),
                )
                return [self._row_to_event(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def _row_to_event(self, row: dict) -> DuplicateEvent:
        """Convert a DB row to a DuplicateEvent."""
        return DuplicateEvent(
            duplicate_event_id=row["duplicate_event_id"],
            incoming_lead_id=row["incoming_lead_id"],
            matched_master_id=row["matched_master_id"],
            match_type=row["match_type"],
            match_reason=row["match_reason"],
            quality_result_id=row["quality_result_id"],
            research_job_id=row["research_job_id"],
            created_at=str(row["created_at"]),
        )

    def count(self) -> int:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM duplicate_events")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM duplicate_events")
            conn.commit()
        finally:
            conn.close()
