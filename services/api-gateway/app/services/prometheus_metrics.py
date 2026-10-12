"""
Round 10 Milestone 1 — Prometheus instrumentation for the API Gateway.

Design decisions:
- Uses prometheus_client's CollectorRegistry to avoid polluting the global
  default registry between tests (each test can pass registry=REGISTRY).
- Exposes a module-level REGISTRY and pre-built metric objects so that all
  instrumentation code imports from here instead of declaring metrics ad-hoc.
- Provides helpers to sync Prometheus Gauges from the in-memory MetricsCollector
  so that /gateway/dashboard and /metrics always report the same underlying
  values.

Metrics exported:
  gateway_requests_total{method, route, status_code}   Counter
  gateway_request_duration_seconds{method, route}      Histogram
  gateway_errors_total{method, route}                  Counter
  gateway_circuit_breaker_state{service}               Gauge  (0=closed, 1=half-open, 2=open)
  gateway_cache_hit_rate{service}                      Gauge  (0.0 – 100.0)
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from app.core.config import settings

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

REGISTRY = CollectorRegistry(auto_describe=False)

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "gateway_requests_total",
    "Total number of HTTP requests processed by the API Gateway.",
    labelnames=["method", "route", "status_code"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "gateway_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=["method", "route"],
    # Derived from settings.LATENCY_HISTOGRAM_BUCKETS (converted to seconds)
    buckets=[
        b / 1000.0
        for b in getattr(
            settings,
            "LATENCY_HISTOGRAM_BUCKETS",
            [10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0],
        )
    ],
    registry=REGISTRY,
)

ERROR_COUNT = Counter(
    "gateway_errors_total",
    "Total number of 5xx error responses returned by the API Gateway.",
    labelnames=["method", "route"],
    registry=REGISTRY,
)

CIRCUIT_BREAKER_STATE = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state for each downstream service. 0=closed, 1=half-open, 2=open.",
    labelnames=["service"],
    registry=REGISTRY,
)

CACHE_HIT_RATE = Gauge(
    "gateway_cache_hit_rate",
    "Cache hit rate percentage (0–100) for each downstream service.",
    labelnames=["service"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# State encoder
# ---------------------------------------------------------------------------

_CB_STATE_VALUES: dict[str, float] = {
    "closed": 0.0,
    "half-open": 1.0,
    "open": 2.0,
}


def cb_state_to_float(state: str) -> float:
    """Convert a circuit breaker state string to a numeric Gauge value."""
    return _CB_STATE_VALUES.get(state, 0.0)


# ---------------------------------------------------------------------------
# Sync helpers — pull latest values from MetricsCollector into Prometheus Gauges
# ---------------------------------------------------------------------------

def sync_gauges_from_collector() -> None:
    """
    Read the current in-memory MetricsCollector snapshot and update the
    Prometheus Gauges for circuit breaker state and cache hit rate.

    Called by the /metrics endpoint immediately before generating the
    Prometheus text exposition so that scrapers always get fresh values.
    """
    # Import here to avoid circular imports at module load time.
    from app.services.metrics import metrics_collector  # noqa: PLC0415

    all_metrics = metrics_collector.get_all_metrics()

    for service_name, svc_data in all_metrics.get("services", {}).items():
        # Circuit breaker state
        cb_state = svc_data.get("circuit_breaker_state", "closed")
        CIRCUIT_BREAKER_STATE.labels(service=service_name).set(
            cb_state_to_float(cb_state)
        )

        # Per-service cache hit rate
        hit_rate = svc_data.get("cache_hit_rate", 0.0)
        CACHE_HIT_RATE.labels(service=service_name).set(hit_rate)


def reset_prometheus_metrics() -> None:
    """Clear all in-memory samples from the Prometheus metric objects."""
    REQUEST_COUNT._metrics.clear()
    REQUEST_LATENCY._metrics.clear()
    ERROR_COUNT._metrics.clear()
    CIRCUIT_BREAKER_STATE._metrics.clear()
    CACHE_HIT_RATE._metrics.clear()
