from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_database
from app.models.failed_login_attempts import FailedLoginAttempt
from app.core.security import create_access_token
from app.database import SessionLocal
client = TestClient(app)

# ============================================================
# TEST HELPERS
# ============================================================

def clear_failed_login_attempts():
    
    db =SessionLocal()

    try:
        db.query(FailedLoginAttempt).delete()
        db.commit()
    finally:
        db.close()


def login_as_ceo():
    return client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )

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

    response = login_as_ceo()

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

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == "ceo@company.com"

def test_current_user_without_token():
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


# ============================================================
# RBAC
# ============================================================

def test_admin_access_allowed():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/test",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted"


def test_admin_access_forbidden():
    clear_failed_login_attempts()

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "supplier@company.com",
            "password": "supplier@123",
        },
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/test",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Forbidden: insufficient permissions"
    )

# ============================================================
# DB-BACKED RATE LIMITING
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
# PASSWORD POLICY / REGISTRATION
# ============================================================

def test_register_success():

    clear_failed_login_attempts()
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newregisteruser@company.com",
            "full_name": "New Register User",
            "password": "NewRegister@123"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "User registered successfully"


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
        headers={
            "Authorization": f"Bearer {expired_token}"
        },
    )

    assert response.status_code == 401


def test_tampered_token():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    token = login.json()["access_token"]

    tampered = (
        token[:-1]
        + ("A" if token[-1] != "A" else "B")
    )

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {tampered}"
        },
    )

    assert response.status_code == 401


# ============================================================
# REFRESH TOKEN
# ============================================================

def test_refresh_success():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    refresh = login.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    new_token = response.json()["access_token"]

    me = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {new_token}"
        },
    )

    assert me.status_code == 200
    assert me.json()["email"] == "ceo@company.com"


def test_refresh_with_access_token_rejected():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    access = login.json()["access_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": access
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_with_garbage_token_returns_401():
    clear_failed_login_attempts()

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": "not.a.real.token"
        },
    )

    assert response.status_code == 401


# ============================================================
# LOGOUT / REFRESH TOKEN REVOCATION
# ============================================================

def test_logout_revokes_refresh_token():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    refresh = login.json()["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": refresh
        },
    )

    assert logout.status_code == 200

    response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": refresh
        },
    )

    assert response.status_code == 401


# ============================================================
# ROLE HIERARCHY
# ============================================================

def test_ceo_has_vp_permissions():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 200
    permissions = response.json()["permissions"]
    assert "vp_operations" in permissions

def test_refresh_token_replay_attack():
    client = TestClient(app)
    # Login and obtain the original refresh token (Token A)
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )

    assert login_response.status_code == 200

    token_a = login_response.json()["refresh_token"]

    # First use of Token A should succeed.
    first_refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": token_a,
        },
    )

    assert first_refresh_response.status_code == 200

    response_data = first_refresh_response.json()

    assert "access_token" in response_data
    assert "refresh_token" in response_data

    # A new refresh token (Token B) should have been issued.
    token_b = response_data["refresh_token"]

    assert token_b != token_a

    # Replay Token A.
    replay_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": token_a,
        },
    )

    # Token A was rotated/revoked, so replay must fail.
    assert replay_response.status_code == 401

    assert replay_response.json()["detail"] == (
        "Invalid or revoked refresh token"
    )

def test_ceo_can_access_vp_level_admin_endpoint():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200


def test_supplier_cannot_access_admin_users():
    clear_failed_login_attempts()

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "supplier@company.com",
            "password": "supplier@123",
        },
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403

def test_ceo_has_all_lower_role_permissions():
    clear_failed_login_attempts()

    login = login_as_ceo()

    assert login.status_code == 200

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers={
            "Authorization": f"Bearer {token}"
        },
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


# ============================================================
# TEST HELPERS
# ============================================================

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
# ADMIN USER MANAGEMENT
# ============================================================

def test_r4_ceo_can_list_users():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_vp_operations_can_list_users():
    login = login_as(
        "vpoperations@company.com",
        "vpoperations@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_create_user_by_ceo():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(token),
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
    assert body["full_name"] == "R4 Create User"
    assert body["role"] == "analyst"
    assert body["is_active"] is True


def test_r4_deactivate_user_by_ceo():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(token),
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
        headers=auth_header(token),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user_id"] == user_id
    assert body["is_active"] is False


def test_r4_non_admin_cannot_deactivate_user():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    token = login["access_token"]

    # Any existing user ID is enough because authorization
    # should be checked before the target-user operation.
    response = client.patch(
        "/api/v1/admin/users/1/deactivate",
        headers=auth_header(token),
    )

    assert response.status_code == 403


def test_r4_admin_can_force_reset_password():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]
    create_response = client.post(
        "/api/v1/admin/users",
        headers=auth_header(token),
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
        headers=auth_header(token),
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

    token = login["access_token"]

    response = client.post(
        "/api/v1/admin/users/1/force-reset-password",
        headers=auth_header(token),
        json={
            "new_password": "NewPassword@12345",
        },
    )

    assert response.status_code == 403


def test_r4_admin_can_view_role_change_history():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    ceo_id = get_user_id_by_email(
        token,
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{ceo_id}/role-history",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_r4_non_admin_cannot_view_role_change_history():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/admin/users/1/role-history",
        headers=auth_header(token),
    )

    assert response.status_code == 403


# ============================================================
# PER-SESSION MANAGEMENT
# ============================================================

def test_r4_admin_can_list_user_sessions():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    ceo_id = get_user_id_by_email(
        token,
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{ceo_id}/sessions",
        headers=auth_header(token),
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
    login1 = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    login2 = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    assert login1["refresh_token"] != login2["refresh_token"]

    token = login1["access_token"]

    ceo_id = get_user_id_by_email(
        token,
        "ceo@company.com",
    )

    response = client.get(
        f"/api/v1/admin/users/{ceo_id}/sessions",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    sessions = response.json()

    assert len(sessions) >= 2


def test_r4_admin_can_revoke_user_session():
    login1 = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    login2 = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login1["access_token"]

    ceo_id = get_user_id_by_email(
        token,
        "ceo@company.com",
    )

    sessions_response = client.get(
        f"/api/v1/admin/users/{ceo_id}/sessions",
        headers=auth_header(token),
    )

    assert sessions_response.status_code == 200

    sessions = sessions_response.json()

    assert len(sessions) >= 2

    session_id = sessions[-1]["id"]

    response = client.delete(
        f"/api/v1/admin/users/{ceo_id}/sessions/{session_id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "Session revoked successfully"
    )


def test_r4_revoked_session_cannot_be_refreshed():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    access_token = login["access_token"]
    refresh_token = login["refresh_token"]

    ceo_id = get_user_id_by_email(
        access_token,
        "ceo@company.com",
    )

    sessions_response = client.get(
        f"/api/v1/admin/users/{ceo_id}/sessions",
        headers=auth_header(access_token),
    )

    assert sessions_response.status_code == 200

    sessions = sessions_response.json()

    assert sessions

    # The session endpoint does not expose the refresh token.
    # The newest session belongs to the login above.
    session_id = max(
        sessions,
        key=lambda session: session["id"],
    )["id"]

    revoke_response = client.delete(
        f"/api/v1/admin/users/{ceo_id}/sessions/{session_id}",
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

    token = login["access_token"]

    response = client.get(
        "/api/v1/admin/users/1/sessions",
        headers=auth_header(token),
    )

    assert response.status_code == 403


# ============================================================
#  ROLE HIERARCHY EDGE CASES
# ============================================================

def test_r4_ceo_has_lower_role_permissions():
    login = login_as(
        "ceo@company.com",
        "ceocompany@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "ceo" in permissions
    assert "vp_operations" in permissions


def test_r4_vp_does_not_have_ceo_permission():
    login = login_as(
        "vpoperations@company.com",
        "vpoperations@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(token),
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

    token = login["access_token"]

    response = client.get(
        "/api/v1/auth/me/permissions",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    permissions = response.json()["permissions"]

    assert "supplier" in permissions
    assert "ceo" not in permissions
    assert "vp_operations" not in permissions


def test_r4_supplier_cannot_access_admin_users():
    login = login_as(
        "supplier@company.com",
        "supplier@123",
    )

    token = login["access_token"]

    response = client.get(
        "/api/v1/admin/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403
