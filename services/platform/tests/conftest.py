import os
# These must be set BEFORE any `app.*` import, because
# app/core/config.py reads os.environ at import time.

os.environ["SECRET_KEY"] = "test-secret-key"
# Use a dedicated test database so running the suite never
# touches (or seeds, or deletes rows from) a real dev database.
os.environ["DATABASE_URL"] = "sqlite:///./test_platform.db"

# Seed credentials for the test database. These are test fixtures only --
# the real deployment supplies them from the environment (see .env.example).
TEST_SEED_PASSWORDS = {
    "CEO_PASSWORD": "ceocompany@123",
    "VP_OPERATIONS_PASSWORD": "vpoperations@123",
    "PROCUREMENT_MANAGER_PASSWORD": "procurement@123",
    "LOGISTICS_MANAGER_PASSWORD": "logistics@123",
    "COMPLIANCE_OFFICER_PASSWORD": "compliance@123",
    "WAREHOUSE_MANAGER_PASSWORD": "warehouse@123",
    "ANALYST_PASSWORD": "analyst@1234",
    "SUPPLIER_PASSWORD": "supplier@123",
}

for _key, _value in TEST_SEED_PASSWORDS.items():
    os.environ.setdefault(_key, _value)

# ============================================================
# PYTEST / APPLICATION IMPORTS
# ============================================================
import pytest
from app.database import Base, engine
from app.seed import seed_database

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
    from app.services.rate_limit_service import (
        _last_abuse_event_at,
        _request_buckets,
    )
    from app.services.mfa_service import _mfa_challenges

    
    # --------------------------------------------------------
    # Create isolated fake Redis for this test
    # --------------------------------------------------------

    fake_client = fakeredis.FakeRedis(
        decode_responses=True
    )

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
            return None

        monkeypatch.setattr(
            app.services.auth_service,
            "publish_event",
            record,
        )

    return events