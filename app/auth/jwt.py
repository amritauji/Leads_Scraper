"""Supabase JWT verification."""

from __future__ import annotations

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, DecodeError

from app.config import SUPABASE_JWT_SECRET


class AuthError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", status: int = 401):
        self.message = message
        self.status = status
        super().__init__(self.message)


def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase JWT access token and return the decoded payload.

    Uses HS256 with the SUPABASE_JWT_SECRET for local verification.
    No remote API call needed.

    Raises:
        AuthError: If token is invalid, expired, or cannot be decoded.
    """
    if not SUPABASE_JWT_SECRET:
        raise AuthError("SUPABASE_JWT_SECRET not configured", 500)

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "aud"]},
        )
    except ExpiredSignatureError:
        raise AuthError("Token has expired", 401)
    except InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}", 401)
    except Exception as e:
        raise AuthError(f"Token verification failed: {e}", 401)

    return payload


def extract_auth_user_id(payload: dict) -> str:
    """Extract the Supabase auth user ID (sub claim) from a decoded JWT payload."""
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Token missing 'sub' claim", 401)
    return sub
