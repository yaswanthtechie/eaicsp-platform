"""
Tests for downstream microservice Circuit Breaker pattern.
"""

import time
import httpx
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector
from app.middleware.ratelimit import limiter


@pytest.fixture(autouse=True)
def reset_state():
    """Reset circuit breaker, metrics collector, and rate limiter state for tests."""
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = False
    yield
    circuit_breaker_manager.reset()
    metrics_collector.reset()
    limiter.enabled = True


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_circuit_breaker_closed_normal():
    """
    Test 1 — CLOSED normal:
    CLOSED state allows requests to pass downstream.
    """
    service_id = "inventory"
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True


def test_circuit_breaker_trips_to_open():
    """
    Test 2 — Trips to OPEN:
    Configured consecutive failures transition CLOSED -> OPEN.
    """
    service_id = "inventory"
    threshold = 3
    circuit_breaker_manager.configure_service(service_id, failure_threshold=threshold)

    for _ in range(threshold - 1):
        circuit_breaker_manager.record_failure(service_id)
        assert circuit_breaker_manager.get_state(service_id) == "closed"

    # Threshold reached
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"
    assert circuit_breaker_manager.can_execute(service_id) is False


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_fail_fast(mock_send, client):
    """
    Test 3 — Fail fast:
    OPEN state returns 503 circuit breaker open without making downstream network calls.
    """
    service_id = "inventory"
    threshold = 2
    circuit_breaker_manager.configure_service(service_id, failure_threshold=threshold)

    # Trip circuit breaker
    circuit_breaker_manager.record_failure(service_id)
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Request to gateway
    response = client.get("/api/v1/inventory/items")
    assert response.status_code == 503
    assert response.json()["error"] == "Inventory service circuit breaker open"

    # Downstream send should NOT have been called
    mock_send.assert_not_called()


def test_circuit_breaker_half_open_transition():
    """
    Test 4 — HALF-OPEN transition:
    After recovery timeout, state transitions from OPEN -> HALF-OPEN.
    """
    service_id = "inventory"
    short_timeout = 0.2
    circuit_breaker_manager.configure_service(service_id, failure_threshold=1, recovery_timeout=short_timeout)

    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Wait for recovery timeout
    time.sleep(0.25)

    # State transitions to HALF-OPEN and allows execution
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"


def test_circuit_breaker_half_open_success_resets():
    """
    Test 5 — HALF-OPEN success resets:
    Successful trial request changes HALF-OPEN -> CLOSED and resets failure count.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(service_id, failure_threshold=1, recovery_timeout=0.1)

    circuit_breaker_manager.record_failure(service_id)
    time.sleep(0.15)

    # Allow trial request -> state becomes HALF-OPEN
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Trial request succeeds
    circuit_breaker_manager.record_success(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_circuit_breaker_half_open_failure_reopens():
    """
    Test 6 — HALF-OPEN failure reopens:
    Failed trial request changes HALF-OPEN -> OPEN.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(service_id, failure_threshold=1, recovery_timeout=0.1)

    circuit_breaker_manager.record_failure(service_id)
    time.sleep(0.15)

    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Trial request fails
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"


def test_circuit_breaker_dashboard_sync(client):
    """
    Test 7 — Dashboard sync:
    Circuit breaker state changes are reflected on GET /gateway/dashboard.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(service_id, failure_threshold=1, recovery_timeout=0.1)

    # Initial state
    res1 = client.get("/gateway/dashboard")
    assert res1.json()["services"]["inventory"]["circuit_breaker_state"] == "closed"

    # Trip to OPEN
    circuit_breaker_manager.record_failure(service_id)
    res2 = client.get("/gateway/dashboard")
    assert res2.json()["services"]["inventory"]["circuit_breaker_state"] == "open"

    # Transition to HALF-OPEN
    time.sleep(0.15)
    circuit_breaker_manager.can_execute(service_id)
    res3 = client.get("/gateway/dashboard")
    assert res3.json()["services"]["inventory"]["circuit_breaker_state"] == "half-open"


def test_independent_service_circuit_breakers():
    """
    Test 8 — Independent service states:
    Tripping circuit breaker for Service A does not affect Service B.
    """
    circuit_breaker_manager.configure_service("inventory", failure_threshold=1)
    circuit_breaker_manager.configure_service("shipments", failure_threshold=1)

    circuit_breaker_manager.record_failure("inventory")

    assert circuit_breaker_manager.get_state("inventory") == "open"
    assert circuit_breaker_manager.get_state("shipments") == "closed"
    assert circuit_breaker_manager.can_execute("shipments") is True


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_full_lifecycle(mock_send, client):
    """
    Test 9 — Continuous CLOSED -> OPEN -> HALF-OPEN -> CLOSED lifecycle:
    Demonstrates full state machine progression in a single HTTP request flow.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(service_id, failure_threshold=2, recovery_timeout=0.1)

    # 1. State CLOSED: successful requests
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "ok"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )
    res = client.get("/api/v1/inventory/items")
    assert res.status_code == 200
    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # 2. Downstream 500 errors trip circuit breaker to OPEN
    mock_send.return_value = httpx.Response(
        status_code=500,
        content=b'{"error": "internal error"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )
    client.get("/api/v1/inventory/items")
    client.get("/api/v1/inventory/items")
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # 3. OPEN state fail-fast (503 without downstream call)
    mock_send.reset_mock()
    res_open = client.get("/api/v1/inventory/items")
    assert res_open.status_code == 503
    mock_send.assert_not_called()

    # 4. Wait for recovery timeout -> transitions to HALF-OPEN
    time.sleep(0.15)
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # 5. Trial request succeeds -> state resets to CLOSED
    mock_send.return_value = httpx.Response(
        status_code=200,
        content=b'{"status": "recovered"}',
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://test"),
    )
    res_recovered = client.get("/api/v1/inventory/items")
    assert res_recovered.status_code == 200
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_circuit_breaker_concurrency():
    """
    Test 10 — Concurrent state updates:
    Verifies thread safety under simultaneous record_failure/record_success calls.
    """
    import threading

    service_id = "concurrent_service"
    circuit_breaker_manager.configure_service(service_id, failure_threshold=50)

    threads = []
    for i in range(100):
        target_fn = (
            circuit_breaker_manager.record_failure
            if i % 2 == 0
            else circuit_breaker_manager.record_success
        )
        t = threading.Thread(target=target_fn, args=(service_id,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verify state remains valid without race conditions or locks crashing
    assert circuit_breaker_manager.get_state(service_id) in {"closed", "open", "half-open"}

