"""Current user context for authenticated requests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CurrentUser:
    """Authenticated application user context."""
    user_id: str
    auth_user_id: str
    email: str
    name: str
    role: str
    is_active: bool

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"

    @property
    def is_bd(self) -> bool:
        return self.role == "bd"

    @property
    def can_manage_leads(self) -> bool:
        """Admin and manager can manage any lead."""
        return self.role in ("admin", "manager")

    @property
    def can_manage_users(self) -> bool:
        return self.role == "admin"

    @property
    def can_review(self) -> bool:
        return self.role in ("admin", "manager")

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "auth_user_id": self.auth_user_id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "is_active": self.is_active,
        }
