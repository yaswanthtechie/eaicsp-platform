"""
Milestone 4 (M4) Test Suite — Full Observability for the API Gateway.

Verifies all 16 M4 Observability Requirements:
1. Per-route request counts
2. Per-route latency histogram
3. Multiple latency buckets & boundaries
4. Per-route error count (5xx counted, 401/403 excluded)
5. Per-route error rate calculation
6. Circuit breaker closed state
7. Circuit breaker open state
8. Circuit breaker half-open state
9. Cache hit count
10. Cache miss count
11. Cache hit-rate calculation
12. X-Caller-Service tracking (and default fallback)
13. Top callers ordering by request count
14. Route normalization (dynamic paths folded to canonical route pattern)
15. Empty/no-metric dashboard behavior
16. Existing dashboard compatibility (preserves M1/M2/M3 response shape)
"""

import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.middleware.ratelimit import limiter
from app.services.cache import cache_service
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector, normalize_route


@pytest.fixture(autouse=True)
def reset_gateway_state():
    """Reset all metrics, caches, circuit breakers, and rate limiters before/after each test."""
    metrics_collector.reset()
    cache_service.clear()
    circuit_breaker_manager.reset()
    limiter.enabled = False
    yield
    metrics_collector.reset()
    cache_service.clear()
    circuit_breaker_manager.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Per-Route Request Counts
# ===========================================================================

def test_per_route_request_counts(client):
    """
    M4 Req 1: Per-route request counts are accurately accumulated per canonical route.
    """
    metrics_collector.record_request("inventory", 10.0, route="/api/v1/inventory")
    metrics_collector.record_request("inventory", 12.0, route="/api/v1/inventory")
    metrics_collector.record_request("inventory", 14.0, route="/api/v1/inventory")
    metrics_collector.record_request("shipments", 20.0, route="/api/v1/shipments")
    metrics_collector.record_request("shipments", 25.0, route="/api/v1/shipments")

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    data = response.json()

    routes = data["metrics"]["routes"]
    assert routes["/api/v1/inventory"]["requests"] == 3
    assert routes["/api/v1/shipments"]["requests"] == 2


# ===========================================================================
# 2. Per-Route Latency Histogram
# ===========================================================================

def test_per_route_latency_histogram(client):
    """
    M4 Req 2: Latency is exposed as histogram bucket information with correct distribution.
    """
    # Send one sample for each bucket
    samples = [
        5.0,     # <= 10ms
        15.0,    # <= 25ms
        35.0,    # <= 50ms
        75.0,    # <= 100ms
        150.0,   # <= 250ms
        350.0,   # <= 500ms
        800.0,   # <= 1s
        1500.0,  # > 1s
    ]

    for lat in samples:
        metrics_collector.record_request("inventory", lat, route="/api/v1/inventory")

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    hist = response.json()["metrics"]["routes"]["/api/v1/inventory"]["latency_histogram"]

    assert hist["<= 10ms"] == 1
    assert hist["<= 25ms"] == 1
    assert hist["<= 50ms"] == 1
    assert hist["<= 100ms"] == 1
    assert hist["<= 250ms"] == 1
    assert hist["<= 500ms"] == 1
    assert hist["<= 1s"] == 1
    assert hist["> 1s"] == 1
    assert sum(hist.values()) == 8


# ===========================================================================
# 3. Multiple Latency Buckets & Boundary Conditions
# ===========================================================================

def test_multiple_latency_buckets(client):
    """
    M4 Req 3: Boundary values fall strictly into their deterministic bucket.
    """
    # Exact boundary: 10.0ms should be <= 10ms, not <= 25ms
    metrics_collector.record_request("inventory", 10.0, route="/api/v1/inventory")
    # 10.01ms should fall in <= 25ms
    metrics_collector.record_request("inventory", 10.01, route="/api/v1/inventory")
    # Exact 1000.0ms should be <= 1s
    metrics_collector.record_request("inventory", 1000.0, route="/api/v1/inventory")
    # 1000.01ms should be > 1s
    metrics_collector.record_request("inventory", 1000.01, route="/api/v1/inventory")

    response = client.get("/gateway/dashboard")
    hist = response.json()["metrics"]["routes"]["/api/v1/inventory"]["latency_histogram"]

    assert hist["<= 10ms"] == 1
    assert hist["<= 25ms"] == 1
    assert hist["<= 1s"] == 1
    assert hist["> 1s"] == 1


# ===========================================================================
# 4. Per-Route Error Count
# ===========================================================================

def test_per_route_error_count(client):
    """
    M4 Req 4: 5xx, timeouts, and request errors count as errors; 401/403 are excluded.
    """
    route = "/api/v1/inventory"
    # Successes
    metrics_collector.record_request("inventory", 10.0, route=route, status_code=200)
    metrics_collector.record_request("inventory", 12.0, route=route, status_code=201)
    # Excluded from errors: 401/403 (client authentication/authorization)
    metrics_collector.record_request("inventory", 5.0, route=route, status_code=401)
    metrics_collector.record_request("inventory", 5.0, route=route, status_code=403)
    # Counted as errors: 500, 503, 504
    metrics_collector.record_request("inventory", 25.0, route=route, status_code=500, is_error=True)
    metrics_collector.record_request("inventory", 30.0, route=route, status_code=504, is_error=True)

    response = client.get("/gateway/dashboard")
    r_metrics = response.json()["metrics"]["routes"][route]

    assert r_metrics["requests"] == 6
    assert r_metrics["errors"] == 2


# ===========================================================================
# 5. Per-Route Error Rate Calculation
# ===========================================================================

def test_per_route_error_rate_calculation(client):
    """
    M4 Req 5: Error rate is calculated as (errors / requests) * 100.0.
    """
    route = "/api/v1/compliance"
    # 7 successes + 3 errors = 10 requests, 30.0% error rate
    for _ in range(7):
        metrics_collector.record_request("compliance", 15.0, route=route, status_code=200)
    for _ in range(3):
        metrics_collector.record_request("compliance", 50.0, route=route, status_code=500, is_error=True)

    response = client.get("/gateway/dashboard")
    r_metrics = response.json()["metrics"]["routes"][route]

    assert r_metrics["requests"] == 10
    assert r_metrics["errors"] == 3
    assert r_metrics["error_rate"] == 30.0


# ===========================================================================
# 6. Circuit Breaker Closed State
# ===========================================================================

def test_circuit_breaker_closed_state(client):
    """
    M4 Req 6: Closed circuit breaker state is visible in metrics and services.
    """
    response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    data = response.json()

    # Visible under metrics.circuit_breakers
    assert data["metrics"]["circuit_breakers"]["inventory"]["state"] == "closed"
    # Compatible with existing services section
    assert data["services"]["inventory"]["circuit_breaker_state"] == "closed"


# ===========================================================================
# 7. Circuit Breaker Open State
# ===========================================================================

def test_circuit_breaker_open_state(client):
    """
    M4 Req 7: Tripped circuit breaker reflects 'open' state on the dashboard.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=30.0,
    )
    # Trip breaker
    circuit_breaker_manager.record_failure(service_id)

    response = client.get("/gateway/dashboard")
    data = response.json()

    assert data["metrics"]["circuit_breakers"][service_id]["state"] == "open"
    assert data["services"][service_id]["circuit_breaker_state"] == "open"


# ===========================================================================
# 8. Circuit Breaker Half-Open State
# ===========================================================================

def test_circuit_breaker_half_open_state(client):
    """
    M4 Req 8: Half-open state is automatically evaluated and exposed on the dashboard.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.05,  # 50ms recovery timeout
    )
    # Trip to open
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Wait for recovery timeout to elapse
    time.sleep(0.08)

    # Dashboard query triggers state inspection -> transitions to half-open
    response = client.get("/gateway/dashboard")
    data = response.json()

    assert data["metrics"]["circuit_breakers"][service_id]["state"] == "half-open"
    assert data["services"][service_id]["circuit_breaker_state"] == "half-open"


# ===========================================================================
# 9. Cache Hit Count
# ===========================================================================

def test_cache_hit_count(client):
    """
    M4 Req 9: Cache hit count is recorded and reflected under metrics.cache.
    """
    cache_service.set("item:100", {"name": "Widget"})
    # 2 hits
    cache_service.get("item:100", service_name="inventory")
    cache_service.get("item:100", service_name="inventory")

    response = client.get("/gateway/dashboard")
    cache_metrics = response.json()["metrics"]["cache"]

    assert cache_metrics["hits"] == 2


# ===========================================================================
# 10. Cache Miss Count
# ===========================================================================

def test_cache_miss_count(client):
    """
    M4 Req 10: Cache miss count is recorded and reflected under metrics.cache.
    """
    # 3 misses
    cache_service.get("nonexistent:1", service_name="inventory")
    cache_service.get("nonexistent:2", service_name="shipments")
    cache_service.get("nonexistent:3", service_name="compliance")

    response = client.get("/gateway/dashboard")
    cache_metrics = response.json()["metrics"]["cache"]

    assert cache_metrics["misses"] == 3


# ===========================================================================
# 11. Cache Hit-Rate Calculation
# ===========================================================================

def test_cache_hit_rate_calculation(client):
    """
    M4 Req 11: Cache hit rate is calculated as (hits / (hits + misses)) * 100.0.
    """
    cache_service.set("cached_key", "value")
    # 3 hits
    cache_service.get("cached_key", service_name="inventory")
    cache_service.get("cached_key", service_name="inventory")
    cache_service.get("cached_key", service_name="inventory")
    # 1 miss
    cache_service.get("missing_key", service_name="inventory")

    response = client.get("/gateway/dashboard")
    cache_metrics = response.json()["metrics"]["cache"]

    assert cache_metrics["hits"] == 3
    assert cache_metrics["misses"] == 1
    assert cache_metrics["hit_rate"] == 75.0


# ===========================================================================
# 12. X-Caller-Service Tracking
# ===========================================================================

@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_x_caller_service_tracking(mock_send, client):
    """
    M4 Req 12: X-Caller-Service is tracked from incoming requests, falling back to 'api-gateway'.
    """
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
    )

    # 1. Explicit caller: frontend
    client.get(
        "/api/v1/inventory/items",
        headers={"X-Caller-Service": "frontend"},
    )

    # 2. Explicit caller: procurement-service
    client.get(
        "/api/v1/inventory/items",
        headers={"X-Caller-Service": "procurement-service"},
    )

    # 3. No caller header -> falls back to 'api-gateway'
    client.get("/api/v1/inventory/items")

    response = client.get("/gateway/dashboard")
    top_callers = response.json()["metrics"]["top_callers"]

    caller_map = {c["caller"]: c["requests"] for c in top_callers}
    assert caller_map.get("frontend") == 1
    assert caller_map.get("procurement-service") == 1
    assert caller_map.get("api-gateway") == 1


# ===========================================================================
# 13. Top Callers Ordering by Request Count
# ===========================================================================

def test_top_callers_ordering(client):
    """
    M4 Req 13: Top callers are returned in descending order of request count.
    """
    # procurement-service: 10 requests
    for _ in range(10):
        metrics_collector.record_caller("procurement-service")
    # frontend: 5 requests
    for _ in range(5):
        metrics_collector.record_caller("frontend")
    # analytics-service: 1 request
    metrics_collector.record_caller("analytics-service")

    response = client.get("/gateway/dashboard")
    top_callers = response.json()["metrics"]["top_callers"]

    assert len(top_callers) >= 3
    assert top_callers[0]["caller"] == "procurement-service"
    assert top_callers[0]["requests"] == 10
    assert top_callers[1]["caller"] == "frontend"
    assert top_callers[1]["requests"] == 5
    assert top_callers[2]["caller"] == "analytics-service"
    assert top_callers[2]["requests"] == 1


# ===========================================================================
# 14. Route Normalization
# ===========================================================================

def test_route_normalization(client):
    """
    M4 Req 14: Dynamic paths (/api/v1/inventory/123, /inventory?q=test)
    are aggregated under canonical route /api/v1/inventory without route explosion.
    """
    # Direct normalization checks
    assert normalize_route("/api/v1/inventory/123") == "/api/v1/inventory"
    assert normalize_route("/api/v1/inventory/items/sku-456") == "/api/v1/inventory"
    assert normalize_route("/api/v1/shipments/batch?id=99") == "/api/v1/shipments"

    # Record under dynamic paths
    metrics_collector.record_request("inventory", 10.0, route="/api/v1/inventory/1")
    metrics_collector.record_request("inventory", 15.0, route="/api/v1/inventory/2")
    metrics_collector.record_request("inventory", 20.0, route="/api/v1/inventory/items?cat=tools")

    response = client.get("/gateway/dashboard")
    routes = response.json()["metrics"]["routes"]

    assert "/api/v1/inventory" in routes
    assert routes["/api/v1/inventory"]["requests"] == 3
    # Ensure no separate dynamic keys were generated
    assert "/api/v1/inventory/1" not in routes
    assert "/api/v1/inventory/2" not in routes


# ===========================================================================
# 15. Empty / No-Metric Dashboard Behavior
# ===========================================================================

def test_empty_dashboard_behavior(client):
    """
    M4 Req 15: Clean dashboard state with deterministic default values when no metrics exist.
    """
    response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "metrics" in data

    # Cache stats: 0 hits, 0 misses, 0.0 hit rate
    cache = data["metrics"]["cache"]
    assert cache["hits"] == 0
    assert cache["misses"] == 0
    assert cache["hit_rate"] == 0.0

    # Top callers: empty list
    assert data["metrics"]["top_callers"] == []

    # Configured service routes are present with 0 counts
    routes = data["metrics"]["routes"]
    for prefix in settings.SERVICE_ROUTES:
        assert prefix in routes
        assert routes[prefix]["requests"] == 0
        assert routes[prefix]["errors"] == 0
        assert routes[prefix]["error_rate"] == 0.0
        assert all(v == 0 for v in routes[prefix]["latency_histogram"].values())

    # All circuit breakers closed
    cbs = data["metrics"]["circuit_breakers"]
    for svc in ["inventory", "shipments", "compliance", "purchase-orders", "auth", "supplier-risk"]:
        assert cbs[svc]["state"] == "closed"


# ===========================================================================
# 16. Existing Dashboard Compatibility
# ===========================================================================

def test_existing_dashboard_compatibility(client):
    """
    M4 Req 16: Existing M1/M2/M3 dashboard fields remain intact and functional.
    """
    metrics_collector.record_request("inventory", 20.0)
    metrics_collector.record_request("inventory", 40.0)

    response = client.get("/gateway/dashboard")
    assert response.status_code == 200
    data = response.json()

    # Required top-level legacy fields
    assert "timestamp" in data
    assert "services" in data

    # Legacy service structure
    inv = data["services"]["inventory"]
    assert inv["request_volume"] == 2
    assert inv["p50_latency_ms"] == 20.0
    assert inv["p95_latency_ms"] == 40.0
    assert inv["circuit_breaker_state"] == "closed"
    assert inv["cache_hit_rate"] == 0.0

    # All 6 configured downstream services must be present
    expected_services = [
        "inventory",
        "shipments",
        "compliance",
        "purchase-orders",
        "auth",
        "supplier-risk",
    ]
    for svc in expected_services:
        assert svc in data["services"]
        s = data["services"][svc]
        assert "circuit_breaker_state" in s
        assert "cache_hit_rate" in s
        assert "request_volume" in s
        assert "p50_latency_ms" in s
        assert "p95_latency_ms" in s
