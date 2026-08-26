"""End-to-end Phase 3 tests: Users, Assignment, Pipeline, Activities, Priority, Next Action.

Tests run against Supabase PostgreSQL.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from datetime import datetime, timezone, timedelta

from app.models import LeadMaster, AppUser
from app.users.store import UserStore
from app.lead_master.service import LeadMasterService
from app.lead_master.store import LeadMasterStore
from app.assignment.store import AssignmentStore
from app.pipeline.store import PipelineStore
from app.activities.store import ActivityStore
from app.phase2 import Phase2Pipeline
from app.review.queue import ReviewQueue
from app.db.quality_store import QualityResultStore
from app.db.confidence_store import ConfidenceResultStore
from app.db.connection import get_connection


# ============================================================================
# Helpers
# ============================================================================

def _clear_all():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM lead_activities")
            cur.execute("DELETE FROM lead_pipeline_history")
            cur.execute("DELETE FROM lead_assignments")
            cur.execute("DELETE FROM lead_master")
            cur.execute("DELETE FROM review_queue")
            cur.execute("DELETE FROM duplicate_events")
            cur.execute("DELETE FROM confidence_results")
            cur.execute("DELETE FROM quality_results")
            cur.execute("DELETE FROM users")
        conn.commit()
    finally:
        conn.close()


def _section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def _sub(title: str):
    print(f"\n  --- {title} ---")


def _ok(condition: bool, msg: str):
    if not condition:
        print(f"  [FAIL] {msg}")
        raise AssertionError(msg)
    print(f"  [OK] {msg}")


def _create_test_users(store: UserStore) -> tuple[AppUser, AppUser, AppUser]:
    admin = AppUser(name="Admin User", email="admin@test.com", role="admin")
    bd1 = AppUser(name="BD One", email="bd1@test.com", role="bd")
    bd2 = AppUser(name="BD Two", email="bd2@test.com", role="bd")
    return store.add(admin), store.add(bd1), store.add(bd2)


def _make_master() -> LeadMaster:
    return LeadMaster(
        lead_id="lead_test_001",
        company_name="TestCorp",
        industry="SaaS",
        website="https://testcorp.com",
        ceo_founder_name="Jane Doe",
        contact_email="jane@testcorp.com",
        confidence_score=85,
        confidence_level="high",
        evidence_refs=["ev_001"],
        source_lead_json={"LeadId": "lead_test_001", "Company Name": "TestCorp"},
    )


# ============================================================================
# CASE 1: New Lead Master initializes Phase 3 fields
# ============================================================================
def test_case_1_new_lead():
    _section("CASE 1: New Lead Master")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)

    _ok(master.pipeline_stage == "new", f"pipeline_stage='new' (got '{master.pipeline_stage}')")
    _ok(master.priority == "medium", f"priority='medium' (got '{master.priority}')")
    _ok(master.assigned_to is None, "assigned_to is None")
    _ok(master.next_action_at is None, "next_action_at is None")

    activities = svc.get_activities(master.master_id)
    types = [a.activity_type for a in activities]
    _ok("lead_created" in types, f"lead_created activity logged (got {types})")

    lead_created = [a for a in activities if a.activity_type == "lead_created"][0]
    _ok(lead_created.performed_by == bd1.user_id, "lead_created performed_by matches")
    print(f"\n  CASE 1 PASSED: New lead initialized with pipeline_stage=new, priority=medium")
    return True


# ============================================================================
# CASE 2: Assignment (new → assigned)
# ============================================================================
def test_case_2_assignment():
    _section("CASE 2: Assignment")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    _ok(master.pipeline_stage == "new", "starts at new")

    lead = svc.assign(master.master_id, bd1.user_id, bd1.user_id, reason="Initial assignment")
    _ok(lead.assigned_to == bd1.user_id, f"assigned_to={lead.assigned_to}")
    _ok(lead.assigned_at is not None, "assigned_at is set")
    _ok(lead.pipeline_stage == "assigned", f"stage advanced to assigned (got '{lead.pipeline_stage}')")

    history = svc.get_assignment_history(master.master_id)
    _ok(len(history) == 1, f"1 assignment record (got {len(history)})")
    _ok(history[0].action == "assigned", f"action='assigned' (got '{history[0].action}')")
    _ok(history[0].assigned_to == bd1.user_id, "assigned_to matches")
    _ok(history[0].reason == "Initial assignment", "reason preserved")

    activities = svc.get_activities(master.master_id)
    types = [a.activity_type for a in activities]
    _ok("lead_assigned" in types, "lead_assigned activity logged")
    _ok("stage_changed" in types, "stage_changed activity logged")

    ph = svc.get_pipeline_history(master.master_id)
    _ok(len(ph) == 1, f"1 pipeline transition (got {len(ph)})")
    _ok(ph[0].from_stage == "new", f"from_stage='new' (got '{ph[0].from_stage}')")
    _ok(ph[0].to_stage == "assigned", f"to_stage='assigned' (got '{ph[0].to_stage}')")

    print(f"\n  CASE 2 PASSED: Assignment with stage advancement and full history")
    return True


# ============================================================================
# CASE 3: Reassignment (stage unchanged)
# ============================================================================
def test_case_3_reassignment():
    _section("CASE 3: Reassignment")
    _clear_all()
    user_store = UserStore()
    _, bd1, bd2 = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    svc.assign(master.master_id, bd1.user_id, bd1.user_id)
    svc.change_stage(master.master_id, "contacted", bd1.user_id)

    lead = svc.reassign(master.master_id, bd2.user_id, bd1.user_id, reason="Coverage change")
    _ok(lead.assigned_to == bd2.user_id, f"assigned_to={lead.assigned_to}")
    _ok(lead.pipeline_stage == "contacted", f"stage still contacted (got '{lead.pipeline_stage}')")

    history = svc.get_assignment_history(master.master_id)
    _ok(len(history) == 2, f"2 assignment records (got {len(history)})")
    _ok(history[0].action == "reassigned", f"latest action='reassigned' (got '{history[0].action}')")
    _ok(history[0].assigned_to == bd2.user_id, "reassigned to bd2")

    activities = svc.get_activities(master.master_id)
    types = [a.activity_type for a in activities]
    _ok("lead_reassigned" in types, "lead_reassigned activity logged")

    print(f"\n  CASE 3 PASSED: Reassignment preserves pipeline stage")
    return True


# ============================================================================
# CASE 4: Unassignment (stage unchanged)
# ============================================================================
def test_case_4_unassignment():
    _section("CASE 4: Unassignment")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    svc.assign(master.master_id, bd1.user_id, bd1.user_id)
    svc.change_stage(master.master_id, "qualified", bd1.user_id)

    lead = svc.unassign(master.master_id, bd1.user_id, reason="Temporarily unassigned")
    _ok(lead.assigned_to is None, f"assigned_to=None (got '{lead.assigned_to}')")
    _ok(lead.pipeline_stage == "qualified", f"stage still qualified (got '{lead.pipeline_stage}')")

    history = svc.get_assignment_history(master.master_id)
    unassigned = [h for h in history if h.action == "unassigned"]
    _ok(len(unassigned) == 1, "1 unassignment record")

    activities = svc.get_activities(master.master_id)
    types = [a.activity_type for a in activities]
    _ok("lead_unassigned" in types, "lead_unassigned activity logged")

    print(f"\n  CASE 4 PASSED: Unassignment preserves pipeline stage")
    return True


# ============================================================================
# CASE 5: Pipeline (assigned → contacted → qualified → opportunity)
# ============================================================================
def test_case_5_pipeline():
    _section("CASE 5: Pipeline Progression")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    svc.assign(master.master_id, bd1.user_id, bd1.user_id)

    stages = ["contacted", "qualified", "opportunity"]
    for stage in stages:
        lead = svc.change_stage(master.master_id, stage, bd1.user_id, reason=f"Moving to {stage}")
        _ok(lead.pipeline_stage == stage, f"stage={stage} (got '{lead.pipeline_stage}')")

    lead = svc.get_lead(master.master_id)
    _ok(lead.pipeline_stage == "opportunity", f"final stage=opportunity")

    ph = svc.get_pipeline_history(master.master_id)
    _ok(len(ph) >= 4, f"at least 4 transitions (got {len(ph)})")
    stages_seen = [t.to_stage for t in reversed(ph)]
    _ok(stages_seen == ["assigned", "contacted", "qualified", "opportunity"],
        f"full history: {stages_seen}")

    activities = svc.get_activities(master.master_id)
    stage_changes = [a for a in activities if a.activity_type == "stage_changed"]
    _ok(len(stage_changes) >= 4, f"at least 4 stage_changed activities (got {len(stage_changes)})")

    print(f"\n  CASE 5 PASSED: Pipeline progression with full history")
    return True


# ============================================================================
# CASE 6: Won
# ============================================================================
def test_case_6_won():
    _section("CASE 6: Won")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    svc.assign(master.master_id, bd1.user_id, bd1.user_id)
    svc.change_stage(master.master_id, "opportunity", bd1.user_id)

    lead = svc.change_stage(master.master_id, "won", bd1.user_id, reason="Deal closed")
    _ok(lead.pipeline_stage == "won", f"stage=won (got '{lead.pipeline_stage}')")

    ph = svc.get_pipeline_history(master.master_id)
    won_transitions = [t for t in ph if t.to_stage == "won"]
    _ok(len(won_transitions) == 1, "1 won transition")
    _ok(won_transitions[0].reason == "Deal closed", f"reason preserved: {won_transitions[0].reason}")

    print(f"\n  CASE 6 PASSED: Won with reason")
    return True


# ============================================================================
# CASE 7: Lost
# ============================================================================
def test_case_7_lost():
    _section("CASE 7: Lost")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    svc.assign(master.master_id, bd1.user_id, bd1.user_id)
    svc.change_stage(master.master_id, "opportunity", bd1.user_id)

    lead = svc.change_stage(master.master_id, "lost", bd1.user_id, reason="Went with competitor")
    _ok(lead.pipeline_stage == "lost", f"stage=lost (got '{lead.pipeline_stage}')")

    ph = svc.get_pipeline_history(master.master_id)
    lost_transitions = [t for t in ph if t.to_stage == "lost"]
    _ok(len(lost_transitions) == 1, "1 lost transition")
    _ok(lost_transitions[0].reason == "Went with competitor", f"reason preserved")

    print(f"\n  CASE 7 PASSED: Lost with reason")
    return True


# ============================================================================
# CASE 8: Priority
# ============================================================================
def test_case_8_priority():
    _section("CASE 8: Priority Change")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)
    _ok(master.priority == "medium", "starts at medium")

    lead = svc.change_priority(master.master_id, "high", bd1.user_id)
    _ok(lead.priority == "high", f"priority=high (got '{lead.priority}')")

    activities = svc.get_activities(master.master_id)
    priority_changes = [a for a in activities if a.activity_type == "priority_changed"]
    _ok(len(priority_changes) == 1, "1 priority_changed activity")
    _ok(priority_changes[0].metadata.get("to_priority") == "high", "metadata has to_priority=high")

    print(f"\n  CASE 8 PASSED: Priority change with activity")
    return True


# ============================================================================
# CASE 9: Next Action
# ============================================================================
def test_case_9_next_action():
    _section("CASE 9: Next Action")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    lead = svc.set_next_action(master.master_id, "call", tomorrow, bd1.user_id)
    _ok(lead.next_action_at is not None, f"next_action_at set")
    _ok(lead.next_action_type == "call", f"next_action_type=call (got '{lead.next_action_type}')")

    activities = svc.get_activities(master.master_id)
    na_set = [a for a in activities if a.activity_type == "next_action_set"]
    _ok(len(na_set) == 1, "1 next_action_set activity")

    lead = svc.clear_next_action(master.master_id, bd1.user_id)
    _ok(lead.next_action_at is None, "next_action_at cleared")
    _ok(lead.next_action_type is None, "next_action_type cleared")

    activities = svc.get_activities(master.master_id)
    na_cleared = [a for a in activities if a.activity_type == "next_action_cleared"]
    _ok(len(na_cleared) == 1, "1 next_action_cleared activity")

    print(f"\n  CASE 9 PASSED: Set and clear next action with activities")
    return True


# ============================================================================
# CASE 10: Manual Activities
# ============================================================================
def test_case_10_manual_activities():
    _section("CASE 10: Manual Activities")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)

    svc.log_manual_activity(master.master_id, "note_added", bd1.user_id,
                            "Important note", "This is a test note")
    svc.log_manual_activity(master.master_id, "call_logged", bd1.user_id,
                            "Initial call", "Spoke with CEO", {"duration_minutes": 15})
    svc.log_manual_activity(master.master_id, "email_logged", bd1.user_id,
                            "Follow-up email", "Sent pricing deck")
    svc.log_manual_activity(master.master_id, "meeting_logged", bd1.user_id,
                            "Demo meeting", "Product demo scheduled")

    activities = svc.get_activities(master.master_id)
    manual = [a for a in activities if a.activity_type in
              ("note_added", "call_logged", "email_logged", "meeting_logged")]
    _ok(len(manual) == 4, f"4 manual activities (got {len(manual)})")

    types = [a.activity_type for a in manual]
    _ok("note_added" in types, "note_added present")
    _ok("call_logged" in types, "call_logged present")
    _ok("email_logged" in types, "email_logged present")
    _ok("meeting_logged" in types, "meeting_logged present")

    call = [a for a in manual if a.activity_type == "call_logged"][0]
    _ok(call.metadata.get("duration_minutes") == 15, "metadata preserved")

    print(f"\n  CASE 10 PASSED: Manual activities with metadata")
    return True


# ============================================================================
# CASE 11: Review Approval → Lead Master with Phase 3
# ============================================================================
def test_case_11_review_approval():
    _section("CASE 11: Review Approval -> Lead Master")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    lead_data = {
        "LeadId": "lead_review_001",
        "Company Name": "ReviewCorp",
        "Industry": "Tech",
        "Website": "https://reviewcorp.com",
        "Founded": "2020",
        "Revenue": "$10M",
        "City/Country": "NYC, USA",
        "Ceo/Founder Name": "John Smith",
        "CEO Linkedn": "https://linkedin.com/in/john-smith",
        "Marketing Head name": "Sarah Lee",
        "Marketing Head Linkedn": None,
        "Contact email": "john@reviewcorp.com",
        "evidence_refs": ["ev_001"],
        "missing_fields": [],
    }

    from app.models import ReviewItem
    rq = ReviewQueue()
    item = ReviewItem(
        lead_id="lead_review_001",
        reason="medium_confidence",
        lead_data=lead_data,
        confidence_score=55,
        confidence_level="medium",
        issues=[],
        conflicts=[],
        evidence_refs=["ev_001"],
    )
    rq.add(item)

    pipeline = Phase2Pipeline()
    result = pipeline.approve_review(item.review_id)
    _ok(result is not None, "Review approved")
    _ok(result.get("master_id") is not None, "Master record created")

    master_id = result["master_id"]
    lead = LeadMasterStore().get_by_id(master_id)
    _ok(lead is not None, "Lead exists in master")
    _ok(lead.pipeline_stage == "new", f"pipeline_stage=new (got '{lead.pipeline_stage}')")
    _ok(lead.priority == "medium", f"priority=medium (got '{lead.priority}')")
    _ok(lead.assigned_to is None, "assigned_to=None")
    _ok(lead.review_id == item.review_id, "review_id linked")

    svc = LeadMasterService()
    activities = svc.get_activities(master_id)
    types = [a.activity_type for a in activities]
    _ok("lead_created" in types, "lead_created activity")
    _ok("review_approved" in types, "review_approved activity")

    print(f"\n  CASE 11 PASSED: Review approval initializes Phase 3 fields")
    return True


# ============================================================================
# CASE 12: Transaction failure (partial update rollback)
# ============================================================================
def test_case_12_transaction_failure():
    _section("CASE 12: Transaction Failure Rollback")
    _clear_all()
    user_store = UserStore()
    _, bd1, _ = _create_test_users(user_store)

    svc = LeadMasterService()
    master = svc.create_master_lead(_make_master(), performed_by=bd1.user_id)

    # Try to assign to a non-existent lead
    try:
        svc.assign("nonexistent_master_id", bd1.user_id, bd1.user_id)
        _ok(False, "Should have raised ValueError")
    except ValueError:
        _ok(True, "ValueError raised for nonexistent lead")

    # Verify original lead is unchanged
    lead = svc.get_lead(master.master_id)
    _ok(lead.assigned_to is None, "original lead unchanged (assigned_to=None)")
    _ok(lead.pipeline_stage == "new", "original lead unchanged (stage=new)")

    # Try invalid stage
    try:
        svc.change_stage(master.master_id, "invalid_stage", bd1.user_id)
        _ok(False, "Should have raised ValueError")
    except ValueError:
        _ok(True, "ValueError raised for invalid stage")

    lead = svc.get_lead(master.master_id)
    _ok(lead.pipeline_stage == "new", "original lead unchanged after invalid stage")

    # Try invalid priority
    try:
        svc.change_priority(master.master_id, "invalid", bd1.user_id)
        _ok(False, "Should have raised ValueError")
    except ValueError:
        _ok(True, "ValueError raised for invalid priority")

    print(f"\n  CASE 12 PASSED: Transaction failures roll back cleanly")
    return True


# ============================================================================
# Run all tests
# ============================================================================
def main():
    print("\n" + "=" * 70)
    print("  PHASE 3 TESTS (Supabase PostgreSQL)")
    print("=" * 70)

    results = []
    tests = [
        ("Case 1: New Lead Master", test_case_1_new_lead),
        ("Case 2: Assignment", test_case_2_assignment),
        ("Case 3: Reassignment", test_case_3_reassignment),
        ("Case 4: Unassignment", test_case_4_unassignment),
        ("Case 5: Pipeline Progression", test_case_5_pipeline),
        ("Case 6: Won", test_case_6_won),
        ("Case 7: Lost", test_case_7_lost),
        ("Case 8: Priority", test_case_8_priority),
        ("Case 9: Next Action", test_case_9_next_action),
        ("Case 10: Manual Activities", test_case_10_manual_activities),
        ("Case 11: Review Approval", test_case_11_review_approval),
        ("Case 12: Transaction Failure", test_case_12_transaction_failure),
    ]

    for name, fn in tests:
        try:
            passed = fn()
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            passed = False
        results.append((name, passed))

    _section("TEST SUMMARY")
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {name}")

    all_passed = all(r[1] for r in results)
    print(f"\n  {'All tests passed!' if all_passed else 'Some tests failed.'}")
    print("=" * 70 + "\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
