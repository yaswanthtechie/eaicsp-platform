"""
Round 10 Milestone 1 — Prometheus instrumentation middleware.

Records every HTTP request passing through the API Gateway into the Prometheus
Counters and Histogram declared in app.services.prometheus_metrics, while
simultaneously feeding the same values into the existing MetricsCollector so
that /gateway/dashboard and /metrics remain consistent.

Skips instrumentation for the /metrics endpoint itself to avoid self-referential
noise in the latency histogram.
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.metrics import metrics_collector, normalize_route
from app.services.prometheus_metrics import (
    ERROR_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
)

# Client-controlled values must never become unbounded label values.
_KNOWN_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that records per-request Prometheus metrics and
    keeps the shared MetricsCollector in sync.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Do not instrument the /metrics scrape endpoint itself.
        if path == "/metrics":
            return await call_next(request)

        method = (
            request.method
            if request.method in _KNOWN_METHODS
            else "OTHER"
        )
        route = normalize_route(path)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Treat unhandled exceptions as 500 errors.
            elapsed = time.perf_counter() - start
            latency_ms = elapsed * 1000.0

            REQUEST_COUNT.labels(method=method, route=route, status_code="500").inc()
            REQUEST_LATENCY.labels(method=method, route=route).observe(elapsed)
            ERROR_COUNT.labels(method=method, route=route).inc()

            metrics_collector.record_request(
                service_name="",
                latency_ms=latency_ms,
                is_error=True,
                status_code=500,
                route=path,
            )
            raise

        elapsed = time.perf_counter() - start
        latency_ms = elapsed * 1000.0
        is_error = status_code >= 500

        REQUEST_COUNT.labels(
            method=method, route=route, status_code=str(status_code)
        ).inc()
        REQUEST_LATENCY.labels(method=method, route=route).observe(elapsed)

        if is_error:
            ERROR_COUNT.labels(method=method, route=route).inc()

        # Keep in-memory MetricsCollector in sync with Prometheus.
        # dashboard.py reads from metrics_collector, so both views stay aligned.
        # Avoid double-counting if downstream proxy already recorded the request.
        req_state = getattr(request, "state", None)
        if not getattr(req_state, "metrics_recorded", False):
            metrics_collector.record_request(
                service_name="",
                latency_ms=latency_ms,
                is_error=is_error,
                status_code=status_code,
                route=path,
            )

        return response
