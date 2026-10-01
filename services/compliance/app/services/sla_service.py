import time
from datetime import datetime, timezone
from threading import Lock


SLA_LATENCY_THRESHOLD_MS = 500


class SLAMetrics:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc)

        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.slow_requests = 0

        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0

        self._lock = Lock()

    def record_request(
        self,
        duration_ms: float,
        success: bool,
    ) -> None:
        with self._lock:
            self.total_requests += 1

            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1

            self.total_latency_ms += duration_ms

            if duration_ms > self.max_latency_ms:
                self.max_latency_ms = duration_ms

            if duration_ms > SLA_LATENCY_THRESHOLD_MS:
                self.slow_requests += 1

    def get_status(self) -> dict:
        # Import here to avoid a circular import:
        #
        # internal_compliance_service
        #     -> sla_service
        #     -> internal_compliance_service
        #
        from app.services.internal_compliance_service import (
            get_cache_metrics,
        )

        with self._lock:
            if self.total_requests > 0:
                average_latency_ms = (
                    self.total_latency_ms
                    / self.total_requests
                )
            else:
                average_latency_ms = 0.0

            if self.failed_requests > 0:
                status = "degraded"
            elif (
                average_latency_ms
                > SLA_LATENCY_THRESHOLD_MS
            ):
                status = "degraded"
            else:
                status = "healthy"

            uptime_seconds = (
                datetime.now(timezone.utc)
                - self.started_at
            ).total_seconds()

            cache_metrics = get_cache_metrics()

            return {
                "service": "compliance",
                "status": status,
                "uptime_status": "available",
                "started_at": self.started_at.isoformat(),
                "uptime_seconds": round(
                    uptime_seconds,
                    2,
                ),

                # SLA request metrics
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "slow_requests": self.slow_requests,
                "average_latency_ms": round(
                    average_latency_ms,
                    2,
                ),
                "max_latency_ms": round(
                    self.max_latency_ms,
                    2,
                ),
                "latency_threshold_ms": (
                    SLA_LATENCY_THRESHOLD_MS
                ),

                # Cache metrics
                "cache_hits": cache_metrics[
                    "cache_hits"
                ],
                "cache_misses": cache_metrics[
                    "cache_misses"
                ],
                "cache_hit_rate": cache_metrics[
                    "cache_hit_rate"
                ],
            }


sla_metrics = SLAMetrics()


def start_timer() -> float:
    return time.perf_counter()


def record_request(
    start_time: float,
    success: bool,
) -> float:
    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    sla_metrics.record_request(
        duration_ms=duration_ms,
        success=success,
    )

    return duration_ms


def get_sla_status() -> dict:
    return sla_metrics.get_status()