"""
Round 10 Milestone 2 — OpenTelemetry + Jaeger distributed tracing middleware.

Responsibilities
----------------
1. Extract W3C trace context (traceparent / tracestate) from every incoming request.
2. Start a server-side span for the gateway request with useful attributes
   (http.method, http.route, http.url, http.status_code, request_id).
3. Inject the active trace context into the *outgoing* headers dict that
   ProxyService.forward_request passes to downstream services, so the full
   trace propagates through the platform.
4. Preserve X-Request-ID completely independently; both headers must coexist.

Tracer-provider setup
---------------------
Call ``setup_tracing()`` once during application startup (lifespan).  It is
idempotent — calling it a second time is a no-op so tests are safe.

Environment variables (all optional)
-------------------------------------
OTEL_ENABLED               bool   default True   — set False to skip all OTel work
OTEL_SERVICE_NAME          str    default "api-gateway"
OTEL_EXPORTER_OTLP_ENDPOINT str   default "http://localhost:4318"
                                   Jaeger >= 1.35 exposes OTLP/HTTP on this port.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("api_gateway.tracing")

# ---------------------------------------------------------------------------
# Lazy OTel imports — only import when tracing is enabled so the gateway
# remains fully functional even if OTel packages are not installed.
# ---------------------------------------------------------------------------

_otel_available = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.propagate import extract, inject
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.trace import SpanKind, StatusCode
    _otel_available = True
except ImportError:  # pragma: no cover
    logger.warning(
        "opentelemetry packages not installed; tracing middleware is a no-op. "
        "Run: pip install opentelemetry-api opentelemetry-sdk "
        "opentelemetry-exporter-otlp-proto-http"
    )
    class StatusCode:  # type: ignore[no-redef]
        OK = "OK"
        ERROR = "ERROR"
        UNSET = "UNSET"
    class SpanKind:  # type: ignore[no-redef]
        SERVER = 1
        CLIENT = 2


# Module-level active tracer provider and configuration flag
_tracer_provider: TracerProvider | None = None
_tracing_configured = False


def setup_tracing(provider: TracerProvider | None = None) -> None:
    """
    Initialise the OpenTelemetry TracerProvider and wire up the OTLP
    exporter pointing at the local Jaeger instance (or use the provided TracerProvider).

    Safe to call multiple times (idempotent).
    """
    global _tracing_configured, _tracer_provider
    if _tracing_configured and provider is None:
        return
    if not _otel_available:
        return

    from app.core.config import settings  # lazy to avoid circular import

    if not settings.OTEL_ENABLED:
        logger.info("Tracing disabled via OTEL_ENABLED=false")
        _tracing_configured = True
        return

    if provider is not None:
        if _tracer_provider is not None and _tracer_provider is not provider:
            try:
                _tracer_provider.shutdown()
            except Exception:
                pass
        _tracer_provider = provider
    elif _tracer_provider is None:
        resource = Resource.create({SERVICE_NAME: settings.OTEL_SERVICE_NAME})

        endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip('/')
        if not endpoint.endswith('/v1/traces'):
            endpoint = f"{endpoint}/v1/traces"

        exporter = OTLPSpanExporter(endpoint=endpoint)
        _tracer_provider = TracerProvider(resource=resource)
        _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    # Register as the global provider so opentelemetry.trace.get_tracer() works
    try:
        from opentelemetry.util._once import Once
        trace._TRACER_PROVIDER = _tracer_provider
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        trace._TRACER_PROVIDER_SET_ONCE.do_once(lambda: None)
    except Exception:
        pass

    # Set W3C TraceContext (traceparent / tracestate) as the global propagator.
    from opentelemetry.propagate import set_global_textmap
    set_global_textmap(TraceContextTextMapPropagator())

    _tracing_configured = True
    logger.info(
        "OpenTelemetry tracing configured — service=%s endpoint=%s",
        settings.OTEL_SERVICE_NAME,
        settings.OTEL_EXPORTER_OTLP_ENDPOINT if provider is None else "custom",
    )


def shutdown_tracing() -> None:
    """
    Shut down the active TracerProvider and flush/clean up any background
    exporter threads.
    """
    global _tracing_configured, _tracer_provider
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
        except Exception:
            pass
        _tracer_provider = None
    _tracing_configured = False
    if _otel_available:
        try:
            from opentelemetry.util._once import Once
            trace._TRACER_PROVIDER = None
            trace._TRACER_PROVIDER_SET_ONCE = Once()
        except Exception:
            pass


def reset_tracing() -> None:
    """Alias for shutdown_tracing to reset all global tracing state."""
    shutdown_tracing()


def set_tracer_provider(provider: TracerProvider | None) -> None:
    """Set the active TracerProvider directly and sync with OpenTelemetry."""
    global _tracer_provider
    _tracer_provider = provider
    if _otel_available and provider is not None:
        try:
            from opentelemetry.util._once import Once
            trace._TRACER_PROVIDER = provider
            trace._TRACER_PROVIDER_SET_ONCE = Once()
            trace._TRACER_PROVIDER_SET_ONCE.do_once(lambda: None)
        except Exception:
            pass


def get_tracer():
    """Return the named tracer for this service (lazy, safe to call before setup)."""
    if not _otel_available:
        return None
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(
            "api-gateway.middleware.tracing",
            schema_url="https://opentelemetry.io/schemas/1.24.0",
        )
    return trace.get_tracer("api-gateway.middleware.tracing", schema_url="https://opentelemetry.io/schemas/1.24.0")


from contextlib import contextmanager

@contextmanager
def start_proxy_span(method: str, service_name: str, target_url: str):
    """
    Context manager to start a child CLIENT span for downstream proxy calls.
    Gracefully falls back to a no-op if OTel is not available or disabled.
    """
    if not _otel_available:
        yield None
        return
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    span_name = f"proxy {method} {service_name}"
    with tracer.start_as_current_span(span_name, kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.method", method)
        span.set_attribute("http.url", str(target_url))
        span.set_attribute("peer.service", service_name)
        yield span



# ---------------------------------------------------------------------------
# Header carrier helpers for W3C trace-context propagation
# ---------------------------------------------------------------------------

class _DictCarrier(dict):
    """Minimal carrier that satisfies both getter and setter protocols."""
    def get(self, key, default=None):  # type: ignore[override]
        return super().get(key.lower(), default)

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)


def extract_trace_context(headers: dict) -> object:
    """
    Extract W3C traceparent / tracestate from request headers and return an
    OTel Context.  Returns a blank context when tracing is unavailable.
    """
    if not _otel_available:
        return object()
    carrier = _DictCarrier({k.lower(): v for k, v in headers.items()})
    return extract(carrier)


def inject_trace_context(headers: dict) -> None:
    """
    Inject the *current* active trace context (traceparent / tracestate) into
    the provided headers dict so downstream services receive the same trace.
    """
    if not _otel_available:
        return
    inject(headers)


# ---------------------------------------------------------------------------
# Starlette middleware
# ---------------------------------------------------------------------------

class TracingMiddleware(BaseHTTPMiddleware):
    """
    OpenTelemetry tracing middleware for the API Gateway.

    - Extracts incoming W3C traceparent so existing distributed traces continue.
    - Wraps each request in a gateway-level server span.
    - Attaches http.* semantic convention attributes + request_id.
    - Records span status on 5xx errors.
    - Adds ``traceparent`` to the response headers so callers can link traces.

    Note: outgoing traceparent injection into proxy calls is done separately
    inside ProxyService (see app/services/proxy.py).  The middleware sets the
    active span context; the proxy helper calls inject_trace_context() on the
    headers dict it is about to forward.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        # Do NOT cache the tracer at __init__ time — the global TracerProvider may be
        # swapped by tests after app import.  Resolve lazily in dispatch() instead.

    async def dispatch(self, request: Request, call_next: Callable):
        if not _otel_available:
            return await call_next(request)

        # Resolve tracer lazily so test fixtures that replace the TracerProvider work.
        tracer = get_tracer()
        if tracer is None:
            return await call_next(request)

        # Extract incoming W3C trace context (links to upstream caller if present)
        parent_ctx = extract_trace_context(dict(request.headers))

        route = request.url.path
        span_name = f"gateway {request.method} {route}"

        with tracer.start_as_current_span(
            span_name,
            context=parent_ctx,
            kind=SpanKind.SERVER,
        ) as span:
            # Semantic convention attributes (OTel HTTP 1.x)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.route", route)
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.headers.get("host", ""))
            span.set_attribute("http.user_agent", request.headers.get("user-agent", ""))

            # Gateway-specific attributes
            request_id = getattr(request.state, "request_id", None) or \
                         request.headers.get("x-request-id", "")
            if request_id:
                span.set_attribute("gateway.request_id", request_id)

            client_ip = request.client.host if request.client else "unknown"
            span.set_attribute("net.peer.ip", client_ip)

            # Store span context on request.state so proxy.py can access it
            request.state.otel_span = span

            response = await call_next(request)

            raw_status = getattr(response, "status_code", 200)
            if isinstance(raw_status, int) and not isinstance(raw_status, bool):
                status_code = raw_status
            else:
                try:
                    status_code = int(raw_status)
                except (TypeError, ValueError):
                    status_code = 200

            span.set_attribute("http.status_code", status_code)

            if status_code >= 500:
                span.set_status(StatusCode.ERROR, f"HTTP {status_code}")
            else:
                span.set_status(StatusCode.OK)

            post_request_id = getattr(request.state, "request_id", None)
            if post_request_id and not request_id:
                span.set_attribute("gateway.request_id", post_request_id)

            # Propagate traceparent back to the caller in the response
            # (useful for front-ends / API consumers that want to correlate)
            carrier = {}
            inject(carrier)
            if "traceparent" in carrier:
                response.headers["traceparent"] = carrier["traceparent"]
            if "tracestate" in carrier and carrier["tracestate"]:
                response.headers["tracestate"] = carrier["tracestate"]

        return response
