"""
Round 10 Milestone 1 — Prometheus metrics tests.

Covers:
1. GET /metrics returns HTTP 200 with text/plain Prometheus format.
2. gateway_requests_total increments correctly per route and method.
3. gateway_request_duration_seconds histogram is present in output.
4. gateway_errors_total increments on 5xx responses.
5. gateway_circuit_breaker_state Gauge reflects MetricsCollector state.
6. gateway_cache_hit_rate Gauge reflects MetricsCollector cache hit rate.
7. /metrics endpoint itself is not recorded in counters (no self-instrumentation).
8. /gateway/dashboard values are consistent with Prometheus metrics.

Isolation strategy:
  Each test that needs to verify counter values does so via direct assertion
  on the REGISTRY after resetting state. The middleware accumulates into the
  shared module-level metric objects; we therefore reset the in-memory state
  and look at relative increments across each test.

NOTE: prometheus_client Counter/Histogram objects cannot be reset once created
(the prometheus_client library does not support resetting counters in the
production registry). Instead, tests that verify absolute counts call
`metrics_collector.reset()` to clear the MetricsCollector, then read gauge
values, or they parse the /metrics text body for relative checks. Tests that
need exact counts use fresh CollectorRegistry instances populated via helper
functions rather than relying on the global REGISTRY.
"""

import os
import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from unittest.mock import AsyncMock, patch

from app.main import app
from app.middleware.ratelimit import limiter
from app.services.metrics import metrics_collector
from app.services.prometheus_metrics import (
    REGISTRY,
    CIRCUIT_BREAKER_STATE,
    CACHE_HIT_RATE,
    cb_state_to_float,
    sync_gauges_from_collector,
    reset_prometheus_metrics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_METRICS_TOKEN = "test-metrics-bearer-token"
METRICS_AUTH_HEADER = {"Authorization": f"Bearer {TEST_METRICS_TOKEN}"}


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset in-memory MetricsCollector, Prometheus metrics, and configure test token."""
    monkeypatch.setenv("METRICS_BEARER_TOKEN", TEST_METRICS_TOKEN)
    metrics_collector.reset()
    reset_prometheus_metrics()
    limiter.enabled = False
    yield
    metrics_collector.reset()
    reset_prometheus_metrics()
    limiter.enabled = True


@pytest.fixture
def metrics_auth_headers():
    """Return deterministic test-only Bearer authorization headers for /metrics."""
    return METRICS_AUTH_HEADER


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Helper: parse Prometheus text output
# ---------------------------------------------------------------------------

def _parse_metric_names(body: str) -> set[str]:
    """Return all metric family names present in a Prometheus text body."""
    names = set()
    for line in body.splitlines():
        if line.startswith("# HELP "):
            names.add(line.split()[2])
    return names


def _get_sample_value(body: str, metric_name: str, labels: dict[str, str] | None = None) -> float | None:
    """
    Scan the Prometheus text body for a sample matching metric_name and labels.
    Returns the float value or None if not found.
    """
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        # line format: metric_name{labels} value [timestamp]
        if not line.startswith(metric_name):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        label_part = parts[0]
        value_str = parts[1]
        if labels:
            match = all(f'{k}="{v}"' in label_part for k, v in labels.items())
            if not match:
                continue
        try:
            return float(value_str)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 1. /metrics endpoint reachability and format
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        """GET /metrics must return HTTP 200."""
        response = client.get("/metrics", headers=METRICS_AUTH_HEADER)
        assert response.status_code == 200

    def test_metrics_content_type_is_prometheus(self, client):
        """GET /metrics must use Prometheus text content type."""
        response = client.get("/metrics", headers=METRICS_AUTH_HEADER)
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_body_is_not_json(self, client):
        """GET /metrics must not return a JSON object."""
        response = client.get("/metrics", headers=METRICS_AUTH_HEADER)
        assert not response.text.startswith("{")

    def test_metrics_contains_required_metric_families(self, client):
        """All five required Round 10 metric families must appear in the output."""
        response = client.get("/metrics", headers=METRICS_AUTH_HEADER)
        body = response.text
        metric_names = _parse_metric_names(body)

        required = {
            "gateway_requests_total",
            "gateway_request_duration_seconds",
            "gateway_errors_total",
            "gateway_circuit_breaker_state",
            "gateway_cache_hit_rate",
        }
        for name in required:
            assert name in metric_names, f"Missing metric family: {name}"

    def test_metrics_endpoint_is_not_self_counted(self, client):
        """
        Requests to /metrics itself must not be recorded in gateway_requests_total.
        PrometheusMiddleware skips instrumentation for the /metrics path.
        """
        # Hit /metrics several times
        for _ in range(3):
            client.get("/metrics", headers=METRICS_AUTH_HEADER)

        # Check the /metrics body: the /metrics route itself should have no counter entry
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text
        # Look for a sample that has route="/metrics"
        for line in body.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            if 'route="/metrics"' in line and "gateway_requests_total" in line:
                # If such a line exists it must have value 0 (which means the
                # label was never incremented — Prometheus omits zero counters
                # unless they were declared with label values).
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 0.0, (
                    f"gateway_requests_total should not count /metrics scrapes: {line}"
                )


# ---------------------------------------------------------------------------
# 2. Request counter increments
# ---------------------------------------------------------------------------

class TestRequestCounter:
    def test_request_count_increments_on_health_hit(self, client):
        """
        A GET /health request should appear as an increment in
        gateway_requests_total with method=GET and route=/health.
        """
        client.get("/health")
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        # We only care that the line exists and has a value > 0
        found_health_counter = False
        for line in body.splitlines():
            if (
                "gateway_requests_total" in line
                and 'method="GET"' in line
                and 'route="/health"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value >= 1.0
                found_health_counter = True
                break
        assert found_health_counter, (
            "gateway_requests_total with route=/health not found in /metrics"
        )

    def test_request_count_records_status_code_label(self, client):
        """
        gateway_requests_total must carry a status_code label matching the
        actual HTTP response code.
        """
        client.get("/health")
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        # /health returns 200 OK
        found = any(
            'status_code="200"' in line
            and "gateway_requests_total" in line
            and not line.startswith("#")
            for line in body.splitlines()
        )
        assert found, "gateway_requests_total must include status_code='200' label"


# ---------------------------------------------------------------------------
# 3. Latency histogram
# ---------------------------------------------------------------------------

class TestLatencyHistogram:
    def test_histogram_sum_is_positive_after_request(self, client):
        """
        After at least one request the histogram _sum must be > 0.
        """
        client.get("/health")
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        # Histogram sum line: gateway_request_duration_seconds_sum{...} <value>
        sum_value: float | None = None
        for line in body.splitlines():
            if (
                "gateway_request_duration_seconds_sum" in line
                and 'route="/health"' in line
                and not line.startswith("#")
            ):
                sum_value = float(line.rsplit(" ", 1)[-1])
                break

        assert sum_value is not None, "histogram _sum line not found"
        assert sum_value > 0.0, "histogram _sum must be > 0 after a real request"

    def test_histogram_count_matches_request_count(self, client):
        """
        After N requests to /health the histogram _count must be >= N.
        """
        n = 3
        for _ in range(n):
            client.get("/health")

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text
        count_value: float | None = None
        for line in body.splitlines():
            if (
                "gateway_request_duration_seconds_count" in line
                and 'route="/health"' in line
                and not line.startswith("#")
            ):
                count_value = float(line.rsplit(" ", 1)[-1])
                break

        assert count_value is not None, "histogram _count line not found"
        assert count_value >= n, f"histogram _count {count_value} must be >= {n}"

    def test_histogram_has_expected_buckets(self, client):
        """
        gateway_request_duration_seconds must expose _bucket lines in the output.
        """
        client.get("/health")
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text
        bucket_lines = [
            line for line in body.splitlines()
            if "gateway_request_duration_seconds_bucket" in line
            and not line.startswith("#")
        ]
        assert len(bucket_lines) > 0, "No histogram bucket lines found in /metrics"


# ---------------------------------------------------------------------------
# 4. Error counter
# ---------------------------------------------------------------------------

class TestErrorCounter:
    def test_no_errors_by_default(self, client):
        """
        gateway_errors_total should not have any incremented samples when
        all responses are successful.
        """
        client.get("/health")
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        for line in body.splitlines():
            if "gateway_errors_total" in line and not line.startswith("#"):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 0.0, (
                    f"Expected 0 errors for successful requests, got {value}: {line}"
                )

    def test_error_counter_increments_on_5xx(self, client):
        """
        Inject a 503 response from the proxy layer and verify
        gateway_errors_total increments.
        """
        import httpx as _httpx

        with patch(
            "app.services.proxy.ProxyService.forward_request",
            new=AsyncMock(
                return_value=__import__("fastapi").responses.JSONResponse(
                    status_code=503, content={"error": "downstream unavailable"}
                )
            ),
        ):
            # Hit any proxied route to trigger the 5xx
            client.get("/api/v1/inventory/items")

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        # There must be at least one gateway_errors_total sample with value >= 1
        found_error = False
        for line in body.splitlines():
            if "gateway_errors_total" in line and not line.startswith("#"):
                value = float(line.rsplit(" ", 1)[-1])
                if value >= 1.0:
                    found_error = True
                    break
        assert found_error, "gateway_errors_total must be >= 1 after a 503 response"


# ---------------------------------------------------------------------------
# 5. Circuit breaker Gauge
# ---------------------------------------------------------------------------

class TestCircuitBreakerGauge:
    def test_cb_state_to_float_encoding(self):
        """Verify circuit breaker state → float encoding."""
        assert cb_state_to_float("closed") == 0.0
        assert cb_state_to_float("half-open") == 1.0
        assert cb_state_to_float("open") == 2.0
        assert cb_state_to_float("unknown") == 0.0  # default fallback

    def test_cb_gauge_shows_closed_by_default(self, client):
        """
        When no circuit breaker state has been explicitly set,
        the Gauge must be 0 (closed).
        """
        # Force a gauge sync without any circuit breaker trips
        sync_gauges_from_collector()
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        for line in body.splitlines():
            if (
                "gateway_circuit_breaker_state" in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 0.0, (
                    f"Expected closed (0.0) but got {value}: {line}"
                )

    def test_cb_gauge_reflects_open_state(self, client):
        """
        Setting a circuit breaker to 'open' and calling sync_gauges_from_collector
        must update the Gauge to 2.0 for that service.
        """
        metrics_collector.set_circuit_breaker_state("inventory", "open")
        sync_gauges_from_collector()

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        found = False
        for line in body.splitlines():
            if (
                "gateway_circuit_breaker_state" in line
                and 'service="inventory"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 2.0, f"Expected 2.0 (open) but got {value}"
                found = True
                break
        assert found, "gateway_circuit_breaker_state{service='inventory'} not found"

    def test_cb_gauge_reflects_half_open_state(self, client):
        """
        Setting a circuit breaker to 'half-open' must result in Gauge value 1.0.
        """
        metrics_collector.set_circuit_breaker_state("compliance", "half-open")
        sync_gauges_from_collector()

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        found = False
        for line in body.splitlines():
            if (
                "gateway_circuit_breaker_state" in line
                and 'service="compliance"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 1.0, f"Expected 1.0 (half-open) but got {value}"
                found = True
                break
        assert found, "gateway_circuit_breaker_state{service='compliance'} not found"


# ---------------------------------------------------------------------------
# 6. Cache hit rate Gauge
# ---------------------------------------------------------------------------

class TestCacheHitRateGauge:
    def test_cache_hit_rate_zero_by_default(self, client):
        """
        When no cache events have been recorded the Gauge must be 0.0.
        """
        sync_gauges_from_collector()
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        for line in body.splitlines():
            if (
                "gateway_cache_hit_rate" in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 0.0, f"Expected 0.0 but got {value}: {line}"

    def test_cache_hit_rate_reflects_collector(self, client):
        """
        Recording 1 hit and 1 miss for 'inventory' should yield 50.0% hit rate.
        """
        metrics_collector.record_request("inventory", 10.0, is_cache_hit=True)
        metrics_collector.record_request("inventory", 10.0, is_cache_miss=True)
        sync_gauges_from_collector()

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        found = False
        for line in body.splitlines():
            if (
                "gateway_cache_hit_rate" in line
                and 'service="inventory"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 50.0, f"Expected 50.0 but got {value}"
                found = True
                break
        assert found, "gateway_cache_hit_rate{service='inventory'} not found"

    def test_cache_hit_rate_100_percent(self, client):
        """Recording only hits yields 100% cache hit rate."""
        metrics_collector.record_request("auth", 5.0, is_cache_hit=True)
        metrics_collector.record_request("auth", 5.0, is_cache_hit=True)
        sync_gauges_from_collector()

        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        found = False
        for line in body.splitlines():
            if (
                "gateway_cache_hit_rate" in line
                and 'service="auth"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 100.0, f"Expected 100.0 but got {value}"
                found = True
                break
        assert found, "gateway_cache_hit_rate{service='auth'} not found"


# ---------------------------------------------------------------------------
# 7. Consistency between /metrics and /gateway/dashboard
# ---------------------------------------------------------------------------

class TestDashboardMetricsConsistency:
    def test_dashboard_still_returns_200(self, client):
        """/gateway/dashboard must still work after Round 10 changes."""
        with patch(
            "app.routes.dashboard.get_system_health",
            new=AsyncMock(return_value={"error": "unavailable"}),
        ):
            response = client.get("/gateway/dashboard")
        assert response.status_code == 200

    def test_circuit_breaker_state_consistent(self, client):
        """
        After setting inventory CB to 'open', both /metrics Gauge and
        /gateway/dashboard must agree on 'open'.
        """
        metrics_collector.set_circuit_breaker_state("inventory", "open")

        # Read dashboard
        with patch(
            "app.routes.dashboard.get_system_health",
            new=AsyncMock(return_value={"error": "unavailable"}),
        ):
            dash_response = client.get("/gateway/dashboard")
        dash_data = dash_response.json()
        dashboard_cb_state = dash_data["services"]["inventory"]["circuit_breaker_state"]
        assert dashboard_cb_state == "open", (
            f"Dashboard shows '{dashboard_cb_state}', expected 'open'"
        )

        # Read Prometheus /metrics
        sync_gauges_from_collector()
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text
        for line in body.splitlines():
            if (
                "gateway_circuit_breaker_state" in line
                and 'service="inventory"' in line
                and not line.startswith("#")
            ):
                value = float(line.rsplit(" ", 1)[-1])
                assert value == 2.0, (
                    f"Prometheus shows {value}, expected 2.0 (open). Dashboard shows 'open'."
                )
                break

    def test_cache_hit_rate_consistent(self, client):
        """
        After recording cache hits, /metrics Gauge and /gateway/dashboard
        must both show the same percentage.
        """
        metrics_collector.record_request("shipments", 12.0, is_cache_hit=True)
        metrics_collector.record_request("shipments", 12.0, is_cache_miss=True)

        with patch(
            "app.routes.dashboard.get_system_health",
            new=AsyncMock(return_value={"error": "unavailable"}),
        ):
            dash_response = client.get("/gateway/dashboard")
        dash_data = dash_response.json()
        dashboard_rate = dash_data["services"]["shipments"]["cache_hit_rate"]

        sync_gauges_from_collector()
        body = client.get("/metrics", headers=METRICS_AUTH_HEADER).text

        prometheus_rate: float | None = None
        for line in body.splitlines():
            if (
                "gateway_cache_hit_rate" in line
                and 'service="shipments"' in line
                and not line.startswith("#")
            ):
                prometheus_rate = float(line.rsplit(" ", 1)[-1])
                break

        assert prometheus_rate is not None, "gateway_cache_hit_rate{service='shipments'} not found"
        assert prometheus_rate == dashboard_rate, (
            f"Mismatch: Prometheus={prometheus_rate}, Dashboard={dashboard_rate}"
        )


class TestMetricsBearerToken:
    """Tests for fail-closed METRICS_BEARER_TOKEN authentication on /metrics."""

    def test_metrics_fails_when_token_env_unset(self, client):
        """When METRICS_BEARER_TOKEN is unset or empty, /metrics fails 503 fail-closed."""
        with patch.dict("os.environ", {"METRICS_BEARER_TOKEN": ""}):
            response = client.get("/metrics")
            assert response.status_code == 503
            assert response.json()["detail"] == "Metrics authentication is not configured"

        with patch.dict("os.environ"):
            os.environ.pop("METRICS_BEARER_TOKEN", None)
            response = client.get("/metrics")
            assert response.status_code == 503
            assert response.json()["detail"] == "Metrics authentication is not configured"

    def test_metrics_rejected_when_token_missing(self, client):
        """When METRICS_BEARER_TOKEN is set, requests without Authorization header fail 401."""
        with patch.dict("os.environ", {"METRICS_BEARER_TOKEN": TEST_METRICS_TOKEN}):
            response = client.get("/metrics")
            assert response.status_code == 401
            assert response.json()["detail"] in ("Missing metrics token", "Invalid metrics token")

    def test_metrics_rejected_when_token_invalid(self, client):
        """When METRICS_BEARER_TOKEN is set, requests with incorrect token fail 401."""
        with patch.dict("os.environ", {"METRICS_BEARER_TOKEN": TEST_METRICS_TOKEN}):
            response = client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid metrics token"

    def test_metrics_accepted_when_token_valid(self, client):
        """When METRICS_BEARER_TOKEN is set, requests with valid Bearer token succeed 200."""
        with patch.dict("os.environ", {"METRICS_BEARER_TOKEN": TEST_METRICS_TOKEN}):
            response = client.get("/metrics", headers=METRICS_AUTH_HEADER)
            assert response.status_code == 200
            assert "# HELP" in response.text

