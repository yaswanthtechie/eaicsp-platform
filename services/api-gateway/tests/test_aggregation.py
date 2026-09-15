"""
Milestone 2 — BFF Aggregation Test Suite.

Verifies:
1. All three downstream services succeed (status: complete).
2. Inventory unavailable (status: partial).
3. Compliance unavailable (status: partial).
4. Logistics unavailable (status: partial).
5. All three unavailable (status: unavailable).
6. Authorization header propagation.
7. X-Request-ID propagation.
8. X-Caller-Service propagation and default ("api-gateway").
9. True parallel execution (asyncio concurrency timing).
10. Aggregation route precedence over catch-all proxy router.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI test client for the gateway."""
    with TestClient(app) as test_client:
        yield test_client


def _make_json_response(status_code: int, data: dict | list, request: httpx.Request) -> httpx.Response:
    """Helper to generate a mock httpx.Response with json body."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode("utf-8"),
        headers={"content-type": "application/json"},
        request=request,
    )


# ---------------------------------------------------------------------------
# 1. All three downstream services succeed
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_all_succeed(mock_send, client):
    """
    Test scenario 1:
    When Inventory, Compliance, and Logistics all respond with 200 OK,
    the gateway returns status: complete and individual service status: ok.
    """
    inventory_data = [{"id": 1, "sku": "SKU-TEST-01", "quantity": 100}]
    compliance_data = {"summary": "All audits passed", "passed": 12, "failed": 0}
    logistics_data = [{"shipment_id": "SH-101", "status": "IN_TRANSIT"}]

    async def side_effect(request: httpx.Request, *args, **kwargs):
        url_str = str(request.url)
        if "/api/v1/inventory" in url_str:
            return _make_json_response(200, inventory_data, request)
        if "/api/v1/compliance/audit/summary" in url_str:
            return _make_json_response(200, compliance_data, request)
        if "/api/v1/shipments/" in url_str:
            return _make_json_response(200, logistics_data, request)
        return _make_json_response(404, {"error": "not found"}, request)

    mock_send.side_effect = side_effect

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "complete"

    assert data["inventory"]["status"] == "ok"
    assert data["inventory"]["data"] == inventory_data

    assert data["compliance"]["status"] == "ok"
    assert data["compliance"]["data"] == compliance_data

    assert data["logistics"]["status"] == "ok"
    assert data["logistics"]["data"] == logistics_data


# ---------------------------------------------------------------------------
# 2. Inventory unavailable
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_inventory_unavailable(mock_send, client):
    """
    Test scenario 2:
    When Inventory service is down (503 / exception), the gateway returns
    status: partial with Inventory status: unavailable and other services status: ok.
    """
    compliance_data = {"passed": 5}
    logistics_data = [{"id": "SH-1"}]

    async def side_effect(request: httpx.Request, *args, **kwargs):
        url_str = str(request.url)
        if "/api/v1/inventory" in url_str:
            raise httpx.ConnectError("Connection refused to inventory:8001", request=request)
        if "/api/v1/compliance/audit/summary" in url_str:
            return _make_json_response(200, compliance_data, request)
        if "/api/v1/shipments/" in url_str:
            return _make_json_response(200, logistics_data, request)
        return _make_json_response(404, {}, request)

    mock_send.side_effect = side_effect

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "partial"

    assert data["inventory"]["status"] == "unavailable"
    assert data["inventory"]["data"] is None
    assert "error" in data["inventory"]
    assert "traceback" not in data["inventory"]["error"].lower()

    assert data["compliance"]["status"] == "ok"
    assert data["compliance"]["data"] == compliance_data

    assert data["logistics"]["status"] == "ok"
    assert data["logistics"]["data"] == logistics_data


# ---------------------------------------------------------------------------
# 3. Compliance unavailable
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_compliance_unavailable(mock_send, client):
    """
    Test scenario 3:
    When Compliance service times out, the gateway returns status: partial
    with Compliance status: unavailable and other services status: ok.
    """
    inventory_data = [{"id": "ITEM-1"}]
    logistics_data = [{"shipment": "SH-2"}]

    async def side_effect(request: httpx.Request, *args, **kwargs):
        url_str = str(request.url)
        if "/api/v1/inventory" in url_str:
            return _make_json_response(200, inventory_data, request)
        if "/api/v1/compliance/audit/summary" in url_str:
            raise httpx.TimeoutException("Read timeout on compliance", request=request)
        if "/api/v1/shipments/" in url_str:
            return _make_json_response(200, logistics_data, request)
        return _make_json_response(404, {}, request)

    mock_send.side_effect = side_effect

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "partial"

    assert data["compliance"]["status"] == "unavailable"
    assert data["compliance"]["data"] is None
    assert "error" in data["compliance"]

    assert data["inventory"]["status"] == "ok"
    assert data["inventory"]["data"] == inventory_data

    assert data["logistics"]["status"] == "ok"
    assert data["logistics"]["data"] == logistics_data


# ---------------------------------------------------------------------------
# 4. Logistics unavailable
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_logistics_unavailable(mock_send, client):
    """
    Test scenario 4:
    When Logistics service returns 500 error, the gateway returns status: partial
    with Logistics status: unavailable and other services status: ok.
    """
    inventory_data = [{"sku": "SKU-99"}]
    compliance_data = {"score": 90}

    async def side_effect(request: httpx.Request, *args, **kwargs):
        url_str = str(request.url)
        if "/api/v1/inventory" in url_str:
            return _make_json_response(200, inventory_data, request)
        if "/api/v1/compliance/audit/summary" in url_str:
            return _make_json_response(200, compliance_data, request)
        if "/api/v1/shipments/" in url_str:
            return _make_json_response(500, {"detail": "Internal server error"}, request)
        return _make_json_response(404, {}, request)

    mock_send.side_effect = side_effect

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "partial"

    assert data["logistics"]["status"] == "unavailable"
    assert data["logistics"]["data"] is None
    assert "error" in data["logistics"]

    assert data["inventory"]["status"] == "ok"
    assert data["inventory"]["data"] == inventory_data

    assert data["compliance"]["status"] == "ok"
    assert data["compliance"]["data"] == compliance_data


# ---------------------------------------------------------------------------
# 5. All three unavailable
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_all_unavailable(mock_send, client):
    """
    Test scenario 5:
    When all three services fail, the gateway returns status: unavailable
    and all service components have status: unavailable without raising 500.
    """
    async def side_effect(request: httpx.Request, *args, **kwargs):
        url_str = str(request.url)
        if "/api/v1/inventory" in url_str:
            raise httpx.ConnectError("Connection refused", request=request)
        if "/api/v1/compliance/audit/summary" in url_str:
            raise httpx.TimeoutException("Timeout", request=request)
        if "/api/v1/shipments/" in url_str:
            return _make_json_response(503, {"error": "Service unavailable"}, request)
        return _make_json_response(404, {}, request)

    mock_send.side_effect = side_effect

    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "unavailable"

    assert data["inventory"]["status"] == "unavailable"
    assert data["inventory"]["data"] is None
    assert "error" in data["inventory"]

    assert data["compliance"]["status"] == "unavailable"
    assert data["compliance"]["data"] is None
    assert "error" in data["compliance"]

    assert data["logistics"]["status"] == "unavailable"
    assert data["logistics"]["data"] is None
    assert "error" in data["logistics"]


# ---------------------------------------------------------------------------
# 6. Authorization header propagation
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_authorization_propagation(mock_send, client):
    """
    Test scenario 6:
    Verify that incoming Authorization header is propagated to all downstream requests.
    """
    captured_requests: list[httpx.Request] = []

    async def side_effect(request: httpx.Request, *args, **kwargs):
        captured_requests.append(request)
        return _make_json_response(200, {"ok": True}, request)

    mock_send.side_effect = side_effect

    test_token = "Bearer test-jwt-token-12345.signature"
    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": test_token},
    )

    assert response.status_code == 200
    assert len(captured_requests) == 3

    for req in captured_requests:
        assert "authorization" in req.headers
        assert req.headers["authorization"] == test_token


# ---------------------------------------------------------------------------
# 7. X-Request-ID propagation
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_request_id_propagation(mock_send, client):
    """
    Test scenario 7:
    Verify that incoming X-Request-ID is propagated to all downstream requests.
    """
    captured_requests: list[httpx.Request] = []

    async def side_effect(request: httpx.Request, *args, **kwargs):
        captured_requests.append(request)
        return _make_json_response(200, {"ok": True}, request)

    mock_send.side_effect = side_effect

    custom_request_id = "req-custom-trace-uuid-999"
    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"X-Request-ID": custom_request_id},
    )

    assert response.status_code == 200
    assert len(captured_requests) == 3

    for req in captured_requests:
        assert "x-request-id" in req.headers
        assert req.headers["x-request-id"] == custom_request_id


# ---------------------------------------------------------------------------
# 8. X-Caller-Service propagation and default
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_caller_service_propagation_and_default(mock_send, client):
    """
    Test scenario 8:
    Verify that X-Caller-Service is propagated when provided,
    and defaults to 'api-gateway' when absent.
    """
    captured_requests: list[httpx.Request] = []

    async def side_effect(request: httpx.Request, *args, **kwargs):
        captured_requests.append(request)
        return _make_json_response(200, {"ok": True}, request)

    mock_send.side_effect = side_effect

    # Case A: Explicit X-Caller-Service provided
    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"X-Caller-Service": "frontend-portal"},
    )
    assert response.status_code == 200
    assert len(captured_requests) == 3
    for req in captured_requests:
        assert req.headers.get("x-caller-service") == "frontend-portal"

    captured_requests.clear()

    # Case B: X-Caller-Service absent -> defaults to api-gateway
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    assert len(captured_requests) == 3
    for req in captured_requests:
        assert req.headers.get("x-caller-service") == "api-gateway"


# ---------------------------------------------------------------------------
# 9. True parallel execution
# ---------------------------------------------------------------------------

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_aggregation_true_parallel_execution(mock_send, client):
    """
    Test scenario 9:
    Verify that the three downstream requests execute concurrently.
    Each downstream request is delayed by 0.1s.
    If sequential, total duration >= 0.3s.
    If parallel, total duration is close to 0.1s (assert < 0.25s).
    """
    delay_per_service = 0.10

    async def slow_side_effect(request: httpx.Request, *args, **kwargs):
        await asyncio.sleep(delay_per_service)
        return _make_json_response(200, {"data": "ok"}, request)

    mock_send.side_effect = slow_side_effect

    start_time = time.perf_counter()
    response = client.get("/api/v1/dashboard/summary")
    elapsed_time = time.perf_counter() - start_time

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "complete"

    # In parallel, elapsed time will be approximately delay_per_service (~0.1s)
    # and significantly less than sequential time (3 * 0.10 = 0.30s).
    assert elapsed_time < 0.25, f"Requests took {elapsed_time:.3f}s; expected concurrent execution under 0.25s"
    assert elapsed_time >= 0.08, f"Requests executed too fast ({elapsed_time:.3f}s), delay was not respected"


# ---------------------------------------------------------------------------
# 10. Aggregation route precedence
# ---------------------------------------------------------------------------

def test_aggregation_route_precedence():
    """
    Test scenario 10:
    Verify that the aggregation router is registered BEFORE the catch-all
    gateway proxy router in FastAPI's route table.
    """
    all_paths = [
        getattr(sub, "path", "")
        for r in app.routes
        for sub in (
            r.original_router.routes
            if hasattr(r, "original_router")
            else (r.routes if hasattr(r, "routes") else [r])
        )
    ]

    assert "/api/v1/dashboard/summary" in all_paths, (
        "Route /api/v1/dashboard/summary was not registered on app"
    )
    assert "/{path:path}" in all_paths, (
        "Catch-all proxy route /{path:path} was not found on app"
    )
    assert all_paths.index("/api/v1/dashboard/summary") < all_paths.index("/{path:path}"), (
        f"Route precedence error: /api/v1/dashboard/summary "
        f"must be registered before catch-all /{path:path}"
    )
