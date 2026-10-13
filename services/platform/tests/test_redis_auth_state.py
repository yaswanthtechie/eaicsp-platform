"""
Round 12+13 Milestone 1/3 unit tests.

Run without Docker: conftest.py swaps Redis for fakeredis and records
Kafka events instead of sending them.
"""
import os
import uuid

import pytest
import redis
from fastapi.testclient import TestClient

import app.core.revocation_store as revocation_store
from app.database import SessionLocal
from app.main import app
from app.models.failed_login_attempts import FailedLoginAttempt

client = TestClient(app)

TEST_PASSWORD = "TestUser@12345"


@pytest.fixture(autouse=True)
def clear_failed_logins():
    """
    Failed logins are counted per IP in the database, which is shared by
    the whole test session. Clear them before and after each test so the
    lockout tests here never push later tests over the IP login limit.
    """
    def clear():
        db = SessionLocal()
        try:
            db.query(FailedLoginAttempt).delete()
            db.commit()
        finally:
            db.close()

    clear()
    yield
    clear()


def _login(email, password):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _new_analyst():
    ceo = _login("ceo@company.com", os.environ["CEO_PASSWORD"])["access_token"]
    email = f"analyst.{uuid.uuid4().hex[:8]}@company.com"
    response = client.post(
        "/api/v1/admin/users",
        headers=_auth(ceo),
        json={
            "email": email,
            "full_name": "Redis Test",
            "password": TEST_PASSWORD,
            "role": "analyst",
        },
    )
    assert response.status_code == 201, response.text
    return email


# ---- test setup --------------------------------------------------------

def test_fakeredis_can_run_the_rate_limiter_lua_script():
    """
    The rate limiter uses Redis EVAL (Lua). fakeredis only supports EVAL
    when `lupa` is installed. If this fails, run:
        pip install -r requirements.txt
    """
    import fakeredis

    assert fakeredis.FakeRedis(decode_responses=True).eval("return 1", 0) == 1


def test_login_is_not_blocked_by_the_rate_limiter_in_tests():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": os.environ["CEO_PASSWORD"],
        },
    )

    assert response.status_code == 200, response.text


# ---- revocation --------------------------------------------------------

def test_logged_out_token_is_rejected_everywhere():
    tokens = _login(_new_analyst(), TEST_PASSWORD)
    headers = _auth(tokens["access_token"])

    assert client.post("/api/v1/auth/verify", headers=headers).status_code == 200

    logout = client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 200, logout.text

    assert client.post("/api/v1/auth/verify", headers=headers).status_code == 401
    # The platform's own protected endpoints must reject it too.
    assert client.get("/api/v1/auth/me/permissions", headers=headers).status_code == 401


def test_logout_does_not_report_success_when_redis_cannot_store_revocation(monkeypatch):
    tokens = _login(_new_analyst(), TEST_PASSWORD)
    headers = _auth(tokens["access_token"])
    real_redis = revocation_store.get_redis()

    class WritesFail:
        """Reads work, but storing the revocation fails."""

        def __getattr__(self, name):
            return getattr(real_redis, name)

        def setex(self, *args, **kwargs):
            raise redis.ConnectionError("Redis write failed")

    monkeypatch.setattr(revocation_store, "get_redis", lambda: WritesFail())
    failed = client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert failed.status_code == 503, failed.text

    # Redis is back: nothing was committed, so a retry works...
    monkeypatch.setattr(revocation_store, "get_redis", lambda: real_redis)
    retry = client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert retry.status_code == 200, retry.text

    # ...and the token is really revoked.
    assert client.post("/api/v1/auth/verify", headers=headers).status_code == 401


# ---- platform.user.locked ----------------------------------------------

def test_account_lock_publishes_one_user_locked_event(published_events):
    email = _new_analyst()

    statuses = [
        client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Wrong!Passw0rd"},
        ).status_code
        for _ in range(5)
    ]

    assert statuses[-1] == 423, statuses

    locked = [e for e in published_events if e["event_type"] == "platform.user.locked"]
    assert len(locked) == 1
    assert isinstance(locked[0]["payload"]["user_id"], int)
    # No PII in the event payload.
    assert email not in str(locked[0]["payload"])


def test_failed_publish_does_not_undo_the_lock(published_events):
    """The conftest recorder returns None, exactly like a Kafka outage."""
    email = _new_analyst()

    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "Wrong!Passw0rd"},
        )

    still_locked = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
    )

    assert still_locked.status_code == 423, still_locked.text