import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import redis
from fastapi.testclient import TestClient

from app.core import config as app_config
from app.core.redis_client import get_redis
from app.core.security import decode_token, hash_token
from app.database import SessionLocal, get_db_now
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
    get_password_reset_token,
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

    import app.services.auth_service as auth_mod

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
        "app.services.auth_service.get_db_now",
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


def test_password_reset_sets_revoked_at_and_avoids_false_reuse_alert():
    """Verify reset_password sets revoked_at and does not trigger false reuse alert on subsequent refresh."""
    email = unique_email("pwd_reset_revoked_at")
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Reset Revoked User",
            "email": email,
            "password": "Password123!",
        },
    )
    assert reg_resp.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        role = (
            db.query(Role).filter(Role.name == "analyst").first()
            or db.query(Role).first()
        )
        if role and user.role_id is None:
            user.role_id = role.id
            db.commit()
    finally:
        db.close()

    # User logs in and receives refresh token
    user_login = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "Password123!"},
    )
    assert user_login.status_code == 200
    user_refresh = user_login.json()["refresh_token"]

    # Request password reset
    req_resp = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
    )
    assert req_resp.status_code == 200
    reset_token = get_password_reset_token(email)

    # Perform password reset
    confirm_resp = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": reset_token,
            "new_password": "NewPassword123!",
        },
    )
    assert confirm_resp.status_code == 200

    # Verify that in DB, user's refresh token record has revoked_at set
    refresh_hash = hash_token(user_refresh)
    db = SessionLocal()
    try:
        row = db.query(RefreshToken).filter(RefreshToken.token == refresh_hash).first()
        assert row is not None
        assert row.is_revoked is True
        assert row.revoked_at is not None

        # Backdate revoked_at past grace period to test reuse classification
        row.revoked_at = datetime.now(UTC) - timedelta(seconds=15)
        db.commit()
    finally:
        db.close()

    # Attempt to refresh with the old token
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": user_refresh},
    )
    assert ref_resp.status_code == 401

    # Verify NO false reuse alert was logged for this family
    family_id = decode_token(user_refresh).get("family_id")
    db = SessionLocal()
    try:
        reuse_log = (
            db.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == TOKEN_REVOKED,
                AuthAuditLog.details.contains("Token reuse detected"),
            )
            .all()
        )
        if family_id:
            for entry in reuse_log:
                assert family_id not in entry.details
    finally:
        db.close()


def test_logged_out_token_refresh_does_not_trigger_false_reuse_alert():
    """Verify attempting to refresh a legitimately logged-out session returns 401 without false reuse alert."""
    login = login_as_ceo()
    refresh_token = login["refresh_token"]
    family_id = decode_token(refresh_token)["family_id"]

    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert logout_resp.status_code == 200

    # Backdate revoked_at past grace period
    token_h = hash_token(refresh_token)
    db = SessionLocal()
    try:
        row = db.query(RefreshToken).filter(RefreshToken.token == token_h).first()
        assert row is not None
        row.revoked_at = datetime.now(UTC) - timedelta(seconds=15)
        db.commit()
    finally:
        db.close()

    # Attempt refresh with logged-out token after grace period
    ref_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert ref_resp.status_code == 401

    # Verify no false reuse alert was created
    db = SessionLocal()
    try:
        reuse_logs = (
            db.query(AuthAuditLog)
            .filter(
                AuthAuditLog.event_type == TOKEN_REVOKED,
                AuthAuditLog.details.contains(family_id),
                AuthAuditLog.details.contains("Token reuse detected"),
            )
            .all()
        )
        assert len(reuse_logs) == 0
    finally:
        db.close()


def test_direct_service_calls_rotate_and_logout_family():
    """Verify rotate_refresh_token and logout_family work directly from auth_service."""
    from app.services.auth_service import logout_family, rotate_refresh_token

    login = login_as_ceo()
    token_1 = login["refresh_token"]

    db = SessionLocal()
    try:
        # Test rotate_refresh_token service function directly
        result = rotate_refresh_token(db, token_1)
        assert "access_token" in result
        assert "refresh_token" in result
        token_2 = result["refresh_token"]
        assert token_2 != token_1

        # Test logout_family service function directly
        token_2_hash = hash_token(token_2)
        row_2 = (
            db.query(RefreshToken).filter(RefreshToken.token == token_2_hash).first()
        )
        assert row_2 is not None
        assert row_2.is_revoked is False

        logout_family(db, row_2)

        # After logout_family, row_2 must be revoked with revoked_at set
        row_2_after = (
            db.query(RefreshToken).filter(RefreshToken.token == token_2_hash).first()
        )
        assert row_2_after is not None
        assert row_2_after.is_revoked is True
        assert row_2_after.revoked_at is not None
    finally:
        db.close()


def test_grace_period_config_parsing_and_fallback():
    """Verify parse_grace_period_seconds validates input and falls back safely to default 10s."""
    from app.core.config import parse_grace_period_seconds

    assert parse_grace_period_seconds("10") == 10
    assert parse_grace_period_seconds("0") == 0
    assert parse_grace_period_seconds("30") == 30
    # Negative values fall back to default
    assert parse_grace_period_seconds("-1") == 10
    assert parse_grace_period_seconds("-10") == 10
    # Non-numeric / invalid strings fall back to default
    assert parse_grace_period_seconds("invalid") == 10
    assert parse_grace_period_seconds("") == 10
    assert parse_grace_period_seconds("   ") == 10


def test_grace_period_boundary_within_and_exceeded():
    """Verify grace period window: replay just inside window preserves family; replay clearly outside window revokes family."""
    login = login_as_ceo()
    token_a = login["refresh_token"]

    # 1. Rotate A -> B
    resp_1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_1.status_code == 200
    token_b = resp_1.json()["refresh_token"]

    # Set token A revoked_at to just inside the grace window (e.g. 5 seconds ago) using the DB clock
    db = SessionLocal()
    try:
        db_now = get_db_now(db)
        hash_a = hash_token(token_a)
        row_a = db.query(RefreshToken).filter(RefreshToken.token == hash_a).first()
        assert row_a is not None
        row_a.revoked_at = db_now - timedelta(
            seconds=app_config.REFRESH_TOKEN_GRACE_PERIOD_SECONDS - 5
        )
        db.commit()
    finally:
        db.close()

    # Replay token A within grace window: gets 401, but family must NOT be revoked
    resp_replay = client.post("/api/v1/auth/refresh", json={"refresh_token": token_a})
    assert resp_replay.status_code == 401

    # Token B must still be valid
    resp_b_check = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_b_check.status_code == 200
    token_c = resp_b_check.json()["refresh_token"]

    # Now set token B revoked_at to clearly outside the grace window (e.g. 15 seconds ago) using the DB clock
    db = SessionLocal()
    try:
        db_now = get_db_now(db)
        hash_b = hash_token(token_b)
        row_b = db.query(RefreshToken).filter(RefreshToken.token == hash_b).first()
        assert row_b is not None
        row_b.revoked_at = db_now - timedelta(
            seconds=app_config.REFRESH_TOKEN_GRACE_PERIOD_SECONDS + 5
        )
        db.commit()
    finally:
        db.close()

    # Replay token B after grace period exceeded: gets 401 AND revokes the family
    resp_replay_b = client.post("/api/v1/auth/refresh", json={"refresh_token": token_b})
    assert resp_replay_b.status_code == 401

    # Active Token C must now be revoked
    resp_c_check = client.post("/api/v1/auth/refresh", json={"refresh_token": token_c})
    assert resp_c_check.status_code == 401


def test_redis_active_token_cache_failure_does_not_break_rotation():
    """Verify that Redis failure during set_family_active_token does not prevent successful rotation."""
    login = login_as_ceo()
    token = login["refresh_token"]

    with patch("app.services.auth_service.set_family_active_token") as mock_set_active:
        mock_set_active.return_value = False

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        new_token = data["refresh_token"]
        assert new_token != token

        # Verify next rotation succeeds from DB
        next_resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": new_token}
        )
        assert next_resp.status_code == 200


def test_is_sha256_hex_strict_validation():
    """Verify is_sha256_hex strictly validates 64 hexadecimal characters and rejects non-hex."""
    # Valid 64-char hex digests
    valid_lower = hashlib.sha256(b"test").hexdigest()
    assert is_sha256_hex(valid_lower) is True
    assert is_sha256_hex(valid_lower.upper()) is True

    # Rejects invalid lengths
    assert is_sha256_hex("a" * 63) is False
    assert is_sha256_hex("a" * 65) is False
    assert is_sha256_hex("") is False

    # Rejects leading/trailing sign or whitespace that int(x, 16) would otherwise accept
    assert is_sha256_hex("+" + "a" * 63) is False
    assert is_sha256_hex("-" + "a" * 63) is False
    assert is_sha256_hex(" " + "a" * 63) is False
    assert is_sha256_hex("a" * 63 + " ") is False

    # Rejects non-hex characters
    assert is_sha256_hex("g" * 64) is False
    assert is_sha256_hex("z" * 64) is False
    assert is_sha256_hex("@" * 64) is False

    # Rejects JWTs containing dots
    jwt_mock = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0." + "a" * 40
    assert is_sha256_hex(jwt_mock) is False


def test_migration_mixed_state_and_preservation():
    """Verify migration correctly handles mixed token states without double-hashing or overwriting."""
    from app.core.security import create_refresh_token

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        raw_jwt_1 = create_refresh_token(
            {"sub": user.email, "user_id": user.id, "nonce": "1"}
        )
        raw_jwt_2 = create_refresh_token(
            {"sub": user.email, "user_id": user.id, "nonce": "2"}
        )
        raw_jwt_3 = create_refresh_token(
            {"sub": user.email, "user_id": user.id, "nonce": "3"}
        )

        existing_hash_1 = hashlib.sha256(b"already_hashed_token_1").hexdigest()
        existing_hash_2 = hashlib.sha256(b"already_hashed_token_2").hexdigest()
        existing_hash_3 = hashlib.sha256(b"already_hashed_token_3").hexdigest()

        past_revocation = datetime.now(UTC) - timedelta(days=2)

        # Row 1: Raw JWT, null family, active
        r1 = RefreshToken(
            user_id=user.id,
            token=raw_jwt_1,
            is_revoked=False,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        # Row 2: Already-hashed, existing family, active
        r2 = RefreshToken(
            user_id=user.id,
            token=existing_hash_1,
            is_revoked=False,
            family_id="fam-preserve-1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        # Row 3: Already-hashed, null family, active
        r3 = RefreshToken(
            user_id=user.id,
            token=existing_hash_2,
            is_revoked=False,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        # Row 4: Raw JWT, existing family, active
        r4 = RefreshToken(
            user_id=user.id,
            token=raw_jwt_2,
            is_revoked=False,
            family_id="fam-preserve-2",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        # Row 5: Raw JWT, null family, revoked without revoked_at
        r5 = RefreshToken(
            user_id=user.id,
            token=raw_jwt_3,
            is_revoked=True,
            revoked_at=None,
            family_id=None,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        # Row 6: Already-hashed, existing family, revoked with existing revoked_at
        r6 = RefreshToken(
            user_id=user.id,
            token=existing_hash_3,
            is_revoked=True,
            revoked_at=past_revocation,
            family_id="fam-preserve-3",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        db.add_all([r1, r2, r3, r4, r5, r6])
        db.commit()
        ids = [r1.id, r2.id, r3.id, r4.id, r5.id, r6.id]
    finally:
        db.close()

    # Run migration with a small batch size of 2 to exercise keyset batching across chunks
    summary = run_refresh_migration(batch_size=2)
    assert summary["tokens_hashed"] == 3  # r1, r4, r5
    assert summary["families_backfilled"] == 3  # r1, r3, r5

    db = SessionLocal()
    try:
        rows = {
            r.id: r
            for r in db.query(RefreshToken).filter(RefreshToken.id.in_(ids)).all()
        }

        # Row 1: hashed, fresh family
        assert (
            rows[ids[0]].token == hashlib.sha256(raw_jwt_1.encode("utf-8")).hexdigest()
        )
        assert rows[ids[0]].family_id is not None
        assert is_sha256_hex(rows[ids[0]].token)

        # Row 2: preserved hash (NOT double-hashed), preserved family
        assert rows[ids[1]].token == existing_hash_1
        assert rows[ids[1]].family_id == "fam-preserve-1"

        # Row 3: preserved hash, fresh family
        assert rows[ids[2]].token == existing_hash_2
        assert rows[ids[2]].family_id is not None

        # Row 4: hashed, preserved family
        assert (
            rows[ids[3]].token == hashlib.sha256(raw_jwt_2.encode("utf-8")).hexdigest()
        )
        assert rows[ids[3]].family_id == "fam-preserve-2"

        # Row 5: hashed, fresh family, revoked_at backfilled
        assert (
            rows[ids[4]].token == hashlib.sha256(raw_jwt_3.encode("utf-8")).hexdigest()
        )
        assert rows[ids[4]].family_id is not None
        assert rows[ids[4]].revoked_at is not None

        # Row 6: preserved hash, preserved family, preserved revoked_at
        assert rows[ids[5]].token == existing_hash_3
        assert rows[ids[5]].family_id == "fam-preserve-3"
    finally:
        db.close()


def test_migration_second_run_idempotency_zero_updates():
    """Verify that running migration when all rows are already migrated produces exactly zero updates."""
    summary_2 = run_refresh_migration(batch_size=2)
    assert summary_2["tokens_hashed"] == 0
    assert summary_2["families_backfilled"] == 0
    assert summary_2["columns_added"] == 0
    assert summary_2["index_created"] == 0


def test_migration_large_batch_processing():
    """Verify bounded keyset batching across many rows with multiple batch chunks."""
    from app.core.security import create_refresh_token

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        legacy_rows = []
        for i in range(25):
            raw_jwt = create_refresh_token(
                {"sub": user.email, "user_id": user.id, "nonce": f"batch_{i}"}
            )
            legacy_rows.append(
                RefreshToken(
                    user_id=user.id,
                    token=raw_jwt,
                    is_revoked=False,
                    family_id=None,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
            )
        db.add_all(legacy_rows)
        db.commit()
        batch_ids = [r.id for r in legacy_rows]
    finally:
        db.close()

    # Process in batches of 7 (requiring 4 batch queries)
    summary = run_refresh_migration(batch_size=7)
    assert summary["tokens_hashed"] >= 25
    assert summary["families_backfilled"] >= 25

    db = SessionLocal()
    try:
        migrated_rows = (
            db.query(RefreshToken).filter(RefreshToken.id.in_(batch_ids)).all()
        )
        assert len(migrated_rows) == 25
        for r in migrated_rows:
            assert is_sha256_hex(r.token)
            assert r.family_id is not None
            assert "." not in r.token
    finally:
        db.close()

    # Rerun immediately: 0 tokens hashed
    summary_rerun = run_refresh_migration(batch_size=7)
    assert summary_rerun["tokens_hashed"] == 0
    assert summary_rerun["families_backfilled"] == 0


def test_migration_64_char_non_hex_token_with_existing_family_id():
    """Verify migration identifies and hashes 64-char non-hex tokens even when family_id is already present, while leaving valid SHA-256 tokens untouched."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        invalid_64_a = "g" * 64
        invalid_64_b = "a" * 63 + "z"
        valid_sha256 = hashlib.sha256(b"already_valid_untouched").hexdigest()

        r1 = RefreshToken(
            user_id=user.id,
            token=invalid_64_a,
            is_revoked=False,
            family_id="fam-existing-64nonhex-1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        r2 = RefreshToken(
            user_id=user.id,
            token=invalid_64_b,
            is_revoked=False,
            family_id="fam-existing-64nonhex-2",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        r3 = RefreshToken(
            user_id=user.id,
            token=valid_sha256,
            is_revoked=False,
            family_id="fam-existing-valid-preserved",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add_all([r1, r2, r3])
        db.commit()
        ids = [r1.id, r2.id, r3.id]
    finally:
        db.close()

    # Run migration with batch_size=1 to verify keyset pagination across single-item batches
    summary = run_refresh_migration(batch_size=1)
    assert summary["tokens_hashed"] >= 2

    db = SessionLocal()
    try:
        rows = {
            r.id: r
            for r in db.query(RefreshToken).filter(RefreshToken.id.in_(ids)).all()
        }

        # Row 1: 64-char non-hex token was hashed, family_id preserved
        assert (
            rows[ids[0]].token
            == hashlib.sha256(invalid_64_a.encode("utf-8")).hexdigest()
        )
        assert rows[ids[0]].family_id == "fam-existing-64nonhex-1"
        assert is_sha256_hex(rows[ids[0]].token)

        # Row 2: 64-char non-hex token was hashed, family_id preserved
        assert (
            rows[ids[1]].token
            == hashlib.sha256(invalid_64_b.encode("utf-8")).hexdigest()
        )
        assert rows[ids[1]].family_id == "fam-existing-64nonhex-2"
        assert is_sha256_hex(rows[ids[1]].token)

        # Row 3: valid SHA-256 token remains strictly UNTOUCHED
        assert rows[ids[2]].token == valid_sha256
        assert rows[ids[2]].family_id == "fam-existing-valid-preserved"
    finally:
        db.close()

    # Second run produces zero updates
    summary_rerun = run_refresh_migration(batch_size=1)
    assert summary_rerun["tokens_hashed"] == 0
    assert summary_rerun["families_backfilled"] == 0
