import json
import logging
import math
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

import pandas as pd
import pytest

# Import the module explicitly from the src package
from src import validate_folder

# Add project root to path so we can resolve default rules dir
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MockReport:
    """Mock implementation of the DataValidator report object."""

    def __init__(self, passed, total_rows_affected=0, errors=None, warnings=None, sample_bad_rows=None,
                 sla_breached=False, sla_violations=None):
        self.config_version = "1.0.0"
        self.passed = passed
        self.total_rows_affected = total_rows_affected
        self.errors = errors or []
        self.warnings = warnings or []
        self.sample_bad_rows = sample_bad_rows or {}
        self.sla_breached = sla_breached
        self.sla_violations = sla_violations or []


@pytest.fixture
def temp_env(tmp_path):
    """Creates a temporary directory structure mimicking a real project."""
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "configs"
    reports_dir = tmp_path / "reports"
    data_dir.mkdir()
    config_dir.mkdir()

    config_file = config_dir / "rules.yaml"
    config_file.touch()

    mapping_file = tmp_path / "routing_map.json"
    mapping_data = {"*.csv": str(config_file)}
    mapping_file.write_text(json.dumps(mapping_data))

    valid_csv = data_dir / "valid.csv"
    valid_csv.touch()

    return {
        "root": tmp_path,
        "data_dir": data_dir,
        "config_file": config_file,
        "mapping_file": mapping_file,
        "valid_csv": valid_csv,
        "reports_dir": reports_dir
    }


def test_sanitize_for_json():
    """Test the JSON sanitizer replaces NaNs and preserves structure."""
    payload = {
        "valid_int": 1,
        "invalid_float": math.nan,
        "nested_list": [{"val": math.nan}, "string_val"]
    }

    cleaned = validate_folder.sanitize_for_json(payload)

    assert cleaned["invalid_float"] is None
    assert cleaned["nested_list"][0]["val"] is None
    assert cleaned["valid_int"] == 1
    assert cleaned["nested_list"][1] == "string_val"


def test_setup_logging(tmp_path):
    log_dir = tmp_path / "logs"
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    root_logger.handlers.clear()

    try:
        validate_folder.setup_logging(log_level="DEBUG", log_dir=str(log_dir))
        assert log_dir.exists()
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 1
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = original_handlers


@patch("src.validate_folder.DataValidator")
def test_load_validator(mock_validator_class):
    mock_instance = MagicMock()
    mock_validator_class.from_config.return_value = mock_instance
    cache = {}

    res1 = validate_folder._load_validator("config1.yaml", "strict", cache, "rules")
    assert res1 == mock_instance

    res2 = validate_folder._load_validator("config1.yaml", "strict", cache, "rules")
    assert res2 == mock_instance
    assert mock_validator_class.from_config.call_count == 1
    mock_validator_class.from_config.assert_called_with("config1.yaml", profile_name="strict", rules_dir="rules")


def test_validate_folder_invalid_folder():
    with pytest.raises(NotADirectoryError, match="Data folder not found"):
        validate_folder.validate_folder(folder_path="fake_folder")


def test_validate_folder_missing_config_and_mapping(temp_env):
    with pytest.raises(ValueError, match="Either 'config_path' or 'mapping_path' must be provided."):
        validate_folder.validate_folder(folder_path=temp_env["data_dir"])


def test_validate_folder_invalid_config_path(temp_env):
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        validate_folder.validate_folder(
            folder_path=temp_env["data_dir"],
            config_path="fake_config.yaml"
        )


def test_validate_folder_invalid_mapping_path(temp_env):
    with pytest.raises(FileNotFoundError, match="Mapping file not found"):
        validate_folder.validate_folder(
            folder_path=temp_env["data_dir"],
            mapping_path="fake_mapping.json"
        )


@patch("src.validate_folder.DataValidator")
def test_validate_folder_no_files_found(mock_validator_class, temp_env):
    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"],
        default_pattern="*.json"
    )
    assert summary == {}


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_single_config_no_reports(mock_validator_class, mock_read_csv, temp_env):
    mock_read_csv.return_value = MagicMock()

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MockReport(passed=True, total_rows_affected=10)
    mock_validator_class.from_config.return_value = mock_instance

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"],
        save_reports=False
    )

    assert summary["passed_files"] == 1
    assert not temp_env["reports_dir"].exists()


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_mapping_with_reports(mock_validator_class, mock_read_csv, temp_env):
    mock_read_csv.return_value = MagicMock()

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MockReport(
        passed=False,
        total_rows_affected=5,
        errors=[{"rule": "NullCheck", "count": 2}],
        sample_bad_rows={"NullCheck": [{"row": 1, "failed_value": math.nan}]},
        sla_breached=True,
        sla_violations=["SLA Breach Mock"]
    )
    mock_validator_class.from_config.return_value = mock_instance

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        mapping_path=temp_env["mapping_file"],
        output_dir=str(temp_env["reports_dir"]),
        save_reports=True
    )

    assert summary["failed_files"] == 1
    assert summary["files_with_sla_breaches"] == 1
    assert temp_env["reports_dir"].exists()

    report_file = temp_env["reports_dir"] / "valid_report.json"
    with open(report_file, "r") as f:
        data = json.load(f)
        assert data["sample_bad_rows"]["NullCheck"][0]["failed_value"] is None
        assert data["sla_breached"] is True


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_hybrid_mapping(mock_validator_class, mock_read_csv, temp_env):
    mock_read_csv.return_value = MagicMock()
    mock_instance = MagicMock()
    mock_instance.validate.return_value = MockReport(passed=True, total_rows_affected=10)
    mock_validator_class.from_config.return_value = mock_instance

    mapping_file = temp_env["root"] / "hybrid_map.json"
    hybrid_data = {
        "*.csv": {"config": str(temp_env["config_file"]), "profile": "strict"},
        "missing_config/*.csv": {"profile": "strict"}
    }
    mapping_file.write_text(json.dumps(hybrid_data))

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        mapping_path=mapping_file,
        profile_name="default"
    )

    assert summary["passed_files"] == 1

    # The internal logic correctly routes the mapped config file through resolve_env_path
    # before instantiating the validator. We must simulate that injection in our assertion.
    from src.validator import resolve_env_path
    expected_path = str(resolve_env_path(str(temp_env["config_file"]), env="dev"))

    mock_validator_class.from_config.assert_called_with(expected_path, profile_name="strict",
                                                        rules_dir=None)


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_empty_csv_error(mock_validator_class, mock_read_csv, temp_env):
    mock_read_csv.side_effect = pd.errors.EmptyDataError("No columns to parse")

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"]
    )

    assert summary["failed_files"] == 1


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_generic_processing_error(mock_validator_class, mock_read_csv, temp_env):
    mock_read_csv.side_effect = Exception("Out of Memory")

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"]
    )

    assert summary["failed_files"] == 1


@patch("time.perf_counter")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_global_timeout(mock_validator_class, mock_perf_counter, temp_env):
    (temp_env["data_dir"] / "valid2.csv").touch()

    mock_perf_counter.side_effect = [0.0, 10.0]

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"],
        global_timeout_seconds=5.0
    )

    assert summary["global_sla_breached"] is True
    assert summary["passed_files"] == 0
    assert summary["failed_files"] == 0


# --- CI/CD System Exit Code Tests ---

@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_success(mock_setup_logging, mock_validate_folder):
    test_args = ["validate_folder.py", "--folder", "/dummy/folder", "--config", "/dummy/config.yaml"]

    mock_validate_folder.return_value = {
        "failed_files": 0,
        "global_sla_breached": False,
        "files_with_sla_breaches": 0
    }

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_SUCCESS


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_exit_validation_failed(mock_setup_logging, mock_validate_folder):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy.yaml"]
    mock_validate_folder.return_value = {"failed_files": 1}

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_VALIDATION_FAILED


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_exit_global_timeout(mock_setup_logging, mock_validate_folder):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy.yaml"]
    mock_validate_folder.return_value = {"failed_files": 0, "global_sla_breached": True}

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_GLOBAL_TIMEOUT


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_exit_sla_breach(mock_setup_logging, mock_validate_folder):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy.yaml"]
    mock_validate_folder.return_value = {"failed_files": 0, "global_sla_breached": False, "files_with_sla_breaches": 1}

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_SLA_BREACH


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_system_exit_on_failure(mock_setup_logging, mock_validate_folder):
    test_args = ["validate_folder.py", "--folder", "/dummy/folder", "--config", "/dummy/config.yaml"]

    mock_validate_folder.side_effect = Exception("Critical Pipeline Failure")

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()

        assert exit_exc.value.code == validate_folder.EXIT_TOOL_ERROR


# --- Tests for Incremental Watermarking in Batch Folder Mode ---

@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
@patch("src.watermark.WatermarkManager")
def test_validate_folder_incremental_updates_watermark(mock_wm_class, mock_validator_class, mock_read_csv, temp_env):
    mock_df = pd.DataFrame({"transaction_id": [10, 20]})
    mock_read_csv.return_value = mock_df

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MockReport(passed=True, total_rows_affected=0)
    mock_validator_class.from_config.return_value = mock_instance

    mock_validator_class.filter_incremental.return_value = mock_df

    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"],
        incremental=True,
        watermark_col="transaction_id"
    )

    assert summary["passed_files"] == 1
    mock_wm_instance.get_watermark.assert_called_once()
    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
@patch("src.watermark.WatermarkManager")
def test_validate_folder_incremental_no_new_data(mock_wm_class, mock_validator_class, mock_read_csv, temp_env):
    mock_df = pd.DataFrame({"transaction_id": [1, 2]})
    mock_read_csv.return_value = mock_df

    mock_instance = MagicMock()
    mock_validator_class.from_config.return_value = mock_instance

    mock_validator_class.filter_incremental.return_value = pd.DataFrame()

    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        config_path=temp_env["config_file"],
        incremental=True,
        watermark_col="transaction_id"
    )

    assert summary["skipped_files"] == 1
    assert summary["passed_files"] == 0
    mock_instance.validate.assert_not_called()
    mock_wm_instance.set_watermark.assert_not_called()


# --- Tests for Profile Interception in CLI ---

@patch("src.validate_folder.DataValidator.list_profiles", return_value=["default", "strict"])
@patch("src.validate_folder.setup_logging")
def test_main_list_profiles_config(mock_setup_logging, mock_list_profiles):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy/config.yaml", "--list-profiles"]
    with patch.object(sys, 'argv', test_args):
        # Assert return value directly without expecting SystemExit
        assert validate_folder.main() == validate_folder.EXIT_SUCCESS

    mock_list_profiles.assert_called_once_with("/dummy/config.yaml")


@patch("src.validate_folder.DataValidator.list_profiles", return_value=[])
@patch("src.validate_folder.setup_logging")
def test_main_list_profiles_config_empty(mock_setup_logging, mock_list_profiles):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy/config.yaml", "--list-profiles"]
    with patch.object(sys, 'argv', test_args):
        assert validate_folder.main() == validate_folder.EXIT_SUCCESS

    mock_list_profiles.assert_called_once_with("/dummy/config.yaml")


@patch("src.validate_folder.DataValidator.list_profiles", return_value=["strict"])
@patch("src.validate_folder.setup_logging")
def test_main_list_profiles_mapping_success(mock_setup_logging, mock_list_profiles, temp_env):
    mapping_file = temp_env["root"] / "map.json"
    mapping_file.write_text(json.dumps({
        "*.csv": "cfg1.yaml",
        "*.tsv": {"config": "cfg2.yaml"},
        "duplicate_test": "cfg1.yaml"
    }))

    test_args = ["validate_folder.py", "--folder", "/dummy", "--mapping", str(mapping_file), "--list-profiles"]
    with patch.object(sys, 'argv', test_args):
        assert validate_folder.main() == validate_folder.EXIT_SUCCESS

    assert mock_list_profiles.call_count == 2


@patch("src.validate_folder.setup_logging")
@patch("src.validate_folder.logger.error")
def test_main_list_profiles_mapping_error(mock_logger_error, mock_setup_logging):
    test_args = ["validate_folder.py", "--folder", "/dummy", "--mapping", "non_existent_map.json", "--list-profiles"]
    with patch.object(sys, 'argv', test_args):
        assert validate_folder.main() == validate_folder.EXIT_SUCCESS

    mock_logger_error.assert_called_once()
    assert "Failed to read mapping file for profiles" in mock_logger_error.call_args[0][0]


# --- Tests for Environment Routing (Cross-Environment Versioning) ---

@patch("src.validate_folder.resolve_env_path")
@patch("src.validate_folder.pd.read_csv")
@patch("src.validate_folder.DataValidator")
def test_validate_folder_env_mapping_resolution(mock_validator_class, mock_read_csv, mock_resolve_env, temp_env):
    """Verifies that the target environment is injected into nested mapping paths."""
    mock_read_csv.return_value = MagicMock()
    mock_instance = MagicMock()
    mock_instance.validate.return_value = MockReport(passed=True, total_rows_affected=10)
    mock_validator_class.from_config.return_value = mock_instance

    # Mock resolve_env_path to return the dummy config file so it passes the subsequent is_file() checks
    mock_resolve_env.return_value = temp_env["config_file"]

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        mapping_path=temp_env["mapping_file"],
        env="staging"
    )

    assert summary["passed_files"] == 1
    # Assert resolve_env_path was called to inject env="staging" for the nested mapping config
    mock_resolve_env.assert_called()
    assert mock_resolve_env.call_args.kwargs.get("env") == "staging"


@patch("os.getenv", return_value="prod")
@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_env_os_variable(mock_setup_logging, mock_validate_folder, mock_getenv):
    """Verifies that main() picks up the VALIDATOR_ENV OS variable by default."""
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy.yaml"]
    mock_validate_folder.return_value = {"failed_files": 0, "global_sla_breached": False, "files_with_sla_breaches": 0}

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_SUCCESS

    # Verify env="prod" was picked up from the OS variable and passed down
    mock_validate_folder.assert_called_once()
    assert mock_validate_folder.call_args.kwargs.get("env") == "prod"
    mock_getenv.assert_any_call("VALIDATOR_ENV")


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_env_cli_override(mock_setup_logging, mock_validate_folder):
    """Verifies that the --env CLI flag successfully overrides OS variables."""
    test_args = ["validate_folder.py", "--folder", "/dummy", "--config", "/dummy.yaml", "--env", "dev"]
    mock_validate_folder.return_value = {"failed_files": 0, "global_sla_breached": False, "files_with_sla_breaches": 0}

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()
        assert exit_exc.value.code == validate_folder.EXIT_SUCCESS

    # Verify env="dev" from the CLI flag successfully overwrote any OS defaults
    mock_validate_folder.assert_called_once()
    assert mock_validate_folder.call_args.kwargs.get("env") == "dev"