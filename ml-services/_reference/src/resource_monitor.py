"""
Resource monitoring for batch model serving.

Tracks:
- CPU usage
- Memory usage
- Number of requests
- Number of models
- Batch size
- Total latency
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Any

import psutil


@dataclass
class ResourceSnapshot:
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    timestamp: float


@dataclass
class BatchMetrics:
    batch_size: int
    model_count: int
    total_predictions: int
    latency_ms: float
    cpu_percent: float
    memory_percent: float
    memory_mb: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResourceMonitor:
    """Collect lightweight process/system resource metrics."""

    def snapshot(self) -> ResourceSnapshot:
        process = psutil.Process()

        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        return ResourceSnapshot(
            cpu_percent=process.cpu_percent(interval=None),
            memory_percent=process.memory_percent(),
            memory_mb=memory_mb,
            timestamp=time.time(),
        )

    def measure_batch(
        self,
        batch_size: int,
        model_count: int,
        total_predictions: int,
        started_at: float,
    ) -> BatchMetrics:
        snapshot = self.snapshot()

        latency_ms = (time.perf_counter() - started_at) * 1000

        return BatchMetrics(
            batch_size=batch_size,
            model_count=model_count,
            total_predictions=total_predictions,
            latency_ms=round(latency_ms, 3),
            cpu_percent=round(snapshot.cpu_percent, 3),
            memory_percent=round(snapshot.memory_percent, 3),
            memory_mb=round(snapshot.memory_mb, 3),
        )