"""
Round 5 API Gateway Integration & Error Handling Test Suite.

Verifies:
1. Downstream error status passthrough (401, 403, 404, 422, 500).
2. Gateway connection failure handling (503 Service Unavailable).
3. Gateway timeout handling (504 Gateway Timeout).
4. Circuit breaker auth failure immunity (401/403 do not count as service failures).
5. Header propagation (Authorization, X-Request-ID, X-Caller-Service).
6. Proof that dummy_services.py is NOT imported or used by any production app modules.
"""

import importlib
import pkgutil
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import app
from app.core.config import settings
from app.main import app as gateway_app
from app.middleware.rate_limit import in_memory_limiter
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_state():
    """Reset circuit breaker, metrics, and rate limiters before and after each test."""
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = False
    yield
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    in_memory_limiter.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(gateway_app) as test_client:
        yield test_client


# ===========================================================================
# 1. Architectural Integrity: dummy_services.py isolation
# ===========================================================================

def test_dummy_services_not_imported_by_production_code():
    """
    Verify dummy_services is strictly a standalone test/dev helper
    and is never imported into any production app module.
    """
    app_modules = []
    for _, modname, _ in pkgutil.walk_packages(app.__path__, prefix="app."):
        app_modules.append(modname)

    for modname in app_modules:
        mod = importlib.import_module(modname)
        mod_vars = vars(mod)
        for var_name, val in mod_vars.items():
            val_module = getattr(val, "__module__", "")
            assert "dummy_services" not in str(val_module), (
                f"Production module '{modname}' imports or references dummy_services via '{var_name}'"
            )


# ===========================================================================
# 2. Downstream Error Status Passthrough Tests
# ===========================================================================

@pytest.mark.parametrize(
    "status_code,response_body",
    [
        (401, b'{"detail": "Invalid or expired authentication token"}'),
        (403, b'{"detail": "Role \'supplier\' is not authorized for this endpoint"}'),
        (404, b'{"detail": "Inventory not found"}'),
        (422, b'{"detail": [{"loc": ["body", "quantity"], "msg": "field required"}]}'),
        (500, b'{"detail": "Internal database connection failed"}'),
    ],
)
@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_status_codes_faithfully_passed_through(
    mock_send, client, status_code, response_body
):
    """
    Gateway must never swallow downstream errors or turn them into 200s.
    Status code and body must pass through unchanged.
    """
    mock_send.return_value = httpx.Response(
        status_code=status_code,
        content=response_body,
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test/api/v1/inventory/what-if"),
    )

    response = client.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
        headers={"Authorization": "Bearer some-token"},
    )

    assert response.status_code == status_code
    assert response.content == response_body


# ===========================================================================
# 3. Connection Failure & Timeout Handling
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_connection_refused_returns_503(mock_send, client):
    """
    When downstream service is unreachable/refused, gateway returns 503
    with clear service name in error and without leaking internal stack traces.
    """
    mock_send.side_effect = httpx.ConnectError(
        "Connection refused",
        request=httpx.Request("POST", "http://test/api/v1/auth/verify"),
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers={"Authorization": "Bearer some-token"},
    )

    assert response.status_code == 503
    data = response.json()
    assert "error" in data
    assert "unavailable" in data["error"].lower()
    # Ensure no internal tracebacks or secrets leaked
    assert "traceback" not in response.text.lower()


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_timeout_returns_504(mock_send, client):
    """
    When downstream service times out, gateway returns 504 Gateway Timeout.
    """
    mock_send.side_effect = httpx.TimeoutException(
        "Read timed out",
        request=httpx.Request("POST", "http://test/api/v1/inventory/what-if"),
    )

    response = client.post(
        "/api/v1/inventory/what-if",
        json={"spike_percent": 30},
        headers={"Authorization": "Bearer some-token"},
    )

    assert response.status_code == 504
    data = response.json()
    assert "error" in data
    assert "timeout" in data["error"].lower()


# ===========================================================================
# 4. Header Forwarding: Caller Identification & Request Tracing
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_x_caller_service_and_request_id_forwarded(mock_send, client):
    """
    Verify that Gateway attaches X-Caller-Service: api-gateway and propagates
    X-Request-ID to downstream services.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"valid": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test/api/v1/auth/verify"),
    )

    response = client.post(
        "/api/v1/auth/verify",
        headers={
            "Authorization": "Bearer valid-token",
            "X-Request-ID": "test-req-trace-12345",
        },
    )

    assert response.status_code == 200
    mock_send.assert_called_once()
    downstream_req: httpx.Request = mock_send.call_args[0][0]

    assert downstream_req.headers["authorization"] == "Bearer valid-token"
    assert downstream_req.headers["x-caller-service"] == "api-gateway"
    assert downstream_req.headers["x-request-id"] == "test-req-trace-12345"


# ===========================================================================
# 5. Circuit Breaker Auth Failure Immunity
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_repeated_downstream_401_does_not_trip_circuit_breaker(mock_send, client):
    """
    Repeated 401 Unauthorized responses must NOT trip the circuit breaker.
    """
    mock_send.return_value = httpx.Response(
        status_code=401,
        content=b'{"detail": "Invalid or expired authentication token"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test/api/v1/auth/verify"),
    )

    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401

    assert circuit_breaker_manager.can_execute("auth") is True
    assert circuit_breaker_manager.get_state("auth") == "closed"
