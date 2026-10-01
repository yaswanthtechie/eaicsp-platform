"""
Prometheus metrics for validation runs.

These are updated by the REAL code paths: the batch CLI
(validate_cli.main) and the streaming consumer (streaming_validator).
There is deliberately no demo that publishes made-up numbers.
"""

from prometheus_client import Counter, Gauge, start_http_server

PASS_RATE_GAUGE = Gauge(
    "validation_pass_rate",
    "Fraction of rows passing validation (latest batch, or the stream so far)",
)
THROUGHPUT_GAUGE = Gauge(
    "validation_records_per_second",
    "Processing throughput in records per second",
)
DLQ_COUNTER = Counter(
    "validation_dlq_total",
    "Total number of records routed to the DLQ",
)
PERSIST_FAILURES_COUNTER = Counter(
    "validation_persist_failures_total",
    "Validation runs that could not be saved to Postgres",
)


def start_metrics_server(port: int = 8000):
    """Start the Prometheus HTTP server (serves /metrics on this port)."""
    start_http_server(port)


def update_batch_metrics(total_rows: int, affected_rows: int, duration_seconds: float):
    """Set the pass-rate and throughput gauges."""
    if total_rows > 0:
        pass_rate = (total_rows - affected_rows) / total_rows
        PASS_RATE_GAUGE.set(pass_rate)

    if duration_seconds > 0:
        throughput = total_rows / duration_seconds
        THROUGHPUT_GAUGE.set(throughput)


def increment_dlq_count(count: int = 1):
    """Increment the dead-letter queue counter."""
    DLQ_COUNTER.inc(count)


def record_persist_failure():
    """Count a run that could not be saved, so a broken DB shows on /metrics."""
    PERSIST_FAILURES_COUNTER.inc()