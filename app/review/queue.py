"""Review Queue backed by PostgreSQL (Supabase)."""

from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras

from app.db.connection import get_connection
from app.models import ReviewItem


class ReviewQueue:
    """PostgreSQL-backed review queue."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url

    def _conn(self):
        return get_connection(self._db_url)

    def add(self, item: ReviewItem) -> ReviewItem:
        """Insert a review item."""
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO review_queue
                       (review_id, lead_id, research_job_id, reason, lead_data,
                        confidence_score, confidence_level, confidence_result_id,
                        quality_result_id, issues, conflicts, evidence_refs,
                        status, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (review_id) DO UPDATE SET
                        lead_data = EXCLUDED.lead_data,
                        confidence_score = EXCLUDED.confidence_score,
                        confidence_level = EXCLUDED.confidence_level,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at""",
                    (
                        item.review_id,
                        item.lead_id,
                        item.research_job_id if hasattr(item, 'research_job_id') else None,
                        item.reason,
                        psycopg2.extras.Json(item.lead_data),
                        item.confidence_score,
                        item.confidence_level,
                        item.confidence_result_id,
                        item.quality_result_id,
                        psycopg2.extras.Json(item.issues),
                        psycopg2.extras.Json(item.conflicts),
                        psycopg2.extras.Json(item.evidence_refs),
                        item.status,
                        item.created_at,
                        item.created_at,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return item

    def get_pending(self) -> list[ReviewItem]:
        """Get all pending review items."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM review_queue WHERE status = 'pending' ORDER BY created_at DESC"
                )
                return [self._row_to_item(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_by_id(self, review_id: str) -> ReviewItem | None:
        """Get a review item by ID."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM review_queue WHERE review_id = %s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return self._row_to_item(row)
        finally:
            conn.close()

    def approve(self, review_id: str) -> ReviewItem | None:
        """Approve a review item."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM review_queue WHERE review_id = %s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    "UPDATE review_queue SET status = 'approved', updated_at = NOW() WHERE review_id = %s",
                    (review_id,),
                )
            conn.commit()
            return self._row_to_item(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reject(self, review_id: str) -> ReviewItem | None:
        """Reject a review item."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM review_queue WHERE review_id = %s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    "UPDATE review_queue SET status = 'rejected', updated_at = NOW() WHERE review_id = %s",
                    (review_id,),
                )
            conn.commit()
            return self._row_to_item(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def edit_and_approve(self, review_id: str, edits: dict[str, Any]) -> ReviewItem | None:
        """Apply edits to lead data and approve."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM review_queue WHERE review_id = %s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                lead_data = row["lead_data"] if isinstance(row["lead_data"], dict) else json.loads(row["lead_data"])
                lead_data.update(edits)
                cur.execute(
                    "UPDATE review_queue SET lead_data = %s, status = 'approved', updated_at = NOW() WHERE review_id = %s",
                    (psycopg2.extras.Json(lead_data), review_id),
                )
            conn.commit()
            item = self.get_by_id(review_id)
            return item
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def send_back_for_research(self, review_id: str, reason: str = "") -> ReviewItem | None:
        """Mark item as needing more research."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM review_queue WHERE review_id = %s", (review_id,))
                row = cur.fetchone()
                if not row:
                    return None
                issues = row["issues"] if isinstance(row["issues"], list) else json.loads(row["issues"])
                if reason:
                    issues.append(f"research_request: {reason}")
                cur.execute(
                    "UPDATE review_queue SET status = 'needs_more_research', issues = %s, updated_at = NOW() WHERE review_id = %s",
                    (psycopg2.extras.Json(issues), review_id),
                )
            conn.commit()
            return self.get_by_id(review_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def count(self) -> int:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM review_queue")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def clear(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM review_queue")
            conn.commit()
        finally:
            conn.close()

    def _row_to_item(self, row: dict) -> ReviewItem:
        """Convert a DB row to a ReviewItem."""
        def _json(val):
            if val is None:
                return []
            if isinstance(val, (list, dict)):
                return val
            return json.loads(val)

        return ReviewItem(
            review_id=row["review_id"],
            lead_id=row["lead_id"],
            reason=row["reason"],
            lead_data=_json(row["lead_data"]),
            confidence_score=row["confidence_score"] or 0,
            confidence_level=row["confidence_level"] or "",
            confidence_result_id=row["confidence_result_id"],
            quality_result_id=row["quality_result_id"],
            issues=_json(row["issues"]),
            conflicts=_json(row["conflicts"]),
            evidence_refs=_json(row["evidence_refs"]),
            status=row["status"],
            created_at=str(row["created_at"]),
        )
