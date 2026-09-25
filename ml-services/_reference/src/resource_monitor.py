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
from dataclasses import asdict, dataclass
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
    """Per-batch process resource metrics."""

    def __init__(self) -> None:
        self._process = psutil.Process()

    def _cpu_seconds(self) -> float:
        """
        Return total CPU time consumed by this process.

        This uses user + system CPU time instead of
        psutil.Process.cpu_percent(interval=None).

        Measuring CPU time at the beginning and end of a batch
        gives an accurate CPU percentage for that batch and
        remains independent when multiple batches run concurrently.
        """
        times = self._process.cpu_times()
        return times.user + times.system

    def start(self) -> tuple[float, float]:
        """
        Start measuring a batch.

        Returns:
            tuple[float, float]:
                (wall-clock start time, CPU start time)
        """
        return time.perf_counter(), self._cpu_seconds()

    def snapshot(self) -> ResourceSnapshot:
        """
        Return the current process resource snapshot.

        Snapshot CPU is based on the current process CPU time.
        Batch CPU usage should be measured using start() and
        measure_batch().
        """
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        return ResourceSnapshot(
            cpu_percent=0.0,
            memory_percent=self._process.memory_percent(),
            memory_mb=memory_mb,
            timestamp=time.time(),
        )

    def measure_batch(
        self,
        batch_size: int,
        model_count: int,
        total_predictions: int,
        started_at: float,
        cpu_started_at: float,
    ) -> BatchMetrics:
        """
        Measure resource usage for one completed batch.

        CPU percentage is calculated from CPU time consumed by
        the process during this batch divided by elapsed wall time.

        The value can exceed 100% when the process uses multiple
        CPU cores.
        """

        wall_seconds = time.perf_counter() - started_at
        cpu_seconds = self._cpu_seconds() - cpu_started_at

        cpu_percent = (
            (cpu_seconds / wall_seconds) * 100
            if wall_seconds > 0
            else 0.0
        )

        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        return BatchMetrics(
            batch_size=batch_size,
            model_count=model_count,
            total_predictions=total_predictions,
            latency_ms=round(wall_seconds * 1000, 3),
            cpu_percent=round(cpu_percent, 3),
            memory_percent=round(
                self._process.memory_percent(),
                3,
            ),
            memory_mb=round(memory_mb, 3),
        )