"""
Milestone 5 (M5) Test Suite — Gateway-Level Authentication Pre-Check.

Verifies:
1. Disabled Mode: When AUTH_PRECHECK_ENABLED is False (default), requests pass through to downstream without pre-check.
2. Missing Token: Protected route request without Authorization header returns 401 without invoking downstream.
3. Malformed Token: Header without Bearer scheme or with empty token returns 401 without invoking downstream.
4. Invalid Token: Token rejected by Platform /verify returns 401 without invoking downstream.
5. Expired Token: Expired token rejected by Platform /verify returns 401 without invoking downstream.
6. Valid Token: Token verified by Platform /verify continues downstream, and Authorization header is preserved.
7. Downstream 403: Pre-check succeeds, downstream role/permission checks still take effect (403 passthrough).
8. Public Routes Exemption: /health, /, /gateway/status, /gateway/dashboard bypass pre-check without tokens.
9. Auth Routes Exemption / Recursion Prevention: /api/v1/auth/* routes bypass pre-check and avoid gateway loops.
10. Platform Timeout: When Platform /verify times out, Gateway fails closed with 504 Gateway Timeout.
11. Platform Unavailable: When Platform /verify has connection error or 5xx, Gateway fails closed with 503.
12. X-Request-ID Propagation: Request ID is forwarded in the Platform /verify call for distributed tracing.
13. Circuit Breaker & Metrics Isolation: Pre-check 401 rejections do not record service failure or trip circuit breaker.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_gateway_state():
    """Reset configuration, circuit breakers, metrics, and rate limiters before and after each test."""
    original_precheck = settings.AUTH_PRECHECK_ENABLED
    settings.AUTH_PRECHECK_ENABLED = True
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = False
    yield
    settings.AUTH_PRECHECK_ENABLED = original_precheck
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    """Create a FastAPI test client for the gateway."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Disabled Mode
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_disabled_mode(mock_send, client):
    """
    When AUTH_PRECHECK_ENABLED is False (default), the Gateway performs no pre-check
    and forwards requests directly to the downstream business service.
    """
    settings.AUTH_PRECHECK_ENABLED = False

    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"items": []}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    # Request without token when pre-check is disabled passes through to downstream
    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 200
    assert response.json() == {"items": []}
    mock_send.assert_called_once()


# ===========================================================================
# 2. Missing Token
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_missing_token_returns_401(mock_send, client):
    """
    When pre-check is enabled, a request to a protected route missing the
    Authorization header is rejected with 401 without invoking downstream.
    """
    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    mock_send.assert_not_called()


# ===========================================================================
# 3. Malformed Token
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_malformed_token_returns_401(mock_send, client):
    """
    Headers that do not adhere to 'Bearer <token>' or contain empty tokens
    are rejected with 401 without invoking downstream.
    """
    # Case A: Basic auth scheme instead of Bearer
    res1 = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert res1.status_code == 401
    assert res1.json() == {"detail": "Invalid or expired token"}

    # Case B: Bearer scheme with empty token
    res2 = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": "Bearer   "},
    )
    assert res2.status_code == 401
    assert res2.json() == {"detail": "Invalid or expired token"}

    mock_send.assert_not_called()


# ===========================================================================
# 4. Invalid Token (Rejected by Platform /verify)
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_invalid_token_rejected_by_platform(mock_send, mock_post, client):
    """
    When Platform /verify returns 401 (invalid signature, wrong token type),
    Gateway rejects with 401 and does not call downstream.
    """
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"detail": "Invalid or expired token"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": "Bearer invalid-signature-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
    mock_post.assert_called_once()
    mock_send.assert_not_called()


# ===========================================================================
# 5. Expired Token (Rejected by Platform /verify)
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_expired_token_rejected_by_platform(mock_send, mock_post, client):
    """
    When Platform /verify indicates the token is expired, Gateway rejects with 401
    before reaching the downstream business service.
    """
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"detail": "Invalid or expired token"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    response = client.get(
        "/api/v1/shipments",
        headers={"Authorization": "Bearer expired-jwt-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}
    mock_post.assert_called_once()
    mock_send.assert_not_called()


# ===========================================================================
# 6. Valid Token (Passes Pre-Check and Continues Downstream)
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_valid_token_forwarded_downstream(mock_send, mock_post, client):
    """
    When Platform /verify validates the token (HTTP 200, valid=True), the request
    is allowed to continue to downstream, and Authorization is forwarded intact.
    """
    token_value = "Bearer valid-procurement-token-12345"

    # Platform /verify returns 200 OK
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "valid": True,
            "user_id": 42,
            "email": "procurement@company.com",
            "role": "procurement_manager",
            "is_active": True,
        },
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    # Downstream Inventory returns 200 OK
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"items": [{"id": 1, "sku": "SKU-100"}]}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": token_value},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [{"id": 1, "sku": "SKU-100"}]}

    mock_post.assert_called_once()
    mock_send.assert_called_once()

    # Downstream request received the exact Authorization header
    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert downstream_req.headers["authorization"] == token_value


# ===========================================================================
# 7. Downstream 403 Authorization Preservation
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_preserves_downstream_403_role_check(mock_send, mock_post, client):
    """
    Pre-check only validates identity (authentication); downstream business services
    remain responsible for role and permission checks (e.g. 403 Forbidden).
    """
    # Pre-check passes: user is authenticated analyst
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={
            "valid": True,
            "user_id": 99,
            "email": "analyst@company.com",
            "role": "analyst",
            "is_active": True,
        },
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    # Downstream Inventory rejects role: analysts cannot delete resources
    mock_send.return_value = httpx.Response(
        status_code=403,
        content=b'{"detail": "Forbidden: Insufficient permissions for role analyst"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("DELETE", "http://test/api/v1/inventory/SKU-999"),
    )

    response = client.delete(
        "/api/v1/inventory/SKU-999",
        headers={"Authorization": "Bearer analyst-valid-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Forbidden: Insufficient permissions for role analyst"
    }


# ===========================================================================
# 8. Public Routes Exemption
# ===========================================================================

def test_m5_precheck_public_routes_exempt(client):
    """
    Health checks, root status, and gateway dashboards are public endpoints
    and must never be blocked by the auth pre-check even without tokens.
    """
    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200

    # 2. Root endpoint
    res_root = client.get("/")
    assert res_root.status_code == 200

    # 3. Gateway status
    res_status = client.get("/gateway/status")
    assert res_status.status_code == 200

    # 4. Gateway dashboard
    res_dash = client.get("/gateway/dashboard")
    assert res_dash.status_code == 200


# ===========================================================================
# 9. Auth Routes Exemption / Recursion Prevention
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_auth_routes_exempt_and_no_loop(mock_send, client):
    """
    Routes under /api/v1/auth/* (login, register, verify) are explicitly exempt
    from pre-check so users can authenticate and verification calls do not recurse.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"access_token": "mock-token", "token_type": "bearer"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/login"),
    )

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    mock_send.assert_called_once()


# ===========================================================================
# 10. Platform Timeout (Fails Closed with 504)
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_platform_timeout_returns_504(mock_send, mock_post, client):
    """
    When Platform /verify times out, the Gateway fails closed with HTTP 504
    Gateway Timeout without executing the downstream business service.
    """
    mock_post.side_effect = httpx.TimeoutException("Platform verification timeout")

    response = client.get(
        "/api/v1/compliance/audits",
        headers={"Authorization": "Bearer some-token"},
    )

    assert response.status_code == 504
    data = response.json()
    assert "timeout" in str(data).lower()
    mock_send.assert_not_called()


# ===========================================================================
# 11. Platform Unavailable (Fails Closed with 503)
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_platform_unavailable_returns_503(mock_send, mock_post, client):
    """
    When Platform /verify has a connection error or returns 503, the Gateway
    fails closed with HTTP 503 Service Unavailable without executing downstream.
    """
    mock_post.side_effect = httpx.ConnectError("Platform service connection refused")

    response = client.get(
        "/api/v1/purchase-orders",
        headers={"Authorization": "Bearer some-token"},
    )

    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in str(data).lower()
    mock_send.assert_not_called()


# ===========================================================================
# 12. X-Request-ID Propagation to Platform /verify
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_propagates_request_id(mock_send, mock_post, client):
    """
    Verify that incoming X-Request-ID is propagated to the Platform /verify call
    for end-to-end distributed tracing.
    """
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"valid": True, "user_id": 1, "role": "ceo"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={
            "Authorization": "Bearer valid-ceo-token",
            "X-Request-ID": "req-trace-uuid-999",
        },
    )

    assert response.status_code == 200
    mock_post.assert_called_once()

    # Inspect headers passed to Platform /verify
    verify_call_kwargs = mock_post.call_args[1]
    verify_headers = verify_call_kwargs.get("headers", {})
    assert verify_headers.get("x-request-id") == "req-trace-uuid-999"
    assert verify_headers.get("x-caller-service") == "api-gateway"


# ===========================================================================
# 13. Circuit Breaker & Metrics Isolation
# ===========================================================================

@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_m5_precheck_circuit_breaker_isolation(mock_send, mock_post, client):
    """
    Auth pre-check rejections (401) must NOT trip the downstream service circuit
    breaker or pollute business service failure statistics.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"detail": "Invalid or expired token"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    # Send 20 rejected requests to /api/v1/inventory
    for _ in range(20):
        res = client.get(
            "/api/v1/inventory/items",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert res.status_code == 401

    # Verify inventory circuit breaker was completely isolated
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True
    _, total_reqs, failures = circuit_breaker_manager.get_failure_rate(service_id)
    assert failures == 0
    assert total_reqs == 0
    mock_send.assert_not_called()
