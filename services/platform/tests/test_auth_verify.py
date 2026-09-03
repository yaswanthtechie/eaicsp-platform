from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.models.users import User
from app.models.roles import Role

client = TestClient(app)


def test_verify_valid_access_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None
        assert user.role is not None

        token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name,
            }
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == user.id
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name
        assert data["role"] == user.role.name
        assert data["is_active"] is True
    finally:
        db.close()


def test_verify_valid_access_token_via_login():
    login_resp = client.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["email"] == "ceo@company.com"
    assert data["role"] == "ceo"
    assert data["is_active"] is True


def test_verify_missing_authorization_header():
    response = client.post("/api/v1/auth/verify")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication token"


def test_verify_invalid_token():
    # Malformed / garbage JWT
    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication token"

    # Non-bearer scheme
    response_non_bearer = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Basic somerandomcredentials"},
    )
    assert response_non_bearer.status_code == 401
    assert response_non_bearer.json()["detail"] == "Invalid or expired authentication token"

    # Empty token string
    response_empty = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer "},
    )
    assert response_empty.status_code == 401
    assert response_empty.json()["detail"] == "Invalid or expired authentication token"


def test_verify_expired_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        expired_token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role.name,
            },
            expires_delta=timedelta(minutes=-10),
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
    finally:
        db.close()


def test_verify_refresh_token_used_as_access_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ceo@company.com").first()
        assert user is not None

        refresh_tok = create_refresh_token(
            {
                "sub": user.email,
                "user_id": user.id,
            }
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {refresh_tok}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
    finally:
        db.close()


def test_verify_unknown_user():
    unknown_token = create_access_token(
        {
            "sub": "unknown_ghost@company.com",
            "user_id": 999999,
            "role": "ceo",
        }
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {unknown_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired authentication token"


def test_verify_inactive_user():
    db = SessionLocal()
    role = db.query(Role).first()
    inactive_user = User(
        email="inactive_user_verify_test@company.com",
        full_name="Inactive Test User",
        password=hash_password("password123"),
        is_active=False,
        role_id=role.id,
    )
    db.add(inactive_user)
    db.commit()
    db.refresh(inactive_user)

    try:
        token = create_access_token(
            {
                "sub": inactive_user.email,
                "user_id": inactive_user.id,
                "role": role.name,
            }
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
    finally:
        db.delete(inactive_user)
        db.commit()
        db.close()


def test_verify_user_without_role():
    db = SessionLocal()
    no_role_user = User(
        email="norole_user_verify_test@company.com",
        full_name="No Role Test User",
        password=hash_password("password123"),
        is_active=True,
        role_id=None,
    )
    db.add(no_role_user)
    db.commit()
    db.refresh(no_role_user)

    try:
        token = create_access_token(
            {
                "sub": no_role_user.email,
                "user_id": no_role_user.id,
                "role": "none",
            }
        )

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired authentication token"
    finally:
        db.delete(no_role_user)
        db.commit()
        db.close()
