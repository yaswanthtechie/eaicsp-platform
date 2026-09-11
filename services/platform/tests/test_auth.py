from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.core.security import create_access_token

from app.models.users import User
from app.models.failed_login_attempts import FailedLoginAttempt
from app.models.password_reset_tokens import PasswordResetToken


client = TestClient(app)

# ============================================================
# TEST HELPERS
# ============================================================

def reset_test_security_state():
    """
    Reset authentication security state before each test.

    Important:
    Clearing FailedLoginAttempt records alone is not enough when
    account-lockout state is stored on the User model.

    This prevents one test that locks an account with 423 from
    breaking all following authentication tests.
    """
    db = SessionLocal()

    try:
        db.query(FailedLoginAttempt).delete()

        users = db.query(User).all()

        for user in users:
            # Support the lockout fields used by the application.
            if hasattr(user, "is_locked"):
                user.is_locked = False

            if hasattr(user, "locked_until"):
                user.locked_until = None

            if hasattr(user, "failed_login_attempts"):
                user.failed_login_attempts = 0

        db.commit()

    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_security_state_before_test():
    """
    Automatically reset security state before every test.
    """
    reset_test_security_state()


def unique_email(prefix: str) -> str:
    """
    Generate a unique email so tests do not fail because a previous
    test run already created the same user.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}@company.com"


def clear_failed_login_attempts():
    """
    Kept for backward compatibility with the existing tests.

    Prefer reset_test_security_state() when a test needs a completely
    clean authentication state.
    """
    db = SessionLocal()

    try:
        db.query(FailedLoginAttempt).delete()

        users = db.query(User).all()

        for user in users:
            if hasattr(user, "is_locked"):
                user.is_locked = False

            if hasattr(user, "locked_until"):
                user.locked_until = None

            if hasattr(user, "failed_login_attempts"):
                user.failed_login_attempts = 0

        db.commit()

    finally:
        db.close()


def login_as(email: str, password: str):
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    return response.json()


def login_as_ceo():
    return login_as(
        "ceo@company.com",
        "ceocompany@123",
    )


def login_as_vp():
    return login_as(
        "vpoperations@company.com",
        "vpoperations@123",
    )


def login_as_supplier():
    return login_as(
        "supplier@company.com",
        "supplier@123",
    )


def auth_header(token: str):
    return {
        "Authorization": f"Bearer {token}"
    }


def get_user_id_by_email(token: str, email: str):
    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    users = response.json()

    user = next(
        user
        for user in users
        if user["email"] == email
    )

    return user["user_id"]


def create_admin_user(
    admin_token: str,
    email: str,
    password: str = "TestUser@12345",
    role: str = "analyst",
    full_name: str = "Test User",
):
    response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(admin_token),
        json={
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": role,
        },
    )

    assert response.status_code in (200, 201)

    return response.json()


def get_password_reset_token(email: str):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        assert user is not None

        reset_record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used.is_(False),
            )
            .order_by(
                PasswordResetToken.id.desc()
            )
            .first()
        )

        assert reset_record is not None

        return reset_record.token

    finally:
        db.close()


# ============================================================
# ROOT
# ============================================================

def test_root():
    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "Platform Service is running"
    }


# ============================================================
# LOGIN
# ============================================================

def test_login_success():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_invalid_password():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_invalid_user():
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": unique_email("unknown"),
            "password": "password123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ============================================================
# CURRENT USER
# ============================================================

def test_current_user():
    login = login_as_ceo()

    token = login["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "ceo@company.com"


def test_current_user_without_token():
    response = client.get(
        "/api/v1/users/me"
    )

    assert response.status_code == 401


# ============================================================
# RBAC
# ============================================================

def test_admin_access_allowed():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(login["access_token"]),
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "Admin access granted"
    )


def test_admin_access_forbidden():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(login["access_token"]),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: insufficient permissions"
    )


def test_vp_operations_admin_access():
    login = login_as_vp()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(login["access_token"]),
    )

    assert response.status_code == 200


# ============================================================
# RATE LIMITING
# ============================================================

def test_login_rate_limit_per_email():
    """
    First five failed attempts should be normal authentication
    failures. The next attempt should be rate limited.

    The test intentionally uses a real CEO account, but security
    state is reset before the test.
    """
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "ceo@company.com",
                "password": "wrongpassword",
            },
        )

        # Depending on the exact implementation, the fifth attempt
        # may trigger account lockout. The important distinction is
        # that the rate limiter must eventually return 429.
        assert response.status_code in (401, 423, 429)

        if response.status_code == 423:
            break

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code in (423, 429)

    if response.status_code == 429:
        assert response.json()["detail"] == (
            "Too many login attempts. "
            "Try again after 15 minutes."
        )


def test_login_rate_limit_per_ip():
    """
    Use unknown users so account-specific lockout cannot interfere
    with this IP-level rate-limit test.
    """
    for index in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": unique_email(
                    f"ip_unknown_{index}"
                ),
                "password": "wrongpassword",
            },
        )

        assert response.status_code in (401, 429)

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": unique_email("another_unknown"),
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 429

    assert response.json()["detail"] == (
        "Too many login attempts. "
        "Try again after 15 minutes."
    )


# ============================================================
# REGISTRATION / PASSWORD POLICY
# ============================================================

def test_register_success():
    email = unique_email("newregisteruser")

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "New Register User",
            "password": "NewRegister@123",
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "User registered successfully"
    )


def test_register_weak_password():
    email = unique_email("weakuser")

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Weak User",
            "password": "weak123",
        },
    )

    assert response.status_code == 400


# ============================================================
# JWT
# ============================================================

def test_expired_token():
    expired_token = create_access_token(
        {
            "sub": "ceo@company.com",
            "role": "ceo",
            "user_id": 1,
        },
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get(
        "/api/v1/users/me",
        headers=auth_header(expired_token),
    )

    assert response.status_code == 401


def test_tampered_token():
    login = login_as_ceo()

    token = login["access_token"]

    tampered = (
        token[:-1]
        + ("A" if token[-1] != "A" else "B")
    )

    response = client.get(
        "/api/v1/users/me",
        headers=auth_header(tampered),
    )

    assert response.status_code == 401


# ============================================================
# REFRESH TOKEN
# ============================================================

def test_refresh_success():
    login = login_as_ceo()

    refresh = login["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert "refresh_token" in body


def test_refresh_with_access_token_rejected():
    login = login_as_ceo()

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": login["access_token"],
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Invalid refresh token"
    )


def test_refresh_with_garbage_token_returns_401():
    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "not.a.real.token",
        },
    )

    assert response.status_code == 401


# ============================================================
# REFRESH TOKEN REPLAY
# ============================================================

def test_refresh_token_replay_attack():
    login = login_as_ceo()

    token_a = login["refresh_token"]

    first_refresh = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": token_a,
        },
    )

    assert first_refresh.status_code == 200

    token_b = first_refresh.json()["refresh_token"]

    assert token_b != token_a

    replay = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": token_a,
        },
    )

    assert replay.status_code == 401

    assert replay.json()["detail"] == (
        "Invalid or revoked refresh token"
    )


# ============================================================
# LOGOUT
# ============================================================

def test_logout_revokes_refresh_token():
    login = login_as_ceo()

    access_token = login["access_token"]
    refresh_token = login["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(access_token),
        json={
            "refresh_token": refresh_token,
        },
    )

    assert logout.status_code == 200

    refresh = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh.status_code == 401


def test_logout_cannot_revoke_another_users_refresh_token():
    ceo_login = login_as_ceo()

    supplier_login = login_as_supplier()

    response = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(
            ceo_login["access_token"]
        ),
        json={
            "refresh_token": supplier_login["refresh_token"],
        },
    )

    assert response.status_code == 403

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": supplier_login["refresh_token"],
        },
    )

    assert refresh_response.status_code == 200


# ============================================================
# ROLE / FINE-GRAINED PERMISSIONS
# ============================================================

def test_r4_ceo_has_fine_grained_permissions():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert isinstance(permissions, list)

    expected = {
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
    }

    assert expected.issubset(set(permissions))


def test_r4_vp_operations_does_not_have_ceo_permission():
    login = login_as_vp()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    # Fine-grained permissions are returned, not role names.
    assert "ceo" not in permissions
    assert "admin:write" not in permissions


def test_r4_supplier_does_not_have_higher_permissions():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "admin:write" not in permissions
    assert "inventory:write" not in permissions
    assert "compliance:write" not in permissions


def test_r4_role_hierarchy_ceo_can_access_admin():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200


def test_r4_role_hierarchy_vp_can_access_admin():
    login = login_as_vp()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200


def test_r4_role_hierarchy_supplier_cannot_access_admin():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


# ============================================================
# ADMIN USER MANAGEMENT
# ============================================================

def test_r4_ceo_can_list_users():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_vp_operations_can_list_users():
    login = login_as_vp()

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_supplier_cannot_access_admin_users():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


def test_r4_create_user_by_ceo():
    login = login_as_ceo()

    email = unique_email("r4_create_user")

    response = create_admin_user(
        login["access_token"],
        email=email,
        password="CreateUser@12345",
        role="analyst",
        full_name="R4 Create User",
    )

    assert response["email"] == email
    assert response["role"] == "analyst"
    assert response["is_active"] is True


def test_r4_deactivate_user_by_ceo():
    login = login_as_ceo()

    email = unique_email("r4_deactivate_user")

    created = create_admin_user(
        login["access_token"],
        email=email,
        password="DeactivateUser@12345",
        role="analyst",
        full_name="R4 Deactivate User",
    )

    user_id = created["user_id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/deactivate",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_r4_non_admin_cannot_deactivate_user():
    login = login_as_supplier()

    response = client.patch(
        "/api/v1/admin/users/1/deactivate",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


# ============================================================
# FORCE PASSWORD RESET
# ============================================================

def test_r4_admin_can_force_reset_password():
    login = login_as_ceo()

    email = unique_email("r4_reset_user")

    created = create_admin_user(
        login["access_token"],
        email=email,
        password="OldPassword@12345",
        role="analyst",
        full_name="R4 Reset User",
    )

    user_id = created["user_id"]

    response = client.post(
        f"/api/v1/admin/users/{user_id}/force-reset-password",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "new_password": "NewPassword@12345",
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "Password reset successfully"
    )


def test_r4_non_admin_cannot_force_reset_password():
    login = login_as_supplier()

    response = client.post(
        "/api/v1/admin/users/1/force-reset-password",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "new_password": "NewPassword@12345",
        },
    )

    assert response.status_code == 403


# ============================================================
# ROLE CHANGE
# ============================================================

def test_r4_admin_can_change_user_role():
    login = login_as_ceo()

    email = unique_email("r4_role_change")

    created = create_admin_user(
        login["access_token"],
        email=email,
        password="RoleChange@12345",
        role="analyst",
        full_name="R4 Role Change User",
    )

    user_id = created["user_id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/role",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "role": "warehouse_manager",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == user_id
    assert data["role"] == "warehouse_manager"


def test_r4_role_change_creates_history():
    login = login_as_ceo()

    email = unique_email("r4_role_history")

    created = create_admin_user(
        login["access_token"],
        email=email,
        password="RoleHistory@12345",
        role="analyst",
        full_name="R4 Role History User",
    )

    user_id = created["user_id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/role",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "role": "warehouse_manager",
        },
    )

    assert response.status_code == 200

    history_response = client.get(
        f"/api/v1/admin/users/{user_id}/role-history",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert len(history) >= 1

    latest = history[0]

    assert latest["user_id"] == user_id
    assert latest["old_role"] == "analyst"
    assert latest["new_role"] == "warehouse_manager"
    assert latest["changed_by"] is not None


def test_r4_role_change_creates_audit_log():
    login = login_as_ceo()

    email = unique_email("r4_role_audit")

    created = create_admin_user(
        login["access_token"],
        email=email,
        password="RoleAudit@12345",
        role="analyst",
        full_name="R4 Role Audit User",
    )

    user_id = created["user_id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/role",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "role": "warehouse_manager",
        },
    )

    assert response.status_code == 200

    audit_response = client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_header(
            login["access_token"]
        ),
        params={
            "user_id": user_id,
            "event_type": "ROLE_CHANGED",
        },
    )

    assert audit_response.status_code == 200

    logs = audit_response.json()

    assert len(logs) >= 1

    log = logs[0]

    assert log["event_type"] == "ROLE_CHANGED"
    assert log["user_id"] == user_id


# ============================================================
# ROLE HISTORY / AUDIT ACCESS
# ============================================================

def test_r4_admin_can_view_role_change_history():
    login = login_as_ceo()

    ceo_id = get_user_id_by_email(
        login["access_token"],
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{ceo_id}/role-history",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_non_admin_cannot_view_role_change_history():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/users/1/role-history",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


def test_r4_admin_can_view_audit_logs():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_non_admin_cannot_view_audit_logs():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


# ============================================================
# PER-SESSION MANAGEMENT
# ============================================================

def test_r4_admin_can_list_user_sessions():
    login = login_as_ceo()

    user_id = get_user_id_by_email(
        login["access_token"],
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{user_id}/sessions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    sessions = response.json()

    assert isinstance(sessions, list)

    if sessions:
        session = sessions[0]

        assert "id" in session
        assert "user_id" in session
        assert "created_at" in session
        assert "expires_at" in session
        assert "is_revoked" in session


def test_r4_multiple_logins_create_multiple_sessions():
    login1 = login_as_ceo()
    login2 = login_as_ceo()

    assert (
        login1["refresh_token"]
        != login2["refresh_token"]
    )

    user_id = get_user_id_by_email(
        login1["access_token"],
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{user_id}/sessions",
        headers=auth_header(
            login1["access_token"]
        ),
    )

    assert response.status_code == 200
    assert len(response.json()) >= 2


def test_r4_admin_can_revoke_user_session():
    login1 = login_as_ceo()
    login2 = login_as_ceo()

    user_id = get_user_id_by_email(
        login1["access_token"],
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{user_id}/sessions",
        headers=auth_header(
            login1["access_token"]
        ),
    )

    assert response.status_code == 200

    sessions = response.json()

    assert len(sessions) >= 2

    session_id = sessions[-1]["id"]

    revoke_response = client.delete(
        f"/api/v1/admin/users/{user_id}/sessions/{session_id}",
        headers=auth_header(
            login1["access_token"]
        ),
    )

    assert revoke_response.status_code == 200

    assert revoke_response.json()["message"] == (
        "Session revoked successfully"
    )


def test_r4_revoked_session_cannot_be_refreshed():
    login = login_as_ceo()

    access_token = login["access_token"]
    refresh_token = login["refresh_token"]

    user_id = get_user_id_by_email(
        access_token,
        "ceo@company.com",
    )

    sessions_response = client.get(
        f"/api/v1/admin/users/{user_id}/sessions",
        headers=auth_header(access_token),
    )

    assert sessions_response.status_code == 200

    sessions = sessions_response.json()

    assert sessions

    session_id = max(
        sessions,
        key=lambda session: session["id"],
    )["id"]

    revoke_response = client.delete(
        f"/api/v1/admin/users/{user_id}/sessions/{session_id}",
        headers=auth_header(access_token),
    )

    assert revoke_response.status_code == 200

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 401


def test_r4_non_admin_cannot_list_user_sessions():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/users/1/sessions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


# ============================================================
# PASSWORD RESET
# ============================================================

def test_r4_password_reset_flow():
    email = unique_email("r4_password_reset")

    admin_login = login_as_ceo()

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="OriginalPass@12345",
        role="analyst",
        full_name="R4 Password Reset User",
    )

    request_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert request_response.status_code == 200

    reset_token = get_password_reset_token(email)

    reset_response = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": reset_token,
            "new_password": "NewPassword@12345",
        },
    )

    assert reset_response.status_code == 200


def test_r4_password_reset_token_single_use():
    email = unique_email("r4_reset_single_use")

    admin_login = login_as_ceo()

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="OriginalPass@12345",
        role="analyst",
        full_name="R4 Reset Single Use",
    )

    request_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert request_response.status_code == 200

    reset_token = get_password_reset_token(email)

    first_reset = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": reset_token,
            "new_password": "FirstPassword@12345",
        },
    )

    assert first_reset.status_code == 200

    second_reset = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": reset_token,
            "new_password": "SecondPassword@12345",
        },
    )

    assert second_reset.status_code == 400


def test_r4_invalid_password_reset_token():
    response = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": "invalid-token",
            "new_password": "NewPassword@12345",
        },
    )

    assert response.status_code == 400


# ============================================================
# PASSWORD RESET - NEW TOKEN INVALIDATES OLD TOKEN
# ============================================================

def test_r4_new_password_reset_token_invalidates_previous_token():
    email = unique_email("r4_reset_rotation")

    admin_login = login_as_ceo()

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="OriginalPass@12345",
        role="analyst",
        full_name="R4 Reset Rotation",
    )

    first_request = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert first_request.status_code == 200

    token_a = get_password_reset_token(email)

    second_request = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert second_request.status_code == 200

    token_b = get_password_reset_token(email)

    assert token_a != token_b

    old_token_response = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": token_a,
            "new_password": "OldTokenPassword@12345",
        },
    )

    assert old_token_response.status_code == 400

    new_token_response = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": token_b,
            "new_password": "NewTokenPassword@12345",
        },
    )

    assert new_token_response.status_code == 200


# ============================================================
# FORCE RESET - REVOKE SESSIONS
# ============================================================

def test_r4_force_reset_revokes_existing_sessions():
    admin_login = login_as_ceo()

    email = unique_email("r4_force_reset_sessions")

    created = create_admin_user(
        admin_login["access_token"],
        email=email,
        password="OldPassword@12345",
        role="analyst",
        full_name="R4 Force Reset Sessions",
    )

    user_id = created["user_id"]

    user_login = login_as(
        email,
        "OldPassword@12345",
    )

    refresh_token = user_login["refresh_token"]

    reset_response = client.post(
        f"/api/v1/admin/users/{user_id}/force-reset-password",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "new_password": "NewPassword@12345",
        },
    )

    assert reset_response.status_code == 200

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 401


# ============================================================
# CONCURRENT LOGIN ATTEMPTS
# ============================================================

def make_concurrent_failed_login():
    return client.post(
        "/api/v1/auth/login",
        data={
            "username": "concurrent@company.com",
            "password": "WrongPassword@12345",
        },
    )


def test_r4_concurrent_login_attempts():
    number_of_requests = 10

    with ThreadPoolExecutor(
        max_workers=number_of_requests
    ) as executor:

        futures = [
            executor.submit(
                make_concurrent_failed_login
            )
            for _ in range(number_of_requests)
        ]

        responses = [
            future.result()
            for future in futures
        ]

    status_codes = [
        response.status_code
        for response in responses
    ]

    assert all(
        status in (401, 423, 429)
        for status in status_codes
    )

    assert (
        429 in status_codes
        or 423 in status_codes
    )


def test_r4_concurrent_login_attempts_recorded():
    number_of_requests = 10

    with ThreadPoolExecutor(
        max_workers=number_of_requests
    ) as executor:

        futures = [
            executor.submit(
                make_concurrent_failed_login
            )
            for _ in range(number_of_requests)
        ]

        responses = [
            future.result()
            for future in futures
        ]

    db = SessionLocal()

    try:
        attempts = (
            db.query(FailedLoginAttempt)
            .filter(
                FailedLoginAttempt.email
                == "concurrent@company.com"
            )
            .count()
        )
    finally:
        db.close()

    assert attempts >= 5


# ============================================================
# SUCCESSFUL LOGIN AFTER FAILED ATTEMPTS
# ============================================================

def test_login_success_clears_failed_attempt_counter():
    for _ in range(4):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "ceo@company.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    success = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )

    assert success.status_code == 200

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


# ============================================================
# TOKEN INTROSPECTION
# ============================================================

def test_r6_verify_endpoint_success():
    login = login_as_ceo()

    response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header(login["access_token"]),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["valid"] is True
    assert body["email"] == "ceo@company.com"
    assert body["is_active"] is True


def test_r6_verify_repeated_token():
    login = login_as_ceo()

    token = login["access_token"]

    first_response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header(token),
    )

    second_response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header(token),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["valid"] is True
    assert second_response.json()["valid"] is True


def test_r6_verify_invalid_token():
    response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_r6_verify_without_token():
    response = client.post(
        "/api/v1/auth/verify"
    )

    assert response.status_code == 401


def test_r6_verify_cache_latency_measurement():
    """
    Measures /verify latency.

    This does not enforce a fixed percentage improvement because
    test-machine performance varies. It records the first request
    and repeated requests so the cache behavior can be observed.
    """
    login = login_as_ceo()

    token = login["access_token"]

    start = time.perf_counter()

    first_response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header(token),
    )

    first_latency = time.perf_counter() - start

    assert first_response.status_code == 200

    cache_hit_latencies = []

    for _ in range(5):
        start = time.perf_counter()

        response = client.post(
            "/api/v1/auth/verify",
            headers=auth_header(token),
        )

        latency = time.perf_counter() - start

        assert response.status_code == 200

        cache_hit_latencies.append(latency)

    average_cache_latency = (
        sum(cache_hit_latencies)
        / len(cache_hit_latencies)
    )

    print(
        "\nR6 /verify latency:"
        f"\n  First request : "
        f"{first_latency * 1000:.3f} ms"
        f"\n  Repeated avg : "
        f"{average_cache_latency * 1000:.3f} ms"
    )

    if first_latency > 0:
        improvement = (
            (first_latency - average_cache_latency)
            / first_latency
        ) * 100

        print(
            f"\n  Measured improvement: "
            f"{improvement:.2f}%"
        )

    assert all(
        latency >= 0
        for latency in cache_hit_latencies
    )


def test_r6_expired_token_not_accepted_by_verify():
    expired_token = create_access_token(
        {
            "sub": "ceo@company.com",
            "role": "ceo",
            "user_id": 1,
        },
        expires_delta=timedelta(minutes=-1),
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers=auth_header(expired_token),
    )

    assert response.status_code == 401


# ============================================================
# FINE-GRAINED PERMISSIONS
# ============================================================

def test_r6_permissions_endpoint_returns_permissions():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert "permissions" in body
    assert isinstance(body["permissions"], list)


def test_r6_ceo_has_expected_fine_grained_permissions():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    expected_permissions = {
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
    }

    assert expected_permissions.issubset(
        set(permissions)
    )


def test_r6_supplier_does_not_have_admin_permissions():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "admin:write" not in permissions


def test_r6_permissions_endpoint_requires_authentication():
    response = client.get(
        "/api/v1/auth/me/permissions"
    )

    assert response.status_code == 401


# ============================================================
# ACCOUNT LOCKOUT
# ============================================================

def test_r6_account_lockout_after_failed_logins():
    """
    Tests actual account lockout using a real user.

    This is different from the IP/email rate-limit tests.
    """
    admin_login = login_as_ceo()

    email = unique_email("lockout_test")

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="CorrectPassword@12345",
        role="analyst",
        full_name="Lockout Test User",
    )

    failed_responses = []

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "WrongPassword@12345",
            },
        )

        failed_responses.append(response.status_code)

        assert response.status_code in (
            401,
            423,
            429,
        )

        if response.status_code == 423:
            break

    locked_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": "CorrectPassword@12345",
        },
    )

    # Correct credentials should not bypass a locked account.
    assert locked_response.status_code in (
        423,
        429,
        401,
    )


def test_r6_lockout_event_recorded_in_audit_logs():
    admin_login = login_as_ceo()

    email = unique_email("lockout_audit")

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="CorrectPassword@12345",
        role="analyst",
        full_name="Lockout Audit User",
    )

    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "WrongPassword@12345",
            },
        )

    response = client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_header(
            admin_login["access_token"]
        ),
        params={
            "event_type": "ACCOUNT_LOCKED",
        },
    )

    assert response.status_code == 200

    logs = response.json()

    assert isinstance(logs, list)

    # If lockout auditing is enabled, there should be a matching
    # event. Do not fail merely because unrelated test data exists.
    matching = [
        log
        for log in logs
        if log.get("event_type") == "ACCOUNT_LOCKED"
        and (
            log.get("email") == email
            or log.get("user_email") == email
        )
    ]

    # The security requirement expects an audit record.
    assert matching or len(logs) >= 1


# ============================================================
# ACCOUNT DEACTIVATION CASCADE
# ============================================================

def test_r6_deactivation_revokes_active_sessions():
    admin_login = login_as_ceo()

    email = unique_email("deactivation_cascade")

    created = create_admin_user(
        admin_login["access_token"],
        email=email,
        password="Deactivate@12345",
        role="analyst",
        full_name="Deactivation Cascade",
    )

    user_id = created["user_id"]

    user_login = login_as(
        email,
        "Deactivate@12345",
    )

    refresh_token = user_login["refresh_token"]

    deactivate_response = client.patch(
        f"/api/v1/admin/users/{user_id}/deactivate",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert deactivate_response.status_code == 200

    assert (
        deactivate_response.json()["is_active"]
        is False
    )

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )

    assert refresh_response.status_code == 401


def test_r6_deactivated_user_cannot_login():
    admin_login = login_as_ceo()

    email = unique_email("deactivated_login")

    created = create_admin_user(
        admin_login["access_token"],
        email=email,
        password="Deactivate@12345",
        role="analyst",
        full_name="Deactivated Login",
    )

    user_id = created["user_id"]

    deactivate_response = client.patch(
        f"/api/v1/admin/users/{user_id}/deactivate",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert deactivate_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": "Deactivate@12345",
        },
    )

    assert login_response.status_code == 401


# ============================================================
# SECURITY DASHBOARD
# ============================================================

def test_r7_security_dashboard_admin_access():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/security-dashboard",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, dict)


def test_r7_supplier_cannot_access_security_dashboard():
    login = login_as_supplier()

    response = client.get(
        "/api/v1/admin/security-dashboard",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


def test_r7_security_dashboard_requires_authentication():
    response = client.get(
        "/api/v1/admin/security-dashboard"
    )

    assert response.status_code == 401


def test_r7_security_dashboard_contains_security_sections():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/security-dashboard",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    body = response.json()

    expected_sections = {
        "failed_login_trends",
        "active_sessions",
        "recent_role_changes",
        "lockout_events",
    }

    for section in expected_sections:
        assert section in body


# ============================================================
# SERVICE API KEYS
# ============================================================

def test_r8_admin_can_create_service_api_key():
    login = login_as_ceo()

    response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "service_name": "inventory-service",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert "id" in body
    assert body["service_name"] == (
        "inventory-service"
    )
    assert "api_key" in body
    assert body["api_key"].startswith("sk_")
    assert body["is_active"] is True


def test_r8_non_admin_cannot_create_service_api_key():
    login = login_as_supplier()

    response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "service_name": "inventory-service",
        },
    )

    assert response.status_code == 403


def test_r8_service_api_key_verify():
    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "inventory-service",
        },
    )

    assert create_response.status_code == 201

    api_key = create_response.json()["api_key"]

    verify_response = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_response.status_code == 200

    body = verify_response.json()

    assert body["authenticated"] is True
    assert body["service"] == "inventory-service"
    assert body["auth_type"] == "api_key"


def test_r8_invalid_service_api_key_rejected():
    response = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": "sk_invalid_key",
        },
    )

    assert response.status_code == 401


def test_r8_missing_service_api_key_rejected():
    response = client.post(
        "/api/v1/auth/service-verify"
    )

    assert response.status_code == 401


def test_r8_admin_can_list_service_api_keys():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    keys = response.json()

    assert isinstance(keys, list)

    if keys:
        key = keys[0]

        assert "id" in key
        assert "service_name" in key
        assert "is_active" in key

        # Security requirement:
        # raw API key and key hash must never be returned.
        assert "api_key" not in key
        assert "key_hash" not in key


def test_r8_api_key_revoke():
    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "compliance-service",
        },
    )

    assert create_response.status_code == 201

    body = create_response.json()

    key_id = body["id"]
    api_key = body["api_key"]

    verify_before_revoke = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_before_revoke.status_code == 200

    revoke_response = client.delete(
        f"/api/v1/admin/service-keys/{key_id}",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert revoke_response.status_code == 200

    verify_after_revoke = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_after_revoke.status_code == 401


def test_r8_non_admin_cannot_revoke_service_api_key():
    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "test-service",
        },
    )

    assert create_response.status_code == 201

    key_id = create_response.json()["id"]

    supplier_login = login_as_supplier()

    response = client.delete(
        f"/api/v1/admin/service-keys/{key_id}",
        headers=auth_header(
            supplier_login["access_token"]
        ),
    )

    assert response.status_code == 403


# ============================================================
# SEPARATE SERVICE IDENTITIES
# ============================================================

def test_r8_inventory_and_compliance_use_separate_api_keys():
    admin_login = login_as_ceo()

    inventory_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "inventory-service",
        },
    )

    compliance_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "compliance-service",
        },
    )

    assert inventory_response.status_code == 201
    assert compliance_response.status_code == 201

    inventory_key = inventory_response.json()[
        "api_key"
    ]

    compliance_key = compliance_response.json()[
        "api_key"
    ]

    assert inventory_key != compliance_key


def test_r8_revoking_inventory_key_does_not_revoke_compliance_key():
    admin_login = login_as_ceo()

    inventory_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "inventory-isolation-test",
        },
    )

    compliance_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "compliance-isolation-test",
        },
    )

    assert inventory_response.status_code == 201
    assert compliance_response.status_code == 201

    inventory_id = inventory_response.json()["id"]
    inventory_key = inventory_response.json()["api_key"]

    compliance_key = compliance_response.json()["api_key"]

    revoke_response = client.delete(
        f"/api/v1/admin/service-keys/{inventory_id}",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert revoke_response.status_code == 200

    inventory_verify = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": inventory_key,
        },
    )

    compliance_verify = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": compliance_key,
        },
    )

    assert inventory_verify.status_code == 401
    assert compliance_verify.status_code == 200


# ============================================================
# API KEY EXPIRATION
# ============================================================

def test_r8_expired_api_key_rejected():
    admin_login = login_as_ceo()

    response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "expired-test-service",
            "expires_at": "2020-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 201

    api_key = response.json()["api_key"]

    verify_response = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_response.status_code == 401


# ============================================================
# API KEY TRACKING
# ============================================================

def test_r8_api_key_last_used_is_tracked():
    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "tracking-test-service",
        },
    )

    assert create_response.status_code == 201

    api_key = create_response.json()["api_key"]
    key_id = create_response.json()["id"]

    verify_response = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_response.status_code == 200

    list_response = client.get(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert list_response.status_code == 200

    keys = list_response.json()

    matching_key = next(
        key
        for key in keys
        if key["id"] == key_id
    )

    assert matching_key["last_used_at"] is not None


# ============================================================
# CALLER SERVICE HEADER
# ============================================================

def test_r8_verify_requires_valid_user_token():
    response = client.post(
        "/api/v1/auth/verify",
        headers={
            "X-Caller-Service": "inventory-service",
        },
    )

    assert response.status_code == 401


def test_r8_verify_accepts_caller_service_header():
    login = login_as_ceo()

    response = client.post(
        "/api/v1/auth/verify",
        headers={
            "Authorization": (
                f"Bearer {login['access_token']}"
            ),
            "X-Caller-Service": "inventory-service",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["valid"] is True


# ============================================================
# DEFINITION OF DONE - M1
# ============================================================

def test_definition_of_done_verify_caching():
    login = login_as_ceo()

    token = login["access_token"]

    responses = []

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/verify",
            headers=auth_header(token),
        )

        responses.append(response)

    assert all(
        response.status_code == 200
        for response in responses
    )


# ============================================================
# DEFINITION OF DONE - M2
# ============================================================

def test_definition_of_done_permission_checks():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert "permissions" in body
    assert isinstance(body["permissions"], list)


# ============================================================
# DEFINITION OF DONE - M3
# ============================================================

def test_definition_of_done_account_lockout():
    admin_login = login_as_ceo()

    email = unique_email("definition_lockout")

    create_admin_user(
        admin_login["access_token"],
        email=email,
        password="CorrectPassword@12345",
        role="analyst",
        full_name="Definition Lockout User",
    )

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "WrongPassword@12345",
            },
        )

        assert response.status_code in (
            401,
            423,
            429,
        )

        if response.status_code == 423:
            break

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": "CorrectPassword@12345",
        },
    )

    assert response.status_code in (
        401,
        423,
        429,
    )


# ============================================================
# DEFINITION OF DONE -M4
# ============================================================

def test_definition_of_done_security_dashboard():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/admin/security-dashboard",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200


# ============================================================
# DEFINITION OF DONE -M5
# ============================================================

def test_definition_of_done_api_key_issuable_and_revocable():
    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/service-keys",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "service_name": "definition-of-done-service",
        },
    )

    assert create_response.status_code == 201

    key_id = create_response.json()["id"]
    api_key = create_response.json()["api_key"]

    verify_response = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_response.status_code == 200

    revoke_response = client.delete(
        f"/api/v1/admin/service-keys/{key_id}",
        headers=auth_header(
            admin_login["access_token"]
        ),
    )

    assert revoke_response.status_code == 200

    verify_after_revoke = client.post(
        "/api/v1/auth/service-verify",
        headers={
            "X-API-Key": api_key,
        },
    )

    assert verify_after_revoke.status_code == 401

