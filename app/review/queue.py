"""Review Queue — manages leads that need human attention."""

from __future__ import annotations

import json
import os
from typing import Any

from app.models import ReviewItem


class ReviewQueue:
    """In-memory review queue with file persistence."""

    def __init__(self, storage_path: str = "output/review_queue.json"):
        self._items: list[ReviewItem] = []
        self._storage_path = storage_path
        self._load()

    def _load(self):
        """Load existing review items from disk."""
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item_dict in data:
                    item = ReviewItem(
                        review_id=item_dict.get("review_id", ""),
                        lead_id=item_dict.get("lead_id", ""),
                        reason=item_dict.get("reason", ""),
                        lead_data=item_dict.get("lead_data", {}),
                        confidence=item_dict.get("confidence", {}),
                        issues=item_dict.get("issues", []),
                        conflicts=item_dict.get("conflicts", []),
                        evidence_refs=item_dict.get("evidence_refs", []),
                        status=item_dict.get("status", "pending"),
                        created_at=item_dict.get("created_at", ""),
                    )
                    self._items.append(item)
            except (json.JSONDecodeError, KeyError):
                self._items = []

    def _save(self):
        """Persist review items to disk."""
        os.makedirs(os.path.dirname(self._storage_path) or ".", exist_ok=True)
        data = [item.to_dict() for item in self._items]
        with open(self._storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def add(self, item: ReviewItem) -> ReviewItem:
        """Add an item to the review queue."""
        self._items.append(item)
        self._save()
        return item

    def get_pending(self) -> list[ReviewItem]:
        """Get all pending review items."""
        return [i for i in self._items if i.status == "pending"]

    def get_all(self) -> list[ReviewItem]:
        """Get all review items."""
        return list(self._items)

    def get_by_id(self, review_id: str) -> ReviewItem | None:
        """Get a review item by ID."""
        return next((i for i in self._items if i.review_id == review_id), None)

    def approve(self, review_id: str) -> ReviewItem | None:
        """Approve a review item."""
        item = self.get_by_id(review_id)
        if item:
            item.status = "approved"
            self._save()
        return item

    def reject(self, review_id: str) -> ReviewItem | None:
        """Reject a review item."""
        item = self.get_by_id(review_id)
        if item:
            item.status = "rejected"
            self._save()
        return item

    def edit_and_approve(self, review_id: str, edits: dict[str, Any]) -> ReviewItem | None:
        """Apply edits to lead data and approve."""
        item = self.get_by_id(review_id)
        if item:
            item.lead_data.update(edits)
            item.status = "approved"
            self._save()
        return item

    def send_back_for_research(self, review_id: str, reason: str = "") -> ReviewItem | None:
        """Mark item as needing more research."""
        item = self.get_by_id(review_id)
        if item:
            item.status = "needs_more_research"
            if reason:
                item.issues.append(f"research_request: {reason}")
            self._save()
        return item

    def clear(self):
        """Clear all items."""
        self._items.clear()
        self._save()
