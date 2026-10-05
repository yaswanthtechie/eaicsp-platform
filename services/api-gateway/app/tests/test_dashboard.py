"""
Tests for the Aggregated Health Dashboard (/gateway/dashboard).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.middleware.ratelimit import limiter
from app.services.metrics import metrics_collector


@pytest.fixture(autouse=True)
def reset_metrics_and_limiter():
    """Reset metrics collector state before and after each test."""
    metrics_collector.reset()
    limiter.enabled = False
    yield
    metrics_collector.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_dashboard_endpoint_structure(client):
    """
    Test GET /gateway/dashboard returns HTTP 200 and expected JSON structure.
    """
    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    data = response.json()
    assert "timestamp" in data
    assert "services" in data

    services = data["services"]
    expected_services = [
        "inventory",
        "shipments",
        "compliance",
        "purchase-orders",
        "auth",
        "supplier-risk",
    ]

    for svc in expected_services:
        assert svc in services
        sdata = services[svc]
        assert "circuit_breaker_state" in sdata
        assert "cache_hit_rate" in sdata
        assert "request_volume" in sdata
        assert "p50_latency_ms" in sdata
        assert "p95_latency_ms" in sdata


def test_dashboard_metrics_recording(client):
    """
    Test recording request volume and latency percentiles.
    """
    # Record test requests for inventory service
    metrics_collector.record_request("inventory", 10.0)
    metrics_collector.record_request("inventory", 20.0)
    metrics_collector.record_request("inventory", 30.0)
    metrics_collector.record_request("inventory", 40.0)
    metrics_collector.record_request("inventory", 100.0)

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    inv = response.json()["services"]["inventory"]
    assert inv["request_volume"] == 5
    assert inv["p50_latency_ms"] == 30.0
    assert inv["p95_latency_ms"] == 100.0


def test_dashboard_cache_hit_rate(client):
    """
    Test cache hit rate calculation.
    """
    metrics_collector.record_request("inventory", 15.0, is_cache_hit=True)
    metrics_collector.record_request("inventory", 25.0, is_cache_miss=True)

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    inv = response.json()["services"]["inventory"]
    assert inv["cache_hit_rate"] == 50.0


def test_dashboard_circuit_breaker_state(client):
    """
    Test circuit breaker state reflection.
    """
    metrics_collector.set_circuit_breaker_state("inventory", "open")

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    inv = response.json()["services"]["inventory"]
    assert inv["circuit_breaker_state"] == "open"


def test_dashboard_empty_metrics(client):
    """
    Test metric default values when no requests have been recorded.
    """
    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    inv = response.json()["services"]["inventory"]
    assert inv["request_volume"] == 0
    assert inv["cache_hit_rate"] == 0.0
    assert inv["p50_latency_ms"] == 0.0
    assert inv["p95_latency_ms"] == 0.0
    assert inv["circuit_breaker_state"] == "closed"


def test_dashboard_100_percent_cache_hit_rate(client):
    """
    Test 100% cache hit rate metrics calculation.
    """
    metrics_collector.record_request("auth", 5.0, is_cache_hit=True)
    metrics_collector.record_request("auth", 8.0, is_cache_hit=True)

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200

    auth_svc = response.json()["services"]["auth"]
    assert auth_svc["cache_hit_rate"] == 100.0


def test_dashboard_health_unavailable_reports_unknown(client):
    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value={"error": "health check unavailable"}),
    ):
        response = client.get("/gateway/dashboard")

    assert response.status_code == 200
    chains = response.json()["dependency_chains"]
    for chain in chains.values():
        assert chain["dependency_status"] == "unknown"
        assert chain["upstream_status"] == "unknown"
        assert chain["reason"] == "Health checks are unavailable"
    assert response.json()["affected_by_dependency"] == {}


def test_dashboard_compliance_degraded_by_route_errors(client):
    metrics_collector.record_request("compliance", 10.0, is_error=True)
    health = {
        "inventory": "UP",
        "compliance": "UP",
        "purchase-order": "UP",
    }

    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value=health),
    ):
        response = client.get("/gateway/dashboard")

    assert response.status_code == 200
    chains = response.json()["dependency_chains"]
    assert chains["inventory_to_compliance"]["dependency_status"] == "degraded"
    assert chains["inventory_to_compliance"]["upstream_status"] == "affected"
    assert chains["inventory_to_compliance"]["reason"] == "compliance error rate is 100.0%"


def test_dashboard_open_dependency_breaker_is_degraded():
    health = {
        "inventory": "UP",
        "compliance": "UP",
        "purchase-order": "UP",
    }

    chains = metrics_collector.get_dependency_health(
        health,
        services_metrics={"compliance": {"circuit_breaker_state": "open"}},
    )

    assert chains["inventory_to_compliance"]["dependency_status"] == "degraded"
    assert chains["inventory_to_compliance"]["reason"] == "compliance circuit breaker is open"


def test_dashboard_reports_upstream_health_independently(client):
    health = {
        "inventory": "DOWN",
        "compliance": "UP",
        "purchase-order": "UP",
    }

    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value=health),
    ):
        response = client.get("/gateway/dashboard")

    assert response.status_code == 200
    inventory_chain = response.json()["dependency_chains"]["inventory_to_compliance"]
    assert inventory_chain["dependency_status"] == "healthy"
    assert inventory_chain["upstream_status"] == "down"
    assert inventory_chain["reason"] == "inventory failed its own health check"


# Keys exactly as get_system_health() returns them (derived from SERVICE_NAMES).
ALL_UP = {
    "inventory": "UP",
    "shipments": "UP",
    "compliance": "UP",
    "purchase-order": "UP",
    "auth": "UP",
    "supplier-risk": "UP",
}


def _dashboard_with_health(client, health):
    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value=health),
    ):
        response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    return response.json()


def test_dashboard_compliance_dependency_healthy(client):
    """Compliance UP means both documented dependency chains are healthy."""
    data = _dashboard_with_health(client, ALL_UP)
    chains = data["dependency_chains"]

    for name in ("inventory_to_compliance", "supplier_portal_to_compliance"):
        assert chains[name]["dependency_status"] == "healthy"
        assert chains[name]["upstream_status"] == "healthy"
    assert data["affected_by_dependency"] == {}


def test_dashboard_compliance_down_affects_both_upstreams(client):
    """Compliance DOWN must mark BOTH Inventory and Supplier Portal as affected."""
    data = _dashboard_with_health(client, {**ALL_UP, "compliance": "DOWN"})
    chains = data["dependency_chains"]

    for name in ("inventory_to_compliance", "supplier_portal_to_compliance"):
        assert chains[name]["dependency_status"] == "down"
        assert chains[name]["upstream_status"] == "affected"
    assert sorted(data["affected_by_dependency"]["compliance"]) == ["inventory", "supplier-portal"]


def test_dashboard_keeps_existing_observability_fields(client):
    """Adding dependency chains must not remove the existing dashboard fields."""
    data = _dashboard_with_health(client, ALL_UP)

    for key in ("services", "metrics", "routes", "circuit_breakers", "cache", "top_callers"):
        assert key in data, key


def test_dashboard_health_unavailable_is_unknown_not_down(client):
    """If the gateway cannot run health checks, it must not report an outage."""
    data = _dashboard_with_health(client, {"error": "health check unavailable"})
    chains = data["dependency_chains"]

    for name in ("inventory_to_compliance", "supplier_portal_to_compliance"):
        assert chains[name]["dependency_status"] == "unknown"
        assert chains[name]["upstream_status"] == "unknown"
    assert data["affected_by_dependency"] == {}


def test_dashboard_compliance_open_breaker_is_degraded(client):
    """Compliance answering /health but with its breaker open is 'struggling'."""
    metrics_collector.set_circuit_breaker_state("compliance", "open")

    data = _dashboard_with_health(client, ALL_UP)
    chain = data["dependency_chains"]["inventory_to_compliance"]

    assert chain["dependency_status"] == "degraded"
    assert chain["upstream_status"] == "affected"
    assert "circuit breaker" in chain["reason"]


def test_dashboard_compliance_high_error_rate_is_degraded(client):
    """Compliance UP but failing 1 in 2 requests (50%) is degraded, not healthy."""
    metrics_collector.record_request("compliance", 10.0, status_code=200)
    metrics_collector.record_request("compliance", 10.0, status_code=503)

    data = _dashboard_with_health(client, ALL_UP)
    chain = data["dependency_chains"]["supplier_portal_to_compliance"]

    assert chain["dependency_status"] == "degraded"
    assert chain["upstream_status"] == "affected"
    assert "error rate" in chain["reason"]


def test_dashboard_upstream_own_outage_is_not_blamed_on_compliance(client):
    """Inventory itself down while Compliance is fine: the chain shows Inventory down."""
    data = _dashboard_with_health(client, {**ALL_UP, "inventory": "DOWN"})
    chain = data["dependency_chains"]["inventory_to_compliance"]

    assert chain["dependency_status"] == "healthy"
    assert chain["upstream_status"] == "down"
    assert data["affected_by_dependency"] == {}
