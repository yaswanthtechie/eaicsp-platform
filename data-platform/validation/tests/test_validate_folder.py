import json
import logging
import math
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# Import the module explicitly from the src package
from src import validate_folder


class MockReport:
    """Mock implementation of the DataValidator report object."""

    def __init__(self, passed, total_rows_affected=0, errors=None, warnings=None, sample_bad_rows=None):
        self.config_version = "1.0.0"
        self.passed = passed
        self.total_rows_affected = total_rows_affected
        self.errors = errors or []
        self.warnings = warnings or []
        self.sample_bad_rows = sample_bad_rows or {}


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

    res1 = validate_folder._load_validator("config1.yaml", cache)
    assert res1 == mock_instance

    res2 = validate_folder._load_validator("config1.yaml", cache)
    assert res2 == mock_instance
    assert mock_validator_class.from_config.call_count == 1


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
        sample_bad_rows={"NullCheck": [{"row": 1, "failed_value": math.nan}]}
    )
    mock_validator_class.from_config.return_value = mock_instance

    summary = validate_folder.validate_folder(
        folder_path=temp_env["data_dir"],
        mapping_path=temp_env["mapping_file"],
        output_dir=str(temp_env["reports_dir"]),
        save_reports=True
    )

    assert summary["failed_files"] == 1
    assert temp_env["reports_dir"].exists()

    report_file = temp_env["reports_dir"] / "valid_report.json"
    with open(report_file, "r") as f:
        data = json.load(f)
        assert data["sample_bad_rows"]["NullCheck"][0]["failed_value"] is None


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


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_success(mock_setup_logging, mock_validate_folder):
    test_args = [
        "validate_folder.py",
        "--folder", "/dummy/folder",
        "--config", "/dummy/config.yaml",
        "--save-reports"
    ]

    with patch.object(sys, 'argv', test_args):
        validate_folder.main()

    mock_setup_logging.assert_called_once()
    mock_validate_folder.assert_called_once_with(
        folder_path="/dummy/folder",
        config_path="/dummy/config.yaml",
        mapping_path=None,
        default_pattern="*.csv",
        top_n_issues=3,
        output_dir="reports",
        save_reports=True
    )


@patch("src.validate_folder.validate_folder")
@patch("src.validate_folder.setup_logging")
def test_main_system_exit_on_failure(mock_setup_logging, mock_validate_folder):
    test_args = [
        "validate_folder.py",
        "--folder", "/dummy/folder",
        "--config", "/dummy/config.yaml"
    ]

    mock_validate_folder.side_effect = Exception("Critical Pipeline Failure")

    with patch.object(sys, 'argv', test_args):
        with pytest.raises(SystemExit) as exit_exc:
            validate_folder.main()

        assert exit_exc.value.code == 1
