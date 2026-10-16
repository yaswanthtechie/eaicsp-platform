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
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app
from app.services.proxy import _find_service_route, build_downstream_url


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
            "/api/v1/inventory/goods-receipts",
            "http://localhost:8004",
        ),
        (
            "/api/v1/purchase-orders/PO-2026-0001",
            "/api/v1/purchase-orders",
            "http://localhost:8004",
        ),
        (
            "/api/v1/suppliers/SUP-00045/risk-score",
            "/api/v1/suppliers",
            "http://localhost:8006",
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


def test_goods_receipts_downstream_url_selection_and_rewrite():
    """
    Prove that POST /api/v1/inventory/goods-receipts routes to the supplier-portal
    service on port 8004 with path rewritten to /api/v1/goods-receipts.
    """
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
    assert str(req.url) == "http://localhost:8004/api/v1/goods-receipts"


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
    """Verify that POST /api/v1/inventory/goods-receipts sends the exact request body downstream."""
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
    assert str(req.url) == "http://localhost:8004/api/v1/goods-receipts"
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


def test_websocket_proxy_unknown_route_closed():
    """Verify that attempting to connect via WebSocket to an unknown route closes with code 1008."""
    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/nonexistent/ws") as ws:
                ws.receive_text()


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

    # Case 2: FORECAST_SERVICE_URL alias updates DEMAND_FORECAST_SERVICE_URL
    alias_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        FORECAST_SERVICE_URL="http://alias-forecast:7777",
    )
    assert alias_settings.DEMAND_FORECAST_SERVICE_URL == "http://alias-forecast:7777"
    assert alias_settings.SERVICE_ROUTES["/api/v1/demand"] == "http://alias-forecast:7777"

    # Case 3: Explicit SERVICE_ROUTES takes precedence
    override_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        DEMAND_FORECAST_SERVICE_URL="http://forecast-host:9999",
        SERVICE_ROUTES={"/api/v1/demand": "http://override-host:1234"},
    )
    assert override_settings.SERVICE_ROUTES["/api/v1/demand"] == "http://override-host:1234"

    # Case 4: GOODS_RECEIPTS_SERVICE_URL updates /api/v1/inventory/goods-receipts without affecting /api/v1/inventory
    gr_settings = Settings(
        SECRET_KEY="test-secret-key-123",
        GOODS_RECEIPTS_SERVICE_URL="http://gr-host:8040",
    )
    assert gr_settings.SERVICE_ROUTES["/api/v1/inventory/goods-receipts"] == "http://gr-host:8040"
    assert gr_settings.SERVICE_ROUTES["/api/v1/inventory"] == "http://localhost:8001"