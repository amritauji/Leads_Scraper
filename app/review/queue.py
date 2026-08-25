"""Review Queue backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.connection import get_connection
from app.models import ReviewItem


class ReviewQueue:
    """SQLite-backed review queue."""

    def __init__(self, db_path: str | None = None):
        self._conn = get_connection(db_path)

    def add(self, item: ReviewItem) -> ReviewItem:
        """Insert a review item."""
        self._conn.execute(
            """INSERT OR REPLACE INTO review_queue
               (review_id, lead_id, reason, lead_data, confidence_score,
                confidence_level, confidence_result_id, quality_result_id,
                issues, conflicts, evidence_refs, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.review_id,
                item.lead_id,
                item.reason,
                json.dumps(item.lead_data, default=str),
                item.confidence_score,
                item.confidence_level,
                item.confidence_result_id,
                item.quality_result_id,
                json.dumps(item.issues, default=str),
                json.dumps(item.conflicts, default=str),
                json.dumps(item.evidence_refs, default=str),
                item.status,
                item.created_at,
            ),
        )
        self._conn.commit()
        return item

    def get_pending(self) -> list[ReviewItem]:
        """Get all pending review items."""
        rows = self._conn.execute(
            "SELECT * FROM review_queue WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_by_id(self, review_id: str) -> ReviewItem | None:
        """Get a review item by ID."""
        row = self._conn.execute(
            "SELECT * FROM review_queue WHERE review_id = ?", (review_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_item(row)

    def approve(self, review_id: str) -> ReviewItem | None:
        """Approve a review item."""
        item = self.get_by_id(review_id)
        if item:
            self._conn.execute(
                "UPDATE review_queue SET status = 'approved' WHERE review_id = ?",
                (review_id,),
            )
            self._conn.commit()
            item.status = "approved"
        return item

    def reject(self, review_id: str) -> ReviewItem | None:
        """Reject a review item."""
        item = self.get_by_id(review_id)
        if item:
            self._conn.execute(
                "UPDATE review_queue SET status = 'rejected' WHERE review_id = ?",
                (review_id,),
            )
            self._conn.commit()
            item.status = "rejected"
        return item

    def edit_and_approve(self, review_id: str, edits: dict[str, Any]) -> ReviewItem | None:
        """Apply edits to lead data and approve."""
        item = self.get_by_id(review_id)
        if item:
            item.lead_data.update(edits)
            self._conn.execute(
                "UPDATE review_queue SET lead_data = ?, status = 'approved' WHERE review_id = ?",
                (json.dumps(item.lead_data, default=str), review_id),
            )
            self._conn.commit()
            item.status = "approved"
        return item

    def send_back_for_research(self, review_id: str, reason: str = "") -> ReviewItem | None:
        """Mark item as needing more research."""
        item = self.get_by_id(review_id)
        if item:
            if reason:
                item.issues.append(f"research_request: {reason}")
            self._conn.execute(
                "UPDATE review_queue SET status = 'needs_more_research', issues = ? WHERE review_id = ?",
                (json.dumps(item.issues, default=str), review_id),
            )
            self._conn.commit()
            item.status = "needs_more_research"
        return item

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]

    def clear(self):
        self._conn.execute("DELETE FROM review_queue")
        self._conn.commit()

    def _row_to_item(self, row: sqlite3.Row) -> ReviewItem:
        """Convert a DB row to a ReviewItem."""
        return ReviewItem(
            review_id=row["review_id"],
            lead_id=row["lead_id"],
            reason=row["reason"],
            lead_data=json.loads(row["lead_data"] or "{}"),
            confidence_score=row["confidence_score"] or 0,
            confidence_level=row["confidence_level"] or "",
            confidence_result_id=row["confidence_result_id"],
            quality_result_id=row["quality_result_id"],
            issues=json.loads(row["issues"] or "[]"),
            conflicts=json.loads(row["conflicts"] or "[]"),
            evidence_refs=json.loads(row["evidence_refs"] or "[]"),
            status=row["status"],
            created_at=row["created_at"],
        )
