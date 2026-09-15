"""
In-memory Circuit Breaker pattern implementation for the API Gateway.
"""

import logging
import threading
import time
from collections import deque

from app.core.config import settings
from app.services.metrics import metrics_collector

logger = logging.getLogger("api_gateway.circuit_breaker")


# ---------------------------------------------------------------------------
# Circuit Breaker State Machine
# ---------------------------------------------------------------------------

class CircuitBreakerManager:
    """
    Thread-safe in-memory Circuit Breaker manager for downstream microservices.

    Trip condition:
        failure_rate > failure_rate_threshold
        within a rolling window_seconds window.

    failure_rate = failures / total_requests  (only requests within the window)

    State machine:
        CLOSED (normal) -> OPEN (tripped) -> HALF-OPEN (trial) -> CLOSED (recovered)
                                                               -> OPEN (trial failed)
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Maps service_id -> dict
        # Structure:
        # {
        #    "state": "closed" | "open" | "half-open",
        #    "window": deque of (timestamp: float, is_success: bool),
        #    "last_state_change": float,
        #    "failure_rate_threshold": float,  # e.g. 0.50 for >50%
        #    "window_seconds": float,          # e.g. 60
        #    "recovery_timeout": float         # e.g. 30
        # }
        self._services: dict[str, dict] = {}

    def _init_service_if_missing(
        self,
        service_id: str,
        failure_rate_threshold: float | None = None,
        window_seconds: float | None = None,
        recovery_timeout: float | None = None,
    ):
        if service_id not in self._services:
            fr_threshold = (
                failure_rate_threshold
                if failure_rate_threshold is not None
                else settings.CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD
            )
            w_seconds = (
                window_seconds
                if window_seconds is not None
                else settings.CIRCUIT_BREAKER_WINDOW_SECONDS
            )
            r_timeout = (
                recovery_timeout
                if recovery_timeout is not None
                else settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
            )
            self._services[service_id] = {
                "state": "closed",
                "window": deque(),
                "last_state_change": time.time(),
                "failure_rate_threshold": fr_threshold,
                "window_seconds": w_seconds,
                "recovery_timeout": r_timeout,
            }

    def configure_service(
        self,
        service_id: str,
        failure_rate_threshold: float | None = None,
        window_seconds: float | None = None,
        recovery_timeout: float | None = None,
        failure_threshold: int | None = None,
    ):
        """
        Configure custom failure rate threshold, window, or recovery timeout
        for a service.

        Note: `failure_threshold` parameter is accepted for backward
        compatibility with older callers but is no longer used by the
        failure-rate-based trip logic.
        """
        with self._lock:
            self._init_service_if_missing(
                service_id, failure_rate_threshold, window_seconds, recovery_timeout
            )
            svc = self._services[service_id]
            if failure_rate_threshold is not None:
                svc["failure_rate_threshold"] = failure_rate_threshold
            if window_seconds is not None:
                svc["window_seconds"] = window_seconds
            if recovery_timeout is not None:
                svc["recovery_timeout"] = recovery_timeout

    def _prune_window(self, svc: dict, now: float):
        """
        Remove entries from the rolling window that are older than
        window_seconds. Must be called while holding self._lock.
        """
        cutoff = now - svc["window_seconds"]
        window = svc["window"]
        while window and window[0][0] < cutoff:
            window.popleft()

    def _compute_failure_rate(self, svc: dict, now: float) -> tuple[float, int, int]:
        """
        Compute the current failure rate using only requests within the
        rolling window. Must be called while holding self._lock.

        Returns:
            (failure_rate, total_requests_in_window, failures_in_window)
        """
        self._prune_window(svc, now)
        window = svc["window"]
        total = len(window)
        if total == 0:
            return 0.0, 0, 0
        failures = sum(1 for _, is_success in window if not is_success)
        return failures / total, total, failures

    def can_execute(self, service_id: str) -> bool:
        """
        Check if request can be executed for `service_id`.

        Returns:
            True if state is CLOSED or transitioned from OPEN -> HALF-OPEN.
            False if state is OPEN and recovery timeout has not expired.
        """
        now = time.time()
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            state = svc["state"]

            if state == "closed":
                return True

            if state == "open":
                elapsed = now - svc["last_state_change"]
                if elapsed >= svc["recovery_timeout"]:
                    # Transition OPEN -> HALF-OPEN
                    svc["state"] = "half-open"
                    svc["last_state_change"] = now
                    metrics_collector.set_circuit_breaker_state(service_id, "half-open")
                    logger.info("Circuit breaker for %s transitioned from OPEN -> HALF-OPEN", service_id)
                    return True
                else:
                    return False

            if state == "half-open":
                return True

    def record_success(self, service_id: str):
        """
        Record a successful request to downstream service.
        """
        now = time.time()
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            state = svc["state"]

            if state == "half-open":
                # Transition HALF-OPEN -> CLOSED
                svc["state"] = "closed"
                svc["window"].clear()
                svc["last_state_change"] = now
                metrics_collector.set_circuit_breaker_state(service_id, "closed")
                logger.info("Circuit breaker for %s transitioned HALF-OPEN -> CLOSED", service_id)
            elif state == "closed":
                svc["window"].append((now, True))
                self._prune_window(svc, now)

    def record_failure(self, service_id: str):
        """
        Record a downstream request failure (HTTP 5xx, timeout, or connection error).
        """
        now = time.time()
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            state = svc["state"]

            if state == "half-open":
                # Trial request failed -> Re-trip HALF-OPEN -> OPEN
                svc["state"] = "open"
                svc["last_state_change"] = now
                metrics_collector.set_circuit_breaker_state(service_id, "open")
                logger.warning("Circuit breaker for %s trial failed: HALF-OPEN -> OPEN", service_id)
            elif state == "closed":
                svc["window"].append((now, False))
                failure_rate, total, failures = self._compute_failure_rate(svc, now)
                if (
                    total > 0
                    and failure_rate > svc["failure_rate_threshold"]
                ):
                    # Trip CLOSED -> OPEN
                    svc["state"] = "open"
                    svc["last_state_change"] = now
                    metrics_collector.set_circuit_breaker_state(service_id, "open")
                    logger.warning(
                        "Circuit breaker for %s tripped CLOSED -> OPEN: "
                        "failure_rate=%.2f (%s/%s requests in %.0fs window, threshold=%.2f)",
                        service_id,
                        failure_rate,
                        failures,
                        total,
                        svc["window_seconds"],
                        svc["failure_rate_threshold"],
                    )
            elif state == "open":
                svc["last_state_change"] = now

    def get_state(self, service_id: str) -> str:
        """
        Return the current circuit breaker state for `service_id`.
        Also performs OPEN -> HALF-OPEN transition if recovery timeout elapsed.
        """
        now = time.time()
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            if svc["state"] == "open":
                elapsed = now - svc["last_state_change"]
                if elapsed >= svc["recovery_timeout"]:
                    svc["state"] = "half-open"
                    svc["last_state_change"] = now
                    metrics_collector.set_circuit_breaker_state(service_id, "half-open")
            return svc["state"]

    def reset(self):
        """
        Reset circuit breaker state for all services.
        """
        with self._lock:
            for service_id in self._services:
                metrics_collector.set_circuit_breaker_state(service_id, "closed")
            self._services.clear()

    # ------------------------------------------------------------------
    # Introspection helpers (useful for tests, dashboards, debugging)
    # ------------------------------------------------------------------

    def get_failure_rate(self, service_id: str) -> tuple[float, int, int]:
        """
        Public helper: return (failure_rate, total_requests, failures)
        for the current rolling window. Thread-safe.
        """
        now = time.time()
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            return self._compute_failure_rate(svc, now)


# Global singleton instance
circuit_breaker_manager = CircuitBreakerManager()
