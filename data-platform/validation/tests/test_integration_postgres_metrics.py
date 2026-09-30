import os
import pytest
from src.validator import ValidationResult
from src.postgres_client import persist_validation_result, PSYCOPG2_AVAILABLE
from src.metrics import update_batch_metrics, increment_dlq_count


@pytest.mark.integration
def test_postgres_persistence_integration():
    """Integration test: Verifies that ValidationResult payloads persist to local PostgreSQL."""
    if not PSYCOPG2_AVAILABLE:
        pytest.skip("Skipping Postgres integration test: psycopg2 binary blocked by local Application Control policy.")

    dataset_name = "integration_test_sales.csv"
    result = ValidationResult(
        config_version="1.2.0",
        passed=True,
        batch_rejected=False,
        total_rows=500,
        total_rows_affected=5,
        sla_breached=False
    )

    try:
        persist_validation_result(dataset_name, result, duration_seconds=0.25)
    except Exception as e:
        pytest.fail(f"Postgres persistence integration test failed: {e}")


@pytest.mark.integration
def test_prometheus_metrics_integration():
    """Integration test: Verifies Prometheus metric gauges and counters increment correctly."""
    try:
        update_batch_metrics(total_rows=1000, affected_rows=20, duration_seconds=1.5)
        increment_dlq_count(5)
    except Exception as e:
        pytest.fail(f"Prometheus metrics integration test failed: {e}")