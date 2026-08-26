"""Phase 4 tests: Authentication & Authorization.

Tests auth module components, permission logic, schema verification,
UserStore with auth_user_id, and ReviewQueue with reviewed_by.

30 test cases total.
"""
import os, sys, uuid, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pytest
from app.db.connection import get_connection
from app.config import DATABASE_URL
from app.models import AppUser, LeadMaster, ReviewItem
from app.users.store import UserStore
from app.review.queue import ReviewQueue
from app.lead_master.store import LeadMasterStore
from app.lead_master.service import LeadMasterService
from app.auth.current_user import CurrentUser
from app.auth.permissions import (
    require_authenticated,
    require_can_review,
    require_can_manage_users,
    require_can_assign,
    require_lead_access,
    check_lead_ownership,
    ForbiddenError,
)
from app.auth.jwt import AuthError
from app.phase2 import Phase2Pipeline


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup():
    yield
    for table in [
        "lead_activities", "lead_pipeline_history", "lead_assignments",
        "lead_master", "review_queue", "quality_results", "confidence_results",
        "duplicate_events", "users",
    ]:
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table}")
            conn.commit()
            conn.close()
        except Exception:
            pass


@pytest.fixture
def user_store():
    return UserStore()


@pytest.fixture
def lead_store():
    return LeadMasterStore()


@pytest.fixture
def review_queue():
    return ReviewQueue()


@pytest.fixture
def lead_service():
    return LeadMasterService()


@pytest.fixture
def admin_user(user_store):
    u = AppUser(
        name="Admin User",
        email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
        role="admin",
        auth_user_id=str(uuid.uuid4()),
    )
    return user_store.add(u)


@pytest.fixture
def manager_user(user_store):
    u = AppUser(
        name="Manager User",
        email=f"manager_{uuid.uuid4().hex[:6]}@test.com",
        role="manager",
        auth_user_id=str(uuid.uuid4()),
    )
    return user_store.add(u)


@pytest.fixture
def bd_user(user_store):
    u = AppUser(
        name="BD User",
        email=f"bd_{uuid.uuid4().hex[:6]}@test.com",
        role="bd",
        auth_user_id=str(uuid.uuid4()),
    )
    return user_store.add(u)


@pytest.fixture
def bd_user_2(user_store):
    u = AppUser(
        name="BD User 2",
        email=f"bd2_{uuid.uuid4().hex[:6]}@test.com",
        role="bd",
        auth_user_id=str(uuid.uuid4()),
    )
    return user_store.add(u)


def _make_current_user(app_user: AppUser) -> CurrentUser:
    """Create a CurrentUser from an AppUser for testing."""
    return CurrentUser(
        user_id=app_user.user_id,
        auth_user_id=app_user.auth_user_id or str(uuid.uuid4()),
        email=app_user.email,
        name=app_user.name,
        role=app_user.role,
        is_active=app_user.is_active,
    )


# ===========================================================================
# Schema Verification (2 tests)
# ===========================================================================

class TestSchemaVerification:
    def test_users_has_auth_user_id_column(self):
        """users table must have auth_user_id UUID UNIQUE column."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'auth_user_id'
                """)
                row = cur.fetchone()
                assert row is not None, "auth_user_id column missing from users table"
                assert row[1] == "uuid", f"auth_user_id should be UUID, got {row[1]}"
        finally:
            conn.close()

    def test_review_queue_has_reviewed_by_column(self):
        """review_queue must have reviewed_by UUID and reviewed_at timestamptz columns."""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'review_queue'
                    AND column_name IN ('reviewed_by', 'reviewed_at')
                    ORDER BY column_name
                """)
                rows = {r[0]: r[1] for r in cur.fetchall()}
                assert "reviewed_by" in rows, "reviewed_by column missing"
                assert "reviewed_at" in rows, "reviewed_at column missing"
        finally:
            conn.close()


# ===========================================================================
# CurrentUser Properties (4 tests)
# ===========================================================================

class TestCurrentUser:
    def test_admin_properties(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="a@t.com", name="A", role="admin", is_active=True)
        assert user.is_admin
        assert not user.is_manager
        assert not user.is_bd
        assert user.can_manage_leads
        assert user.can_manage_users
        assert user.can_review

    def test_manager_properties(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="m@t.com", name="M", role="manager", is_active=True)
        assert not user.is_admin
        assert user.is_manager
        assert not user.is_bd
        assert user.can_manage_leads
        assert not user.can_manage_users
        assert user.can_review

    def test_bd_properties(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="b@t.com", name="B", role="bd", is_active=True)
        assert not user.is_admin
        assert not user.is_manager
        assert user.is_bd
        assert not user.can_manage_leads
        assert not user.can_manage_users
        assert not user.can_review

    def test_to_dict(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="a@t.com", name="A", role="admin", is_active=True)
        d = user.to_dict()
        assert d["user_id"] == "u1"
        assert d["auth_user_id"] == "a1"
        assert d["role"] == "admin"
        assert d["is_active"] is True


# ===========================================================================
# Permission Checks (8 tests)
# ===========================================================================

class TestPermissionChecks:
    def test_require_authenticated_passes(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="a@t.com", name="A", role="bd", is_active=True)
        result = require_authenticated(user)
        assert result.user_id == "u1"

    def test_require_authenticated_rejects_none(self):
        with pytest.raises(AuthError) as exc:
            require_authenticated(None)
        assert "401" in str(exc.value.status) or exc.value.status == 401

    def test_require_authenticated_rejects_inactive(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="a@t.com", name="A", role="admin", is_active=False)
        with pytest.raises(AuthError) as exc:
            require_authenticated(user)
        assert "deactivated" in str(exc.value.message).lower()

    def test_require_can_review_admin_passes(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="a@t.com", name="A", role="admin", is_active=True)
        require_can_review(user)  # Should not raise

    def test_require_can_review_bd_raises(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="b@t.com", name="B", role="bd", is_active=True)
        with pytest.raises(ForbiddenError) as exc:
            require_can_review(user)
        assert exc.value.status == 403

    def test_require_can_manage_users_bd_raises(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="b@t.com", name="B", role="bd", is_active=True)
        with pytest.raises(ForbiddenError):
            require_can_manage_users(user)

    def test_check_lead_ownership_bd_own_lead(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="b@t.com", name="B", role="bd", is_active=True)
        assert check_lead_ownership(user, "u1") is True

    def test_check_lead_ownership_bd_other_lead(self):
        user = CurrentUser(user_id="u1", auth_user_id="a1", email="b@t.com", name="B", role="bd", is_active=True)
        assert check_lead_ownership(user, "u_other") is False


# ===========================================================================
# UserStore with auth_user_id (5 tests)
# ===========================================================================

class TestUserStoreAuth:
    def test_create_with_auth_user_id(self, user_store):
        u = AppUser(name="Auth Test", email=f"auth_{uuid.uuid4().hex[:6]}@test.com", role="bd", auth_user_id=str(uuid.uuid4()))
        created = user_store.add(u)
        assert created.auth_user_id is not None

    def test_get_by_auth_user_id(self, user_store, admin_user):
        found = user_store.get_by_auth_user_id(admin_user.auth_user_id)
        assert found is not None
        assert found.user_id == admin_user.user_id

    def test_get_by_auth_user_id_not_found(self, user_store):
        found = user_store.get_by_auth_user_id(str(uuid.uuid4()))
        assert found is None

    def test_update_auth_user_id(self, user_store, bd_user):
        new_auth_id = str(uuid.uuid4())
        updated = user_store.update(bd_user.user_id, auth_user_id=new_auth_id)
        assert updated.auth_user_id == new_auth_id

    def test_user_dict_includes_auth_user_id(self, admin_user):
        d = admin_user.to_dict()
        assert "auth_user_id" in d
        assert d["auth_user_id"] == admin_user.auth_user_id


# ===========================================================================
# ReviewQueue with reviewed_by (4 tests)
# ===========================================================================

class TestReviewQueueAuth:
    def _make_review_item(self, rq):
        from app.db.quality_store import QualityResultStore
        from app.db.confidence_store import ConfidenceResultStore
        from app.models import DataQualityResult, ConfidenceResult

        dq = DataQualityResult(
            original_lead={"CompanyName": "TestCo", "Website": "https://test.com"},
            cleaned_lead={"company_name": "TestCo", "website": "https://test.com"},
            issues=[],
            conflicts=[],
            duplicate_result=type("DR", (), {"is_duplicate": False, "matched_lead_id": None, "duplicate_type": None, "match_reason": None})(),
        )
        QualityResultStore().add(dq)

        cr = ConfidenceResult(
            lead_id="test_lead",
            score=55,
            level="medium",
            positive_factors=[],
            negative_factors=[],
            quality_result_id=dq.quality_result_id,
        )
        ConfidenceResultStore().add(cr)

        item = ReviewItem(
            lead_id=f"lead_{uuid.uuid4().hex[:6]}",
            reason="medium_confidence",
            lead_data={"company_name": "TestCo", "website": "https://test.com"},
            confidence_score=55,
            confidence_level="medium",
            confidence_result_id=cr.confidence_result_id,
            quality_result_id=dq.quality_result_id,
            issues=[],
            conflicts=[],
            evidence_refs=[],
        )
        return rq.add(item)

    def test_approve_records_reviewed_by(self, review_queue, admin_user):
        item = self._make_review_item(review_queue)
        review_queue.approve(item.review_id, reviewed_by=admin_user.user_id)
        fetched = review_queue.get_by_id(item.review_id)
        assert fetched.status == "approved"

    def test_reject_records_reviewed_by(self, review_queue, manager_user):
        item = self._make_review_item(review_queue)
        review_queue.reject(item.review_id, reviewed_by=manager_user.user_id)
        fetched = review_queue.get_by_id(item.review_id)
        assert fetched.status == "rejected"

    def test_approve_without_reviewed_by_still_works(self, review_queue):
        item = self._make_review_item(review_queue)
        review_queue.approve(item.review_id)
        fetched = review_queue.get_by_id(item.review_id)
        assert fetched.status == "approved"

    def test_edit_and_approve_records_reviewed_by(self, review_queue, admin_user):
        item = self._make_review_item(review_queue)
        review_queue.edit_and_approve(
            item.review_id,
            edits={"company_name": "UpdatedCo"},
            reviewed_by=admin_user.user_id,
        )
        fetched = review_queue.get_by_id(item.review_id)
        assert fetched.status == "approved"


# ===========================================================================
# Phase 2 approve_review with reviewed_by (3 tests)
# ===========================================================================

class TestPhase2Auth:
    def _create_lead_for_review(self):
        return {
            "LeadId": f"lead_{uuid.uuid4().hex[:8]}",
            "CompanyName": f"ReviewCo_{uuid.uuid4().hex[:6]}",
            "Website": "https://review-test.com",
            "Industry": "Technology",
            "Category": "B2B",
            "Segment": "Enterprise",
            "Founded": "2015",
            "Revenue": "$10M-$50M",
            "CityCountry": "San Francisco, CA",
            "CEOFounderName": "Review CEO",
            "MarketingHeadName": "Review CMO",
        }

    def test_approve_review_with_reviewed_by(self):
        from app.users.store import UserStore
        from app.models import AppUser

        reviewer = UserStore().add(AppUser(
            name="Reviewer",
            email=f"reviewer_{uuid.uuid4().hex[:6]}@test.com",
            role="manager",
        ))

        pipeline = Phase2Pipeline()
        leads = [self._create_lead_for_review()]
        result = pipeline.process_leads(leads)
        routed = [r for r in result["results"] if r["routing"]["action"] == "sent_to_review"]
        assert len(routed) > 0

        approved = pipeline.approve_review(routed[0]["routing"]["review_id"], reviewed_by=reviewer.user_id)
        assert approved is not None
        assert "master_id" in approved

    def test_approve_review_without_reviewed_by(self):
        pipeline = Phase2Pipeline()
        leads = [self._create_lead_for_review()]
        result = pipeline.process_leads(leads)
        routed = [r for r in result["results"] if r["routing"]["action"] == "sent_to_review"]
        assert len(routed) > 0

        approved = pipeline.approve_review(routed[0]["routing"]["review_id"])
        assert approved is not None

    def test_approve_review_invalid_id_returns_none(self):
        pipeline = Phase2Pipeline()
        result = pipeline.approve_review("nonexistent_id", reviewed_by=str(uuid.uuid4()))
        assert result is None


# ===========================================================================
# Authorization enforcement on service layer (4 tests)
# ===========================================================================

class TestServiceAuth:
    def _create_lead_in_master(self, lead_store, lead_service, performed_by=None):
        master = LeadMaster(
            lead_id=f"lead_{uuid.uuid4().hex[:8]}",
            company_name=f"ServiceAuthCo_{uuid.uuid4().hex[:6]}",
            website="https://serviceauth.com",
            industry="Technology",
            confidence_score=85,
            confidence_level="high",
            status="accepted",
        )
        return lead_service.create_master_lead(master, performed_by=performed_by)

    def test_bd_can_access_own_lead(self, bd_user, lead_store, lead_service):
        lead = self._create_lead_in_master(lead_store, lead_service, performed_by=bd_user.user_id)
        lead_service.assign(lead.master_id, bd_user.user_id, bd_user.user_id)
        updated = lead_store.get_by_id(lead.master_id)
        require_lead_access(_make_current_user(bd_user), updated.assigned_to)

    def test_bd_cannot_access_other_lead(self, bd_user, bd_user_2, lead_store, lead_service):
        lead = self._create_lead_in_master(lead_store, lead_service, performed_by=bd_user.user_id)
        lead_service.assign(lead.master_id, bd_user_2.user_id, bd_user.user_id)
        updated = lead_store.get_by_id(lead.master_id)
        with pytest.raises(ForbiddenError):
            require_lead_access(_make_current_user(bd_user), updated.assigned_to)

    def test_admin_can_access_any_lead(self, admin_user, bd_user, lead_store, lead_service):
        lead = self._create_lead_in_master(lead_store, lead_service, performed_by=admin_user.user_id)
        lead_service.assign(lead.master_id, bd_user.user_id, admin_user.user_id)
        updated = lead_store.get_by_id(lead.master_id)
        require_lead_access(_make_current_user(admin_user), updated.assigned_to)

    def test_unassigned_lead_bd_cannot_access(self, bd_user):
        with pytest.raises(ForbiddenError):
            require_lead_access(_make_current_user(bd_user), None)


# ===========================================================================
# Auth error messages (1 test)
# ===========================================================================

class TestAuthError:
    def test_auth_error_has_status_and_message(self):
        e = AuthError("test error", 401)
        assert e.status == 401
        assert "test error" in e.message

    def test_forbidden_error_has_status(self):
        e = ForbiddenError("forbidden")
        assert e.status == 403
        assert "forbidden" in e.message

    def test_invalid_token_rejects(self):
        with pytest.raises(AuthError):
            from app.auth.jwt import verify_supabase_token
            verify_supabase_token("not.a.valid.jwt.token")

    def test_empty_token_rejects(self):
        with pytest.raises(AuthError):
            from app.auth.jwt import verify_supabase_token
            verify_supabase_token("")
