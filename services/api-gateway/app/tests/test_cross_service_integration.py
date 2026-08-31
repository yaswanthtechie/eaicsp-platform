"""
Cross-service Platform -> Gateway JWT Integration Tests.

Verifies end-to-end integration:
1. Real platform roles issued by platform auth are verified and enforce correct quotas.
2. Tokens signed with wrong secret are rejected and never receive privileged quotas.
3. Expired, malformed, and missing-claim tokens do not crash the gateway and fall back safely.
4. /gateway/status contract returns 200 and exposes no secrets or credentials.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import extract_jwt_identity, in_memory_limiter
from app.middleware.ratelimit import limiter

PLATFORM_ROLES_AND_QUOTAS = [
    ("ceo", 200),
    ("vp_operations", 200),
    ("procurement_manager", 100),
    ("logistics_manager", 100),
    ("compliance_officer", 100),
    ("warehouse_manager", 100),
    ("analyst", 60),
    ("supplier", 60),
]


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    """Reset in-memory limiter and SlowAPI limiter before each test."""
    in_memory_limiter.reset()
    limiter.enabled = False
    old_trusted = list(getattr(settings, "TRUSTED_PROXIES", []))
    settings.TRUSTED_PROXIES = []
    old_load_test = getattr(settings, "LOAD_TEST_MODE", False)
    settings.LOAD_TEST_MODE = False

    yield

    in_memory_limiter.reset()
    limiter.enabled = True
    settings.TRUSTED_PROXIES = old_trusted
    settings.LOAD_TEST_MODE = old_load_test


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_platform_access_token(
    user_id: int | str,
    email: str,
    role: str,
    secret_key: str = settings.SECRET_KEY,
    algorithm: str = settings.JWT_ALGORITHM,
    expires_delta: timedelta | None = None,
) -> str:
    """Simulates platform create_access_token from services/platform/app/core/security.py."""
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)

    payload = {
        "sub": email,
        "user_id": user_id,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Platform -> Gateway Role Quota Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role,expected_quota", PLATFORM_ROLES_AND_QUOTAS)
def test_platform_token_for_all_real_roles(client, role, expected_quota):
    """
    Verifies that a valid token created with platform claims for every real platform
    role is accepted by the gateway and receives its exact configured rate limit.
    """
    token = create_platform_access_token(
        user_id=f"user_{role}_01",
        email=f"{role}@eaicsp.com",
        role=role,
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == str(expected_quota)
    assert int(response.headers["X-RateLimit-Remaining"]) == expected_quota - 1


# ---------------------------------------------------------------------------
# Wrong Secret Rejection Tests (Mandatory Security Regression Test)
# ---------------------------------------------------------------------------

def test_wrong_secret_jwt_is_rejected_and_receives_default_limit(client):
    """
    Security Test:
    1. Create a JWT using a fake/wrong secret with HS256 algorithm and privileged role 'ceo'.
    2. Send it to the gateway.
    3. Verify that the gateway does NOT accept the forged identity.
    4. Verify that it receives the default IP limit (60) rather than the privileged executive limit (200).
    """
    wrong_secret = "attacker-controlled-forged-secret-key-32-chars-long"
    forged_token = create_platform_access_token(
        user_id="hacker_user",
        email="hacker@evil.com",
        role="ceo",
        secret_key=wrong_secret,
    )

    headers = {"Authorization": f"Bearer {forged_token}"}
    response = client.get("/", headers=headers)

    assert response.status_code == 200
    default_quota = settings.get_role_rate_limit("default")
    ceo_quota = settings.get_role_rate_limit("ceo")

    assert default_quota == 60
    assert ceo_quota == 200
    assert response.headers["X-RateLimit-Limit"] == str(default_quota)
    assert response.headers["X-RateLimit-Limit"] != str(ceo_quota)


def test_shared_platform_secret_round_trip(client):
    """
    Proves that when the platform signing secret matches the gateway verification secret,
    the token is accepted, whereas altering the secret immediately causes rejection.
    """
    correct_token = create_platform_access_token(
        user_id="real_vp",
        email="vp@eaicsp.com",
        role="vp_operations",
        secret_key=settings.SECRET_KEY,
    )
    res_valid = client.get("/", headers={"Authorization": f"Bearer {correct_token}"})
    assert res_valid.status_code == 200
    assert res_valid.headers["X-RateLimit-Limit"] == "200"

    tampered_token = create_platform_access_token(
        user_id="real_vp",
        email="vp@eaicsp.com",
        role="vp_operations",
        secret_key="completely-different-signing-secret",
    )
    res_tampered = client.get("/", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 200
    assert res_tampered.headers["X-RateLimit-Limit"] == "60"


# ---------------------------------------------------------------------------
# Expired, Malformed, and Unmapped Role Tokens
# ---------------------------------------------------------------------------

def test_expired_platform_token_falls_back_to_default(client):
    """An expired token must be rejected and fall back to unauthenticated default quota."""
    expired_token = create_platform_access_token(
        user_id="expired_ceo",
        email="ceo@eaicsp.com",
        role="ceo",
        expires_delta=timedelta(minutes=-10),  # 10 minutes in the past
    )
    response = client.get("/", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "60"


def test_malformed_token_does_not_crash_gateway(client):
    """Malformed tokens must return 200 with default limit, never unhandled 500 error."""
    malformed_tokens = [
        "not.a.jwt",
        "invalid_base64_header.invalid_body.invalid_sig",
        "Bearer",
        "",
        "...",
    ]
    for bad_token in malformed_tokens:
        response = client.get("/", headers={"Authorization": f"Bearer {bad_token}"})
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "60"


def test_unmapped_role_falls_back_safely(client):
    """A role that does not exist in the platform enum falls back safely to default quota."""
    token = create_platform_access_token(
        user_id="custom_role_user",
        email="custom@eaicsp.com",
        role="nonexistent_superadmin",
    )
    response = client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "60"


# ---------------------------------------------------------------------------
# Gateway Status Endpoint Contract & Security Verification
# ---------------------------------------------------------------------------

def test_gateway_status_endpoint_contract(client):
    """
    Verifies GET /gateway/status response contract:
    - HTTP 200
    - Exact JSON body fields: status, version, app_name
    - No sensitive credentials or secrets exposed
    """
    response = client.get("/gateway/status")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == settings.VERSION
    assert data["app_name"] == settings.APP_NAME

    # Security check: verify no secrets or internal configuration are exposed
    body_str = response.text.lower()
    assert "secret_key" not in body_str
    assert "jwt_secret" not in body_str
    assert "password" not in body_str
    assert settings.SECRET_KEY.lower() not in body_str
