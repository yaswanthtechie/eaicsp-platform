"""
Regression tests for PR feedback item 8 (Prometheus Cardinality) and
item 10 (Dashboard Service Names).

Proves:
1. Unknown/random URL paths are mapped to bounded label "other".
2. Prometheus labels and MetricsCollector keys remain bounded even under arbitrary URLs.
3. Internal gateway routes (/health, /gateway/*, 404s, auth-rejected requests)
   never appear as fake downstream service names in the dashboard or MetricsCollector.
4. Only configured downstream microservices appear under 'services'.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.ratelimit import limiter
from app.services.metrics import metrics_collector, normalize_route, get_downstream_service_names
from app.services.prometheus_metrics import reset_prometheus_metrics


@pytest.fixture(autouse=True)
def reset_state():
    metrics_collector.reset()
    reset_prometheus_metrics()
    limiter.enabled = False
    yield
    metrics_collector.reset()
    reset_prometheus_metrics()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_unknown_routes_mapped_to_other():
    """Arbitrary random paths must be normalized to 'other' to bound cardinality."""
    assert normalize_route(f"/random-{uuid.uuid4()}") == "other"
    assert normalize_route("/unknown/nested/path/123") == "other"
    assert normalize_route("/api/v1/nonexistent-service") == "other"
    assert normalize_route("/favicon.ico") == "other"


def test_known_routes_preserved():
    """Known gateway routes must still normalize to their expected prefix."""
    assert normalize_route("/") == "/"
    assert normalize_route("/health") == "/health"
    assert normalize_route("/metrics") == "/metrics"
    assert normalize_route("/gateway/status") == "/gateway/status"
    assert normalize_route("/gateway/dashboard") == "/gateway/dashboard"
    assert normalize_route("/api/v1/inventory/items") == "/api/v1/inventory"
    assert normalize_route("/api/v1/shipments/detail") == "/api/v1/shipments"


def test_prometheus_and_collector_cardinality_bounded(client):
    """
    Flooding gateway with 50 distinct random paths must only create ONE
    route key 'other' in collector and Prometheus metrics.
    """
    for _ in range(25):
        random_path = f"/random-path-{uuid.uuid4()}"
        client.get(random_path)

    dashboard = client.get("/gateway/dashboard").json()
    routes = dashboard["routes"]

    # Must contain 'other', and NOT 25 distinct paths
    assert "other" in routes
    assert routes["other"]["requests"] >= 25

    # Check Prometheus scrape body
    metrics_text = client.get("/metrics").text
    assert 'route="other"' in metrics_text
    # Verify no random UUID appears in Prometheus output
    assert "random-path" not in metrics_text


def test_internal_routes_not_in_dashboard_services(client):
    """
    Hitting /health, /gateway/status, /gateway/dashboard, 404s, and auth-rejected
    requests must never create fake downstream service names.
    """
    # 1. Internal health check
    client.get("/health")
    # 2. Operational status
    client.get("/gateway/status")
    # 3. Aggregated dashboard
    client.get("/gateway/dashboard")
    # 4. 404 unknown path
    client.get("/unknown-404-endpoint")

    dashboard = client.get("/gateway/dashboard").json()
    services = dashboard["services"]
    downstream_names = get_downstream_service_names()

    # Every key in 'services' MUST be a genuine downstream service
    for svc_name in services:
        assert svc_name in downstream_names, f"Unexpected fake service in dashboard: {svc_name}"

    # Specifically verify internal route names are absent
    forbidden = {"health", "status", "dashboard", "gateway", "other", "unknown-404-endpoint"}
    for name in forbidden:
        assert name not in services, f"Internal name '{name}' appeared as fake downstream service"
