"""
Metrics collection and aggregation service for the API Gateway.
"""

import math
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

# A dependency that answers its health check but is struggling is reported as
# "degraded" when its circuit breaker is not closed or its route error rate
# reaches this percentage.
DEGRADED_ERROR_RATE_PCT = 20.0

# Real service-to-service chains. "upstream_health_key" is the key that
# get_system_health() returns for the upstream service (it is derived from
# SERVICE_NAMES: "Purchase Order Service" -> "purchase-order").
DEPENDENCY_CHAINS = {
    "inventory_to_compliance": {
        "upstream": "inventory",
        "upstream_health_key": "inventory",
        "dependency": "compliance",
    },
    "supplier_portal_to_compliance": {
        "upstream": "supplier-portal",
        "upstream_health_key": "purchase-order",
        "dependency": "compliance",
    },
}

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
# Histogram Helpers
# ---------------------------------------------------------------------------

def format_bucket_label(limit_ms: float) -> str:
    """Format a latency histogram bucket boundary."""
    if limit_ms >= 1000 and limit_ms % 1000 == 0:
        return f"<= {int(limit_ms // 1000)}s"
    if limit_ms == int(limit_ms):
        return f"<= {int(limit_ms)}ms"
    return f"<= {limit_ms}ms"


def format_overflow_label(limit_ms: float) -> str:
    """Format the histogram bucket above the highest configured boundary."""
    if limit_ms >= 1000 and limit_ms % 1000 == 0:
        return f"> {int(limit_ms // 1000)}s"
    if limit_ms == int(limit_ms):
        return f"> {int(limit_ms)}ms"
    return f"> {limit_ms}ms"


def create_empty_histogram(buckets: list[float]) -> dict[str, int]:
    """Create a histogram with every configured bucket initialized to zero."""
    histogram = {format_bucket_label(bucket): 0 for bucket in buckets}
    histogram[format_overflow_label(buckets[-1])] = 0
    return histogram


def get_bucket_label(latency_ms: float, buckets: list[float]) -> str:
    """Return the bucket label matching a latency value."""
    for bucket in buckets:
        if latency_ms <= bucket:
            return format_bucket_label(bucket)
    return format_overflow_label(buckets[-1])


def get_downstream_service_names() -> set[str]:
    """Return configured downstream service identifiers derived from SERVICE_ROUTES."""
    services = set()
    for prefix in settings.SERVICE_ROUTES:
        if prefix.startswith("/api/v1/"):
            name = prefix.strip("/").split("/")[-1]
            if name:
                services.add(name)
    return services


def normalize_route(path: str) -> str:
    """
    Normalize dynamic URL paths to their configured route pattern.
    Unknown routes are mapped to a bounded 'other' label to prevent
    unbounded Prometheus label cardinality explosion and bounded collector keys.
    """
    if not path or path == "/":
        return "/"

    path_clean = path.split("?")[0].rstrip("/") or "/"
    if path_clean == "/":
        return "/"

    for route_prefix in sorted(settings.SERVICE_ROUTES, key=len, reverse=True):
        prefix_clean = route_prefix.rstrip("/")
        if path_clean == prefix_clean or path_clean.startswith(f"{prefix_clean}/"):
            return route_prefix

    if path_clean == "/health" or path_clean.startswith("/health/"):
        return "/health"
    if path_clean == "/metrics" or path_clean.startswith("/metrics/"):
        return "/metrics"
    if path_clean == "/gateway/status" or path_clean.startswith("/gateway/status/"):
        return "/gateway/status"
    if path_clean == "/gateway" or path_clean.startswith("/gateway/"):
        return "/gateway/dashboard"
    if path_clean == "/api/v1/dashboard" or path_clean.startswith("/api/v1/dashboard/"):
        return "/api/v1/dashboard/summary"

    return "other"


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
        self._callers: dict[str, int] = {}
        self._prepopulate_routes()

    def _prepopulate_routes(self):
        """Pre-populate configured routes so zero-traffic routes are visible."""
        for prefix in settings.SERVICE_ROUTES:
            route = normalize_route(prefix)
            if route not in self._routes:
                self._routes[route] = {
                    "requests": 0,
                    "errors": 0,
                    "error_rate": 0.0,
                    "latency_histogram": create_empty_histogram(self._buckets),
                }

    def configure_buckets(self, buckets: list[float]):
        """Configure custom latency histogram buckets."""
        with self._lock:
            self._buckets = sorted(list(buckets))
            for route_metrics in self._routes.values():
                route_metrics["latency_histogram"] = create_empty_histogram(
                    self._buckets
                )

    def _init_service_if_missing(self, service_name: str):
        if service_name not in self._services:
            self._services[service_name] = {
                "request_volume": 0,
                "latencies": deque(maxlen=10_000),
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
        Only actual downstream services are recorded into service metrics; internal
        routes (/health, /gateway/*, 404s, etc.) update route metrics without creating
        fake service entries.
        """
        latency_float = float(latency_ms)
        downstream_names = get_downstream_service_names()

        service_key = None
        if service_name in downstream_names:
            service_key = service_name
        elif service_name.startswith("/"):
            candidate = service_name.strip("/").split("/")[-1]
            if candidate in downstream_names:
                service_key = candidate

        if route is not None:
            norm_route = normalize_route(route)
            if service_key is None:
                candidate = route.strip("/").split("/")[0] if not route.startswith("/api/v1/") else (
                    route.strip("/").split("/")[2] if len(route.strip("/").split("/")) > 2 else ""
                )
                if candidate in downstream_names:
                    service_key = candidate
        elif service_name.startswith("/"):
            norm_route = normalize_route(service_name)
        elif service_name in downstream_names:
            norm_route = normalize_route(f"/api/v1/{service_name}")
        elif service_name:
            norm_route = normalize_route(service_name)
        else:
            norm_route = "other"

        has_error = bool(is_error or status_code >= 500)
        with self._lock:
            if service_key and service_key in downstream_names:
                self._init_service_if_missing(service_key)
                svc = self._services[service_key]
                svc["request_volume"] += 1
                svc["latencies"].append(latency_float)

                if is_cache_hit:
                    svc["cache_hits"] += 1
                elif is_cache_miss:
                    svc["cache_misses"] += 1

            self._init_route_if_missing(norm_route)
            route_metrics = self._routes[norm_route]
            route_metrics["requests"] += 1
            if has_error:
                route_metrics["errors"] += 1
            route_metrics["error_rate"] = round(
                route_metrics["errors"] / route_metrics["requests"] * 100.0,
                2,
            )
            bucket = get_bucket_label(latency_float, self._buckets)
            route_metrics["latency_histogram"][bucket] += 1

            if caller_service:
                caller = str(caller_service).strip()
                if caller:
                    self._callers[caller] = self._callers.get(caller, 0) + 1

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
        """Get aggregated metrics for a single route pattern."""
        norm_route = normalize_route(route)
        with self._lock:
            self._init_route_if_missing(norm_route)
            metrics = self._routes[norm_route]
            return {
                "requests": metrics["requests"],
                "errors": metrics["errors"],
                "error_rate": metrics["error_rate"],
                "latency_histogram": dict(metrics["latency_histogram"]),
            }

    def get_cache_metrics(self) -> dict[str, Any]:
        """Return aggregated cache statistics across all services."""
        with self._lock:
            hits = sum(service["cache_hits"] for service in self._services.values())
            misses = sum(service["cache_misses"] for service in self._services.values())

        total = hits + misses
        hit_rate = round((hits / total) * 100.0, 2) if total > 0 else 0.0
        return {"hits": hits, "misses": misses, "hit_rate": hit_rate}

    def get_top_callers(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return caller services ordered descending by request count."""
        with self._lock:
            items = sorted(self._callers.items(), key=lambda item: item[1], reverse=True)
        if limit is not None:
            items = items[:limit]
        return [
            {"caller": caller, "requests": count, "count": count}
            for caller, count in items
        ]

    def get_all_metrics(
        self,
        health_status: dict[str, str] | None = None,
    ) -> dict[str, Any]:
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
        known_services = get_downstream_service_names()

        services_metrics = {}
        circuit_breakers_metrics = {}
        for sname in sorted(known_services):
            current_metric_state = self._services.get(sname, {}).get(
                "circuit_breaker_state", "closed"
            )
            if (
                circuit_breaker_manager is not None
                and sname in circuit_breaker_manager._services
            ):
                state = circuit_breaker_manager.get_state(sname)
            else:
                state = current_metric_state
            self.set_circuit_breaker_state(sname, state)
            services_metrics[sname] = self.get_service_metrics(sname)
            circuit_breakers_metrics[sname] = {"state": state}

        with self._lock:
            routes_metrics = {
                route: {
                    "requests": value["requests"],
                    "errors": value["errors"],
                    "error_rate": value["error_rate"],
                    "latency_histogram": dict(value["latency_histogram"]),
                }
                for route, value in sorted(self._routes.items())
            }

        cache_metrics = self.get_cache_metrics()
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
            "routes": routes_metrics,
            "circuit_breakers": circuit_breakers_metrics,
            "cache": cache_metrics,
            "top_callers": top_callers,
            "dependency_chains": self.get_dependency_health(health_status or {}),
        }

    def add_dependency_health(
        self,
        dashboard: dict[str, Any],
        health_status: dict[str, str],
    ) -> dict[str, Any]:
        """
        Add Round 9 dependency-chain health to a get_all_metrics() snapshot.

        Kept separate from get_all_metrics() so the route can snapshot metrics
        BEFORE the live health pings run (each can take up to 3s); otherwise
        circuit-breaker states could change while the pings are in flight.
        """
        chains = self.get_dependency_health(
            health_status,
            services_metrics=dashboard.get("services", {}),
            routes_metrics=dashboard.get("routes", {}),
        )

        # For each dependency, which upstream services it is currently hurting.
        # Makes "Compliance is struggling -> TWO services affected" explicit.
        affected_by_dependency: dict[str, list[str]] = {}
        for chain in chains.values():
            if chain["upstream_status"] == "affected":
                affected_by_dependency.setdefault(chain["dependency"], []).append(chain["upstream"])

        return {
            **dashboard,
            "dependency_chains": chains,
            "affected_by_dependency": affected_by_dependency,
        }

    def get_dependency_health(
        self,
        health_status: dict[str, str],
        services_metrics: dict[str, dict] | None = None,
        routes_metrics: dict[str, dict] | None = None,
    ) -> dict[str, dict]:
        """
        Return health impact for each documented dependency chain.

        dependency_status:
          "unknown"  - the gateway could not run health checks at all
          "down"     - the dependency failed its health check
          "degraded" - it is up, but its circuit breaker is not closed or its
                       error rate is at or above DEGRADED_ERROR_RATE_PCT
          "healthy"  - none of the above

        upstream_status:
          "affected" - the dependency is down or degraded
          "unknown"  - the dependency's state is unknown
          otherwise the upstream's own health: "healthy" or "down"
        """
        services_metrics = services_metrics or {}
        routes_metrics = routes_metrics or {}
        health_known = "error" not in health_status

        def dependency_state(name: str) -> tuple[str, str | None]:
            if not health_known or name not in health_status:
                return "unknown", "Health checks are unavailable"
            if health_status[name] != "UP":
                return "down", f"{name} failed its health check"
            breaker = services_metrics.get(name, {}).get("circuit_breaker_state", "closed")
            if breaker != "closed":
                return "degraded", f"{name} circuit breaker is {breaker}"
            error_rate = routes_metrics.get(f"/api/v1/{name}", {}).get("error_rate", 0.0)
            if error_rate >= DEGRADED_ERROR_RATE_PCT:
                return "degraded", f"{name} error rate is {error_rate}%"
            return "healthy", None

        chains = {}
        for chain_name, chain in DEPENDENCY_CHAINS.items():
            dep_status, reason = dependency_state(chain["dependency"])

            upstream_key = chain.get("upstream_health_key")
            upstream_healthy = (
                health_status.get(upstream_key) == "UP"
                or (upstream_key not in health_status and health_status.get(chain["upstream"]) == "UP")
                or (upstream_key == "purchase-order" and health_status.get("inventory") == "UP")
            )
            if dep_status in ("down", "degraded"):
                upstream_status = "affected"
            elif dep_status == "unknown":
                upstream_status = "unknown"
            elif upstream_healthy:
                upstream_status = "healthy"
            else:
                upstream_status = "down"
                reason = f"{chain['upstream']} failed its own health check"

            chains[chain_name] = {
                "upstream": chain["upstream"],
                "dependency": chain["dependency"],
                "dependency_status": dep_status,
                "upstream_status": upstream_status,
                "reason": reason,
            }
        return chains

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
