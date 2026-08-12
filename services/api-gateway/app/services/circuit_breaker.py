"""
In-memory Circuit Breaker pattern implementation for the API Gateway.
"""

import logging
import threading
import time
from typing import Dict, Optional

from app.core.config import settings
from app.services.metrics import metrics_collector

logger = logging.getLogger("api_gateway.circuit_breaker")


# ---------------------------------------------------------------------------
# Circuit Breaker State Machine
# ---------------------------------------------------------------------------

class CircuitBreakerManager:
    """
    Thread-safe in-memory Circuit Breaker manager for downstream microservices.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Maps service_id -> dict
        # Structure:
        # {
        #    "state": "closed" | "open" | "half-open",
        #    "consecutive_failures": int,
        #    "last_state_change": float,
        #    "failure_threshold": int,
        #    "recovery_timeout": float
        # }
        self._services: Dict[str, dict] = {}

    def _init_service_if_missing(
        self,
        service_id: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
    ):
        if service_id not in self._services:
            f_threshold = (
                failure_threshold
                if failure_threshold is not None
                else settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
            )
            r_timeout = (
                recovery_timeout
                if recovery_timeout is not None
                else settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
            )
            self._services[service_id] = {
                "state": "closed",
                "consecutive_failures": 0,
                "last_state_change": time.time(),
                "failure_threshold": f_threshold,
                "recovery_timeout": r_timeout,
            }

    def configure_service(
        self,
        service_id: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[float] = None,
    ):
        """
        Configure custom failure threshold or recovery timeout for a service.
        """
        with self._lock:
            self._init_service_if_missing(service_id, failure_threshold, recovery_timeout)
            svc = self._services[service_id]
            if failure_threshold is not None:
                svc["failure_threshold"] = failure_threshold
            if recovery_timeout is not None:
                svc["recovery_timeout"] = recovery_timeout

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

            return True

    def record_success(self, service_id: str):
        """
        Record a successful request to downstream service.
        """
        with self._lock:
            self._init_service_if_missing(service_id)
            svc = self._services[service_id]
            state = svc["state"]

            if state == "half-open":
                # Transition HALF-OPEN -> CLOSED
                svc["state"] = "closed"
                svc["consecutive_failures"] = 0
                svc["last_state_change"] = time.time()
                metrics_collector.set_circuit_breaker_state(service_id, "closed")
                logger.info("Circuit breaker for %s transitioned HALF-OPEN -> CLOSED", service_id)
            elif state == "closed":
                svc["consecutive_failures"] = 0

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
                svc["consecutive_failures"] += 1
                if svc["consecutive_failures"] >= svc["failure_threshold"]:
                    # Trip CLOSED -> OPEN
                    svc["state"] = "open"
                    svc["last_state_change"] = now
                    metrics_collector.set_circuit_breaker_state(service_id, "open")
                    logger.warning(
                        "Circuit breaker for %s tripped CLOSED -> OPEN after %s consecutive failures",
                        service_id,
                        svc["consecutive_failures"],
                    )
            elif state == "open":
                svc["last_state_change"] = now

    def get_state(self, service_id: str) -> str:
        """
        Return the current circuit breaker state for `service_id`.
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
            for service_id in self._services.keys():
                metrics_collector.set_circuit_breaker_state(service_id, "closed")
            self._services.clear()


# Global singleton instance
circuit_breaker_manager = CircuitBreakerManager()
