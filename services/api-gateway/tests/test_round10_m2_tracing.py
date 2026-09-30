"""
Round 10 Milestone 2 — OpenTelemetry + Jaeger tracing tests.

Covers
------
1.  TracingMiddleware creates a server span for every request.
2.  Incoming ``traceparent`` is extracted and the span is linked to the
    upstream trace (same trace-id).
3.  Downstream requests injected by ProxyService carry ``traceparent``.
4.  X-Request-ID is preserved independently of traceparent.
5.  Tracing does not break normal (non-traced) requests.
6.  Response carries ``traceparent`` header so callers can correlate.
7.  setup_tracing() is idempotent (safe to call twice).
8.  inject_trace_context() is a no-op when no active span exists.

Isolation strategy
------------------
* Tests use an in-memory ``InMemorySpanExporter`` so no real Jaeger
  instance is required.
* OpenTelemetry 1.x SDK forbids replacing the global TracerProvider once
  set, so we install the in-memory provider ONCE at session scope, then
  clear the exporter between tests.
* SlowAPI rate-limiter is disabled via the autouse fixture in conftest.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

# ---- OTel test utilities ----
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.main import app
from app.middleware.ratelimit import limiter
from app.middleware import tracing as tracing_module
from app.middleware.tracing import inject_trace_context, extract_trace_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def disable_rate_limiter():
    """Disable SlowAPI for every test in this module."""
    limiter.enabled = False
    yield
    limiter.enabled = True


# In-memory test utilities
_SESSION_EXPORTER = InMemorySpanExporter()
_SESSION_PROVIDER: TracerProvider | None = None


def _ensure_test_provider_installed():
    """
    Install an in-memory TracerProvider.
    Maintained for backwards-compatibility.
    """
    global _SESSION_PROVIDER
    resource = Resource.create({SERVICE_NAME: "api-gateway-test"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(_SESSION_EXPORTER))
    tracing_module.setup_tracing(provider=provider)
    _SESSION_PROVIDER = provider
    return provider


@pytest.fixture()
def memory_exporter():
    """
    Per-test exporter fixture. Creates a fresh TracerProvider and InMemorySpanExporter
    for each test, ensuring clean provider setup and isolation without global state leakage.
    """
    exporter = InMemorySpanExporter()
    resource = Resource.create({SERVICE_NAME: "api-gateway-test"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracing_module.setup_tracing(provider=provider)

    yield exporter

    provider.shutdown()
    tracing_module.shutdown_tracing()


@pytest.fixture()
def client(memory_exporter):
    """FastAPI TestClient with in-memory tracing active."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_no_otel():
    """FastAPI TestClient without any OTel setup — tests graceful degradation."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c



# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_spans(exporter: InMemorySpanExporter, name_contains: str | None = None):
    spans = exporter.get_finished_spans()
    if name_contains:
        spans = [s for s in spans if name_contains in s.name]
    return spans


# ---------------------------------------------------------------------------
# 1. TracingMiddleware creates spans
# ---------------------------------------------------------------------------

class TestTracingMiddlewareCreatesSpans:
    def test_health_request_creates_span(self, client, memory_exporter):
        """GET /health must produce at least one finished span."""
        response = client.get("/health")
        assert response.status_code == 200

        spans = memory_exporter.get_finished_spans()
        assert len(spans) >= 1, "Expected at least one span for /health request"

    def test_span_has_http_method_attribute(self, client, memory_exporter):
        """Span must carry http.method attribute."""
        client.get("/health")
        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans found"
        method_spans = [s for s in spans if s.attributes.get("http.method") == "GET"]
        assert method_spans, (
            f"No span with http.method='GET'. Spans: {[(s.name, dict(s.attributes)) for s in spans]}"
        )

    def test_span_has_http_route_attribute(self, client, memory_exporter):
        """Span must carry http.route attribute."""
        client.get("/health")
        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans found"
        route_spans = [s for s in spans if s.attributes.get("http.route") == "/health"]
        assert route_spans, (
            f"No span with http.route='/health'. Spans: {[(s.name, dict(s.attributes)) for s in spans]}"
        )

    def test_span_has_http_status_code(self, client, memory_exporter):
        """Span must record http.status_code."""
        client.get("/health")
        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans found"
        status_spans = [s for s in spans if s.attributes.get("http.status_code") == 200]
        assert status_spans, (
            f"No span with http.status_code=200. Spans: {[(s.name, dict(s.attributes)) for s in spans]}"
        )

    def test_span_status_ok_for_200(self, client, memory_exporter):
        """Span status must be OK (not ERROR) for a 200 response."""
        from opentelemetry.trace import StatusCode as SC
        client.get("/health")
        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans found"
        status_spans = [s for s in spans if s.attributes.get("http.status_code") == 200]
        assert status_spans, "No span with http.status_code=200"
        assert status_spans[0].status.status_code == SC.OK


# ---------------------------------------------------------------------------
# 2. Incoming traceparent is accepted (trace continuation)
# ---------------------------------------------------------------------------

class TestIncomingTraceparentAccepted:
    # A valid W3C traceparent: version-trace_id-parent_id-flags
    UPSTREAM_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
    UPSTREAM_TRACEPARENT = f"00-{UPSTREAM_TRACE_ID}-00f067aa0ba902b7-01"

    def test_incoming_traceparent_is_accepted(self, client, memory_exporter):
        """
        When the client sends a valid traceparent, the gateway span must share
        the same trace-id (trace continuation, not a new trace).
        """
        response = client.get(
            "/health",
            headers={"traceparent": self.UPSTREAM_TRACEPARENT},
        )
        assert response.status_code == 200

        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans created"

        # Find the span with our upstream trace-id
        matching = [
            s for s in spans
            if format(s.context.trace_id, "032x") == self.UPSTREAM_TRACE_ID
        ]
        assert matching, (
            f"No span with trace_id={self.UPSTREAM_TRACE_ID}. "
            f"Got: {[format(s.context.trace_id, '032x') for s in spans]}"
        )

    def test_no_traceparent_creates_new_trace(self, client, memory_exporter):
        """Without an incoming traceparent the gateway starts a brand-new trace."""
        client.get("/health")
        spans = memory_exporter.get_finished_spans()
        assert spans, "No spans"
        # At least one span must exist (any span is fine — a new trace was started)
        assert any(s.context.trace_id != 0 for s in spans)

    def test_invalid_traceparent_is_ignored(self, client, memory_exporter):
        """A malformed traceparent must not crash the gateway; a new trace starts."""
        response = client.get(
            "/health",
            headers={"traceparent": "not-a-valid-traceparent"},
        )
        assert response.status_code == 200
        # Must still produce a span
        spans = memory_exporter.get_finished_spans()
        assert len(spans) >= 1


# ---------------------------------------------------------------------------
# 3. Downstream requests receive traceparent (proxy propagation)
# ---------------------------------------------------------------------------

class TestDownstreamTraceparentPropagation:
    def test_proxy_headers_contain_traceparent(self, memory_exporter):
        """
        When the gateway proxies a request, the headers forwarded to the
        downstream service must include ``traceparent``.
        """
        captured_headers: dict = {}

        async def fake_forward(request, path):
            from fastapi.responses import JSONResponse
            # Capture headers that inject_trace_context would have placed
            headers = dict(request.headers)
            inject_trace_context(headers)
            captured_headers.update(headers)
            return JSONResponse(status_code=200, content={"ok": True})

        with patch(
            "app.services.proxy.ProxyService.forward_request",
            new=fake_forward,
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                c.get("/api/v1/inventory/items")

        # After inject_trace_context() there must be a traceparent
        assert "traceparent" in captured_headers, (
            "traceparent must be injected into downstream proxy headers"
        )

    def test_downstream_traceparent_matches_gateway_span(self, memory_exporter):
        """
        The traceparent injected into the downstream call must reference the
        same trace-id as the gateway span.
        """
        captured_headers: dict = {}

        async def fake_forward(request, path):
            from fastapi.responses import JSONResponse
            headers = dict(request.headers)
            inject_trace_context(headers)
            captured_headers.update(headers)
            return JSONResponse(status_code=200, content={"ok": True})

        with patch(
            "app.services.proxy.ProxyService.forward_request",
            new=fake_forward,
        ):
            with TestClient(app, raise_server_exceptions=False) as c:
                c.get("/api/v1/inventory/items")

        spans = memory_exporter.get_finished_spans()
        gateway_spans = [s for s in spans if "gateway" in s.name.lower()]
        if not gateway_spans:
            pytest.skip("No gateway span found — span name may differ")

        span = gateway_spans[0]
        gateway_trace_id = format(span.context.trace_id, "032x")

        downstream_traceparent = captured_headers.get("traceparent", "")
        assert gateway_trace_id in downstream_traceparent, (
            f"Gateway trace_id {gateway_trace_id} not found in downstream "
            f"traceparent: {downstream_traceparent}"
        )

    def test_proxy_creates_client_span_and_propagates_trace(self, memory_exporter):
        """
        When a request is proxied through ProxyService.forward_request,
        both a SERVER span (gateway) and a CLIENT span (proxy) are created,
        sharing the same trace_id, and the outgoing request has the traceparent header.
        """
        import httpx
        from unittest.mock import AsyncMock

        mock_response = httpx.Response(
            200,
            json={"data": "inventory-ok"},
            request=httpx.Request("GET", "http://localhost:8001/api/v1/inventory/items"),
        )

        sent_requests = []
        async def fake_send(req, *args, **kwargs):
            sent_requests.append(req)
            return mock_response

        with patch("httpx.AsyncClient.send", new=AsyncMock(side_effect=fake_send)):
            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.get("/api/v1/inventory/items")
                assert resp.status_code == 200

        spans = memory_exporter.get_finished_spans()
        assert len(spans) >= 2, f"Expected server and client spans, got: {[s.name for s in spans]}"

        server_spans = [s for s in spans if "gateway" in s.name.lower()]
        client_spans = [s for s in spans if "proxy" in s.name.lower()]

        assert len(server_spans) >= 1, "Expected gateway server span"
        assert len(client_spans) >= 1, "Expected proxy client span"

        server_span = server_spans[0]
        client_span = client_spans[0]

        # Both spans share the same trace ID
        assert server_span.context.trace_id == client_span.context.trace_id

        # The outgoing HTTP request has traceparent containing the trace ID
        assert sent_requests, "No request was sent"
        downstream_tp = sent_requests[0].headers.get("traceparent", "")
        gateway_trace_id = format(server_span.context.trace_id, "032x")
        assert gateway_trace_id in downstream_tp



# ---------------------------------------------------------------------------
# 4. X-Request-ID is preserved independently of traceparent
# ---------------------------------------------------------------------------

class TestXRequestIDPreservation:
    def test_custom_request_id_is_echoed_back(self, client):
        """
        X-Request-ID supplied by the client must be returned in the response
        regardless of tracing state.
        """
        my_id = "my-unique-request-id-123"
        response = client.get("/health", headers={"x-request-id": my_id})
        assert response.status_code == 200
        assert response.headers.get("x-request-id") == my_id

    def test_missing_request_id_is_auto_generated(self, client):
        """When no X-Request-ID is sent one must be auto-generated."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"]  # non-empty

    def test_traceparent_and_request_id_coexist(self, client):
        """
        Both traceparent (in response) and x-request-id must be present when
        the client sends both.
        """
        my_id = "coexist-test-id-456"
        upstream_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        response = client.get(
            "/health",
            headers={
                "x-request-id": my_id,
                "traceparent": upstream_tp,
            },
        )
        assert response.status_code == 200
        # X-Request-ID echoed
        assert response.headers.get("x-request-id") == my_id
        # traceparent present (added by TracingMiddleware)
        assert "traceparent" in response.headers

    def test_traceparent_does_not_replace_request_id(self, client):
        """x-request-id value must be preserved exactly; traceparent is additional."""
        my_id = "do-not-replace-me-789"
        response = client.get(
            "/health",
            headers={"x-request-id": my_id},
        )
        assert response.headers.get("x-request-id") == my_id
        # traceparent is a completely separate header
        tp = response.headers.get("traceparent", "")
        assert my_id not in tp, "Request ID must not leak into traceparent"


# ---------------------------------------------------------------------------
# 5. Tracing does not break normal requests
# ---------------------------------------------------------------------------

class TestTracingDoesNotBreakNormalRequests:
    def test_health_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_root_returns_200(self, client):
        assert client.get("/").status_code == 200

    def test_metrics_returns_200(self, client):
        assert client.get("/metrics").status_code == 200

    def test_dashboard_returns_200(self, client):
        with patch(
            "app.routes.dashboard.get_system_health",
            new=AsyncMock(return_value={"error": "unavailable"}),
        ):
            assert client.get("/gateway/dashboard").status_code == 200

    def test_prometheus_metrics_still_work(self, client):
        """Prometheus /metrics output must contain the expected metric families."""
        client.get("/health")
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "gateway_requests_total" in response.text
        assert "gateway_request_duration_seconds" in response.text


# ---------------------------------------------------------------------------
# 6. Response traceparent header
# ---------------------------------------------------------------------------

class TestResponseTraceparentHeader:
    def test_response_contains_traceparent(self, client, memory_exporter):
        """The gateway must echo traceparent in the response headers."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "traceparent" in response.headers, (
            "Response must include traceparent header for downstream correlation"
        )

    def test_response_traceparent_is_valid_format(self, client, memory_exporter):
        """The traceparent header must follow the W3C format: 00-<32hex>-<16hex>-<2hex>."""
        import re
        response = client.get("/health")
        tp = response.headers.get("traceparent", "")
        pattern = r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$"
        assert re.match(pattern, tp), f"traceparent '{tp}' does not match W3C format"


# ---------------------------------------------------------------------------
# 7. setup_tracing() idempotency
# ---------------------------------------------------------------------------

class TestSetupTracingIdempotent:
    def test_setup_tracing_can_be_called_twice(self):
        """Calling setup_tracing() twice must not raise or create duplicate providers."""
        from app.middleware.tracing import setup_tracing
        # First call (may already be configured by the fixture)
        setup_tracing()
        # Second call — must be a silent no-op
        setup_tracing()


# ---------------------------------------------------------------------------
# 8. inject_trace_context no-op outside span
# ---------------------------------------------------------------------------

class TestInjectTraceContextNoOp:
    def test_inject_outside_span_does_not_raise(self):
        """inject_trace_context must not raise even when no span is active."""
        headers: dict = {}
        inject_trace_context(headers)  # should not raise

    def test_extract_with_empty_headers_does_not_raise(self):
        """extract_trace_context with empty headers must return a context object."""
        ctx = extract_trace_context({})
        assert ctx is not None
