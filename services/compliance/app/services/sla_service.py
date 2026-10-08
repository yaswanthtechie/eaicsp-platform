import time
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Callable

from app.core.config import (
    SLA_LATENCY_THRESHOLD_MS,
    SLA_MAX_ERROR_RATE,
    SLA_WINDOW_SECONDS,
)


class SLAMetrics:
    

    def __init__(
        self,
        window_seconds: float = SLA_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.started_at = datetime.now(timezone.utc)

        # Lifetime counters (reporting only)
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.slow_requests = 0

        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0

        # Recent window: (timestamp, duration_ms, success)
        self._window_seconds = window_seconds
        self._clock = clock
        self._recent: deque[tuple[float, float, bool]] = deque()

        self._lock = Lock()

    def _prune(self, now: float) -> None:
        while (
            self._recent
            and now - self._recent[0][0] > self._window_seconds
        ):
            self._recent.popleft()

    def record_request(
        self,
        duration_ms: float,
        success: bool,
    ) -> None:
        with self._lock:
            now = self._clock()

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

            self._recent.append((now, duration_ms, success))
            self._prune(now)

    def get_status(self) -> dict:
        
        from app.services.internal_compliance_service import (
            get_cache_metrics,
        )

        with self._lock:
            now = self._clock()
            self._prune(now)

            # Lifetime average (reporting only)
            if self.total_requests > 0:
                average_latency_ms = (
                    self.total_latency_ms
                    / self.total_requests
                )
            else:
                average_latency_ms = 0.0

            # Recent window (decides health)
            window_requests = len(self._recent)
            window_failed = sum(
                1 for _, _, ok in self._recent if not ok
            )

            if window_requests > 0:
                window_error_rate = window_failed / window_requests
                window_average_latency_ms = (
                    sum(d for _, d, _ in self._recent)
                    / window_requests
                )
            else:
                window_error_rate = 0.0
                window_average_latency_ms = 0.0

            if (
                window_error_rate > SLA_MAX_ERROR_RATE
                or window_average_latency_ms
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
                "uptime_seconds": round(uptime_seconds, 2),

                # Lifetime request metrics
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
                "latency_threshold_ms": SLA_LATENCY_THRESHOLD_MS,

                # Recent window (what `status` is based on)
                "window_seconds": self._window_seconds,
                "window_requests": window_requests,
                "window_error_rate": round(
                    window_error_rate,
                    4,
                ),
                "window_average_latency_ms": round(
                    window_average_latency_ms,
                    2,
                ),
                "max_error_rate": SLA_MAX_ERROR_RATE,

                # Cache metrics
                "cache_hits": cache_metrics["cache_hits"],
                "cache_misses": cache_metrics["cache_misses"],
                "cache_hit_rate": cache_metrics["cache_hit_rate"],
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