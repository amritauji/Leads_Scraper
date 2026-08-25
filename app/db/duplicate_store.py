"""SQLite store for Duplicate Events."""

from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.models import DuplicateEvent


class DuplicateEventStore:
    """Persists DuplicateEvent records to SQLite."""

    def __init__(self, db_path: str | None = None):
        self._conn = get_connection(db_path)

    def add(self, event: DuplicateEvent) -> DuplicateEvent:
        """Insert a DuplicateEvent."""
        self._conn.execute(
            """INSERT OR REPLACE INTO duplicate_events
               (duplicate_event_id, incoming_lead_id, matched_master_id,
                match_type, match_reason, quality_result_id,
                research_job_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
        self._conn.commit()
        return event

    def get_by_id(self, duplicate_event_id: str) -> DuplicateEvent | None:
        """Retrieve a DuplicateEvent by ID."""
        row = self._conn.execute(
            "SELECT * FROM duplicate_events WHERE duplicate_event_id = ?",
            (duplicate_event_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_event(row)

    def get_all(self) -> list[DuplicateEvent]:
        """Retrieve all duplicate events."""
        rows = self._conn.execute(
            "SELECT * FROM duplicate_events ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_by_incoming_lead_id(self, lead_id: str) -> list[DuplicateEvent]:
        """Retrieve duplicate events for an incoming lead."""
        rows = self._conn.execute(
            "SELECT * FROM duplicate_events WHERE incoming_lead_id = ? ORDER BY created_at DESC",
            (lead_id,),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, row: sqlite3.Row) -> DuplicateEvent:
        """Convert a DB row to a DuplicateEvent."""
        return DuplicateEvent(
            duplicate_event_id=row["duplicate_event_id"],
            incoming_lead_id=row["incoming_lead_id"],
            matched_master_id=row["matched_master_id"],
            match_type=row["match_type"],
            match_reason=row["match_reason"],
            quality_result_id=row["quality_result_id"],
            research_job_id=row["research_job_id"],
            created_at=row["created_at"],
        )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM duplicate_events").fetchone()[0]

    def clear(self):
        self._conn.execute("DELETE FROM duplicate_events")
        self._conn.commit()
