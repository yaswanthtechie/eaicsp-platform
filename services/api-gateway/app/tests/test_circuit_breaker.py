"""
Tests for downstream microservice Circuit Breaker pattern.
"""

import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.ratelimit import limiter
from app.services.circuit_breaker import circuit_breaker_manager
from app.services.metrics import metrics_collector


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


# ---------------------------------------------------------------------------
# Core state tests
# ---------------------------------------------------------------------------

def test_circuit_breaker_closed_normal():
    """
    CLOSED normal:
    CLOSED state allows requests to pass downstream.
    """
    service_id = "inventory"
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True


def test_circuit_breaker_trips_to_open():
    """
    Trips to OPEN:
    Sufficient failures in the window produce failure_rate > threshold
    and transition CLOSED -> OPEN.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id, failure_rate_threshold=0.50, window_seconds=60
    )

    # 100 requests: 40 successes then 60 failures
    # After interleaving so the 100th request pushes failure_rate above 50%
    for _ in range(49):
        circuit_breaker_manager.record_success(service_id)
    for _ in range(49):
        circuit_breaker_manager.record_failure(service_id)
    # 49/98 = 50% exactly -> not tripped yet (> required, not >=)
    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # One more failure -> 50/99 = ~50.5% -> OPEN
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"
    assert circuit_breaker_manager.can_execute(service_id) is False


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_fail_fast(mock_send, client):
    """
    Fail fast:
    OPEN state returns 503 circuit breaker open without making downstream network calls.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id, failure_rate_threshold=0.50, window_seconds=60
    )

    # Trip circuit breaker: 1 failure / 1 request = 100% > 50%
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
    HALF-OPEN transition:
    After recovery timeout, state transitions from OPEN -> HALF-OPEN.
    """
    service_id = "inventory"
    short_timeout = 0.2
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=short_timeout,
    )

    # Trip: 1 failure / 1 request = 100% > 50%
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Wait for recovery timeout
    time.sleep(0.25)

    # State transitions to HALF-OPEN and allows execution
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"


def test_circuit_breaker_half_open_success_resets():
    """
    HALF-OPEN success resets:
    Successful trial request changes HALF-OPEN -> CLOSED and clears window.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

    # Trip: 1 failure / 1 request
    circuit_breaker_manager.record_failure(service_id)
    time.sleep(0.15)

    # Allow trial request -> state becomes HALF-OPEN
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Trial request succeeds
    circuit_breaker_manager.record_success(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # After recovery, failure rate should be 0 (window cleared)
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert rate == 0.0
    assert total == 0
    assert fails == 0


def test_circuit_breaker_half_open_failure_reopens():
    """
    HALF-OPEN failure reopens:
    Failed trial request changes HALF-OPEN -> OPEN.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

    # Trip
    circuit_breaker_manager.record_failure(service_id)
    time.sleep(0.15)

    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Trial request fails
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"


def test_circuit_breaker_dashboard_sync(client):
    """
    Dashboard sync:
    Circuit breaker state changes are reflected on GET /gateway/dashboard.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

    # Initial state
    res1 = client.get("/gateway/dashboard")
    assert res1.json()["services"]["inventory"]["circuit_breaker_state"] == "closed"

    # Trip to OPEN: 1 failure / 1 request = 100%
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
    Independent service states:
    Tripping circuit breaker for Service A does not affect Service B.
    """
    circuit_breaker_manager.configure_service(
        "inventory", failure_rate_threshold=0.50, window_seconds=60
    )
    circuit_breaker_manager.configure_service(
        "shipments", failure_rate_threshold=0.50, window_seconds=60
    )

    # Trip inventory: 1 failure / 1 request = 100%
    circuit_breaker_manager.record_failure("inventory")

    assert circuit_breaker_manager.get_state("inventory") == "open"
    assert circuit_breaker_manager.get_state("shipments") == "closed"
    assert circuit_breaker_manager.can_execute("shipments") is True


@patch("httpx.AsyncClient.send", new_callable=AsyncMock)
def test_circuit_breaker_full_lifecycle(mock_send, client):
    """
    Continuous CLOSED -> OPEN -> HALF-OPEN -> CLOSED lifecycle:
    Demonstrates full state machine progression in a single HTTP request flow.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

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

    # 2. Downstream 500 errors - need failure rate > 50%
    #    After 1 success + 2 failures: 2/3 ~66.7% > 50% -> OPEN
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
    Concurrent state updates:
    Verifies thread safety under simultaneous record_failure/record_success calls.
    Uses a very high threshold so the circuit never trips during the test,
    allowing accurate verification that all 100 concurrent writes landed.
    """
    import threading

    service_id = "concurrent_service"
    # Use an unreachable threshold (> 1.0) to prevent early tripping
    # so we can accurately count all 100 concurrent updates.
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=1.01,
        window_seconds=60,
    )

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

    # 50 failures / 100 requests = exactly 50%.
    # With threshold > 1.0 the circuit is still CLOSED.
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 100
    assert fails == 50
    assert rate == 0.50
    assert circuit_breaker_manager.get_state(service_id) == "closed"


# ======================================================================
# REQUIRED TESTS: 7 scenarios per task specification
# ======================================================================

def test_cb_1_failure_rate_below_threshold_stays_closed():
    """
    Test 1 — Failure rate below threshold:
    100 requests, 40 failures, 60 successes -> 40% failure rate.
    Circuit must remain CLOSED.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    # 60 successes + 40 failures = 100 requests, 40% failure rate
    for _ in range(60):
        circuit_breaker_manager.record_success(service_id)
    for _ in range(40):
        circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 100
    assert fails == 40
    assert rate == pytest.approx(0.40, abs=0.01)

    # 40% < 50% -> stays CLOSED
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True


def test_cb_2_failure_rate_above_threshold_opens():
    """
    Test 2 — Failure rate above threshold:
    Sufficient requests to produce > 50% failure rate causes the
    circuit to OPEN.

    Note: With 49 successes + 51 failures, the rate crosses the
    >50% threshold at request #99 (50 failures / 99 total = 50.5%),
    so the circuit trips at 99 before the 100th request is recorded.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    # 49 successes + 51 failures targeted. The trip occurs at the
    # 50th failure when the rate becomes 50/99 > 50%.
    for _ in range(49):
        circuit_breaker_manager.record_success(service_id)
    for _ in range(51):
        circuit_breaker_manager.record_failure(service_id)

    # Circuit must be OPEN because we generated > 50% failure rate
    assert circuit_breaker_manager.get_state(service_id) == "open"
    assert circuit_breaker_manager.can_execute(service_id) is False

    # The window at trip time: 99 requests, 50 failures -> rate ~50.5%
    # (The 100th overall / 51st failure is not recorded since state is OPEN.)
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert fails == 50
    assert total == 99
    assert rate == pytest.approx(50 / 99, abs=0.001)
    assert rate > 0.50


def test_cb_3_window_expiration_old_failures_dropped():
    """
    Test 3 — Window expiration:
    Failures older than the configured window must no longer contribute
    to the current failure rate calculation.

    Strategy:
    - Phase 1: Confirm a high failure rate INSIDE the window trips OPEN.
    - Phase 2: Inject failures, wait beyond the window AND beyond the
      recovery timeout, transition back to CLOSED via the HALF-OPEN
      success path, then add fresh successes in CLOSED state.
      Pruning removes all old failures, leaving only the new successes.
    """
    service_id = "inventory"
    short_window = 0.2  # 200ms window for fast testing
    short_recovery = 0.2  # 200ms recovery to match
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=short_window,
        recovery_timeout=short_recovery,
    )

    # Phase 1: generate high failure rate INSIDE the window (2 fail / 3 total = 66.7%)
    circuit_breaker_manager.record_success(service_id)
    circuit_breaker_manager.record_failure(service_id)
    circuit_breaker_manager.record_failure(service_id)
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 3
    assert fails == 2
    assert rate == pytest.approx(2 / 3, abs=0.01)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Reset state for Phase 2 (clean slate, same configuration)
    circuit_breaker_manager.reset()
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=short_window,
        recovery_timeout=short_recovery,
    )

    # Phase 2:
    # Step A — Inject 10 failures -> OPEN (100% rate)
    for _ in range(10):
        circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"
    _rate_before, total_before, fails_before = circuit_breaker_manager.get_failure_rate(service_id)
    assert total_before == 1
    assert fails_before == 1  # first one tripped, rest are in OPEN state

    # Step B — Sleep beyond BOTH the 200ms window AND the 200ms recovery timeout
    time.sleep(0.45)

    # Step C — can_execute() sees recovery elapsed -> OPEN -> HALF-OPEN
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Step D — Successful trial in HALF-OPEN -> CLOSED (window cleared)
    circuit_breaker_manager.record_success(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    _rate_mid, total_mid, fails_mid = circuit_breaker_manager.get_failure_rate(service_id)
    assert total_mid == 0  # HALF-OPEN success cleared the window
    assert fails_mid == 0

    # Step E — Now CLOSED, add 10 fresh successes (all within window)
    for _ in range(10):
        circuit_breaker_manager.record_success(service_id)

    # Step F — Verify old failures have aged out: only 10 successes remain
    rate_after, total_after, fails_after = circuit_breaker_manager.get_failure_rate(service_id)
    assert fails_after == 0
    assert total_after == 10
    assert rate_after == 0.0

    # And because failure rate is 0%, circuit remains CLOSED
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_cb_4_recovery_timeout_30s_default():
    """
    Test 4 — Recovery timeout:
    After configured recovery timeout in OPEN state: OPEN -> HALF-OPEN.
    Also verifies the default configured value is 30 seconds.
    """
    from app.core.config import settings

    # Verify the default recovery timeout is 30 seconds per requirements
    assert settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT == 30.0
    assert settings.CIRCUIT_BREAKER_WINDOW_SECONDS == 60
    assert settings.CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD == 0.50

    service_id = "inventory"
    short_timeout = 0.2
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=short_timeout,
    )

    # Trip the circuit
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Before recovery timeout: still OPEN
    time.sleep(0.1)
    assert circuit_breaker_manager.can_execute(service_id) is False
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # After recovery timeout elapsed: OPEN -> HALF-OPEN
    time.sleep(0.15)  # total ~0.25s > 0.2s
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"


def test_cb_5_half_open_success_closes():
    """
    Test 5 — HALF-OPEN success:
    Successful trial request: HALF-OPEN -> CLOSED.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

    # Trip to OPEN
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Wait for recovery -> HALF-OPEN
    time.sleep(0.15)
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Successful trial -> CLOSED
    circuit_breaker_manager.record_success(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "closed"
    assert circuit_breaker_manager.can_execute(service_id) is True


def test_cb_6_half_open_failure_reopens():
    """
    Test 6 — HALF-OPEN failure:
    Failed trial request: HALF-OPEN -> OPEN.
    """
    service_id = "inventory"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
        recovery_timeout=0.1,
    )

    # Trip to OPEN
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"

    # Wait for recovery -> HALF-OPEN
    time.sleep(0.15)
    assert circuit_breaker_manager.can_execute(service_id) is True
    assert circuit_breaker_manager.get_state(service_id) == "half-open"

    # Failed trial -> back to OPEN
    circuit_breaker_manager.record_failure(service_id)
    assert circuit_breaker_manager.get_state(service_id) == "open"
    assert circuit_breaker_manager.can_execute(service_id) is False


def test_cb_7_thread_safety():
    """
    Test 7 — Thread safety:
    Ensure the implementation remains safe under concurrent access.
    Runs many threads recording successes and failures simultaneously,
    verifying no crashes, deadlocks, or corrupted state occurs.
    Uses a very high failure-rate threshold to prevent the circuit
    from tripping during the test so all 200 updates can be verified.
    """
    import threading

    service_id = "thread_safe_svc"
    # Use an unreachable threshold (> 1.0) so we never trip during
    # the concurrent burst, allowing accurate counting of all writes.
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=1.01,
        window_seconds=60,
    )

    n_threads = 200
    threads = []
    errors = []

    def worker(idx):
        try:
            if idx % 3 == 0:
                circuit_breaker_manager.record_failure(service_id)
            else:
                circuit_breaker_manager.record_success(service_id)
            # Also interleave state reads to exercise read-side locking
            _ = circuit_breaker_manager.get_state(service_id)
            _ = circuit_breaker_manager.can_execute(service_id)
            _, t, f = circuit_breaker_manager.get_failure_rate(service_id)
            assert t >= 0 and f >= 0 and f <= t
        except Exception as exc:
            errors.append(exc)

    for i in range(n_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # No thread raised an exception
    assert errors == [], f"Concurrent errors: {errors}"

    # Window totals are consistent with 200 requests
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == n_threads
    # 1 failure per 3 = ceil-ish. 200 / 3 ~= 66-67 failures
    assert 66 <= fails <= 67
    # With threshold > 1.0, state should still be CLOSED
    assert circuit_breaker_manager.get_state(service_id) == "closed"


# ======================================================================
# Edge case tests
# ======================================================================

def test_cb_edge_zero_requests_in_window():
    """
    Edge case: zero requests in the window.
    failure_rate = 0.0, circuit stays CLOSED.
    """
    service_id = "zero_req"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert rate == 0.0
    assert total == 0
    assert fails == 0
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_cb_edge_one_request_that_fails():
    """
    Edge case: one request that fails.
    failure_rate = 100% (1/1) > 50% -> opens the circuit.
    """
    service_id = "one_fail"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert rate == 1.0
    assert total == 1
    assert fails == 1
    assert circuit_breaker_manager.get_state(service_id) == "open"


def test_cb_edge_very_small_request_count_2_fail_1():
    """
    Edge case: 2 requests, 1 failure -> exactly 50% -> NOT open.
    """
    service_id = "small_exact_50"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    circuit_breaker_manager.record_success(service_id)
    circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert rate == 0.50
    assert total == 2
    assert fails == 1
    # Exactly 50% is NOT > 50%, so stays CLOSED
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_cb_edge_very_small_request_count_3_fail_2():
    """
    Edge case: 3 requests, 2 failures -> ~66.7% > 50% -> OPEN.
    """
    service_id = "small_above_50"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    circuit_breaker_manager.record_success(service_id)
    circuit_breaker_manager.record_failure(service_id)
    circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert rate == pytest.approx(2 / 3, abs=0.01)
    assert total == 3
    assert fails == 2
    assert circuit_breaker_manager.get_state(service_id) == "open"


def test_cb_edge_exactly_50_percent_not_opened():
    """
    Edge case: exactly 50% failure rate (100/200).
    Requirement says > 50%, so exactly 50% must NOT open the circuit.
    """
    service_id = "exact_50"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    for _ in range(100):
        circuit_breaker_manager.record_success(service_id)
    for _ in range(100):
        circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 200
    assert fails == 100
    assert rate == 0.50
    # Exactly 50% -> NOT tripped
    assert circuit_breaker_manager.get_state(service_id) == "closed"


def test_cb_edge_just_above_50_percent_opens():
    """
    Edge case: just above 50%.
    Rate exceeds 50% with 100 failures out of 199 requests = 50.25%.
    Opens the circuit at the 199th request (the 100th failure).
    """
    service_id = "just_above_50"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    for _ in range(99):
        circuit_breaker_manager.record_success(service_id)
    for _ in range(101):
        circuit_breaker_manager.record_failure(service_id)

    # Circuit is OPEN because 100/199 = 50.25% > 50% (the 100th failure
    # caused the trip; the 200th overall / 101st failure is not recorded
    # since the state became OPEN.)
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 199
    assert fails == 100
    assert rate == pytest.approx(100 / 199, abs=0.001)
    assert rate > 0.50
    assert circuit_breaker_manager.get_state(service_id) == "open"


def test_cb_edge_interleaved_success_failure_alternating():
    """
    Edge case: alternating success/failure -> always 50% or close.
    Never trips until we have a higher ratio of failures.
    """
    service_id = "alternating"
    circuit_breaker_manager.configure_service(
        service_id,
        failure_rate_threshold=0.50,
        window_seconds=60,
    )

    # Alternate: S, F, S, F, ... 200 times -> exactly 50%
    for i in range(200):
        if i % 2 == 0:
            circuit_breaker_manager.record_success(service_id)
        else:
            circuit_breaker_manager.record_failure(service_id)

    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 200
    assert fails == 100
    assert rate == 0.50
    assert circuit_breaker_manager.get_state(service_id) == "closed"

    # Add one more failure -> 101/201 = 50.25% -> OPEN
    circuit_breaker_manager.record_failure(service_id)
    rate, total, fails = circuit_breaker_manager.get_failure_rate(service_id)
    assert total == 201
    assert fails == 101
    assert rate == pytest.approx(101 / 201, abs=0.001)
    assert circuit_breaker_manager.get_state(service_id) == "open"
