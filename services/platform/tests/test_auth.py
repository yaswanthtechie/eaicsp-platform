   
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

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

def clear_failed_login_attempts():
    db = SessionLocal()

    try:
        db.query(FailedLoginAttempt).delete()
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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "unknown@company.com",
            "password": "password123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ============================================================
# CURRENT USER
# ============================================================

def test_current_user():
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    response = client.get(
        "/api/v1/admin/test",
        headers=auth_header(login["access_token"]),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "Forbidden: insufficient permissions"
    )


# ============================================================
# RATE LIMITING
# ============================================================

def test_login_rate_limit_per_email():
    clear_failed_login_attempts()

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "ceo@company.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 429

    assert response.json()["detail"] == (
        "Too many login attempts. "
        "Try again after 15 minutes."
    )


def test_login_rate_limit_per_ip():
    clear_failed_login_attempts()

    for index in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": f"unknown{index}@company.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "anotherunknown@company.com",
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
    clear_failed_login_attempts()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newregisteruser@company.com",
            "full_name": "New Register User",
            "password": "NewRegister@123",
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "User registered successfully"
    )


def test_register_weak_password():
    clear_failed_login_attempts()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weakuser@company.com",
            "full_name": "Weak User",
            "password": "weak123",
        },
    )

    assert response.status_code == 400


# ============================================================
# JWT
# ============================================================

def test_expired_token():
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

    ceo_login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    supplier_login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    response = client.post(
        "/api/v1/auth/logout",
        headers=auth_header(
            ceo_login["access_token"]
        ),
        json={
            "refresh_token": supplier_login["refresh_token"],
        },
    )

    # Your implementation correctly identifies
    # that the refresh token belongs to another user.
    assert response.status_code == 403

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": supplier_login["refresh_token"],
        },
    )

    # Supplier session must still work.
    assert refresh_response.status_code == 200


# ============================================================
# ROLE HIERARCHY
# ============================================================

def test_r4_ceo_has_lower_role_permissions():
    login = login_as_ceo()

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "ceo" in permissions
    assert "vp_operations" in permissions
    assert "procurement_manager" in permissions
    assert "logistics_manager" in permissions
    assert "compliance_officer" in permissions
    assert "warehouse_manager" in permissions
    assert "analyst" in permissions
    assert "supplier" in permissions


def test_r4_vp_does_not_have_ceo_permission():
    login = login_as(
        "vpoperations@company.com",
        "vpoperations@123",
    )

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "vp_operations" in permissions
    assert "ceo" not in permissions


def test_r4_supplier_does_not_have_higher_permissions():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "supplier" in permissions
    assert "ceo" not in permissions
    assert "vp_operations" not in permissions


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
    login = login_as(
        "vpoperations@company.com",
        "vpoperations@123",
    )

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_supplier_cannot_access_admin_users():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 403


def test_r4_create_user_by_ceo():
    login = login_as_ceo()

    response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_create_user@company.com",
            "full_name": "R4 Create User",
            "password": "CreateUser@12345",
            "role": "analyst",
        },
    )

    assert response.status_code in (200, 201)

    body = response.json()

    assert body["email"] == "r4_create_user@company.com"
    assert body["role"] == "analyst"
    assert body["is_active"] is True


def test_r4_deactivate_user_by_ceo():
    login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_deactivate_user@company.com",
            "full_name": "R4 Deactivate User",
            "password": "DeactivateUser@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}/deactivate",
        headers=auth_header(
            login["access_token"]
        ),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_r4_non_admin_cannot_deactivate_user():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

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

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_reset_user@company.com",
            "full_name": "R4 Reset User",
            "password": "OldPassword@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

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
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

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

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_role_change@company.com",
            "full_name": "R4 Role Change User",
            "password": "RoleChange@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

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

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_role_history@company.com",
            "full_name": "R4 Role History User",
            "password": "RoleHistory@12345",
            "role": "compliance_officer",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

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
    assert latest["old_role"] == "compliance_officer"
    assert latest["new_role"] == "warehouse_manager"
    assert latest["changed_by"] is not None


def test_r4_role_change_creates_audit_log():
    login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            login["access_token"]
        ),
        json={
            "email": "r4_role_audit@company.com",
            "full_name": "R4 Role Audit User",
            "password": "RoleAudit@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

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
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

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
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

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

    response = client.get(
        f"/api/v1/admin/users/"
        f"{get_user_id_by_email(login1['access_token'], 'ceo@company.com')}"
        "/sessions",
        headers=auth_header(
            login1["access_token"]
        ),
    )

    assert response.status_code == 200

    sessions = response.json()

    assert len(sessions) >= 2

    session_id = sessions[-1]["id"]

    revoke_response = client.delete(
        f"/api/v1/admin/users/"
        f"{get_user_id_by_email(login1['access_token'], 'ceo@company.com')}"
        f"/sessions/{session_id}",
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
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

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
    email = "r4_password_reset@company.com"

    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "email": email,
            "full_name": "R4 Password Reset User",
            "password": "OriginalPass@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    request_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert request_response.status_code == 200

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

        reset_token = reset_record.token

    finally:
        db.close()

    reset_response = client.post(
        "/api/v1/auth/password-reset/reset",
        json={
            "token": reset_token,
            "new_password": "NewPassword@12345",
        },
    )

    assert reset_response.status_code == 200


def test_r4_password_reset_token_single_use():
    email = "r4_reset_single_use@company.com"

    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "email": email,
            "full_name": "R4 Reset Single Use",
            "password": "OriginalPass@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    # Correct endpoint: REQUEST a reset token.
    request_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert request_response.status_code == 200

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

        reset_token = reset_record.token

    finally:
        db.close()

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
    email = "r4_reset_rotation@company.com"

    admin_login = login_as_ceo()

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "email": email,
            "full_name": "R4 Reset Rotation",
            "password": "OriginalPass@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    # Token A
    first_request = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert first_request.status_code == 200

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        token_a = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
            )
            .order_by(
                PasswordResetToken.id.desc()
            )
            .first()
            .token
        )
    finally:
        db.close()

    # Token B
    second_request = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": email,
        },
    )

    assert second_request.status_code == 200

    db = SessionLocal()

    try:
        token_records = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
            )
            .order_by(
                PasswordResetToken.id.desc()
            )
            .all()
        )

        token_b = token_records[0].token

    finally:
        db.close()

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

    email = "r4_force_reset_sessions@company.com"

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(
            admin_login["access_token"]
        ),
        json={
            "email": email,
            "full_name": "R4 Force Reset Sessions",
            "password": "OldPassword@12345",
            "role": "analyst",
        },
    )

    assert create_response.status_code in (200, 201)

    user_id = create_response.json()["user_id"]

   
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
    clear_failed_login_attempts()

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
        status in (401, 429)
        for status in status_codes
    )

    assert 429 in status_codes


def test_r4_concurrent_login_attempts_recorded():
    clear_failed_login_attempts()

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
    clear_failed_login_attempts()

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