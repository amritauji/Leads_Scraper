"""Flask authentication dependencies.

Provides get_current_user() for use in route handlers.
"""

from __future__ import annotations

from functools import wraps
from flask import request

from app.auth.jwt import verify_supabase_token, extract_auth_user_id, AuthError
from app.auth.current_user import CurrentUser
from app.users.store import UserStore


def get_current_user() -> CurrentUser | None:
    """Extract and verify the current user from the Authorization header.

    Returns CurrentUser if valid, None if no token or invalid token.
    Does NOT raise — callers decide whether to enforce authentication.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # Strip "Bearer "
    if not token:
        return None

    try:
        payload = verify_supabase_token(token)
        auth_user_id = extract_auth_user_id(payload)
    except AuthError:
        return None

    # Map auth user to application user
    store = UserStore()
    user = store.get_by_auth_user_id(auth_user_id)
    if not user:
        return None

    return CurrentUser(
        user_id=user.user_id,
        auth_user_id=user.auth_user_id or auth_user_id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
    )


def require_auth(f):
    """Decorator: endpoint requires authenticated, active user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from app.auth.permissions import require_authenticated
        user = get_current_user()
        try:
            user = require_authenticated(user)
        except AuthError as e:
            from flask import jsonify
            return jsonify({"error": e.message}), e.status
        request.current_user = user
        return f(*args, **kwargs)
    return decorated
