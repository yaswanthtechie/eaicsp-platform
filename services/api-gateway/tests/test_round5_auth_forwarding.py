"""
Round 5 Pod 1 - API Gateway Authentication Forwarding, 401/403 Passthrough,
and Circuit Breaker Immunity Test Suite.

Verifies:
1. Authorization Header Forwarding:
   - 'Authorization: Bearer <token>' header is faithfully forwarded from
     the Gateway to downstream services without modification or loss.
2. Downstream 401 Passthrough:
   - Downstream 401 Unauthorized responses pass through the Gateway unchanged:
     status code 401, exact JSON body, and supported response headers (e.g. WWW-Authenticate).
   - Gateway never converts 401 into a 500, 503, or generic error.
3. Downstream 403 Passthrough:
   - Downstream 403 Forbidden responses pass through the Gateway unchanged:
     status code 403 and exact JSON body.
4. Circuit Breaker Auth Failure Immunity:
   - Repeated 401 and 403 responses are NOT counted as service failures.
   - Circuit breaker remains in CLOSED state.
   - can_execute() remains True throughout.
   - Existing circuit breaker protection for real 5xx / timeout failures remains intact.
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
    """Create a FastAPI test client for the gateway."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Authorization Header Forwarding Tests
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_authorization_header_forwarded_exact(mock_send, client):
    """
    Requirement 1:
    Verify that when the client sends 'Authorization: Bearer <token>',
    the API Gateway forwards the exact same Authorization header downstream.
    """
    token_value = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIn0.signature"
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": token_value},
    )

    assert response.status_code == 200
    mock_send.assert_called_once()

    # Inspect the downstream request sent by httpx
    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert "authorization" in downstream_req.headers
    assert downstream_req.headers["authorization"] == token_value


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_authorization_header_forwarded_for_post_with_body(mock_send, client):
    """
    Requirement 1 (POST):
    Verify that Authorization header is forwarded on mutating methods (POST) along with body.
    """
    token_value = "Bearer custom-procurement-manager-token-abc-123"
    request_payload = {"sku": "SKU-9999", "quantity": 50}

    mock_send.return_value = httpx.Response(
        status_code=201,
        content=b'{"sku": "SKU-9999", "quantity": 50, "created": true}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "http://test/api/v1/inventory"),
    )

    response = client.post(
        "/api/v1/inventory",
        json=request_payload,
        headers={"Authorization": token_value},
    )

    assert response.status_code == 201
    mock_send.assert_called_once()

    downstream_req: httpx.Request = mock_send.call_args[0][0]
    assert downstream_req.headers["authorization"] == token_value
    assert downstream_req.content == b'{"sku":"SKU-9999","quantity":50}'


# ===========================================================================
# 2. Downstream 401 Passthrough Tests
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_401_passthrough_unmodified(mock_send, client):
    """
    Requirement 2:
    Verify that when downstream returns HTTP 401:
    - Gateway returns HTTP 401
    - Downstream response body is preserved unchanged
    - Supported headers (e.g. WWW-Authenticate) are preserved
    - Gateway does not convert 401 into 500 or generic error
    """
    downstream_401_body = b'{"detail": "Could not validate credentials", "error_code": "TOKEN_INVALID"}'
    mock_send.return_value = httpx.Response(
        status_code=401,
        content=downstream_401_body,
        headers={
            "content-type": "application/json",
            "www-authenticate": 'Bearer error="invalid_token", error_description="The token is expired"',
        },
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    response = client.get(
        "/api/v1/inventory/items",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Could not validate credentials",
        "error_code": "TOKEN_INVALID",
    }
    assert response.headers.get("www-authenticate") == 'Bearer error="invalid_token", error_description="The token is expired"'


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_401_missing_token_passthrough(mock_send, client):
    """
    Requirement 2 (Missing Token):
    Verify downstream 401 due to missing Authorization header passes through faithfully.
    """
    downstream_401_body = b'{"detail": "Not authenticated"}'
    mock_send.return_value = httpx.Response(
        status_code=401,
        content=downstream_401_body,
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    response = client.get("/api/v1/inventory/items")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


# ===========================================================================
# 3. Downstream 403 Passthrough Tests
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_downstream_403_passthrough_unmodified(mock_send, client):
    """
    Requirement 3:
    Verify that when downstream returns HTTP 403:
    - Gateway returns HTTP 403
    - Downstream response body is preserved unchanged
    - Gateway does not convert 403 into 500 or generic error
    """
    downstream_403_body = b'{"detail": "Forbidden: Insufficient permissions for role analyst on resource inventory"}'
    mock_send.return_value = httpx.Response(
        status_code=403,
        content=downstream_403_body,
        headers={"content-type": "application/json"},
        request=httpx.Request("DELETE", "http://test/api/v1/inventory/SKU-123"),
    )

    response = client.delete(
        "/api/v1/inventory/SKU-123",
        headers={"Authorization": "Bearer analyst-valid-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Forbidden: Insufficient permissions for role analyst on resource inventory"
    }


# ===========================================================================
# 4. Circuit Breaker Authentication Failure Immunity Tests
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_immune_to_repeated_401_responses(mock_send, client):
    """
    Requirement 4 (401 Immunity):
    Verify that 20 consecutive downstream 401 responses do NOT trip the circuit breaker.
    - State remains CLOSED
    - can_execute() remains True
    - Failure count remains 0
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    mock_send.return_value = httpx.Response(
        status_code=401,
        content=b'{"detail": "Invalid token"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    # Send 20 consecutive requests that return 401
    for _ in range(20):
        res = client.get(
            "/api/v1/inventory/items",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert res.status_code == 401

    # Circuit breaker must remain CLOSED and healthy
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True

    failure_rate, total_reqs, failures = circuit_breaker_manager.get_failure_rate(service_id)
    assert failures == 0
    assert failure_rate == 0.0
    assert total_reqs == 20


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_immune_to_repeated_403_responses(mock_send, client):
    """
    Requirement 4 (403 Immunity):
    Verify that 20 consecutive downstream 403 responses do NOT trip the circuit breaker.
    - State remains CLOSED
    - can_execute() remains True
    - Failure count remains 0
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    mock_send.return_value = httpx.Response(
        status_code=403,
        content=b'{"detail": "Permission denied"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )

    # Send 20 consecutive requests that return 403
    for _ in range(20):
        res = client.get(
            "/api/v1/inventory/items",
            headers={"Authorization": "Bearer low-privilege-token"},
        )
        assert res.status_code == 403

    # Circuit breaker must remain CLOSED and healthy
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True

    failure_rate, total_reqs, failures = circuit_breaker_manager.get_failure_rate(service_id)
    assert failures == 0
    assert failure_rate == 0.0
    assert total_reqs == 20


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_preserves_real_5xx_service_failure_tripping(mock_send, client):
    """
    Requirement 4 (Preserve Real Failure Behavior):
    Verify that while 401/403 do not count as failures, real 500 errors STILL
    trip the circuit breaker when failure rate threshold (>50%) is exceeded.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    # Step 1: 10 auth 401 requests (recorded as success/healthy service)
    mock_send.return_value = httpx.Response(
        status_code=401,
        content=b'{"detail": "Unauthorized"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )
    for _ in range(10):
        res = client.get("/api/v1/inventory/items")
        assert res.status_code == 401

    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # Step 2: Send 10 HTTP 500 downstream internal server errors (10/20 = 50.0% -> still CLOSED)
    mock_send.return_value = httpx.Response(
        status_code=500,
        content=b'{"error": "Internal Database Crash"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test/api/v1/inventory/items"),
    )
    for _ in range(10):
        res = client.get("/api/v1/inventory/items")
        assert res.status_code == 500

    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # Step 3: Send 11th HTTP 500 downstream internal server error -> 11/21 = 52.4% > 50% -> TRIPS to OPEN
    res_11 = client.get("/api/v1/inventory/items")
    assert res_11.status_code == 500

    # Circuit breaker must now be OPEN
    assert circuit_breaker_manager.get_state(service_id) == "open"
    assert circuit_breaker_manager.can_execute(service_id) is False

    # Step 4: Subsequent request must fail fast with 503 circuit breaker open
    fast_fail_res = client.get("/api/v1/inventory/items")
    assert fast_fail_res.status_code == 503
    assert fast_fail_res.json()["error"] == "Inventory service circuit breaker open"

