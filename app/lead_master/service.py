"""Lead Master Service — central service for all Phase 3 lead operations.

All mutations to lead_master go through this service to ensure:
- Atomic transactions
- Automatic activity logging
- Consistent state management
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg2

from app.config import PIPELINE_STAGES, MANUAL_ACTIVITY_TYPES
from app.db.connection import get_connection
from app.models import (
    Activity,
    AssignmentRecord,
    LeadMaster,
    PipelineTransition,
)
from app.lead_master.store import LeadMasterStore
from app.assignment.store import AssignmentStore
from app.pipeline.store import PipelineStore
from app.activities.store import ActivityStore


class LeadMasterService:
    """Central service for lead master operations with automatic activity logging."""

    def __init__(self, db_url: str | None = None):
        self._db_url = db_url
        self.lead_master = LeadMasterStore(db_url)
        self.assignments = AssignmentStore(db_url)
        self.pipeline = PipelineStore(db_url)
        self.activities = ActivityStore(db_url)

    def _conn(self):
        return get_connection(self._db_url)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _uuid(self) -> str:
        return str(uuid.uuid4())

    def create_master_lead(
        self,
        record: LeadMaster,
        performed_by: str | None = None,
    ) -> LeadMaster:
        """Create a new Lead Master record with Phase 3 initialization.

        Sets pipeline_stage=new, priority=medium, and logs lead_created activity.
        Both high-confidence and review-approved leads use this path.
        """
        record.pipeline_stage = "new"
        record.pipeline_stage_at = self._now()
        record.priority = "medium"
        record.assigned_to = None
        record.assigned_at = None
        record.assigned_by = None

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                # Insert lead master
                cur.execute(
                    """INSERT INTO lead_master
                       (master_id, lead_id, research_job_id, company_name, website,
                        industry, category, segment, founded, revenue, city_country,
                        ceo_founder_name, ceo_linkedin, marketing_head_name,
                        marketing_head_linkedin, contact_email, confidence_score,
                        confidence_level, confidence_result_id, quality_result_id,
                        data_quality_issues, evidence_refs, raw_evidence_refs,
                        review_id, source_lead_json, status, created_at, updated_at,
                        assigned_to, assigned_at, assigned_by,
                        pipeline_stage, pipeline_stage_at, pipeline_changed_by,
                        priority, next_action_at, next_action_type)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (master_id) DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        pipeline_stage = EXCLUDED.pipeline_stage,
                        pipeline_stage_at = EXCLUDED.pipeline_stage_at,
                        priority = EXCLUDED.priority,
                        updated_at = EXCLUDED.updated_at""",
                    (
                        record.master_id, record.lead_id, record.research_job_id,
                        record.company_name, record.website, record.industry,
                        record.category, record.segment, record.founded, record.revenue,
                        record.city_country, record.ceo_founder_name, record.ceo_linkedin,
                        record.marketing_head_name, record.marketing_head_linkedin,
                        record.contact_email, record.confidence_score, record.confidence_level,
                        record.confidence_result_id, record.quality_result_id,
                        psycopg2.extras.Json(record.data_quality_issues),
                        psycopg2.extras.Json(record.evidence_refs),
                        psycopg2.extras.Json(record.raw_evidence_refs),
                        record.review_id,
                        psycopg2.extras.Json(record.source_lead_json),
                        record.status, record.created_at, record.updated_at,
                        record.assigned_to, record.assigned_at, record.assigned_by,
                        record.pipeline_stage, record.pipeline_stage_at,
                        record.pipeline_changed_by, record.priority,
                        record.next_action_at, record.next_action_type,
                    ),
                )

                # Log lead_created activity
                activity_id = self._uuid()
                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'lead_created', %s, %s, %s, %s, %s)""",
                    (activity_id, record.master_id, performed_by,
                     f"Lead created: {record.company_name or record.master_id}",
                     "New lead entered Lead Master",
                     psycopg2.extras.Json({"confidence_score": record.confidence_score,
                                            "pipeline_stage": "new"}),
                     record.created_at),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return record

    def get_lead(self, master_id: str) -> LeadMaster | None:
        return self.lead_master.get_by_id(master_id)

    def list_leads(self, **filters) -> list[LeadMaster]:
        return self.lead_master.get_all(**filters)

    def assign(
        self,
        master_id: str,
        assigned_to: str,
        assigned_by: str,
        reason: str | None = None,
    ) -> LeadMaster:
        """Assign a lead to a user.

        If pipeline_stage is 'new', auto-advances to 'assigned'.
        """
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get current state
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()
                old_stage = row["pipeline_stage"]
                new_stage = "assigned" if old_stage == "new" else old_stage

                # Update lead_master
                cur.execute(
                    """UPDATE lead_master SET
                        assigned_to = %s, assigned_at = %s, assigned_by = %s,
                        pipeline_stage = %s, pipeline_stage_at = CASE WHEN %s != %s THEN %s ELSE pipeline_stage_at END,
                        pipeline_changed_by = CASE WHEN %s != %s THEN %s ELSE pipeline_changed_by END,
                        updated_at = %s
                       WHERE master_id = %s""",
                    (assigned_to, now, assigned_by, new_stage, new_stage, old_stage, now,
                     new_stage, old_stage, assigned_by, now, master_id),
                )

                # Insert assignment history
                cur.execute(
                    """INSERT INTO lead_assignments
                       (assignment_id, master_id, assigned_to, assigned_by, action, reason, created_at)
                       VALUES (%s, %s, %s, %s, 'assigned', %s, %s)""",
                    (self._uuid(), master_id, assigned_to, assigned_by, reason, now),
                )

                # Log activity
                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'lead_assigned', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, assigned_by,
                     f"Lead assigned",
                     f"Assigned to user",
                     psycopg2.extras.Json({"assigned_to": assigned_to, "assigned_by": assigned_by}),
                     now),
                )

                # If stage changed, log that too
                if new_stage != old_stage:
                    cur.execute(
                        """INSERT INTO lead_pipeline_history
                           (transition_id, master_id, from_stage, to_stage, changed_by, reason, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (self._uuid(), master_id, old_stage, new_stage, assigned_by,
                         "Auto-advanced on first assignment", now),
                    )
                    cur.execute(
                        """INSERT INTO lead_activities
                           (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                           VALUES (%s, %s, 'stage_changed', %s, %s, %s, %s, %s)""",
                        (self._uuid(), master_id, assigned_by,
                         f"Stage changed: {old_stage} -> {new_stage}",
                         "Auto-advanced on first assignment",
                         psycopg2.extras.Json({"from_stage": old_stage, "to_stage": new_stage}),
                         now),
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def reassign(
        self,
        master_id: str,
        new_user: str,
        assigned_by: str,
        reason: str | None = None,
    ) -> LeadMaster:
        """Reassign a lead to a different user. Does NOT change pipeline stage."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()

                cur.execute(
                    """UPDATE lead_master SET
                        assigned_to = %s, assigned_at = %s, assigned_by = %s, updated_at = %s
                       WHERE master_id = %s""",
                    (new_user, now, assigned_by, now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_assignments
                       (assignment_id, master_id, assigned_to, assigned_by, action, reason, created_at)
                       VALUES (%s, %s, %s, %s, 'reassigned', %s, %s)""",
                    (self._uuid(), master_id, new_user, assigned_by, reason, now),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'lead_reassigned', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, assigned_by,
                     "Lead reassigned",
                     f"Reassigned from {row['assigned_to'] or 'none'} to {new_user}",
                     psycopg2.extras.Json({"from_user": str(row["assigned_to"]) if row["assigned_to"] else None, "to_user": new_user}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def unassign(self, master_id: str, performed_by: str, reason: str | None = None) -> LeadMaster:
        """Unassign a lead. Does NOT reset pipeline stage."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()
                old_user = str(row["assigned_to"]) if row["assigned_to"] else None

                cur.execute(
                    """UPDATE lead_master SET
                        assigned_to = NULL, assigned_at = NULL, assigned_by = NULL, updated_at = %s
                       WHERE master_id = %s""",
                    (now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_assignments
                       (assignment_id, master_id, assigned_to, assigned_by, action, reason, created_at)
                       VALUES (%s, %s, %s, %s, 'unassigned', %s, %s)""",
                    (self._uuid(), master_id, old_user or performed_by, performed_by, reason, now),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'lead_unassigned', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, performed_by,
                     "Lead unassigned",
                     f"Removed assignment from {old_user or 'none'}",
                     psycopg2.extras.Json({"previous_user": old_user}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def change_stage(
        self,
        master_id: str,
        to_stage: str,
        changed_by: str,
        reason: str | None = None,
    ) -> LeadMaster:
        """Change the pipeline stage of a lead."""
        if to_stage not in PIPELINE_STAGES:
            raise ValueError(f"Invalid stage: {to_stage}. Valid: {PIPELINE_STAGES}")

        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()
                old_stage = row["pipeline_stage"]

                cur.execute(
                    """UPDATE lead_master SET
                        pipeline_stage = %s, pipeline_stage_at = %s, pipeline_changed_by = %s, updated_at = %s
                       WHERE master_id = %s""",
                    (to_stage, now, changed_by, now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_pipeline_history
                       (transition_id, master_id, from_stage, to_stage, changed_by, reason, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, old_stage, to_stage, changed_by, reason, now),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'stage_changed', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, changed_by,
                     f"Stage changed: {old_stage} -> {to_stage}",
                     reason,
                     psycopg2.extras.Json({"from_stage": old_stage, "to_stage": to_stage}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def change_priority(
        self,
        master_id: str,
        new_priority: str,
        performed_by: str,
    ) -> LeadMaster:
        """Change the priority of a lead."""
        if new_priority not in ("low", "medium", "high"):
            raise ValueError(f"Invalid priority: {new_priority}. Valid: low, medium, high")

        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()
                old_priority = row["priority"]

                cur.execute(
                    "UPDATE lead_master SET priority = %s, updated_at = %s WHERE master_id = %s",
                    (new_priority, now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'priority_changed', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, performed_by,
                     f"Priority changed: {old_priority} -> {new_priority}",
                     None,
                     psycopg2.extras.Json({"from_priority": old_priority, "to_priority": new_priority}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def set_next_action(
        self,
        master_id: str,
        action_type: str,
        action_at: str,
        performed_by: str,
    ) -> LeadMaster:
        """Set a follow-up / next action for a lead."""
        if action_type not in ("call", "email", "meeting", "follow_up", "other"):
            raise ValueError(f"Invalid action type: {action_type}")

        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()

                cur.execute(
                    """UPDATE lead_master SET
                        next_action_at = %s, next_action_type = %s, updated_at = %s
                       WHERE master_id = %s""",
                    (action_at, action_type, now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'next_action_set', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, performed_by,
                     f"Next action set: {action_type}",
                     f"Scheduled for {action_at}",
                     psycopg2.extras.Json({"action_type": action_type, "action_at": action_at}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def clear_next_action(self, master_id: str, performed_by: str) -> LeadMaster:
        """Clear the next action for a lead."""
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM lead_master WHERE master_id = %s FOR UPDATE", (master_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Lead {master_id} not found")

                now = self._now()

                cur.execute(
                    """UPDATE lead_master SET
                        next_action_at = NULL, next_action_type = NULL, updated_at = %s
                       WHERE master_id = %s""",
                    (now, master_id),
                )

                cur.execute(
                    """INSERT INTO lead_activities
                       (activity_id, master_id, activity_type, performed_by, title, description, metadata, created_at)
                       VALUES (%s, %s, 'next_action_cleared', %s, %s, %s, %s, %s)""",
                    (self._uuid(), master_id, performed_by,
                     "Next action cleared",
                     None,
                     psycopg2.extras.Json({}),
                     now),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return self.lead_master.get_by_id(master_id)

    def log_manual_activity(
        self,
        master_id: str,
        activity_type: str,
        performed_by: str,
        title: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Activity:
        """Log a manual activity (note, call, email, meeting)."""
        if activity_type not in MANUAL_ACTIVITY_TYPES:
            raise ValueError(f"Invalid manual activity type: {activity_type}. Valid: {MANUAL_ACTIVITY_TYPES}")

        activity = Activity(
            master_id=master_id,
            activity_type=activity_type,
            performed_by=performed_by,
            title=title,
            description=description,
            metadata=metadata or {},
        )

        return self.activities.log(activity)

    def get_activities(self, master_id: str, limit: int = 50, offset: int = 0) -> list[Activity]:
        return self.activities.get_for_lead(master_id, limit, offset)

    def get_assignment_history(self, master_id: str) -> list[AssignmentRecord]:
        return self.assignments.get_history(master_id)

    def get_pipeline_history(self, master_id: str) -> list[PipelineTransition]:
        return self.pipeline.get_history(master_id)
