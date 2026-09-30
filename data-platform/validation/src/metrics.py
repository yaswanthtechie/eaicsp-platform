from prometheus_client import start_http_server, Gauge, Counter

# Define Prometheus metrics
PASS_RATE_GAUGE = Gauge('validation_pass_rate', 'Fraction of rows passing validation successfully')
THROUGHPUT_GAUGE = Gauge('validation_records_per_second', 'Processing throughput in records per second')
DLQ_COUNTER = Counter('validation_dlq_total', 'Total number of records routed to the DLQ')


def start_metrics_server(port: int = 8000):
    """Starts the Prometheus HTTP metrics server."""
    start_http_server(port)


def update_batch_metrics(total_rows: int, affected_rows: int, duration_seconds: float):
    """Updates batch-level performance and pass-rate gauges."""
    if total_rows > 0:
        pass_rate = (total_rows - affected_rows) / total_rows
        PASS_RATE_GAUGE.set(pass_rate)

    if duration_seconds > 0:
        throughput = total_rows / duration_seconds
        THROUGHPUT_GAUGE.set(throughput)


def increment_dlq_count(count: int = 1):
    """Increments the Dead-Letter Queue counter."""
    DLQ_COUNTER.inc(count)


def main():  # pragma: no cover
    import time
    print("Starting Prometheus metrics server on port 8000...")
    start_metrics_server(8000)
    # Simulate updating metrics
    update_batch_metrics(total_rows=500, affected_rows=10, duration_seconds=2.0)
    increment_dlq_count(3)
    print("Metrics updated. Server running... Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down metrics server.")

if __name__ == "__main__":  # pragma: no cover
    main()