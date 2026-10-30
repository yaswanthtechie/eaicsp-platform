"""
Round 15 API Gateway routing and correlation tests.

Validates:
1. Route resolution for all Round 15 endpoints (REST and WebSocket).
2. Longest-prefix matching and rejection of invalid sibling prefixes.
3. Downstream URL construction and path rewriting.
4. Query parameter preservation.
5. Correlation ID (X-Request-ID) and W3C traceparent propagation.
6. HTTP method and request body forwarding.
7. WebSocket proxy routing and bidirectional message forwarding.
8. Unknown routes and downstream failure handling.
9. Configuration precedence across environment and individual service URLs.
"""

import asyncio
from contextlib import asynccontextmanager
import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app
from app.services.proxy import (
    _extract_websocket_token,
    _find_service_route,
    _safe_websocket_exception_detail,
    build_downstream_url,
)


# ---------------------------------------------------------------------------
# 1. Route Resolution for All Round 15 Required Endpoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("path", "expected_prefix", "expected_target_url"),
    [
        (
            "/api/v1/demand/forecast/SKU-000123",
            "/api/v1/demand",
            "http://localhost:8007",
        ),
        (
            "/api/v1/inventory/optimization/recommendations",
            "/api/v1/inventory",
            "http://localhost:8001",
        ),
        (
            "/api/v1/inventory/goods-receipts",
            "/api/v1/inventory",
            "http://localhost:8001",
        ),
        (
            "/api/v1/purchase-orders/PO-2026-0001",
            "/api/v1/purchase-orders",
            "http://localhost:8004",
        ),
        (
            "/api/v1/suppliers/SUP-00045/risk-score",
            "/api/v1/supplier-risk",
            "http://localhost:8006",
        ),
        (
            "/api/v1/suppliers/SUP-00045/stats",
            "/api/v1/suppliers",
            "http://localhost:8004",
        ),
        (
            "/api/v1/suppliers/SUP-00045/scorecard",
            "/api/v1/suppliers",
            "http://localhost:8004",
        ),
        (
            "/api/v1/analytics/kpis",
            "/api/v1/analytics",
            "http://localhost:8008",
        ),
        (
            "/api/v1/analytics/kpis/real-time",
            "/api/v1/analytics",
            "http://localhost:8008",
        ),
    ],
)
def test_round15_required_endpoints_route_resolution(
    path: str, expected_prefix: str, expected_target_url: str
):
    """Verify that every Round 15 required endpoint matches its configured downstream prefix and target URL."""
    route = _find_service_route(path)
    assert route is not None, f"Expected path {path} to resolve to a downstream service"
    matched_prefix, target_url = route
    assert matched_prefix == expected_prefix
    assert target_url == expected_target_url


# ---------------------------------------------------------------------------
# 2. Longest-Prefix Matching and Sibling Prefix Isolation
# ---------------------------------------------------------------------------

def test_find_service_route_prefers_longest_prefix():
    """Verify that more specific (longer) route prefixes take precedence over parent prefixes."""
    routes = {
        "/api/v1/inventory": "http://localhost:8001",
        "/api/v1/inventory/optimization": "http://localhost:8010",
    }
    with patch("app.services.proxy.settings.SERVICE_ROUTES", routes):
        # Specific sub-route must resolve to the longer prefix
        assert _find_service_route("/api/v1/inventory/optimization/recommendations") == (
            "/api/v1/inventory/optimization",
            "http://localhost:8010",
        )
        # Sibling route under inventory still resolves to the base prefix
        assert _find_service_route("/api/v1/inventory/items") == (
            "/api/v1/inventory",
            "http://localhost:8001",
        )


@pytest.mark.parametrize(
    "invalid_path",
    [
        "/api/v1/inventory-invalid",
        "/api/v1/suppliers-fake/123",
        "/api/v1/demand-invalid/forecast",
        "/api/v1/analytics-other/metrics",
        "/api/v1/unknown-service",
        "/api/v2/unregistered",
    ],
)
def test_invalid_sibling_prefixes_do_not_match(invalid_path: str):
    """Verify that paths sharing prefixes without clean boundary delimiters do not match."""
    assert _find_service_route(invalid_path) is None


# ---------------------------------------------------------------------------
# 3. Downstream URL Construction and Path Rewriting
# ---------------------------------------------------------------------------

def test_build_downstream_url_standard_no_rewrite():
    """Ensure URLs are constructed cleanly without rewriting when no rewrite prefix is configured."""
    url = build_downstream_url(
        target_base_url="http://localhost:8007",
        path="/api/v1/demand/forecast/SKU-000123",
        route_prefix="/api/v1/demand",
        query="horizon=30&warehouse_id=WH-BLR-01",
        rewrites={},
    )
    assert url == "http://localhost:8007/api/v1/demand/forecast/SKU-000123?horizon=30&warehouse_id=WH-BLR-01"


def test_build_downstream_url_with_configured_rewrite():
    """Ensure path prefixes are rewritten as configured while keeping suffixes and queries intact."""
    # Example 1: Explicit goods receipts rewrite: /api/v1/inventory/goods-receipts -> /api/v1/goods-receipts
    url_gr = build_downstream_url(
        target_base_url="http://localhost:8004",
        path="/api/v1/inventory/goods-receipts",
        route_prefix="/api/v1/inventory/goods-receipts",
        query="",
        rewrites={"/api/v1/inventory/goods-receipts": "/api/v1/goods-receipts"},
    )
    assert url_gr == "http://localhost:8004/api/v1/goods-receipts"

    # Example 2: Rewrite public /api/v1/suppliers to downstream /api/v1/supplier-risk
    url1 = build_downstream_url(
        target_base_url="http://localhost:8006",
        path="/api/v1/suppliers/SUP-00045/risk-score",
        route_prefix="/api/v1/suppliers",
        query="",
        rewrites={"/api/v1/suppliers": "/api/v1/supplier-risk"},
    )
    assert url1 == "http://localhost:8006/api/v1/supplier-risk/SUP-00045/risk-score"

    # Example 3: Fallback prefix rewrite when path starts with rewritten prefix
    url2 = build_downstream_url(
        target_base_url="http://localhost:8004",
        path="/api/v1/inventory/goods-receipts",
        route_prefix="/api/v1/inventory",
        query="",
        rewrites={"/api/v1/inventory": "/api/v1"},
    )
    assert url2 == "http://localhost:8004/api/v1/goods-receipts"

    # Example 4: Stripping the prefix completely
    url3 = build_downstream_url(
        target_base_url="http://localhost:8007",
        path="/api/v1/demand/forecast/SKU-000123",
        route_prefix="/api/v1/demand",
        query="horizon=30",
        rewrites={"/api/v1/demand": ""},
    )
    assert url3 == "http://localhost:8007/forecast/SKU-000123?horizon=30"


def test_goods_receipts_routes_to_inventory_without_rewrite():
    """
    Prove that POST /api/v1/inventory/goods-receipts routes through /api/v1/inventory
    to the inventory service on port 8001 without rewrite.
    """
    route = _find_service_route("/api/v1/inventory/goods-receipts")
    assert route == ("/api/v1/inventory", "http://localhost:8001")

    url = build_downstream_url(
        target_base_url="http://localhost:8001",
        path="/api/v1/inventory/goods-receipts",
        route_prefix="/api/v1/inventory",
    )
    assert url == "http://localhost:8001/api/v1/inventory/goods-receipts"

    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(201, json={"receipt_id": "GR-001"}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.post("/api/v1/inventory/goods-receipts", json={"quantity": 10})
            assert resp.status_code == 201

    assert len(sent_requests) == 1
    req = sent_requests[0]
    assert req.method == "POST"
    assert str(req.url) == "http://localhost:8001/api/v1/inventory/goods-receipts"


def test_inventory_endpoints_preserve_inventory_routing_without_rewrite():
    """
    Prove that general inventory endpoints (recommendations, items) route to
    the inventory service on port 8001 and are NOT redirected to port 8004 or rewritten.
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"items": []}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp1 = client.get("/api/v1/inventory/optimization/recommendations?warehouse_id=WH-01")
            assert resp1.status_code == 200
            resp2 = client.get("/api/v1/inventory/items/SKU-001")
            assert resp2.status_code == 200

    assert len(sent_requests) == 2
    assert str(sent_requests[0].url) == "http://localhost:8001/api/v1/inventory/optimization/recommendations?warehouse_id=WH-01"
    assert str(sent_requests[1].url) == "http://localhost:8001/api/v1/inventory/items/SKU-001"


def test_purchase_orders_routing_preserved():
    """
    Prove that purchase order endpoints route to port 8004 unchanged.
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"orders": []}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/purchase-orders/PO-100?status=open")
            assert resp.status_code == 200

    assert len(sent_requests) == 1
    assert str(sent_requests[0].url) == "http://localhost:8004/api/v1/purchase-orders/PO-100?status=open"


def test_supplier_risk_downstream_url_selection_default_and_rewrite():
    """
    Prove that GET /api/v1/suppliers/{supplier_id}/risk-score routes to port 8006
    without rewrite by default, and rewrites to /api/v1/supplier-risk when configured.
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"score": 85.0}, request=request)

    # 1. Default routing (no rewrite in SERVICE_ROUTE_REWRITES)
    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/suppliers/SUP-00045/risk-score")
            assert resp.status_code == 200

    assert len(sent_requests) == 1
    assert str(sent_requests[0].url) == "http://localhost:8006/api/v1/suppliers/SUP-00045/risk-score"

    # 2. Configured rewrite (when downstream supports /api/v1/supplier-risk)
    sent_requests.clear()
    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with patch.dict(
            "app.services.proxy.settings.SERVICE_ROUTE_REWRITES",
            {"/api/v1/suppliers": "/api/v1/supplier-risk"},
            clear=False,
        ):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.get("/api/v1/suppliers/SUP-00045/risk-score?detail=true")
                assert resp.status_code == 200

    assert len(sent_requests) == 1
    assert str(sent_requests[0].url) == "http://localhost:8006/api/v1/supplier-risk/SUP-00045/risk-score?detail=true"


def test_supplier_portal_endpoints_route_to_supplier_portal_port_8004():
    """
    Verify that general supplier endpoints route to Supplier Portal (port 8004).
    Specifically:
    - /api/v1/suppliers/{id}/stats
    - /api/v1/suppliers/{id}/scorecard
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp_stats = client.get("/api/v1/suppliers/SUP-00045/stats")
            assert resp_stats.status_code == 200

            resp_scorecard = client.get("/api/v1/suppliers/SUP-00045/scorecard")
            assert resp_scorecard.status_code == 200

    assert len(sent_requests) == 2
    assert str(sent_requests[0].url) == "http://localhost:8004/api/v1/suppliers/SUP-00045/stats"
    assert str(sent_requests[1].url) == "http://localhost:8004/api/v1/suppliers/SUP-00045/scorecard"


def test_supplier_portal_supplier_endpoints_not_sent_to_supplier_risk():
    """
    Verify routing separation:
    - /api/v1/suppliers/SUP-00045/stats routes to port 8004.
    - /api/v1/suppliers/SUP-00045/risk-score routes to port 8006.
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp_stats = client.get("/api/v1/suppliers/SUP-00045/stats")
            assert resp_stats.status_code == 200

            resp_risk = client.get("/api/v1/suppliers/SUP-00045/risk-score")
            assert resp_risk.status_code == 200

    assert len(sent_requests) == 2
    assert str(sent_requests[0].url) == "http://localhost:8004/api/v1/suppliers/SUP-00045/stats"
    assert str(sent_requests[1].url) == "http://localhost:8006/api/v1/suppliers/SUP-00045/risk-score"


def test_supplier_risk_score_pattern_routing_and_malformed_ids():
    """
    Verify that only /api/v1/suppliers/{supplier_id}/risk-score routes to Supplier Risk (port 8006).
    Malformed supplier IDs must still route to Supplier Risk so its contract returns validation errors.
    """
    # Valid and malformed IDs must all match the risk-score pattern and route to /api/v1/supplier-risk
    supplier_ids = [
        "SUP-00045",
        "invalid-id",
        "123",
        "bad_supplier_id",
        "MALFORMED!!",
        "non-existent-uuid-1234",
    ]
    for sup_id in supplier_ids:
        path = f"/api/v1/suppliers/{sup_id}/risk-score"
        route = _find_service_route(path)
        assert route is not None, f"Expected {path} to resolve"
        assert route == ("/api/v1/supplier-risk", "http://localhost:8006")

        # Also with optional trailing slash
        route_slash = _find_service_route(f"{path}/")
        assert route_slash == ("/api/v1/supplier-risk", "http://localhost:8006")

    # Verify that a request with malformed ID is actually sent downstream to port 8006
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(422, json={"detail": "Invalid supplier ID format"}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/suppliers/invalid-id/risk-score")
            assert resp.status_code == 422
            assert resp.json() == {"detail": "Invalid supplier ID format"}

    assert len(sent_requests) == 1
    assert str(sent_requests[0].url) == "http://localhost:8006/api/v1/suppliers/invalid-id/risk-score"


def test_pattern_route_ignored_when_owner_prefix_not_in_service_routes():
    """
    Verify that if the pattern's owner prefix is not present in SERVICE_ROUTES,
    it falls back to normal prefix matching.
    """
    routes_without_risk = dict(settings.SERVICE_ROUTES)
    routes_without_risk.pop("/api/v1/supplier-risk", None)

    with patch.object(settings, "SERVICE_ROUTES", routes_without_risk):
        route = _find_service_route("/api/v1/suppliers/SUP-00045/risk-score")
        # Since /api/v1/supplier-risk is missing, it falls back to prefix matching /api/v1/suppliers (port 8004)
        assert route == ("/api/v1/suppliers", "http://localhost:8004")


# ---------------------------------------------------------------------------
# 4. Correlation ID (X-Request-ID) and W3C traceparent Propagation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "endpoint", "request_body"),
    [
        ("GET", "/api/v1/demand/forecast/SKU-000123?horizon=30", None),
        ("GET", "/api/v1/inventory/optimization/recommendations", None),
        ("POST", "/api/v1/inventory/goods-receipts", {"po_id": "PO-2026-000123", "quantity": 50}),
        ("GET", "/api/v1/suppliers/SUP-00045/risk-score", None),
        ("GET", "/api/v1/analytics/kpis?warehouse_id=WH-BLR-01", None),
    ],
)
def test_correlation_and_tracing_propagation_across_required_endpoints(
    method: str, endpoint: str, request_body: dict | None
):
    """
    Verify that every required Round 15 HTTP endpoint propagates the incoming
    X-Request-ID and injects W3C traceparent into the downstream call.
    """
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    client_request_id = f"r15-test-{uuid.uuid4()}"
    incoming_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    headers = {
        "X-Request-ID": client_request_id,
        "traceparent": incoming_traceparent,
    }

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            elif method == "POST":
                response = client.post(endpoint, json=request_body, headers=headers)
            else:
                pytest.fail(f"Unsupported test method: {method}")

    assert response.status_code == 200
    assert response.headers.get("x-request-id") == client_request_id
    assert len(sent_requests) == 1

    downstream_req = sent_requests[0]
    downstream_headers = downstream_req.headers

    # Verify X-Request-ID propagation
    assert downstream_headers.get("x-request-id") == client_request_id

    # Verify W3C traceparent propagation
    propagated_traceparent = downstream_headers.get("traceparent")
    assert propagated_traceparent, "traceparent must be present on downstream call"
    # The trace ID should be preserved from the incoming traceparent
    assert "4bf92f3577b34da6a3ce929d0e0e4736" in propagated_traceparent

    # Verify caller identity
    assert downstream_headers.get("x-caller-service") == "api-gateway"


def test_request_id_generated_when_missing():
    """Verify that when client omits X-Request-ID, the gateway generates a valid UUID and propagates it."""
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={"ok": True}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/analytics/kpis")
            assert resp.status_code == 200

    assert len(sent_requests) == 1
    downstream_id = sent_requests[0].headers.get("x-request-id")
    client_resp_id = resp.headers.get("x-request-id")

    assert downstream_id, "Generated X-Request-ID must be forwarded downstream"
    assert downstream_id == client_resp_id
    # Validate UUID format
    uuid.UUID(downstream_id)


# ---------------------------------------------------------------------------
# 5. Method, Body, and Query Parameter Preservation
# ---------------------------------------------------------------------------

def test_post_goods_receipts_preserves_body_and_method():
    """Verify that POST /api/v1/inventory/goods-receipts sends the exact request body downstream to port 8001."""
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(201, json={"receipt_id": "GR-001"}, request=request)

    payload = {
        "po_number": "PO-2026-000123",
        "supplier_id": "SUP-00045",
        "warehouse_id": "WH-BLR-01",
        "items": [{"sku_id": "SKU-000123", "received_quantity": 100}],
    }

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.post("/api/v1/inventory/goods-receipts", json=payload)
            assert resp.status_code == 201

    assert len(sent_requests) == 1
    req = sent_requests[0]
    assert req.method == "POST"
    assert str(req.url) == "http://localhost:8001/api/v1/inventory/goods-receipts"
    assert json.loads(req.content.decode("utf-8")) == payload
    assert "application/json" in req.headers.get("content-type", "")


def test_query_parameters_preserved_downstream():
    """Verify that complex query strings are completely forwarded to the target service."""
    sent_requests: list[httpx.Request] = []

    async def fake_send(request: httpx.Request, *args, **kwargs):
        sent_requests.append(request)
        return httpx.Response(200, json={}, request=request)

    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/api/v1/demand/forecast/SKU-000123?horizon=30&warehouse_id=WH-BLR-01&confidence=0.8")
            assert resp.status_code == 200

    assert len(sent_requests) == 1
    downstream_url = str(sent_requests[0].url)
    assert "horizon=30" in downstream_url
    assert "warehouse_id=WH-BLR-01" in downstream_url
    assert "confidence=0.8" in downstream_url


# ---------------------------------------------------------------------------
# 6. WebSocket Proxying for Analytics Real-Time Endpoint
# ---------------------------------------------------------------------------

class MockDownstreamWebSocket:
    """Mock downstream WebSocket for bidirectional proxy verification."""

    def __init__(self):
        self.sent_to_downstream: list[str | bytes] = []
        self.incoming_from_downstream: asyncio.Queue[str | bytes] = asyncio.Queue()
        self.subprotocol: str | None = None
        self.closed: bool = False

    async def send(self, data: str | bytes):
        self.sent_to_downstream.append(data)

    async def __aiter__(self):
        while not self.closed:
            try:
                msg = await asyncio.wait_for(self.incoming_from_downstream.get(), timeout=0.1)
                yield msg
            except (asyncio.TimeoutError, asyncio.CancelledError):
                break

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True


def test_websocket_proxy_analytics_realtime_bidirectional():
    """
    Verify WebSocket proxying for WS /api/v1/analytics/kpis/real-time:
    - Target URL converted to ws://
    - Query parameters preserved (?token=...)
    - Headers propagated (x-request-id, traceparent, x-caller-service)
    - Bidirectional message transmission (client->downstream and downstream->client).
    """
    mock_ws = MockDownstreamWebSocket()
    captured_connect_urls: list[str] = []
    captured_extra_headers: list[dict] = []

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        captured_connect_urls.append(uri)
        headers = kwargs.get("extra_headers") or kwargs.get("additional_headers") or {}
        captured_extra_headers.append(headers)
        # Send an initial welcome alert from downstream
        await mock_ws.incoming_from_downstream.put(
            json.dumps({"event_id": "evt-001", "type": "kpi.update", "value": 98.5})
        )
        try:
            yield mock_ws
        finally:
            await mock_ws.close()

    incoming_traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect(
                "/api/v1/analytics/kpis/real-time?token=test_jwt_bearer_token",
                headers={
                    "X-Request-ID": "ws-req-corr-456",
                    "traceparent": incoming_traceparent,
                },
            ) as ws:
                # 1. Receive message from downstream
                received_msg = ws.receive_text()
                parsed = json.loads(received_msg)
                assert parsed["event_id"] == "evt-001"
                assert parsed["type"] == "kpi.update"

                # 2. Send message from client to downstream
                client_msg = json.dumps({"type": "ping", "timestamp": "2026-10-16T10:00:00Z"})
                ws.send_text(client_msg)

    # Verify downstream connection URL
    assert len(captured_connect_urls) == 1
    assert captured_connect_urls[0] == "ws://localhost:8008/api/v1/analytics/kpis/real-time?token=test_jwt_bearer_token"

    # Verify headers sent to downstream WebSocket
    headers_sent = captured_extra_headers[0]
    assert headers_sent.get("x-request-id") == "ws-req-corr-456"
    assert headers_sent.get("x-caller-service") == "api-gateway"

    # Verify W3C traceparent propagation (trace ID preserved from incoming header)
    ws_traceparent = headers_sent.get("traceparent")
    assert ws_traceparent, "traceparent must be present on downstream WebSocket call"
    assert "4bf92f3577b34da6a3ce929d0e0e4736" in ws_traceparent

    # Verify downstream received client's ping message
    assert len(mock_ws.sent_to_downstream) == 1
    assert json.loads(mock_ws.sent_to_downstream[0])["type"] == "ping"


def test_websocket_proxy_generates_correlation_and_traceparent_when_missing():
    """Verify WebSocket proxying generates a valid UUID for X-Request-ID and injects W3C traceparent when omitted."""
    mock_ws = MockDownstreamWebSocket()
    captured_extra_headers: list[dict] = []

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        headers = kwargs.get("extra_headers") or kwargs.get("additional_headers") or {}
        captured_extra_headers.append(headers)
        yield mock_ws

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/analytics/kpis/real-time") as ws:
                pass

    assert len(captured_extra_headers) == 1
    headers_sent = captured_extra_headers[0]
    ws_req_id = headers_sent.get("x-request-id")
    assert ws_req_id, "Generated X-Request-ID must be present"
    uuid.UUID(ws_req_id)

    ws_traceparent = headers_sent.get("traceparent")
    assert ws_traceparent, "Generated W3C traceparent must be present"
    assert ws_traceparent.startswith("00-")


def test_websockets_connect_header_argument_matches_installed_version():
    """Verify websockets.connect receives the correct header kwarg according to the installed websockets version."""
    import inspect
    import websockets

    sig = inspect.signature(websockets.connect)
    expected_kwarg = "additional_headers" if "additional_headers" in sig.parameters else "extra_headers"

    mock_ws = MockDownstreamWebSocket()
    captured_kwargs: list[dict] = []

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        captured_kwargs.append(kwargs)
        yield mock_ws

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/analytics/kpis/real-time") as ws:
                pass

    assert len(captured_kwargs) == 1
    assert expected_kwarg in captured_kwargs[0], f"Expected {expected_kwarg} in websockets.connect arguments"
    assert captured_kwargs[0].get("open_timeout") == 5.0


def test_websocket_proxy_unknown_route_closed():
    """Verify that attempting to connect via WebSocket to an unknown route closes with code 1008."""
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/nonexistent/ws") as ws:
                ws.receive_text()
        assert exc_info.value.code == 1008
        assert exc_info.value.reason == "Service not found for the requested path."


def test_websocket_not_on_allowlist_is_closed():
    """A non-allowlisted path closes with code 1008; no downstream connection is opened."""
    with patch("websockets.connect") as mock_connect:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/inventory/optimization/recommendations") as ws:
                    ws.receive_text()
            assert exc_info.value.code == 1008
            assert exc_info.value.reason == "Service not found for the requested path."

        mock_connect.assert_not_called()


def test_websocket_proxy_rejects_non_allowlisted_known_http_routes():
    """
    Verify that known gateway HTTP routes or non-allowlisted routes are rejected
    when connected to via WebSocket with close code 1008, and no downstream connection is opened.
    """
    non_allowlisted_paths = [
        "/api/v1/inventory/optimization/recommendations",
        "/api/v1/demand/forecast/SKU-000123",
        "/api/v1/purchase-orders/PO-100",
        "/api/v1/suppliers/SUP-00045/risk-score",
        "/api/v1/analytics/kpis",
    ]
    with patch("websockets.connect") as mock_connect:
        with TestClient(app) as client:
            for path in non_allowlisted_paths:
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    with client.websocket_connect(path) as ws:
                        ws.receive_text()
                assert exc_info.value.code == 1008
                assert exc_info.value.reason == "Service not found for the requested path."

        mock_connect.assert_not_called()


def test_websocket_proxy_open_timeout_configuration():
    """Verify that websockets.connect receives open_timeout=5.0 by default and custom values when configured."""
    mock_ws = MockDownstreamWebSocket()
    captured_kwargs: list[dict] = []

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        captured_kwargs.append(kwargs)
        yield mock_ws

    # 1. Default open_timeout (5.0s)
    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/analytics/kpis/real-time") as ws:
                pass

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0].get("open_timeout") == 5.0

    # 2. Custom open_timeout configuration
    captured_kwargs.clear()
    with patch("websockets.connect", side_effect=fake_ws_connect):
        with patch.object(settings, "WEBSOCKET_OPEN_TIMEOUT_SECONDS", 10.0):
            with TestClient(app) as client:
                with client.websocket_connect("/api/v1/analytics/kpis/real-time") as ws:
                    pass

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0].get("open_timeout") == 10.0


# ---------------------------------------------------------------------------
# WebSocket Authentication Precheck (Fix 1)
# ---------------------------------------------------------------------------

class DummyWebSocket:
    def __init__(self, headers: dict | None = None, query_params: dict | None = None):
        self.headers = headers or {}
        self.query_params = query_params or {}


def test_extract_websocket_token_order_and_formats():
    """Verify token extraction order: Authorization header -> ?token= -> Sec-WebSocket-Protocol."""
    # 1. Authorization header (Bearer scheme)
    ws1 = DummyWebSocket(headers={"Authorization": "Bearer token_from_header"})
    assert _extract_websocket_token(ws1) == "token_from_header"

    # Lowercase authorization header
    ws1_lower = DummyWebSocket(headers={"authorization": "Bearer token_from_header_lower"})
    assert _extract_websocket_token(ws1_lower) == "token_from_header_lower"

    # 2. Query parameter (?token=)
    ws2 = DummyWebSocket(query_params={"token": "token_from_query"})
    assert _extract_websocket_token(ws2) == "token_from_query"

    # 3. Sec-WebSocket-Protocol (bearer, <token>)
    ws3 = DummyWebSocket(headers={"Sec-WebSocket-Protocol": "bearer, token_from_subprotocol"})
    assert _extract_websocket_token(ws3) == "token_from_subprotocol"

    # Precedence: Header over query over subprotocol
    ws_all = DummyWebSocket(
        headers={
            "Authorization": "Bearer header_token",
            "Sec-WebSocket-Protocol": "bearer, subproto_token",
        },
        query_params={"token": "query_token"},
    )
    assert _extract_websocket_token(ws_all) == "header_token"

    ws_query_and_sub = DummyWebSocket(
        headers={"Sec-WebSocket-Protocol": "bearer, subproto_token"},
        query_params={"token": "query_token"},
    )
    assert _extract_websocket_token(ws_query_and_sub) == "query_token"

    # Return None when missing or invalid
    assert _extract_websocket_token(DummyWebSocket()) is None
    assert _extract_websocket_token(DummyWebSocket(headers={"Authorization": "Basic 12345"})) is None
    assert _extract_websocket_token(DummyWebSocket(query_params={"token": "   "})) is None
    assert _extract_websocket_token(DummyWebSocket(headers={"Sec-WebSocket-Protocol": "mqtt"})) is None


def test_websocket_rejected_without_token_when_auth_precheck_enabled(monkeypatch):
    """Missing token is rejected with close code 4401; downstream is never opened."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    with patch("websockets.connect") as mock_ws_connect:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/analytics/kpis/real-time") as ws:
                    ws.receive_text()

            assert exc_info.value.code == 4401
            assert exc_info.value.reason == "Unauthorized"
            mock_ws_connect.assert_not_called()


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_rejected_when_platform_rejects_token(mock_post, monkeypatch):
    """Platform /verify returns HTTP 401; WebSocket closes with code 4401; downstream not opened."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"detail": "Invalid or expired token"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    with patch("websockets.connect") as mock_ws_connect:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=bad.jwt.token") as ws:
                    ws.receive_text()

            assert exc_info.value.code == 4401
            assert exc_info.value.reason == "Unauthorized"
            mock_ws_connect.assert_not_called()
            mock_post.assert_called_once()
            call_headers = mock_post.call_args[1].get("headers", {})
            assert call_headers.get("Authorization") == "Bearer bad.jwt.token"


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_query_token_is_verified_with_platform(mock_post, monkeypatch):
    """?token=good.jwt is sent to Platform /verify as Bearer good.jwt; valid token allows downstream proxying."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"valid": True, "user_id": 100},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    mock_ws = MockDownstreamWebSocket()

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        await mock_ws.incoming_from_downstream.put(json.dumps({"event": "connected"}))
        try:
            yield mock_ws
        finally:
            await mock_ws.close()

    with patch("websockets.connect", side_effect=fake_ws_connect) as mock_ws_connect:
        with TestClient(app) as client:
            with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=good.jwt") as ws:
                msg = json.loads(ws.receive_text())
                assert msg == {"event": "connected"}

    mock_post.assert_called_once()
    call_headers = mock_post.call_args[1].get("headers", {})
    assert call_headers.get("Authorization") == "Bearer good.jwt"


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_token_from_authorization_header_proxied(mock_post, monkeypatch):
    """Token extraction from Authorization header is sent to /verify and proxied."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"valid": True, "user_id": 101},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    mock_ws = MockDownstreamWebSocket()

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        await mock_ws.incoming_from_downstream.put(json.dumps({"status": "ok"}))
        try:
            yield mock_ws
        finally:
            await mock_ws.close()

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect(
                "/api/v1/analytics/kpis/real-time",
                headers={"Authorization": "Bearer header.valid.jwt"},
            ) as ws:
                msg = json.loads(ws.receive_text())
                assert msg == {"status": "ok"}

    mock_post.assert_called_once()
    call_headers = mock_post.call_args[1].get("headers", {})
    assert call_headers.get("Authorization") == "Bearer header.valid.jwt"


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_token_from_sec_websocket_protocol_proxied(mock_post, monkeypatch):
    """Token extraction from Sec-WebSocket-Protocol is sent to /verify and proxied."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"valid": True, "user_id": 102},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    mock_ws = MockDownstreamWebSocket()

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        await mock_ws.incoming_from_downstream.put(json.dumps({"status": "ok_proto"}))
        try:
            yield mock_ws
        finally:
            await mock_ws.close()

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with TestClient(app) as client:
            with client.websocket_connect(
                "/api/v1/analytics/kpis/real-time",
                subprotocols=["bearer", "subproto.valid.jwt"],
            ) as ws:
                msg = json.loads(ws.receive_text())
                assert msg == {"status": "ok_proto"}

    mock_post.assert_called_once()
    call_headers = mock_post.call_args[1].get("headers", {})
    assert call_headers.get("Authorization") == "Bearer subproto.valid.jwt"


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_precheck_platform_error_returns_1013(mock_post, monkeypatch):
    """Platform /verify error (503/504) closes connection with code 1013 and Try again later."""
    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)

    mock_post.return_value = httpx.Response(
        status_code=503,
        json={"detail": "Service unavailable"},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    with patch("websockets.connect") as mock_ws_connect:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/v1/analytics/kpis/real-time?token=any.token") as ws:
                    ws.receive_text()

            assert exc_info.value.code == 1013
            assert exc_info.value.reason == "Try again later"
            mock_ws_connect.assert_not_called()


def test_websocket_failure_log_does_not_contain_token(caplog):
    """
    Simulated downstream failure closes with code 1011;
    captured logs do not contain the secret token or sensitive query parameters,
    even if downstream connection exception message includes them.
    """
    import logging

    synthetic_token = "synthetic_secret_token_123"
    sensitive_param = "top_secret_api_key_456"
    raw_query = f"token={synthetic_token}&api_key={sensitive_param}&filter=active"

    # Exception simulating downstream error containing full raw URL with secret token & query
    failing_exc = Exception(
        f"Failed to connect to ws://localhost:8008/api/v1/analytics/kpis/real-time?{raw_query}"
    )

    with patch("websockets.connect", side_effect=failing_exc):
        with caplog.at_level(logging.WARNING, logger="api_gateway.proxy"):
            with TestClient(app) as client:
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    with client.websocket_connect(f"/api/v1/analytics/kpis/real-time?{raw_query}") as ws:
                        ws.receive_text()

                assert exc_info.value.code == 1011
                assert exc_info.value.reason == "Downstream service unavailable"

    # Verify secret token and sensitive query parameter are NOT leaked in any log record
    assert synthetic_token not in caplog.text
    assert sensitive_param not in caplog.text
    assert "api_key" not in caplog.text
    # Verify the sanitized URL is logged
    assert "ws://localhost:8008/api/v1/analytics/kpis/real-time" in caplog.text
    assert "Downstream WebSocket connection failed" in caplog.text


@patch("httpx.AsyncClient.post", new_callable=AsyncMock)
def test_websocket_downstream_failure_with_precheck_sanitizes_token_in_logs(mock_post, monkeypatch, caplog):
    """
    Verify token and sensitive query parameter redaction in WebSocket downstream error log
    when precheck is enabled and downstream connection raises an exception containing secrets.
    """
    import logging

    monkeypatch.setattr(settings, "AUTH_PRECHECK_ENABLED", True)
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"valid": True, "user_id": 999},
        request=httpx.Request("POST", "http://localhost:8005/api/v1/auth/verify"),
    )

    synthetic_token = "synthetic_precheck_token_789"
    sensitive_param = "super_confidential_param_999"
    raw_query = f"token={synthetic_token}&secret_param={sensitive_param}"

    failing_exc = Exception(f"Connection refused with {raw_query}")

    with patch("websockets.connect", side_effect=failing_exc):
        with caplog.at_level(logging.WARNING, logger="api_gateway.proxy"):
            with TestClient(app) as client:
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    with client.websocket_connect(f"/api/v1/analytics/kpis/real-time?{raw_query}") as ws:
                        ws.receive_text()

                assert exc_info.value.code == 1011
                assert exc_info.value.reason == "Downstream service unavailable"

    assert synthetic_token not in caplog.text
    assert sensitive_param not in caplog.text
    assert "secret_param" not in caplog.text
    assert "ws://localhost:8008/api/v1/analytics/kpis/real-time" in caplog.text
    assert "Downstream WebSocket connection failed" in caplog.text


def test_websocket_streaming_exception_debug_log_does_not_contain_sensitive_details(caplog):
    """
    Verify that exceptions inside client_to_downstream and downstream_to_client
    log only the exception type and do not leak sensitive tokens or query parameters.
    """
    import logging

    mock_ws = MockDownstreamWebSocket()
    synthetic_token = "synthetic_stream_token_456"

    async def bad_send(msg):
        raise ValueError(f"Corrupt payload containing {synthetic_token} and secret_key=classified")

    mock_ws.send = bad_send

    @asynccontextmanager
    async def fake_ws_connect(uri: str, **kwargs):
        try:
            yield mock_ws
        finally:
            await mock_ws.close()

    with patch("websockets.connect", side_effect=fake_ws_connect):
        with caplog.at_level(logging.DEBUG, logger="api_gateway.proxy"):
            with TestClient(app) as client:
                with client.websocket_connect(f"/api/v1/analytics/kpis/real-time?token={synthetic_token}") as ws:
                    ws.send_text('{"type": "ping"}')

    assert synthetic_token not in caplog.text
    assert "classified" not in caplog.text
    assert "secret_key" not in caplog.text
    assert "ValueError" in caplog.text


def test_safe_websocket_exception_detail_redacts_sensitive_info():
    """
    Unit test for _safe_websocket_exception_detail ensuring tokens, URLs,
    and sensitive parameters are redacted to exception type name.
    """
    raw_url = "ws://localhost:8008/api/v1/analytics/kpis/real-time?token=secret123&key=456"

    # 1. Exception containing raw target URL
    exc1 = Exception(f"Failed to connect to {raw_url}")
    assert _safe_websocket_exception_detail(exc1, target_url=raw_url) == "Exception"

    # 2. Exception containing raw query
    exc2 = Exception("Handshake error with query token=secret123&key=456")
    assert _safe_websocket_exception_detail(exc2, query="token=secret123&key=456") == "Exception"

    # 3. Exception containing token
    exc3 = Exception("Authentication token secret123 expired")
    assert _safe_websocket_exception_detail(exc3, token="secret123") == "Exception"

    # 4. Exception containing sensitive keywords
    exc4 = ValueError("Invalid bearer token passed")
    assert _safe_websocket_exception_detail(exc4) == "ValueError"

    # 5. Safe exception preserves message
    exc5 = ConnectionRefusedError("Connection refused")
    assert _safe_websocket_exception_detail(exc5) == "Connection refused"



# ---------------------------------------------------------------------------
# 7. Error Handling and Unknown Routes
# ---------------------------------------------------------------------------

def test_unknown_http_route_returns_404():
    """Verify that HTTP requests to unregistered route prefixes return 404."""
    with TestClient(app) as client:
        resp = client.get("/api/v1/unknown-service-path/test")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Service not found for the requested path."}


def test_downstream_service_unavailable_returns_503():
    """Verify that connection failure to downstream microservice returns 503."""
    with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=httpx.ConnectError("Connection refused"))):
        with TestClient(app) as client:
            resp = client.get("/api/v1/demand/forecast/SKU-000123")
            assert resp.status_code == 503
            assert "unavailable" in resp.json().get("error", "").lower()


# ---------------------------------------------------------------------------
# 8. Configuration Precedence & Synchronization
# ---------------------------------------------------------------------------

def test_config_precedence_and_url_synchronization():
    """
    Verify Settings precedence:
    1. Individual service URLs populate SERVICE_ROUTES when not explicitly overridden.
    2. Explicit SERVICE_ROUTES takes precedence over default or individual URLs.
    """
    # Case 1: Custom service URL updates route mapping
    custom_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        DEMAND_FORECAST_SERVICE_URL="http://forecast-host:9999",
        ANALYTICS_SERVICE_URL="http://analytics-host:8888",
    )
    assert custom_settings.SERVICE_ROUTES["/api/v1/demand"] == "http://forecast-host:9999"
    assert custom_settings.SERVICE_ROUTES["/api/v1/analytics"] == "http://analytics-host:8888"

    # Case 2: Explicit SERVICE_ROUTES takes precedence
    override_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        DEMAND_FORECAST_SERVICE_URL="http://forecast-host:9999",
        SERVICE_ROUTES={"/api/v1/demand": "http://override-host:1234"},
    )
    assert override_settings.SERVICE_ROUTES["/api/v1/demand"] == "http://override-host:1234"

    # Case 3: Goods Receipts is not a dedicated entry in SERVICE_ROUTES and follows INVENTORY_SERVICE_URL
    inv_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        INVENTORY_SERVICE_URL="http://inv-host:8001",
    )
    assert inv_settings.SERVICE_ROUTES["/api/v1/inventory"] == "http://inv-host:8001"
    assert "/api/v1/inventory/goods-receipts" not in inv_settings.SERVICE_ROUTES
    assert not hasattr(inv_settings, "GOODS_RECEIPTS_SERVICE_URL")

    # Case 4: Changing SUPPLIER_RISK_SERVICE_URL updates /api/v1/supplier-risk
    # without moving Supplier Portal routes away from PURCHASE_ORDERS_SERVICE_URL
    supplier_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        PURCHASE_ORDERS_SERVICE_URL="http://portal-host:8004",
        SUPPLIER_RISK_SERVICE_URL="http://custom-risk-host:9006",
    )
    assert supplier_settings.SERVICE_ROUTES["/api/v1/supplier-risk"] == "http://custom-risk-host:9006"
    assert supplier_settings.SERVICE_ROUTES["/api/v1/suppliers"] == "http://portal-host:8004"
    assert supplier_settings.SERVICE_ROUTES["/api/v1/purchase-orders"] == "http://portal-host:8004"
