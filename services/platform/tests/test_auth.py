from fastapi.testclient import TestClient
from app.main import app
from app.routes.auth_routes import login_attempts

client = TestClient(app)


def clear_attempts():
    login_attempts.clear()


def login_as_ceo():
    return client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceo123"
        }
    )


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Platform Service is running"
    }


def test_login_success():
    clear_attempts()

    response = login_as_ceo()

    assert response.status_code == 200

    body = response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_invalid_password():
    clear_attempts()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_invalid_user():
    clear_attempts()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "unknown@company.com",
            "password": "password123"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_current_user():
    clear_attempts()

    login = login_as_ceo()

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["email"] == "ceo@company.com"


def test_current_user_without_token():
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_admin_access_allowed():
    clear_attempts()

    login = login_as_ceo()

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/test",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Admin access granted"


def test_admin_access_forbidden():
    clear_attempts()

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "supplier@company.com",
            "password": "sup123"
        }
    )

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/admin/test",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: insufficient permissions"


def test_login_rate_limit():
    clear_attempts()

    for _ in range(5):
        client.post(
            "/api/v1/auth/login",
            data={
                "username": "ceo@company.com",
                "password": "wrongpassword"
            }
        )

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many login attempts. Try again after 15 minutes."


def test_expired_token():

    expired_token = create_access_token(
        {
            "sub": "ceo@company.com",
            "role": "ceo",
            "user_id": 1
        },
        expires_delta=timedelta(minutes=-1)
    )

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {expired_token}"
        }
    )
    assert response.status_code == 401

def test_tampered_token():

    login = login_as_ceo()

    token = login.json()["access_token"]

    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    response = client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {tampered}"
        }
    )
    assert response.status_code == 401