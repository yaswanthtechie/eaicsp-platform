"""
Live End-to-End Integration Test Suite against Rahul's Real Platform Service.

Verifies:
1. Client -> Gateway -> Platform: Real login flow (POST /api/v1/auth/login)
2. Client -> Gateway -> Platform: Real token verification (POST /api/v1/auth/verify)
3. Client -> Gateway -> Platform: Real missing/invalid token rejection (401)
4. Client -> Gateway -> Platform: Circuit breaker immunity against 401/403 responses
5. Verification of Platform hardening responses through Gateway (Invalid or expired authentication token)
"""

import os
import socket
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app as gateway_app

REAL_PLATFORM_URL = os.getenv(
    "PLATFORM_SERVICE_URL",
    getattr(settings, "PLATFORM_SERVICE_URL", "http://localhost:8005"),
)
REAL_GATEWAY_URL = os.getenv("REAL_GATEWAY_URL", "http://localhost:8000")


def _is_service_reachable(url: str) -> bool:
    """Check if the given HTTP service host and port are accepting TCP connections."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


if not _is_service_reachable(REAL_PLATFORM_URL):
    pytestmark = pytest.mark.skip(
        reason=(
            f"Live integration prerequisite missing: Real platform service at {REAL_PLATFORM_URL} "
            "is unreachable. Start Rahul's platform service on port 8005 to run live integration tests."
        )
    )


class PlatformGatewayLiveCaller:
    """
    HTTP caller that sends requests through the API Gateway to the real Platform service.
    Prefers live running gateway daemon (:8000) if active, or uses TestClient(gateway_app)
    configured with REAL_PLATFORM_URL.
    """

    def __init__(self, gateway_url: str, platform_url: str):
        self.gateway_url = gateway_url.rstrip("/")
        self.platform_url = platform_url.rstrip("/")
        self.use_live_daemon = _is_service_reachable(self.gateway_url)

    def post(
        self,
        path: str,
        data: dict | None = None,
        json: dict | list | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        req_headers = dict(headers or {})
        if self.use_live_daemon:
            with httpx.Client(base_url=self.gateway_url, timeout=10.0) as client:
                return client.post(path, data=data, json=json, headers=req_headers)
        else:
            _SENTINEL = object()
            original_route = settings.SERVICE_ROUTES.get("/api/v1/auth", _SENTINEL)
            settings.SERVICE_ROUTES["/api/v1/auth"] = self.platform_url
            try:
                with TestClient(gateway_app) as client:
                    return client.post(path, data=data, json=json, headers=req_headers)
            finally:
                if original_route is not _SENTINEL:
                    settings.SERVICE_ROUTES["/api/v1/auth"] = original_route
                else:
                    settings.SERVICE_ROUTES.pop("/api/v1/auth", None)

    def get(self, path: str, headers: dict | None = None) -> httpx.Response:
        req_headers = dict(headers or {})
        if self.use_live_daemon:
            with httpx.Client(base_url=self.gateway_url, timeout=10.0) as client:
                return client.get(path, headers=req_headers)
        else:
            _SENTINEL = object()
            original_route = settings.SERVICE_ROUTES.get("/api/v1/auth", _SENTINEL)
            settings.SERVICE_ROUTES["/api/v1/auth"] = self.platform_url
            try:
                with TestClient(gateway_app) as client:
                    return client.get(path, headers=req_headers)
            finally:
                if original_route is not _SENTINEL:
                    settings.SERVICE_ROUTES["/api/v1/auth"] = original_route
                else:
                    settings.SERVICE_ROUTES.pop("/api/v1/auth", None)


@pytest.fixture
def live_caller():
    return PlatformGatewayLiveCaller(REAL_GATEWAY_URL, REAL_PLATFORM_URL)


# ===========================================================================
# Live Integration Tests Against Real Platform Service
# ===========================================================================

def test_real_platform_login_through_gateway(live_caller):
    """
    Phase 10: Step 1 & 2 - Login through the Gateway to Rahul's Platform Service
    and receive real access token.
    """
    response = live_caller.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"
    assert len(data["access_token"]) > 20


def test_real_platform_verify_token_flow(live_caller):
    """
    Phase 10: Step 3 to 7 - Real Auth Verify Live Flow:
    1. Login to obtain real access token.
    2. Send Authorization: Bearer <real_access_token> to Gateway POST /api/v1/auth/verify.
    3. Gateway forwards to Platform.
    4. Platform validates JWT and DB user.
    5. Returns verified user information.
    """
    # 1. Login
    login_resp = live_caller.post(
        "/api/v1/auth/login",
        data={
            "username": "ceo@company.com",
            "password": "ceocompany@123",
        },
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # 2. Verify via Gateway
    verify_resp = live_caller.post(
        "/api/v1/auth/verify",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert verify_resp.status_code == 200, f"Verify failed: {verify_resp.text}"
    verified = verify_resp.json()
    assert verified["valid"] is True
    assert verified["email"] == "ceo@company.com"
    assert verified["role"] == "ceo"
    assert verified["is_active"] is True
    assert "user_id" in verified
    assert "full_name" in verified


def test_real_platform_verify_missing_token_returns_401(live_caller):
    """
    Verify Gateway passes through 401 when no token is provided.
    Platform error message: 'Invalid or expired authentication token'.
    """
    response = live_caller.post("/api/v1/auth/verify")

    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid or expired authentication token"


def test_real_platform_verify_invalid_token_returns_401(live_caller):
    """
    Verify Gateway passes through 401 when invalid token is provided.
    """
    response = live_caller.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer invalid_live_token_string_12345"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid or expired authentication token"


def test_real_platform_repeated_401_breaker_immunity(live_caller):
    """
    Verify repeated 401 authentication rejections do not trip the circuit breaker.
    """
    for _ in range(5):
        resp = live_caller.post(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer invalid_probe_token"},
        )
        assert resp.status_code == 401

    # Ensure subsequent call is not blocked by a 503 circuit breaker
    final_resp = live_caller.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer invalid_probe_token"},
    )
    assert final_resp.status_code == 401
    assert final_resp.status_code != 503
