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


def test_dashboard_compliance_dependency_healthy(client):
    """
    Compliance UP means both documented dependency chains are healthy.
    """
    health = {
        "inventory": "UP",
        "shipments": "UP",
        "compliance": "UP",
        "purchase-orders": "UP",
        "auth": "UP",
        "supplier-risk": "UP",
    }

    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value=health),
    ):
        response = client.get("/gateway/dashboard")

    assert response.status_code == 200

    chains = response.json()["dependency_chains"]

    assert chains["inventory_to_compliance"]["dependency_status"] == "healthy"
    assert chains["inventory_to_compliance"]["upstream_status"] == "healthy"

    assert chains["supplier_portal_to_compliance"]["dependency_status"] == "healthy"
    assert chains["supplier_portal_to_compliance"]["upstream_status"] == "healthy"


def test_dashboard_compliance_down_affects_both_upstreams(client):
    """
    Compliance DOWN must mark both Inventory and Supplier Portal as affected.
    """
    health = {
        "inventory": "UP",
        "shipments": "UP",
        "compliance": "DOWN",
        "purchase-orders": "UP",
        "auth": "UP",
        "supplier-risk": "UP",
    }

    with patch(
        "app.routes.dashboard.get_system_health",
        new=AsyncMock(return_value=health),
    ):
        response = client.get("/gateway/dashboard")

    assert response.status_code == 200

    chains = response.json()["dependency_chains"]

    inventory_chain = chains["inventory_to_compliance"]
    assert inventory_chain["dependency_status"] == "down"
    assert inventory_chain["upstream_status"] == "affected"

    supplier_portal_chain = chains["supplier_portal_to_compliance"]
    assert supplier_portal_chain["dependency_status"] == "down"
    assert supplier_portal_chain["upstream_status"] == "affected"
