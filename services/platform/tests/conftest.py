import os
import secrets

from dotenv import load_dotenv

# A developer's .env wins; the random values below only fill the gaps.
load_dotenv()

# These must be set BEFORE any `app.*` import, because
# app/core/config.py reads os.environ at import time.
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"

# Tests always use a dedicated database, never the developer's DATABASE_URL.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite:///./test_platform.db",
)

# Seed credentials for the test database: random per run, never committed.
# setdefault lets CI (or a developer) supply their own values instead.
SEED_PASSWORD_KEYS = (
    "CEO_PASSWORD",
    "VP_OPERATIONS_PASSWORD",
    "PROCUREMENT_MANAGER_PASSWORD",
    "LOGISTICS_MANAGER_PASSWORD",
    "COMPLIANCE_OFFICER_PASSWORD",
    "WAREHOUSE_MANAGER_PASSWORD",
    "ANALYST_PASSWORD",
    "SUPPLIER_PASSWORD",
)

for _key in SEED_PASSWORD_KEYS:
    os.environ.setdefault(_key, f"Test-{secrets.token_hex(8)}@1")

# ============================================================
# PYTEST / APPLICATION IMPORTS
# ============================================================
import pytest  # noqa: E402 - Test environment setup runs before imports.

from app.database import Base, engine  # noqa: E402 - Test environment setup runs before imports.
from app.seed import seed_database  # noqa: E402 - Test environment setup runs before imports.


# ============================================================
# DATABASE SETUP
# ============================================================
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    seed_database()

    yield

    Base.metadata.drop_all(bind=engine)


# ============================================================
# SECURITY STATE RESET
# ============================================================
# Unit tests use fakeredis, so Docker/real Redis is NOT required.
# Production application code still uses the real Redis client.
# The in-memory dictionaries are cleared for backward
# compatibility with existing tests.
# ============================================================
@pytest.fixture(autouse=True)
def reset_security_state(monkeypatch):

    import fakeredis

    import app.core.redis_client
    import app.core.revocation_store
    import app.core.token_cache
    import app.services.rate_limit_service
    from app.services.mfa_service import _mfa_challenges
    from app.services.rate_limit_service import (
        _last_abuse_event_at,
        _request_buckets,
    )

    # --------------------------------------------------------
    # Create isolated fake Redis for this test
    # --------------------------------------------------------

    fake_client = fakeredis.FakeRedis(decode_responses=True)

    # --------------------------------------------------------
    # Patch the central Redis client
    # --------------------------------------------------------

    monkeypatch.setattr(
        app.core.redis_client,
        "redis_client",
        fake_client,
    )

    # --------------------------------------------------------
    # Patch modules that imported get_redis directly
    # --------------------------------------------------------

    monkeypatch.setattr(
        app.core.revocation_store,
        "get_redis",
        lambda: fake_client,
    )

    monkeypatch.setattr(
        app.core.token_cache,
        "get_redis",
        lambda: fake_client,
    )

    monkeypatch.setattr(
        app.services.rate_limit_service,
        "get_redis",
        lambda: fake_client,
    )

    # --------------------------------------------------------
    # Clear legacy in-memory compatibility state
    # --------------------------------------------------------
    _request_buckets.clear()
    _last_abuse_event_at.clear()
    _mfa_challenges.clear()

    yield
    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------
    fake_client.flushall()

    _request_buckets.clear()
    _last_abuse_event_at.clear()
    _mfa_challenges.clear()


# ============================================================
# KAFKA: unit tests never contact a real broker
# ============================================================
# Records every event the app tries to publish instead of sending it.
# Use the `published_events` fixture in a test to inspect them.
# Integration tests (marked `integration`) still use real Kafka.
# ============================================================
@pytest.fixture(autouse=True)
def published_events(request, monkeypatch):
    events = []

    if request.node.get_closest_marker("integration") is None:
        import app.services.auth_service

        def record(event_type, payload):
            events.append({"event_type": event_type, "payload": payload})

        monkeypatch.setattr(
            app.services.auth_service,
            "publish_event",
            record,
        )

    return events
