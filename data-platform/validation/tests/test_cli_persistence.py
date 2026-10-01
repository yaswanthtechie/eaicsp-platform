"""
The batch CLI saves every run to Postgres (Round 12-13, Milestone 3).
Postgres itself is faked here; tests/test_integration_postgres_metrics.py
covers the real database.
"""

from unittest.mock import patch

import pytest

from data_validator import validate_cli
from data_validator.postgres_client import PersistenceError


@pytest.fixture
def config_and_csv(tmp_path):
    dev_dir = tmp_path / "dev"
    dev_dir.mkdir()
    config = dev_dir / "rules.yaml"
    config.write_text(
        'version: "1.0.0"\n'
        "rules:\n"
        "  - name: test_not_null\n"
        "    field: target_col\n"
        "    type: not_null\n"
        "    severity: ERROR\n"
    )
    csv = tmp_path / "sales_batch.csv"
    csv.write_text("target_col,other_col\n1,A\n2,B\n")
    return config, csv


def _run(config, csv, tmp_path):
    return validate_cli.main([
        "--file", str(csv),
        "--config", str(config),
        "--output", str(tmp_path / "report.json"),
        "--env", "dev",
    ])


def test_batch_run_is_saved_with_real_counts(config_and_csv, tmp_path, monkeypatch):
    config, csv = config_and_csv
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    with patch(
        "data_validator.postgres_client.persist_validation_result",
        return_value=11,
    ) as persist:
        code = _run(config, csv, tmp_path)

    assert code == validate_cli.EXIT_SUCCESS
    kwargs = persist.call_args.kwargs
    assert kwargs["dataset_name"] == "sales_batch.csv"
    assert kwargs["mode"] == "batch"
    assert kwargs["result"].total_rows == 2
    assert kwargs["result"].evaluated_rules == ["test_not_null"]
    assert kwargs["duration_seconds"] >= 0


def test_failed_save_is_a_tool_error_and_is_counted(config_and_csv, tmp_path, monkeypatch):
    config, csv = config_and_csv
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")

    with patch(
        "data_validator.postgres_client.persist_validation_result",
        side_effect=PersistenceError("db down"),
    ), patch("data_validator.metrics.record_persist_failure") as failure:
        code = _run(config, csv, tmp_path)

    assert code == validate_cli.EXIT_TOOL_ERROR
    failure.assert_called_once()


def test_no_database_url_is_logged_not_faked(config_and_csv, tmp_path, monkeypatch):
    config, csv = config_and_csv
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # The CLI logger does not propagate to pytest's caplog, so watch it directly.
    with patch("data_validator.postgres_client.persist_validation_result") as persist, \
            patch.object(validate_cli.logger, "warning") as warning:
        code = _run(config, csv, tmp_path)

    assert code == validate_cli.EXIT_SUCCESS
    persist.assert_not_called()
    assert any(
        "NOT saved to Postgres" in str(call.args[0])
        for call in warning.call_args_list
    )