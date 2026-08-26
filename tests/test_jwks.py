"""Phase 4 JWKS tests: Asymmetric JWT verification with caching.

12 test cases verifying JWKS-first verification, legacy HS256 fallback,
caching, key rotation, and algorithm rejection.

Uses locally generated RSA keys to simulate Supabase JWKS signing.
"""
import os, sys, time, uuid
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pytest
import jwt as pyjwt
import requests as _requests_mod
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from app.auth.jwt import (
    verify_supabase_token,
    AuthError,
    reset_jwks_client,
)
from app.auth.jwks import JWKSClient


# ---------------------------------------------------------------------------
# Test key material (generated once per module)
# ---------------------------------------------------------------------------

_RSA_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
_RSA_PUBLIC_KEY = _RSA_PRIVATE_KEY.public_key()

_RSA_KID = "test-rsa-key-001"
_SUPABASE_ISSUER = "https://test-project.supabase.co"
_JWKS_URL = f"{_SUPABASE_ISSUER}/auth/v1/.well-known/jwks.json"

_RSA_PEM = _RSA_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _build_jwks_response(keys: list[dict]) -> dict:
    return {"keys": keys}


def _export_rsa_jwk(kid: str) -> dict:
    pub_numbers = _RSA_PUBLIC_KEY.public_numbers()
    from base64 import urlsafe_b64encode
    def _b64(n):
        byte_len = (n.bit_length() + 7) // 8
        return urlsafe_b64encode(n.to_bytes(byte_len, 'big')).rstrip(b'=').decode()
    return {
        "kty": "RSA", "kid": kid,
        "n": _b64(pub_numbers.n), "e": _b64(pub_numbers.e),
        "alg": "RS256", "use": "sig",
    }


def _make_rs256_token(sub: str, issuer: str, kid: str, exp_offset: int = 3600) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": sub, "iss": issuer, "aud": "authenticated",
         "exp": now + exp_offset, "iat": now},
        _RSA_PEM, algorithm="RS256", headers={"kid": kid},
    )


def _make_hs256_token(sub: str, issuer: str, secret: str, exp_offset: int = 3600) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": sub, "iss": issuer, "aud": "authenticated",
         "exp": now + exp_offset, "iat": now},
        secret, algorithm="HS256",
    )


def _mock_jwks_get(jwks_data: dict):
    """Return a MagicMock that replaces requests.get to return JWKS data."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = jwks_data
    mock_resp.raise_for_status.return_value = None
    mock_get = MagicMock(return_value=mock_resp)
    return mock_get


# ---------------------------------------------------------------------------
# Tests — JWT verification
# ---------------------------------------------------------------------------

class TestJWKSVerification:
    """Tests JWKS-first asymmetric token verification."""

    def setup_method(self):
        reset_jwks_client()

    def teardown_method(self):
        reset_jwks_client()

    # Test 1: Valid asymmetric token → accepted
    def test_valid_asymmetric_token_accepted(self):
        sub = str(uuid.uuid4())
        token = _make_rs256_token(sub, _SUPABASE_ISSUER, _RSA_KID)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                payload = verify_supabase_token(token)
                assert payload["sub"] == sub
                assert payload["iss"] == _SUPABASE_ISSUER

    # Test 2: Invalid asymmetric signature → 401
    def test_invalid_asymmetric_signature_rejected(self):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        sub = str(uuid.uuid4())
        now = int(time.time())
        token = pyjwt.encode(
            {"sub": sub, "iss": _SUPABASE_ISSUER, "aud": "authenticated",
             "exp": now + 3600, "iat": now},
            other_pem, algorithm="RS256", headers={"kid": _RSA_KID},
        )
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                with pytest.raises(AuthError) as exc:
                    verify_supabase_token(token)
                assert exc.value.status == 401

    # Test 3: Expired asymmetric token → 401
    def test_expired_asymmetric_token_rejected(self):
        sub = str(uuid.uuid4())
        token = _make_rs256_token(sub, _SUPABASE_ISSUER, _RSA_KID, exp_offset=-3600)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                with pytest.raises(AuthError) as exc:
                    verify_supabase_token(token)
                assert exc.value.status == 401
                assert "expired" in exc.value.message.lower()

    # Test 4: Wrong issuer → 401
    def test_wrong_issuer_rejected(self):
        sub = str(uuid.uuid4())
        token = _make_rs256_token(sub, "https://wrong-project.supabase.co", _RSA_KID)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                with pytest.raises(AuthError) as exc:
                    verify_supabase_token(token)
                assert exc.value.status == 401

    # Test 5: Unsupported algorithm → 401
    def test_unsupported_algorithm_rejected(self):
        sub = str(uuid.uuid4())
        now = int(time.time())
        token = pyjwt.encode(
            {"sub": sub, "iss": _SUPABASE_ISSUER, "aud": "authenticated",
             "exp": now + 3600, "iat": now},
            _RSA_PEM, algorithm="PS256", headers={"kid": _RSA_KID},
        )

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with pytest.raises(AuthError) as exc:
                verify_supabase_token(token)
            assert exc.value.status == 401
            assert "unsupported" in exc.value.message.lower()

    # Test 6: Unknown kid → 401
    def test_unknown_kid_rejected(self):
        sub = str(uuid.uuid4())
        unknown_kid = "nonexistent-key-id"
        token = _make_rs256_token(sub, _SUPABASE_ISSUER, unknown_kid)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                with pytest.raises(AuthError) as exc:
                    verify_supabase_token(token)
                assert exc.value.status == 401
                assert "unknown" in exc.value.message.lower() or "signing key" in exc.value.message.lower()

    # Test 7: JWKS caching works
    def test_jwks_caching_works(self):
        sub = str(uuid.uuid4())
        token = _make_rs256_token(sub, _SUPABASE_ISSUER, _RSA_KID)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)) as mock_get:
                payload1 = verify_supabase_token(token)
                payload2 = verify_supabase_token(token)

                assert payload1["sub"] == sub
                assert payload2["sub"] == sub
                # Only one HTTP call — second used cache
                assert mock_get.call_count == 1

    # Test 8: Key rotation / alternate valid kid works
    def test_key_rotation_alternate_kid_works(self):
        new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        new_pem = new_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        new_pub = new_key.public_key()
        new_numbers = new_pub.public_numbers()
        from base64 import urlsafe_b64encode
        def _b64(n):
            byte_len = (n.bit_length() + 7) // 8
            return urlsafe_b64encode(n.to_bytes(byte_len, 'big')).rstrip(b'=').decode()

        new_kid = "rotated-key-002"
        new_jwk = {
            "kty": "RSA", "kid": new_kid,
            "n": _b64(new_numbers.n), "e": _b64(new_numbers.e),
            "alg": "RS256", "use": "sig",
        }

        sub = str(uuid.uuid4())
        now = int(time.time())
        token = pyjwt.encode(
            {"sub": sub, "iss": _SUPABASE_ISSUER, "aud": "authenticated",
             "exp": now + 3600, "iat": now},
            new_pem, algorithm="RS256", headers={"kid": new_kid},
        )
        jwks_data = _build_jwks_response([new_jwk])

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwks.requests.get", _mock_jwks_get(jwks_data)):
                payload = verify_supabase_token(token)
                assert payload["sub"] == sub

    # Test 9: Legacy HS256 token works only when legacy fallback is configured
    def test_legacy_hs256_works_with_secret_configured(self):
        sub = str(uuid.uuid4())
        secret = "test-legacy-secret-key-for-hs256"
        token = _make_hs256_token(sub, _SUPABASE_ISSUER, secret)

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwt.SUPABASE_JWT_SECRET", secret):
                payload = verify_supabase_token(token)
                assert payload["sub"] == sub

    # Test 10: Legacy token fails when fallback is disabled
    def test_legacy_hs256_fails_without_secret(self):
        sub = str(uuid.uuid4())
        secret = "test-legacy-secret-key-for-hs256"
        token = _make_hs256_token(sub, _SUPABASE_ISSUER, secret)

        with patch("app.auth.jwt.SUPABASE_URL", _SUPABASE_ISSUER):
            with patch("app.auth.jwt.SUPABASE_JWT_SECRET", ""):
                with pytest.raises(AuthError) as exc:
                    verify_supabase_token(token)
                assert exc.value.status == 401
                assert "hs256" in exc.value.message.lower() or "legacy" in exc.value.message.lower()


# ---------------------------------------------------------------------------
# JWKSClient unit tests
# ---------------------------------------------------------------------------

class TestJWKSClient:
    def setup_method(self):
        reset_jwks_client()

    def teardown_method(self):
        reset_jwks_client()

    def test_clear_cache_forces_refetch(self):
        client = JWKSClient(_JWKS_URL)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        mock_resp = MagicMock()
        mock_resp.json.return_value = jwks_data
        mock_resp.raise_for_status.return_value = None

        with patch("app.auth.jwks.requests.get", return_value=mock_resp) as mock_get:
            client.get_signing_key(_RSA_KID)
            assert mock_get.call_count == 1

            client.get_signing_key(_RSA_KID)
            assert mock_get.call_count == 1  # cached

            client.clear_cache()
            client.get_signing_key(_RSA_KID)
            assert mock_get.call_count == 2  # refetched

    def test_fetch_failure_retains_cached_keys(self):
        client = JWKSClient(_JWKS_URL, cache_ttl=0)
        jwks_data = _build_jwks_response([_export_rsa_jwk(_RSA_KID)])

        with patch("app.auth.jwks.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = jwks_data
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            key = client.get_signing_key(_RSA_KID)
            assert key is not None

        # Second call: network error — should retain cached key
        with patch("app.auth.jwks.requests.get", side_effect=_requests_mod.ConnectionError("network error")):
            key2 = client.get_signing_key(_RSA_KID)
            assert key2 is not None
