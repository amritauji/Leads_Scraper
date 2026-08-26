"""Permission checks and authorization helpers."""

from __future__ import annotations

from app.auth.current_user import CurrentUser


class ForbiddenError(Exception):
    """Raised when authorization fails."""
    def __init__(self, message: str = "Forbidden"):
        self.message = message
        self.status = 403
        super().__init__(self.message)


def require_authenticated(user: CurrentUser | None) -> CurrentUser:
    """Ensure user is authenticated and active. Returns the user or raises."""
    if user is None:
        from app.auth.jwt import AuthError
        raise AuthError("Authentication required", 401)
    if not user.is_active:
        from app.auth.jwt import AuthError
        raise AuthError("Account is deactivated", 401)
    return user


def require_role(user: CurrentUser, *roles: str):
    """Ensure user has one of the specified roles."""
    require_authenticated(user)
    if user.role not in roles:
        raise ForbiddenError(f"Requires role: {', '.join(roles)}")


def require_admin(user: CurrentUser):
    require_role(user, "admin")


def require_manager_or_admin(user: CurrentUser):
    require_role(user, "admin", "manager")


def require_can_review(user: CurrentUser):
    """Only admin and manager can access review queue."""
    require_role(user, "admin", "manager")


def require_can_manage_leads(user: CurrentUser):
    """Admin and manager can manage any lead."""
    require_role(user, "admin", "manager")


def require_can_assign(user: CurrentUser):
    """Only admin and manager can assign/reassign leads."""
    require_role(user, "admin", "manager")


def require_can_manage_users(user: CurrentUser):
    """Only admin can manage users."""
    require_role(user, "admin")


def check_lead_ownership(user: CurrentUser, assigned_to: str | None) -> bool:
    """Check if a BD user owns this lead. Admin/manager always pass."""
    if user.can_manage_leads:
        return True
    return assigned_to == user.user_id


def require_lead_access(user: CurrentUser, assigned_to: str | None):
    """Require access to a specific lead. BD users must own it."""
    require_authenticated(user)
    if not check_lead_ownership(user, assigned_to):
        raise ForbiddenError("Access denied: lead not assigned to you")
