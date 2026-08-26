"""Supabase JWT verification with JWKS-first, legacy HS256 fallback.

Verification strategy:
  1. Decode token header (unverified) to get kid and alg
  2. If alg is asymmetric (RS256, ES256, RS384, ES384):
     → verify with JWKS signing key
  3. If alg is HS256 and SUPABASE_JWT_SECRET is configured:
     → verify with symmetric secret (legacy compatibility)
  4. If alg is HS256 and no SUPABASE_JWT_SECRET configured:
     → reject (legacy disabled)
  5. Any other algorithm → reject

Claims verified: signature, exp, iss, sub.
"""

from __future__ import annotations

import logging

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError, InvalidAudienceError, ImmatureSignatureError
from jwt.exceptions import DecodeError as PyJWTDecodeError

from app.config import SUPABASE_URL, SUPABASE_JWT_SECRET

logger = logging.getLogger(__name__)

# Asymmetric algorithms supported for JWKS verification
_ASYMMETRIC_ALGOS = {"RS256", "ES256", "RS384", "ES384"}

# Legacy symmetric algorithm
_LEGACY_ALGOS = {"HS256"}

# All accepted algorithms (for algorithm confusion protection)
_ALL_ACCEPTED_ALGOS = _ASYMMETRIC_ALGOS | _LEGACY_ALGOS


class AuthError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", status: int = 401):
        self.message = message
        self.status = status
        super().__init__(self.message)


def _get_supabase_issuer() -> str | None:
    """Derive the Supabase issuer URL from SUPABASE_URL.

    Supabase tokens have iss = SUPABASE_URL (e.g. https://rqumyeivufwojihgwbwu.supabase.co).
    """
    if not SUPABASE_URL:
        return None
    return SUPABASE_URL.rstrip("/")


def verify_supabase_token(token: str) -> dict:
    """Verify a Supabase JWT access token and return the decoded payload.

    JWKS-first strategy:
      - Asymmetric tokens (RS256/ES256) → JWKS verification
      - Legacy HS256 tokens → SUPABASE_JWT_SECRET fallback (if configured)
      - Unknown/unsupported algorithms → rejected

    Raises:
        AuthError: If token is invalid, expired, has wrong issuer, or uses unsupported algorithm.
    """
    # Step 1: Decode header without verification to get kid/alg
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise AuthError("Malformed token", 401)

    alg = header.get("alg", "")
    kid = header.get("kid")

    if not alg:
        raise AuthError("Token missing algorithm", 401)

    issuer = _get_supabase_issuer()
    if not issuer:
        raise AuthError("SUPABASE_URL not configured", 500)

    # Step 2: Route by algorithm
    if alg in _ASYMMETRIC_ALGOS:
        return _verify_with_jwks(token, kid, alg, issuer)
    elif alg in _LEGACY_ALGOS:
        return _verify_with_legacy(token, alg, issuer)
    else:
        raise AuthError(f"Unsupported token algorithm: {alg}", 401)


def _verify_with_jwks(token: str, kid: str | None, alg: str, issuer: str) -> dict:
    """Verify an asymmetric token using JWKS signing keys."""
    if not kid:
        raise AuthError("Asymmetric token missing 'kid' header", 401)

    from app.auth.jwks import JWKSClient, SUPPORTED_ASYMMETRIC_ALGORITHMS

    if alg not in SUPPORTED_ASYMMETRIC_ALGORITHMS:
        raise AuthError(f"Unsupported asymmetric algorithm: {alg}", 401)

    jwks_url = f"{issuer}/auth/v1/.well-known/jwks.json"
    client = _get_jwks_client(jwks_url)

    try:
        signing_key = client.get_signing_key(kid)
    except ValueError as e:
        raise AuthError(f"Unknown signing key: {e}", 401)

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=list(_ASYMMETRIC_ALGOS),
            issuer=issuer,
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except ExpiredSignatureError:
        raise AuthError("Token has expired", 401)
    except ImmatureSignatureError:
        raise AuthError("Token not yet valid", 401)
    except InvalidAudienceError:
        raise AuthError("Invalid token audience", 401)
    except InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}", 401)
    except PyJWTDecodeError as e:
        raise AuthError(f"Token decode error: {e}", 401)
    except Exception as e:
        raise AuthError(f"Token verification failed: {e}", 401)

    return payload


def _verify_with_legacy(token: str, alg: str, issuer: str) -> dict:
    """Verify a legacy HS256 token using SUPABASE_JWT_SECRET.

    Only active when SUPABASE_JWT_SECRET is configured.
    """
    if not SUPABASE_JWT_SECRET:
        raise AuthError(
            "HS256 token received but SUPABASE_JWT_SECRET not configured. "
            "This legacy signing algorithm is disabled.",
            401,
        )

    logger.debug("Verifying legacy HS256 token with SUPABASE_JWT_SECRET")

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            issuer=issuer,
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except ExpiredSignatureError:
        raise AuthError("Token has expired", 401)
    except ImmatureSignatureError:
        raise AuthError("Token not yet valid", 401)
    except InvalidAudienceError:
        raise AuthError("Invalid token audience", 401)
    except InvalidTokenError as e:
        raise AuthError(f"Invalid token: {e}", 401)
    except PyJWTDecodeError as e:
        raise AuthError(f"Token decode error: {e}", 401)
    except Exception as e:
        raise AuthError(f"Token verification failed: {e}", 401)

    return payload


def extract_auth_user_id(payload: dict) -> str:
    """Extract the Supabase auth user ID (sub claim) from a decoded JWT payload."""
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Token missing 'sub' claim", 401)
    return sub


# ---------------------------------------------------------------------------
# Module-level JWKS client singleton (lazy-initialized, thread-safe)
# ---------------------------------------------------------------------------
_jwks_client: JWKSClient | None = None
_jwks_url_global: str | None = None


def _get_jwks_client(jwks_url: str) -> "JWKSClient":
    """Get or create a cached JWKSClient for the given URL."""
    global _jwks_client, _jwks_url_global

    if _jwks_client is None or _jwks_url_global != jwks_url:
        from app.auth.jwks import JWKSClient
        _jwks_client = JWKSClient(jwks_url)
        _jwks_url_global = jwks_url

    return _jwks_client


def reset_jwks_client():
    """Reset the JWKS client singleton. For testing only."""
    global _jwks_client, _jwks_url_global
    if _jwks_client:
        _jwks_client.clear_cache()
    _jwks_client = None
    _jwks_url_global = None
