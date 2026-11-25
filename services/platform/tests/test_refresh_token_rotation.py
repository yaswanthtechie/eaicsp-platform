import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import redis
from fastapi.testclient import TestClient

from app.core.redis_client import get_redis
from app.core.security import decode_token, hash_token
from app.database import SessionLocal
from app.main import app
from app.models.auth_audit_logs import AuthAuditLog
from app.models.refresh_token import RefreshToken
from app.models.roles import Role
from app.models.users import User
from app.services.audit_service import TOKEN_REVOKED
from scripts.migrate_refresh_tokens_family_and_hash import (
    is_sha256_hex,
)
from scripts.migrate_refresh_tokens_family_and_hash import (
    run_migration as run_refresh_migration,
)
from tests.test_auth import (
    auth_header,
    login_as_ceo,
    login_as_vp,
    reset_test_security_state,
    unique_email,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    reset_test_security_state()


def test_normal_refresh_rotation_and_family():
    """Verify refresh token rotation generates a new token under the same family and hashes tokens."""
    login = login_as_ceo()
    token_1 = login["refresh_token"]

    payload_1 = decode_token(token_1)
    assert "family_id" in payload_1
    family_id_1 = payload_1["family_id"]
    assert family_id_1 is not None

    db = SessionLocal()
    try:
        # Check database stores SHA-256 hash and not raw JWT
        token_hash_1 = hash_token(token_1)
        db_row_1 = (
            db.query(RefreshToken).filter(RefreshToken.token == token_hash_1).first()
        )
        assert db_row_1 is not None
        assert db_row_1.family_id == family_id_1
        assert is_sha256_hex(db_row_1.token)
        assert "." not in db_row_1.token
        assert db_row_1.is_revoked is False
    finally:
        db.close()

    # 1. Rotate token
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    token_2 = body["refresh_token"]
    assert token_2 != token_1

    payload_2 = decode_token(token_2)
    assert payload_2["family_id"] == family_id_1  # Preserves family ID!

    db = SessionLocal()
    try:
        # Verify old token is marked revoked with revoked_at set
        row_1 = (
            db.query(RefreshToken).filter(RefreshToken.token == token_hash_1).first()
        )
        assert row_1.is_revoked is True
        assert row_1.revoked_at is not None

        # Verify new token is active in the same family
        token_hash_2 = hash_token(token_2)
        row_2 = (
            db.query(RefreshToken).filter(RefreshToken.token == token_hash_2).first()
        )
        assert row_2 is not None
        assert row_2.family_id == family_id_1
        assert row_2.is_revoked is False
    finally:
        db.close()

    # 2. Rotate second token successfully
    resp_2 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_2})
    assert resp_2.status_code == 200
    token_3 = resp_2.json()["refresh_token"]
    assert token_3 != token_2
    assert decode_token(token_3)["family_id"] == family_id_1


def test_grace_period_reuse_within_window_returns_401_without_family_revocation():
    """Verify reuse within 10-second grace period returns 401 without revoking the family."""
    login = login_as_ceo()
    token_a = login["refresh_token"]

    # First rotation: A -> B
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_1.status_code == 200
    token_b = resp_1.json()["refresh_token"]

    # Replay token A immediately (within grace period <= 10s)
    resp_replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_replay.status_code == 401
    assert resp_replay.json()["detail"] == "Invalid or revoked refresh token"

    # Crucial assertion: Token B MUST still be valid because family was NOT revoked
    resp_b = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_b.status_code == 200
    assert "access_token" in resp_b.json()


def test_two_genuinely_overlapping_refresh_requests():
    """Verify two genuinely overlapping refresh requests: exactly one succeeds and loser gets 401 without family revocation."""
    login = login_as_ceo()
    shared_token = login["refresh_token"]

    results = []

    def attempt_refresh():
        return client.post("/api/v1/auth/refresh", json={"refresh_token": shared_token})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_refresh) for _ in range(2)]
        for f in futures:
            results.append(f.result())

    status_codes = [r.status_code for r in results]
    assert status_codes.count(200) == 1, (
        f"Expected exactly one 200, got: {status_codes}"
    )
    assert status_codes.count(401) == 1, f"Expected one 401, got: {status_codes}"

    winner_resp = next(r for r in results if r.status_code == 200)
    new_token = winner_resp.json()["refresh_token"]

    # Verify winning token can be refreshed (family not revoked)
    next_refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_token}
    )
    assert next_refresh.status_code == 200


def test_delayed_request_already_in_flight_when_another_request_won():
    """An in-flight loser gets 401 without revoking the winning token family."""
    import threading

    login = login_as_ceo()
    token_a = login["refresh_token"]

    req2_started = threading.Event()
    req1_won = threading.Event()
    results = {}

    import app.routes.auth_routes as auth_mod

    original_get_db_now = auth_mod.get_db_now
    first_call_lock = threading.Lock()
    first_call = True

    def hooked_get_db_now(db):
        nonlocal first_call

        request_time = original_get_db_now(db)

        with first_call_lock:
            should_pause = first_call
            if first_call:
                first_call = False

        if should_pause:
            req2_started.set()
            if not req1_won.wait(timeout=10):
                raise TimeoutError("Request 1 did not finish in time")

        return request_time

    def run_req2():
        results["loser"] = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_a},
        )

    with patch(
        "app.routes.auth_routes.get_db_now",
        side_effect=hooked_get_db_now,
    ):
        t2 = threading.Thread(target=run_req2)
        t2.start()

        assert req2_started.wait(timeout=10), (
            "Request 2 did not capture its database timestamp"
        )

        resp_1 = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_a},
        )
        assert resp_1.status_code == 200
        token_b = resp_1.json()["refresh_token"]

        req1_won.set()
        t2.join(timeout=10)

    assert not t2.is_alive(), "Request 2 did not finish"
    assert "loser" in results
    assert results["loser"].status_code == 401

    resp_b = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_b},
    )
    assert resp_b.status_code == 200
    assert "access_token" in resp_b.json()


def test_old_token_replayed_after_10_seconds_while_later_descendant_active_revokes_family():
    """Verify that an old token replayed after 10s while a later descendant remains active REVOKES the family."""
    login = login_as_ceo()
    token_a = login["refresh_token"]

    # Rotation 1: A -> B (Token B is active)
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_1.status_code == 200
    token_b = resp_1.json()["refresh_token"]
    family_id = decode_token(token_b)["family_id"]

    # Simulate token A having been revoked 15 seconds ago (beyond 10s grace period)
    db = SessionLocal()
    try:
        hash_a = hash_token(token_a)
        row_a = db.query(RefreshToken).filter(RefreshToken.token == hash_a).first()
        assert row_a is not None
        row_a.revoked_at = datetime.now(UTC) - timedelta(seconds=15)
        db.commit()
    finally:
        db.close()

    # Replay token A after 10 seconds: this is a new request, not an in-flight request.
    resp_replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_replay.status_code == 401

    # CRUCIAL CHECK: Must revoke the entire family! Active Token B MUST NOW FAIL!
    resp_b = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_b.status_code == 401

    db = SessionLocal()
    try:
        family_rows = (
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).all()
        )
        for r in family_rows:
            assert r.is_revoked is True

        audit_entry = (
            db.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == TOKEN_REVOKED,
                AuthAuditLog.details.contains(family_id),
            )
            .first()
        )
        assert audit_entry is not None
        assert token_a not in audit_entry.details
        assert token_b not in audit_entry.details
    finally:
        db.close()


def test_old_token_replayed_after_multiple_successful_rotations_revokes_family():
    """Verify that an old token replayed after multiple rotations REVOKES the entire family."""
    login = login_as_ceo()
    token_a = login["refresh_token"]

    # Rotation 1: A -> B
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_1.status_code == 200
    token_b = resp_1.json()["refresh_token"]

    # Rotation 2: B -> C (Token C is active)
    resp_2 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_2.status_code == 200
    token_c = resp_2.json()["refresh_token"]
    family_id = decode_token(token_c)["family_id"]

    # Simulate token A being revoked 15 seconds ago
    db = SessionLocal()
    try:
        hash_a = hash_token(token_a)
        row_a = db.query(RefreshToken).filter(RefreshToken.token == hash_a).first()
        assert row_a is not None
        row_a.revoked_at = datetime.now(UTC) - timedelta(seconds=15)
        db.commit()
    finally:
        db.close()

    # Replay token A after multiple rotations
    resp_replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_replay.status_code == 401

    # Entire family revoked! Active Token C must fail!
    resp_c = client.post("/api/v1/auth/refresh", json={"refresh_token": token_c})
    assert resp_c.status_code == 401

    db = SessionLocal()
    try:
        family_rows = (
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).all()
        )
        for r in family_rows:
            assert r.is_revoked is True
    finally:
        db.close()


def test_concurrent_refresh_requests_only_one_succeeds():
    """Verify concurrent refresh requests: atomic UPDATE ensures exactly one succeeds and losers get 401."""
    login = login_as_ceo()
    shared_token = login["refresh_token"]

    results = []

    def attempt_refresh():
        # Each thread gets its own TestClient request
        return client.post("/api/v1/auth/refresh", json={"refresh_token": shared_token})

    # Execute 5 concurrent requests with the exact same refresh token
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt_refresh) for _ in range(5)]
        for f in futures:
            results.append(f.result())

    status_codes = [r.status_code for r in results]

    # Exactly 1 request succeeds with 200 OK
    assert status_codes.count(200) == 1, (
        f"Expected exactly one 200, got: {status_codes}"
    )
    # All losing concurrent requests receive HTTP 401
    assert status_codes.count(401) == 4, f"Expected four 401s, got: {status_codes}"

    # Extract the winning newly issued token
    winner_resp = next(r for r in results if r.status_code == 200)
    new_token = winner_resp.json()["refresh_token"]

    # Verify that the family is still intact and the new token can be refreshed
    next_refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_token}
    )
    assert next_refresh.status_code == 200


def test_logout_revokes_entire_family():
    """Verify logout revokes all tokens belonging to the refresh token family."""
    login = login_as_ceo()
    token_a = login["refresh_token"]

    # Rotate A -> B
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_1.status_code == 200
    token_b = resp_1.json()["refresh_token"]
    family_id = decode_token(token_b)["family_id"]

    # Logout with Token B
    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": token_b},
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert logout_resp.status_code == 200

    # Token B cannot be refreshed
    resp_b = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_b.status_code == 401

    # In DB: all tokens in the family are marked is_revoked = True
    db = SessionLocal()
    try:
        family_rows = (
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).all()
        )
        for r in family_rows:
            assert r.is_revoked is True
    finally:
        db.close()


def test_expired_refresh_token_returns_401():
    """Verify an expired refresh token is rejected with HTTP 401."""
    login = login_as_ceo()
    token = login["refresh_token"]
    token_h = hash_token(token)

    db = SessionLocal()
    try:
        row = db.query(RefreshToken).filter(RefreshToken.token == token_h).first()
        row.expires_at = datetime.now(UTC) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_redis_fallback_when_redis_unavailable():
    """Verify PostgreSQL acts as source of truth and /refresh succeeds even if Redis is unavailable."""
    login = login_as_ceo()
    token = login["refresh_token"]

    with patch("app.core.revocation_store.get_redis") as mock_redis:
        mock_redis.side_effect = redis.ConnectionError("Redis connection refused")

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200
        new_token = resp.json()["refresh_token"]
        assert new_token != token


def test_migration_hashes_existing_raw_tokens_and_preserves_validity():
    """Verify migration script hashes raw token rows and allows existing users to continue refreshing."""
    db = SessionLocal()
    try:
        # Insert a raw unhashed mock token
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        from app.core.security import create_refresh_token

        raw_jwt = create_refresh_token({"sub": user.email, "user_id": user.id})

        # Directly insert raw JWT into table (simulating legacy pre-migration row)
        legacy_row = RefreshToken(
            user_id=user.id,
            token=raw_jwt,
            is_revoked=False,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            family_id=None,
        )
        db.add(legacy_row)
        db.commit()
        db.refresh(legacy_row)
        legacy_id = legacy_row.id
    finally:
        db.close()

    # Run migration
    summary = run_refresh_migration()
    assert summary["tokens_hashed"] >= 1

    db = SessionLocal()
    try:
        migrated_row = (
            db.query(RefreshToken).filter(RefreshToken.id == legacy_id).first()
        )
        assert migrated_row.family_id is not None
        assert is_sha256_hex(migrated_row.token)
        assert migrated_row.token == hashlib.sha256(raw_jwt.encode("utf-8")).hexdigest()
    finally:
        db.close()

    # The client holding raw_jwt calls /refresh -> MUST SUCCEED
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_jwt})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


def test_refresh_response_contract_schema():
    """Validate that the refresh endpoint response matches contracts/openapi/refresh_contract.json."""
    contract_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "contracts"
        / "openapi"
        / "refresh_contract.json"
    )
    assert contract_path.exists(), f"Contract file not found at {contract_path}"

    with open(contract_path, encoding="utf-8") as f:
        schema = json.load(f)

    login = login_as_ceo()
    resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert resp.status_code == 200
    data = resp.json()

    for required_field in schema["required"]:
        assert required_field in data, (
            f"Missing required contract field: {required_field}"
        )

    assert isinstance(data["access_token"], str)
    assert isinstance(data["refresh_token"], str)
    assert data["token_type"] == "bearer"


def test_redis_restart_empty_cache_keeps_refresh_state_and_reconstructs_cache():
    """Verify state remains correct after Redis restart (cache cleared), and rotation continues from PostgreSQL."""
    login = login_as_ceo()
    token_1 = login["refresh_token"]

    # Rotation 1: 1 -> 2
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    assert resp_1.status_code == 200
    token_2 = resp_1.json()["refresh_token"]

    # Simulate Redis restart / cache wipe
    try:
        redis_client = get_redis()
        redis_client.flushdb()
    except redis.exceptions.RedisError:
        pass

    # Rotation 2: 2 -> 3 with empty Redis cache! Must succeed from PostgreSQL source of truth
    resp_2 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_2})
    assert resp_2.status_code == 200
    token_3 = resp_2.json()["refresh_token"]
    assert token_3 != token_2

    # Backdate ancestor token_1's revoked_at by 15 seconds (past the 10-second grace period)
    db = SessionLocal()
    try:
        hash_1 = hash_token(token_1)
        row_1 = db.query(RefreshToken).filter(RefreshToken.token == hash_1).first()
        assert row_1 is not None
        row_1.revoked_at = datetime.now(UTC) - timedelta(seconds=15)
        db.commit()
    finally:
        db.close()

    # Now replay token_1 (ancestor) after Redis restart -> PostgreSQL detects reuse and revokes family!
    resp_replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token_1})
    assert resp_replay.status_code == 401

    # Active token_3 must now be revoked
    resp_3 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_3})
    assert resp_3.status_code == 401


def test_admin_session_revocation_invalidates_family():
    """Verify admin individual session revocation correctly invalidates the entire token family."""
    ceo_login = login_as_ceo()
    ceo_token = ceo_login["access_token"]
    vp_login = login_as_vp()
    vp_user_id = decode_token(vp_login["access_token"])["user_id"]
    vp_refresh = vp_login["refresh_token"]

    # VP rotates token: A -> B
    resp_rot = client.post("/api/v1/auth/refresh", json={"refresh_token": vp_refresh})
    assert resp_rot.status_code == 200
    vp_token_b = resp_rot.json()["refresh_token"]

    # List VP sessions as CEO
    list_resp = client.get(
        f"/api/v1/admin/users/{vp_user_id}/sessions",
        headers=auth_header(ceo_token),
    )
    assert list_resp.status_code == 200
    sessions = list_resp.json()
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    # Revoke that session
    del_resp = client.delete(
        f"/api/v1/admin/users/{vp_user_id}/sessions/{session_id}",
        headers=auth_header(ceo_token),
    )
    assert del_resp.status_code == 200

    # VP's active token_b must now be revoked
    refresh_after = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": vp_token_b}
    )
    assert refresh_after.status_code == 401


def test_admin_deactivation_invalidates_family():
    """Verify admin deactivation invalidates active sessions and token families."""
    ceo_login = login_as_ceo()
    ceo_token = ceo_login["access_token"]

    # Register a new user to deactivate
    email = unique_email("deact_family")
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Deact User", "email": email, "password": "Password123!"},
    )
    assert reg_resp.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        target_user_id = user.id
        role = db.query(Role).filter(Role.name == "analyst").first()
        if not role:
            role = db.query(Role).first()
        if role and user.role_id is None:
            user.role_id = role.id
            db.commit()
    finally:
        db.close()

    # User logs in and gets tokens
    user_login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password123!"},
    )
    assert user_login.status_code == 200
    user_refresh = user_login.json()["refresh_token"]

    # Admin deactivates user
    deact_resp = client.patch(
        f"/api/v1/admin/users/{target_user_id}/deactivate",
        headers=auth_header(ceo_token),
    )
    assert deact_resp.status_code == 200

    # User refresh must be rejected with 401
    refresh_resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": user_refresh}
    )
    assert refresh_resp.status_code == 401


def test_admin_force_password_reset_invalidates_family():
    """Verify admin force password reset invalidates active sessions and token families."""
    ceo_login = login_as_ceo()
    ceo_token = ceo_login["access_token"]

    # Register a new user
    email = unique_email("reset_family")
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reset User",
            "email": email,
            "password": "Password123!",
        },
    )
    assert reg_resp.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        target_user_id = user.id

        role = db.query(Role).filter(Role.name == "analyst").first()
        if not role:
            role = db.query(Role).first()

        if role and user.role_id is None:
            user.role_id = role.id
            db.commit()
    finally:
        db.close()

    # User logs in and gets tokens
    user_login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password123!"},
    )
    assert user_login.status_code == 200
    user_refresh = user_login.json()["refresh_token"]

    # Admin forces password reset
    reset_resp = client.post(
        f"/api/v1/admin/users/{target_user_id}/force-reset-password",
        headers=auth_header(ceo_token),
        json={"new_password": "NewPassword456!"},
    )

    print("Force reset response:", reset_resp.status_code, reset_resp.json())
    assert reset_resp.status_code == 200

    # User's old refresh token must now be rejected
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": user_refresh},
    )
    assert refresh_resp.status_code == 401
