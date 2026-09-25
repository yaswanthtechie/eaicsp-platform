"""
Metrics collection and aggregation service for the API Gateway.
"""

import math
import threading
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

# ---------------------------------------------------------------------------
# Percentile Helper
# ---------------------------------------------------------------------------


def calculate_percentile(data: list[float], percentile: float) -> float:
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
# Histogram Helper Functions
# ---------------------------------------------------------------------------

def format_bucket_label(limit_ms: float) -> str:
    """
    Format a bucket boundary in milliseconds into a deterministic human-readable label.
    e.g. 10.0 -> '<= 10ms', 1000.0 -> '<= 1s'.
    """
    if limit_ms >= 1000 and limit_ms % 1000 == 0:
        return f"<= {int(limit_ms // 1000)}s"
    elif limit_ms == int(limit_ms):
        return f"<= {int(limit_ms)}ms"
    else:
        return f"<= {limit_ms}ms"


def format_overflow_label(limit_ms: float) -> str:
    """
    Format an overflow bucket label above the highest configured bucket threshold.
    e.g. 1000.0 -> '> 1s'.
    """
    if limit_ms >= 1000 and limit_ms % 1000 == 0:
        return f"> {int(limit_ms // 1000)}s"
    elif limit_ms == int(limit_ms):
        return f"> {int(limit_ms)}ms"
    else:
        return f"> {limit_ms}ms"


def create_empty_histogram(buckets: list[float]) -> dict[str, int]:
    """
    Create a deterministic histogram dictionary with all buckets set to 0.
    """
    hist = {format_bucket_label(b): 0 for b in buckets}
    hist[format_overflow_label(buckets[-1])] = 0
    return hist


def get_bucket_label(latency_ms: float, buckets: list[float]) -> str:
    """
    Determine which discrete bucket a latency value falls into.
    """
    for b in buckets:
        if latency_ms <= b:
            return format_bucket_label(b)
    return format_overflow_label(buckets[-1])


def normalize_route(path: str) -> str:
    """
    Normalize dynamic URL paths to their canonical route pattern.
    e.g. /api/v1/inventory/123 -> /api/v1/inventory
    """
    if not path:
        return "/"

    # Strip query string if present
    path_clean = path.split("?")[0]

    # Check against known service routes (longest match first)
    for route_prefix in sorted(settings.SERVICE_ROUTES.keys(), key=len, reverse=True):
        if path_clean == route_prefix or path_clean.startswith(f"{route_prefix}/"):
            return route_prefix

    if path_clean.startswith("/health"):
        return "/health"
    if path_clean.startswith("/gateway"):
        return "/gateway/dashboard"
    if path_clean.startswith("/api/v1/dashboard"):
        return "/api/v1/dashboard/summary"

    return path_clean.rstrip("/") or "/"


# ---------------------------------------------------------------------------
# Metrics Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Thread-safe in-memory metrics collector for API Gateway services and routes.
    """

    def __init__(self, buckets: list[float] | None = None):
        self._lock = threading.Lock()
        self._buckets: list[float] = list(
            buckets
            if buckets is not None
            else getattr(
                settings,
                "LATENCY_HISTOGRAM_BUCKETS",
                [10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0],
            )
        )

        # Service metrics map: service_name -> dict
        self._services: dict[str, dict[str, Any]] = {}

        # Route metrics map: route_pattern -> dict
        # {
        #   "requests": int,
        #   "errors": int,
        #   "error_rate": float,
        #   "latency_histogram": dict[str, int]
        # }
        self._routes: dict[str, dict[str, Any]] = {}

        # Caller metrics map: caller_service -> int
        self._callers: dict[str, int] = {}

        # Pre-populate configured service routes
        self._prepopulate_routes()

    def _prepopulate_routes(self):
        """Pre-populate all configured SERVICE_ROUTES so they appear with zero metrics."""
        for prefix in settings.SERVICE_ROUTES:
            norm = normalize_route(prefix)
            if norm not in self._routes:
                self._routes[norm] = {
                    "requests": 0,
                    "errors": 0,
                    "error_rate": 0.0,
                    "latency_histogram": create_empty_histogram(self._buckets),
                }

    def configure_buckets(self, buckets: list[float]):
        """
        Configure custom latency histogram buckets.
        """
        with self._lock:
            self._buckets = sorted(list(buckets))
            for rdata in self._routes.values():
                rdata["latency_histogram"] = create_empty_histogram(self._buckets)

    def _init_service_if_missing(self, service_name: str):
        if service_name not in self._services:
            self._services[service_name] = {
                "request_volume": 0,
                "latencies": [],
                "cache_hits": 0,
                "cache_misses": 0,
                "circuit_breaker_state": "closed",
            }

    def _init_route_if_missing(self, route: str):
        if route not in self._routes:
            self._routes[route] = {
                "requests": 0,
                "errors": 0,
                "error_rate": 0.0,
                "latency_histogram": create_empty_histogram(self._buckets),
            }

    def record_request(
        self,
        service_name: str,
        latency_ms: float,
        is_cache_hit: bool = False,
        is_cache_miss: bool = False,
        is_error: bool = False,
        status_code: int = 200,
        caller_service: str | None = None,
        route: str | None = None,
    ):
        """
        Record a request completion for a downstream service and its route.
        """
        latency_float = float(latency_ms)

        # Resolve route pattern and service ID
        if route is not None:
            norm_route = normalize_route(route)
            s_name = service_name or norm_route.strip("/").split("/")[-1]
        elif service_name.startswith("/"):
            norm_route = normalize_route(service_name)
            s_name = norm_route.strip("/").split("/")[-1]
        else:
            s_name = service_name
            norm_route = normalize_route(f"/api/v1/{service_name}")

        # Check error status: HTTP 5xx or explicitly passed error
        has_error = bool(is_error or (status_code >= 500))

        with self._lock:
            # 1. Update service metrics
            self._init_service_if_missing(s_name)
            svc = self._services[s_name]
            svc["request_volume"] += 1
            svc["latencies"].append(latency_float)

            if is_cache_hit:
                svc["cache_hits"] += 1
            elif is_cache_miss:
                svc["cache_misses"] += 1

            # 2. Update route metrics
            self._init_route_if_missing(norm_route)
            r_data = self._routes[norm_route]
            r_data["requests"] += 1
            if has_error:
                r_data["errors"] += 1

            total_req = r_data["requests"]
            err_count = r_data["errors"]
            r_data["error_rate"] = (
                round((err_count / total_req) * 100.0, 2) if total_req > 0 else 0.0
            )

            bucket = get_bucket_label(latency_float, self._buckets)
            if bucket in r_data["latency_histogram"]:
                r_data["latency_histogram"][bucket] += 1
            else:
                r_data["latency_histogram"][bucket] = 1

            # 3. Update caller metrics
            if caller_service:
                caller_clean = str(caller_service).strip()
                if caller_clean:
                    self._callers[caller_clean] = self._callers.get(caller_clean, 0) + 1

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

    def record_caller(self, caller_service: str):
        """
        Record an incoming request by caller service.
        """
        if not caller_service:
            return
        caller_clean = str(caller_service).strip()
        if not caller_clean:
            return
        with self._lock:
            self._callers[caller_clean] = self._callers.get(caller_clean, 0) + 1

    def get_service_metrics(self, service_name: str) -> dict[str, Any]:
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

    def get_route_metrics(self, route: str) -> dict[str, Any]:
        """
        Get aggregated metrics for a single route pattern.
        """
        norm_route = normalize_route(route)
        with self._lock:
            self._init_route_if_missing(norm_route)
            r = self._routes[norm_route]
            return {
                "requests": r["requests"],
                "errors": r["errors"],
                "error_rate": r["error_rate"],
                "latency_histogram": dict(r["latency_histogram"]),
            }

    def get_cache_metrics(self) -> dict[str, Any]:
        """
        Return aggregated cache statistics across all services.
        """
        with self._lock:
            hits = sum(s["cache_hits"] for s in self._services.values())
            misses = sum(s["cache_misses"] for s in self._services.values())

        total = hits + misses
        hit_rate = round((hits / total) * 100.0, 2) if total > 0 else 0.0
        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": hit_rate,
        }

    def get_top_callers(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Return caller services ordered descending by request count.
        """
        with self._lock:
            items = sorted(self._callers.items(), key=lambda x: x[1], reverse=True)

        if limit is not None:
            items = items[:limit]

        return [
            {"caller": caller, "requests": count, "count": count}
            for caller, count in items
        ]

    def get_all_metrics(self) -> dict[str, Any]:
        """
        Return aggregated metrics for all services and routes.
        Preserves all existing fields while adding structured M4 observability.
        """
        # Lazily query circuit breaker manager to prevent circular import
        try:
            from app.services.circuit_breaker import circuit_breaker_manager
        except ImportError:
            circuit_breaker_manager = None

        # Extract configured downstream service names from SERVICE_ROUTES
        known_services = set()
        for prefix in settings.SERVICE_ROUTES:
            if prefix.startswith("/api/v1/"):
                name = prefix.strip("/").split("/")[-1]
                known_services.add(name)

        with self._lock:
            for sname in self._services:
                known_services.add(sname)

        # Sync circuit breaker state and build per-service metrics
        services_metrics = {}
        circuit_breakers_metrics = {}
        for sname in sorted(known_services):
            current_metric_state = self._services.get(sname, {}).get("circuit_breaker_state", "closed")
            if circuit_breaker_manager is not None and sname in circuit_breaker_manager._services:
                real_state = circuit_breaker_manager.get_state(sname)
            else:
                real_state = current_metric_state

            self.set_circuit_breaker_state(sname, real_state)
            services_metrics[sname] = self.get_service_metrics(sname)
            circuit_breakers_metrics[sname] = {
                "state": real_state,
            }

        # Build route metrics
        with self._lock:
            routes_metrics = {
                r_path: {
                    "requests": r_val["requests"],
                    "errors": r_val["errors"],
                    "error_rate": r_val["error_rate"],
                    "latency_histogram": dict(r_val["latency_histogram"]),
                }
                for r_path, r_val in sorted(self._routes.items())
            }

        # Cache metrics
        cache_metrics = self.get_cache_metrics()

        # Top callers
        top_callers = self.get_top_callers()

        observability_metrics = {
            "routes": routes_metrics,
            "circuit_breakers": circuit_breakers_metrics,
            "cache": cache_metrics,
            "top_callers": top_callers,
        }

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": services_metrics,
            "metrics": observability_metrics,
            # Top-level aliases for direct consumer access
            "routes": routes_metrics,
            "circuit_breakers": circuit_breakers_metrics,
            "cache": cache_metrics,
            "top_callers": top_callers,
        }

    def reset(self):
        """
        Reset all recorded metrics back to initial state.
        """
        with self._lock:
            self._services.clear()
            self._routes.clear()
            self._callers.clear()
            self._prepopulate_routes()


# Global singleton metrics collector instance
metrics_collector = MetricsCollector()
