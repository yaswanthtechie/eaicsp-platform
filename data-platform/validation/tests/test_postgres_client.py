import pytest
from unittest.mock import patch, MagicMock
from src.validator import ValidationResult
import src.postgres_client as pg_client


@pytest.fixture
def dummy_result():
    return ValidationResult(
        config_version="1.2.0", passed=True, batch_rejected=False,
        total_rows=100, total_rows_affected=0, sla_breached=False
    )


@patch("src.postgres_client.PSYCOPG2_AVAILABLE", False)
@patch("src.postgres_client.logger")
def test_persist_blocked_by_policy(mock_logger, dummy_result):
    """Verifies graceful mock fallback when system policy blocks psycopg2."""
    pg_client.persist_validation_result("test.csv", dummy_result, 1.0)

    mock_logger.info.assert_called_once()
    assert "[Mock DB]" in mock_logger.info.call_args[0][0]


@patch("src.postgres_client.PSYCOPG2_AVAILABLE", True)
@patch("src.postgres_client.psycopg2", create=True)  # Added create=True
def test_persist_success(mock_psycopg2, dummy_result):
    """Verifies correct SQL execution and commit when DB is available."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    pg_client.persist_validation_result("test.csv", dummy_result, 1.0)

    mock_psycopg2.connect.assert_called_once()
    mock_cursor.execute.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()


@patch("src.postgres_client.PSYCOPG2_AVAILABLE", True)
@patch("src.postgres_client.psycopg2", create=True)  # Added create=True
@patch("src.postgres_client.logger")
def test_persist_exception_handling(mock_logger, mock_psycopg2, dummy_result):
    """Verifies exceptions during connection or insert do not crash the pipeline."""
    mock_psycopg2.connect.side_effect = Exception("DB Timeout")

    pg_client.persist_validation_result("test.csv", dummy_result, 1.0)

    mock_logger.error.assert_called_once()
    assert "Failed to persist validation run" in mock_logger.error.call_args[0][0]