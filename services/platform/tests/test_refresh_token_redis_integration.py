"""Real Redis restart integration test for refresh token rotation.

Verifies that:
1. Refresh token rotation caches the active token in real Redis under
   platform:family_active:<family_id>.
2. When Redis cache is lost (simulating a Redis restart / cache loss) by
   deleting platform:family_* keys without flushdb/flushall, refresh still
   succeeds from the database (PostgreSQL in CI / production) and reconstructs
   the Redis family active cache.
3. Only the test's family cache keys are cleaned up.

Marked strictly with @pytest.mark.integration and requires real Redis.
"""

from __future__ import annotations

import os

import pytest
import redis
from fastapi.testclient import TestClient

from app.core import (
    redis_client as redis_client_mod,
)
from app.core import (
    revocation_store as revocation_store_mod,
)
from app.core import (
    token_cache as token_cache_mod,
)
from app.core.revocation_store import (
    FAMILY_ACTIVE_PREFIX,
    FAMILY_REVOCATION_PREFIX,
    get_family_active_token,
)
from app.core.security import decode_token, hash_token
from app.main import app
from app.services import rate_limit_service as rate_limit_mod
from tests.test_auth import login_as_ceo, reset_test_security_state

pytestmark = pytest.mark.integration


@pytest.fixture
def real_redis(monkeypatch: pytest.MonkeyPatch) -> redis.Redis:
    """Restore the real Redis client and verify connectivity with ping().

    tests/conftest.py replaces Redis with fakeredis for unit tests.
    This fixture restores the real Redis client for integration testing.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        client: redis.Redis = redis.Redis.from_url(redis_url, decode_responses=True)
        if not client.ping():
            pytest.fail(f"Redis ping failed at {redis_url}")
    except (redis.RedisError, OSError) as exc:
        pytest.fail(f"Real Redis is not reachable at {redis_url}: {exc}")

    monkeypatch.setattr(redis_client_mod, "redis_client", client)
    monkeypatch.setattr(revocation_store_mod, "get_redis", lambda: client)
    monkeypatch.setattr(token_cache_mod, "get_redis", lambda: client)
    monkeypatch.setattr(rate_limit_mod, "get_redis", lambda: client)

    return client


def test_refresh_token_redis_restart_reconstructs_family_cache(
    real_redis: redis.Redis,
) -> None:
    """Verify refresh succeeds and reconstructs Redis cache after Redis cache loss.

    Simulates Redis restart by wiping only keys matching platform:family_*,
    never calling flushdb() or flushall().
    """
    reset_test_security_state()
    test_client = TestClient(app)

    # 1. Log in as CEO to obtain an initial refresh token
    login_data = login_as_ceo()
    token_1 = login_data["refresh_token"]

    claims_1 = decode_token(token_1)
    family_id = claims_1.get("family_id")
    assert family_id is not None, "Initial refresh token must have a family_id claim"

    active_key = f"{FAMILY_ACTIVE_PREFIX}{family_id}"

    try:
        # 2. Rotate token: token_1 -> token_2
        resp_1 = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": token_1}
        )
        assert resp_1.status_code == 200, f"First refresh failed: {resp_1.text}"
        body_1 = resp_1.json()
        token_2 = body_1["refresh_token"]
        assert token_2 != token_1

        claims_2 = decode_token(token_2)
        assert claims_2.get("family_id") == family_id

        # 3. Verify refresh-token family cache exists after rotation
        token_2_hash = hash_token(token_2)
        cached_hash_1 = real_redis.get(active_key)
        assert cached_hash_1 == token_2_hash
        assert get_family_active_token(family_id) == token_2_hash

        # 4. Simulate Redis cache loss / restart:
        # Delete ONLY keys matching platform:family_*; never flushdb() or flushall()
        family_keys = list(real_redis.scan_iter("platform:family_*"))
        if family_keys:
            real_redis.delete(*family_keys)

        # Confirm the family cache is absent
        assert real_redis.get(active_key) is None
        assert get_family_active_token(family_id) is None

        # 5. Verify refresh still succeeds from database and reconstructs family cache
        resp_2 = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": token_2}
        )
        assert resp_2.status_code == 200, (
            f"Refresh after Redis restart failed: {resp_2.text}"
        )
        body_2 = resp_2.json()
        token_3 = body_2["refresh_token"]
        assert token_3 != token_2

        claims_3 = decode_token(token_3)
        assert claims_3.get("family_id") == family_id

        # Verify Redis family cache has been reconstructed
        token_3_hash = hash_token(token_3)
        cached_hash_2 = real_redis.get(active_key)
        assert cached_hash_2 == token_3_hash
        assert get_family_active_token(family_id) == token_3_hash

    finally:
        # 6. Clean up only the test's family cache keys
        real_redis.delete(active_key)
        real_redis.delete(f"{FAMILY_REVOCATION_PREFIX}{family_id}")
