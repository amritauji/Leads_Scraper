"""JWKS client with TTL-based caching for Supabase Auth token verification.

Fetches signing keys from the Supabase JWKS endpoint and caches them.
Respects key rotation by re-fetching when an unknown kid is encountered.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests
from jwt.algorithms import RSAAlgorithm, ECAlgorithm

logger = logging.getLogger(__name__)

# Supported asymmetric algorithms for Supabase tokens
SUPPORTED_ASYMMETRIC_ALGORITHMS = {"RS256", "ES256", "RS384", "ES384"}

# Default cache TTL: 1 hour
_DEFAULT_CACHE_TTL = 3600

# HTTP timeout for JWKS fetch
_JWKS_TIMEOUT = 10


class JWKSClient:
    """Fetches and caches JWKS signing keys from Supabase Auth.

    Thread-safe. Re-fetches on unknown kid (rotation handling).
    """

    def __init__(self, jwks_url: str, cache_ttl: int = _DEFAULT_CACHE_TTL):
        self._jwks_url = jwks_url
        self._cache_ttl = cache_ttl
        self._keys: dict[str, Any] = {}  # kid -> jwt.algorithms key
        self._raw_keys: list[dict] = []  # raw JWKS key objects
        self._fetched_at: float = 0.0
        self._lock = threading.Lock()

    def get_signing_key(self, kid: str) -> Any:
        """Get the signing key for a given kid.

        Fetches from JWKS if cache is empty, expired, or kid is unknown.
        Returns a PyJWT-compatible key object.
        Raises ValueError if kid not found after fetch.
        """
        with self._lock:
            # Check cache freshness and kid presence
            cache_age = time.time() - self._fetched_at
            if cache_age > self._cache_ttl or kid not in self._keys:
                self._fetch_keys()

            if kid not in self._keys:
                raise ValueError(f"Unknown signing key kid: {kid}")

            return self._keys[kid]

    def _fetch_keys(self) -> None:
        """Fetch JWKS from the endpoint and rebuild the key cache."""
        try:
            resp = requests.get(
                self._jwks_url,
                timeout=_JWKS_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("Failed to fetch JWKS from %s: %s", self._jwks_url, e)
            # If we have cached keys and this is a rotation-fetch failure,
            # keep the old keys rather than failing hard on a transient error.
            if self._keys:
                logger.info("Retaining %d cached JWKS keys after fetch failure", len(self._keys))
            return

        keys_list = data.get("keys", [])
        if not keys_list:
            logger.warning("JWKS endpoint returned empty keys list")
            return

        new_keys: dict[str, Any] = {}
        for jwk in keys_list:
            kid = jwk.get("kid")
            kty = jwk.get("kty")
            alg = jwk.get("alg", "")

            if not kid or not kty:
                continue

            if alg and alg not in SUPPORTED_ASYMMETRIC_ALGORITHMS:
                continue

            try:
                key = self._build_key(jwk, kty)
                if key is not None:
                    new_keys[kid] = key
            except Exception as e:
                logger.debug("Skipping JWK kid=%s: %s", kid, e)
                continue

        if new_keys:
            self._keys = new_keys
            self._raw_keys = list(keys_list)
            self._fetched_at = time.time()
            logger.debug("Loaded %d signing keys from JWKS", len(new_keys))

    @staticmethod
    def _build_key(jwk: dict, kty: str) -> Any:
        """Build a PyJWT-compatible key from a JWK object."""
        if kty == "RSA":
            return RSAAlgorithm.from_jwk(jwk)
        elif kty == "EC":
            return ECAlgorithm.from_jwk(jwk)
        return None

    def clear_cache(self) -> None:
        """Force re-fetch on next get_signing_key call."""
        with self._lock:
            self._keys.clear()
            self._raw_keys.clear()
            self._fetched_at = 0.0

    @property
    def cached_key_count(self) -> int:
        return len(self._keys)
