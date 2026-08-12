"""
Metrics collection and aggregation service for the API Gateway.
"""

import math
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.core.config import settings


# ---------------------------------------------------------------------------
# Percentile Helper
# ---------------------------------------------------------------------------

def calculate_percentile(data: List[float], percentile: float) -> float:
    """
    Calculate the given percentile (0 to 100) of a list of numbers
    using the standard nearest-rank method.
    """
    if not data:
        return 0.0

    sorted_data = sorted(data)
    n = len(sorted_data)

    rank = math.ceil((percentile / 100.0) * n)
    index = max(0, min(rank - 1, n - 1))

    return round(float(sorted_data[index]), 2)


# ---------------------------------------------------------------------------
# Metrics Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Thread-safe in-memory metrics collector for API Gateway services.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Service metrics map: service_name -> dict
        # Dict structure:
        # {
        #   "request_volume": int,
        #   "latencies": List[float],
        #   "cache_hits": int,
        #   "cache_misses": int,
        #   "circuit_breaker_state": str ("closed" | "open" | "half-open")
        # }
        self._services: Dict[str, dict] = {}

    def _init_service_if_missing(self, service_name: str):
        if service_name not in self._services:
            self._services[service_name] = {
                "request_volume": 0,
                "latencies": [],
                "cache_hits": 0,
                "cache_misses": 0,
                "circuit_breaker_state": "closed",
            }

    def record_request(
        self,
        service_name: str,
        latency_ms: float,
        is_cache_hit: bool = False,
        is_cache_miss: bool = False,
    ):
        """
        Record a request completion for a downstream service.
        """
        with self._lock:
            self._init_service_if_missing(service_name)
            svc = self._services[service_name]
            svc["request_volume"] += 1
            svc["latencies"].append(float(latency_ms))

            if is_cache_hit:
                svc["cache_hits"] += 1
            elif is_cache_miss:
                svc["cache_misses"] += 1

    def set_circuit_breaker_state(self, service_name: str, state: str):
        """
        Update the circuit breaker state for a service.
        """
        with self._lock:
            self._init_service_if_missing(service_name)
            self._services[service_name]["circuit_breaker_state"] = state

    def record_cache_hit(self, service_name: str):
        """
        Record a cache hit for a service.
        """
        with self._lock:
            self._init_service_if_missing(service_name)
            self._services[service_name]["cache_hits"] += 1

    def record_cache_miss(self, service_name: str):
        """
        Record a cache miss for a service.
        """
        with self._lock:
            self._init_service_if_missing(service_name)
            self._services[service_name]["cache_misses"] += 1

    def get_service_metrics(self, service_name: str) -> dict:
        """
        Get aggregated metrics for a single service.
        """
        with self._lock:
            self._init_service_if_missing(service_name)
            svc = self._services[service_name]

            request_volume = svc["request_volume"]
            latencies = list(svc["latencies"])
            cache_hits = svc["cache_hits"]
            cache_misses = svc["cache_misses"]
            cb_state = svc["circuit_breaker_state"]

        total_cache_attempts = cache_hits + cache_misses
        if total_cache_attempts > 0:
            cache_hit_rate = round((cache_hits / total_cache_attempts) * 100.0, 2)
        else:
            cache_hit_rate = 0.0

        p50 = calculate_percentile(latencies, 50.0)
        p95 = calculate_percentile(latencies, 95.0)

        return {
            "circuit_breaker_state": cb_state,
            "cache_hit_rate": cache_hit_rate,
            "request_volume": request_volume,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
        }

    def get_all_metrics(self) -> dict:
        """
        Return aggregated metrics for all services.
        """
        # Extract configured downstream service names from SERVICE_ROUTES
        known_services = set()
        for prefix in settings.SERVICE_ROUTES.keys():
            if prefix.startswith("/api/v1/"):
                name = prefix.strip("/").split("/")[-1]
                known_services.add(name)

        with self._lock:
            for sname in self._services.keys():
                known_services.add(sname)

        services_metrics = {}
        for sname in sorted(known_services):
            services_metrics[sname] = self.get_service_metrics(sname)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": services_metrics,
        }

    def reset(self):
        """
        Reset all recorded metrics.
        """
        with self._lock:
            self._services.clear()


# Global singleton metrics collector instance
metrics_collector = MetricsCollector()
