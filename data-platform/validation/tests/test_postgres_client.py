"""
Unit tests for postgres_client with a fake psycopg2. The point: every
failure is LOUD (PersistenceError), never a pretend save.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from data_validator.postgres_client import (
    PersistenceError,
    fetch_run,
    persist_validation_result,
)
from data_validator.validator import ValidationResult

DSN = "postgresql://user:s3cret-pass@localhost:5432/validation_db"


@pytest.fixture
def result():
    return ValidationResult(
        config_version="dev-1.0.0",
        passed=False,
        batch_rejected=False,
        total_rows=100,
        total_rows_affected=4,
        sla_breached=False,
        evaluated_rules=["sku_format", "quantity_positive"],
    )


@pytest.fixture
def fake_psycopg2(monkeypatch):
    """A fake psycopg2 whose cursor returns run_id 42."""
    monkeypatch.setenv("DATABASE_URL", DSN)
    module = MagicMock()
    conn = module.connect.return_value
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (42,)
    with patch.dict(sys.modules, {"psycopg2": module}):
        yield module, conn, cursor


def test_saves_run_and_returns_run_id(fake_psycopg2, result):
    module, conn, cursor = fake_psycopg2

    run_id = persist_validation_result("sales.csv", result, 1.5)

    assert run_id == 42
    module.connect.assert_called_once_with(DSN)
    sql, params = cursor.execute.call_args[0]
    assert "INSERT INTO validation_runs" in sql
    assert "%s" in sql  # parameterised, never string-built
    assert params == (
        "batch", "sales.csv", "dev-1.0.0", ["sku_format", "quantity_positive"],
        False, False, 100, 4, 1.5, False,
    )
    conn.close.assert_called_once()


def test_rules_applied_and_mode_can_be_overridden(fake_psycopg2, result):
    _, _, cursor = fake_psycopg2

    persist_validation_result(
        "sales.raw", result, 0.5, mode="stream", rules_applied=["only_this"]
    )

    params = cursor.execute.call_args[0][1]
    assert params[0] == "stream"
    assert params[3] == ["only_this"]


def test_missing_database_url_is_an_error(monkeypatch, result):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch.dict(sys.modules, {"psycopg2": MagicMock()}):
        with pytest.raises(PersistenceError, match="DATABASE_URL is not set"):
            persist_validation_result("sales.csv", result, 1.0)


def test_blocked_driver_is_an_error_not_a_mock(monkeypatch, result):
    monkeypatch.setenv("DATABASE_URL", DSN)
    with patch.dict(sys.modules, {"psycopg2": None}):  # import fails
        with pytest.raises(PersistenceError, match="NOT saved"):
            persist_validation_result("sales.csv", result, 1.0)


def test_connection_failure_never_leaks_the_password(fake_psycopg2, result):
    module, _, _ = fake_psycopg2
    module.connect.side_effect = Exception("could not connect to server")

    with pytest.raises(PersistenceError) as exc_info:
        persist_validation_result("sales.csv", result, 1.0)

    assert "s3cret-pass" not in str(exc_info.value)


def test_insert_failure_raises_and_closes_connection(fake_psycopg2, result):
    _, conn, cursor = fake_psycopg2
    cursor.execute.side_effect = Exception('relation "validation_runs" does not exist')

    with pytest.raises(PersistenceError, match="does not exist"):
        persist_validation_result("sales.csv", result, 1.0)

    conn.close.assert_called_once()


@pytest.mark.parametrize("kwargs, message", [
    ({"mode": "nightly"}, "mode must be one of"),
    ({"dataset_name": ""}, "dataset_name"),
    ({"duration_seconds": -1.0}, "negative"),
])
def test_bad_arguments_are_rejected(result, kwargs, message):
    args = {"dataset_name": "sales.csv", "result": result, "duration_seconds": 1.0}
    args.update(kwargs)

    with pytest.raises(ValueError, match=message):
        persist_validation_result(**args)


def test_fetch_run_returns_a_dict(fake_psycopg2):
    _, conn, cursor = fake_psycopg2
    cursor.fetchone.return_value = (42, "batch", "sales.csv")
    cursor.description = [("run_id",), ("mode",), ("dataset_name",)]

    row = fetch_run(42)

    assert row == {"run_id": 42, "mode": "batch", "dataset_name": "sales.csv"}
    assert cursor.execute.call_args[0][1] == (42,)
    conn.close.assert_called_once()


def test_fetch_run_returns_none_when_missing(fake_psycopg2):
    _, _, cursor = fake_psycopg2
    cursor.fetchone.return_value = None

    assert fetch_run(999) is None


def test_fetch_run_failure_is_an_error(fake_psycopg2):
    _, _, cursor = fake_psycopg2
    cursor.execute.side_effect = Exception("boom")

    with pytest.raises(PersistenceError, match="Could not read validation run 7"):
        fetch_run(7)