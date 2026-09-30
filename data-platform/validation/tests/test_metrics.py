from unittest.mock import patch
from src.metrics import start_metrics_server, update_batch_metrics, increment_dlq_count


@patch("src.metrics.start_http_server")
def test_start_metrics_server(mock_start):
    """Verifies the Prometheus HTTP server initializes on the correct port."""
    start_metrics_server(8080)
    mock_start.assert_called_once_with(8080)


@patch("src.metrics.PASS_RATE_GAUGE")
@patch("src.metrics.THROUGHPUT_GAUGE")
def test_update_batch_metrics_success(mock_throughput, mock_pass_rate):
    """Verifies gauge calculations for standard batch results."""
    update_batch_metrics(total_rows=100, affected_rows=10, duration_seconds=2.0)

    mock_pass_rate.set.assert_called_once_with(0.9)
    mock_throughput.set.assert_called_once_with(50.0)


@patch("src.metrics.PASS_RATE_GAUGE")
@patch("src.metrics.THROUGHPUT_GAUGE")
def test_update_batch_metrics_zero_safeguards(mock_throughput, mock_pass_rate):
    """Verifies gauges bypass updates safely on 0 rows or 0 duration."""
    update_batch_metrics(total_rows=0, affected_rows=0, duration_seconds=0.0)

    mock_pass_rate.set.assert_not_called()
    mock_throughput.set.assert_not_called()


@patch("src.metrics.DLQ_COUNTER")
def test_increment_dlq_count(mock_dlq):
    """Verifies the DLQ counter increments correctly."""
    increment_dlq_count(5)
    mock_dlq.inc.assert_called_once_with(5)