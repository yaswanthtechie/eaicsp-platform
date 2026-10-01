import socket
import urllib.request
from unittest.mock import patch

from prometheus_client import REGISTRY

from data_validator.metrics import (
    increment_dlq_count,
    record_persist_failure,
    start_metrics_server,
    update_batch_metrics,
)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_metrics_endpoint_serves_real_values_over_http():
    """Start the real Prometheus server and scrape /metrics like Prometheus would."""
    port = _free_port()
    start_metrics_server(port)

    dlq_before = REGISTRY.get_sample_value("validation_dlq_total") or 0.0
    update_batch_metrics(total_rows=200, affected_rows=50, duration_seconds=4.0)
    increment_dlq_count(3)

    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5).read().decode()

    assert "validation_pass_rate 0.75" in body
    assert "validation_records_per_second 50.0" in body
    assert f"validation_dlq_total {dlq_before + 3}" in body


def test_record_persist_failure_increments_counter():
    before = REGISTRY.get_sample_value("validation_persist_failures_total") or 0.0

    record_persist_failure()

    assert REGISTRY.get_sample_value("validation_persist_failures_total") == before + 1


@patch("data_validator.metrics.start_http_server")
def test_start_metrics_server(mock_start):
    """Verifies the Prometheus HTTP server initializes on the correct port."""
    start_metrics_server(8080)
    mock_start.assert_called_once_with(8080)


@patch("data_validator.metrics.PASS_RATE_GAUGE")
@patch("data_validator.metrics.THROUGHPUT_GAUGE")
def test_update_batch_metrics_success(mock_throughput, mock_pass_rate):
    """Verifies gauge calculations for standard batch results."""
    update_batch_metrics(total_rows=100, affected_rows=10, duration_seconds=2.0)

    mock_pass_rate.set.assert_called_once_with(0.9)
    mock_throughput.set.assert_called_once_with(50.0)


@patch("data_validator.metrics.PASS_RATE_GAUGE")
@patch("data_validator.metrics.THROUGHPUT_GAUGE")
def test_update_batch_metrics_zero_safeguards(mock_throughput, mock_pass_rate):
    """Verifies gauges bypass updates safely on 0 rows or 0 duration."""
    update_batch_metrics(total_rows=0, affected_rows=0, duration_seconds=0.0)

    mock_pass_rate.set.assert_not_called()
    mock_throughput.set.assert_not_called()


@patch("data_validator.metrics.DLQ_COUNTER")
def test_increment_dlq_count(mock_dlq):
    """Verifies the DLQ counter increments correctly."""
    increment_dlq_count(5)
    mock_dlq.inc.assert_called_once_with(5)