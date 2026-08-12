from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.seed import seed_database
from app.models.failed_login_attempts import FailedLoginAttempt
from app.core.security import create_access_token
from app.database import SessionLocal
client = TestClient(app)

if __name__ == "__main__":
  seed_database()
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



