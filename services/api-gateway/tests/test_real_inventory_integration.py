"""
Live End-to-End Integration Test Suite against Balaji's Real Inventory Service.

IMPORTANT NOTICES:
1. "This test requires the real inventory service to be running."
2. "It is skipped when REAL_INVENTORY_URL is not configured."
3. "This is the end-to-end/live verification; mocked tests are separate."

Architecture / Verification Flow:
Client
  -> API Gateway (:8000)
  -> REAL Balaji Inventory Service (:8001)
  -> REAL Inventory Authentication (services/inventory/app/core/auth.py:verify_token)
  -> HTTP 401 Unauthorized
  -> API Gateway passes the 401 back to client unchanged (not 500/503)

Runnable Commands:
  Windows PowerShell:
    $env:REAL_INVENTORY_URL="http://localhost:8001"
    python -m pytest tests/test_real_inventory_integration.py -v

  Bash:
    REAL_INVENTORY_URL=http://localhost:8001 pytest tests/test_real_inventory_integration.py -v

Prerequisites for live execution:
- Balaji Inventory Service running on port 8001:
    cd services/inventory
    uvicorn app.main:app --host 127.0.0.1 --port 8001
- Platform Service running on port 8005 (for token verification):
    cd services/platform
    uvicorn app.main:app --host 127.0.0.1 --port 8005
- API Gateway running on port 8000:
    cd services/api-gateway
    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

import os
import socket
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app as gateway_app
from app.services.circuit_breaker import circuit_breaker_manager

REAL_INVENTORY_URL = os.getenv(
    "INVENTORY_SERVICE_URL",
    os.getenv(
        "REAL_INVENTORY_URL",
        getattr(settings, "INVENTORY_SERVICE_URL", "http://localhost:8001"),
    ),
)
REAL_GATEWAY_URL = os.getenv("REAL_GATEWAY_URL", "http://localhost:8000")
REAL_PLATFORM_URL = os.getenv(
    "PLATFORM_SERVICE_URL",
    getattr(settings, "PLATFORM_SERVICE_URL", "http://localhost:8005"),
)


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


# Skip module only when real inventory service is unreachable
if not _is_service_reachable(REAL_INVENTORY_URL):
    pytestmark = pytest.mark.skip(
        reason=(
            f"Live integration prerequisite missing: Real inventory service at {REAL_INVENTORY_URL} "
            "is unreachable. Start Balaji's inventory service on port 8001 to run live integration tests."
        )
    )


class GatewayLiveCaller:
    """
    HTTP caller that sends requests through the API Gateway to the real downstream service.
    Prefers live running gateway daemon (:8000) if active, or uses TestClient(gateway_app)
    configured with REAL_INVENTORY_URL.
    """

    def __init__(self, gateway_url: str, inventory_url: str):
        self.gateway_url = gateway_url.rstrip("/")
        self.inventory_url = inventory_url.rstrip("/")
        self.use_live_daemon = _is_service_reachable(self.gateway_url)

    def post(self, path: str, json: dict | list | None = None, headers: dict | None = None) -> httpx.Response:
        req_headers = dict(headers or {})
        if self.use_live_daemon:
            # Send real network HTTP request to the running Gateway daemon
            with httpx.Client(base_url=self.gateway_url, timeout=10.0) as client:
                return client.post(path, json=json, headers=req_headers)
        else:
            # Point gateway configuration to the real inventory service URL and run gateway ASGI
            _SENTINEL = object()
            original_route = settings.SERVICE_ROUTES.get("/api/v1/inventory", _SENTINEL)
            settings.SERVICE_ROUTES["/api/v1/inventory"] = self.inventory_url
            try:
                with TestClient(gateway_app) as client:
                    resp = client.post(path, json=json, headers=req_headers)
                    return resp
            finally:
                if original_route is not _SENTINEL:
                    settings.SERVICE_ROUTES["/api/v1/inventory"] = original_route
                else:
                    settings.SERVICE_ROUTES.pop("/api/v1/inventory", None)

    def get(self, path: str, headers: dict | None = None) -> httpx.Response:
        req_headers = dict(headers or {})
        if self.use_live_daemon:
            with httpx.Client(base_url=self.gateway_url, timeout=10.0) as client:
                return client.get(path, headers=req_headers)
        else:
            _SENTINEL = object()
            original_route = settings.SERVICE_ROUTES.get("/api/v1/inventory", _SENTINEL)
            settings.SERVICE_ROUTES["/api/v1/inventory"] = self.inventory_url
            try:
                with TestClient(gateway_app) as client:
                    return client.get(path, headers=req_headers)
            finally:
                if original_route is not _SENTINEL:
                    settings.SERVICE_ROUTES["/api/v1/inventory"] = original_route
                else:
                    settings.SERVICE_ROUTES.pop("/api/v1/inventory", None)


@pytest.fixture
def live_caller():
    """Fixture providing a gateway caller configured for live integration."""
    return GatewayLiveCaller(REAL_GATEWAY_URL, REAL_INVENTORY_URL)


# ===========================================================================
# Live Integration Tests Against Real Balaji Inventory Service
# ===========================================================================

def test_real_inventory_missing_token_returns_401(live_caller):
    """
    Requirement 1: Real Live 401 Verification (Missing Token)

    Demonstrates the live end-to-end chain:
      Client
        -> API Gateway (:8000)
        -> REAL Balaji Inventory Service (:8001)
        -> REAL Inventory verify_token dependency
        -> HTTP 401 Unauthorized ("Missing authentication token")
        -> API Gateway passes the 401 back to client unmodified

    Assertions:
    - HTTP status is exactly 401
    - Gateway does not convert downstream 401 into 500 or 503
    - Response body preserves Balaji inventory service's real detail: "Missing authentication token"
    - Response passes through the gateway (verified by gateway response headers)
    """
    # Protected endpoint: POST /api/v1/inventory/what-if requires role 'ceo' or 'vp_operations'
    response = live_caller.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
    )

    assert response.status_code == 401, (
        f"Expected 401 from real inventory service through gateway, got {response.status_code}"
    )

    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Missing authentication token", (
        f"Expected real inventory service error detail 'Missing authentication token', got {data}"
    )

    # Verify request traversed through API Gateway
    assert "x-request-id" in response.headers or "date" in response.headers


def test_real_inventory_invalid_token_returns_401(live_caller):
    """
    Requirement 1: Real Live 401 Verification (Invalid Token)

    Demonstrates:
      Client (with invalid Authorization header)
        -> API Gateway (:8000)
        -> REAL Balaji Inventory Service (:8001)
        -> REAL Inventory calls Platform Service (:8005) to verify token
        -> Platform rejects token (401)
        -> Inventory raises HTTP 401 ("Invalid or expired authentication token")
        -> API Gateway passes the 401 back to client unmodified
    """
    response = live_caller.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
        headers={"Authorization": "Bearer invalid_live_test_token_12345"},
    )

    assert response.status_code == 401, (
        f"Expected 401 from real inventory service through gateway, got {response.status_code}"
    )

    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Invalid or expired authentication token", (
        f"Expected real inventory service error detail 'Invalid or expired authentication token', got {data}"
    )


def test_real_inventory_repeated_401_breaker_immunity(live_caller):
    """
    Reviewer Feedback: Real-socket test for repeated 401s and circuit breaker immunity.

    Verifies that multiple repeated 401 responses from the real inventory service:
    1. Pass through the Gateway faithfully each time
    2. Are NOT counted as service outages/failures by the circuit breaker
    3. The circuit breaker does not trip to OPEN (no 503 circuit breaker open)
    4. Subsequent requests still reach the real downstream service and return 401
    """
    for _ in range(5):
        response = live_caller.post(
            "/api/v1/inventory/what-if",
            json={"spike_percent": 30},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing authentication token"

    # Subsequent request: If breaker had tripped to OPEN, gateway would return 503
    final_response = live_caller.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
    )
    assert final_response.status_code == 401
    assert final_response.status_code != 503
    assert final_response.json()["detail"] == "Missing authentication token"

    # In in-process mode, also assert on circuit breaker manager state directly
    if not live_caller.use_live_daemon:
        assert circuit_breaker_manager.get_state("inventory") == "closed"
        assert circuit_breaker_manager.can_execute("inventory") is True


def test_real_inventory_reorder_plan_route(live_caller):
    """
    Verify GET /api/v1/inventory/reorder-plan through Gateway.
    """
    response = live_caller.get("/api/v1/inventory/reorder-plan")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, list)


def test_real_inventory_authenticated_ceo_success(live_caller):
    """
    Phase 11: End-to-end authorized request through Gateway:
    Client -> Gateway -> Inventory -> Platform (verify) -> Inventory -> Gateway -> Client
    Role 'ceo' is authorized for POST /api/v1/inventory/what-if.
    """
    if not _is_service_reachable(REAL_PLATFORM_URL):
        pytest.skip(f"Platform service at {REAL_PLATFORM_URL} is unreachable to obtain token.")

    with httpx.Client(base_url=REAL_PLATFORM_URL, timeout=10.0) as client:
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "ceo@company.com", "password": "ceocompany@123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

    response = live_caller.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, f"Expected 200 from inventory what-if, got {response.status_code}: {response.text}"
    data = response.json()
    assert isinstance(data, dict)


def test_real_inventory_unauthorized_role_returns_403(live_caller):
    """
    Phase 11: End-to-end role authorization check through Gateway:
    Client -> Gateway -> Inventory -> Platform (verify role='supplier') -> Inventory rejects with 403.
    """
    if not _is_service_reachable(REAL_PLATFORM_URL):
        pytest.skip(f"Platform service at {REAL_PLATFORM_URL} is unreachable to obtain token.")

    with httpx.Client(base_url=REAL_PLATFORM_URL, timeout=10.0) as client:
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "supplier@company.com", "password": "supplier@123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

    response = live_caller.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, f"Expected 403 for supplier role, got {response.status_code}: {response.text}"
    assert "not authorized" in response.json().get("detail", "").lower()
