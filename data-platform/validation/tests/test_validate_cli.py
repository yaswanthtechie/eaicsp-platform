import logging
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

# Import mapped correctly to the src folder
import src.validate_cli as validate_cli


# --- Fixtures ---

@pytest.fixture
def mock_args() -> list[str]:
    return ["--file", "dummy.csv", "--config", "dummy.yaml", "--output", "dummy.json"]


@pytest.fixture
def mock_report() -> MagicMock:
    report = MagicMock()
    report.passed = True
    report.total_rows_affected = 0
    report.model_dump.return_value = {"status": "success"}
    # Remove dict method to force model_dump usage by default
    del report.dict
    return report


# --- Tests for setup_logger ---

@patch("logging.basicConfig")
def test_setup_logger(mock_basic_config):
    logger = validate_cli.setup_logger("DEBUG")

    # 1. Verify basicConfig was called with the exact level and format expected
    mock_basic_config.assert_called_once_with(
        level=logging.DEBUG,
        format=validate_cli.DEFAULT_LOG_FORMAT
    )

    # 2. Verify the function returns the correct named logger
    assert logger.name == "src.validate_cli"


# --- Tests for parse_args ---

def test_parse_args_success(mock_args):
    args = validate_cli.parse_args(mock_args)
    assert isinstance(args.file, Path)
    assert args.file.name == "dummy.csv"
    assert args.config.name == "dummy.yaml"
    assert args.output.name == "dummy.json"


def test_parse_args_missing_required():
    with pytest.raises(SystemExit):
        validate_cli.parse_args([])


# --- Tests for export_report ---

@patch("pathlib.Path.mkdir")
@patch("pathlib.Path.open", new_callable=mock_open)
@patch("json.dump")
def test_export_report_pydantic_v2(mock_json, mock_file, mock_mkdir, mock_report):
    validate_cli.export_report(mock_report, Path("dummy.json"))
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_report.model_dump.assert_called_once()
    mock_json.assert_called_once()


@patch("pathlib.Path.mkdir")
@patch("pathlib.Path.open", new_callable=mock_open)
@patch("json.dump")
def test_export_report_pydantic_v1(mock_json, mock_file, mock_mkdir):
    v1_report = MagicMock()
    v1_report.dict.return_value = {"status": "success"}
    del v1_report.model_dump

    validate_cli.export_report(v1_report, Path("dummy.json"))
    v1_report.dict.assert_called_once()
    mock_json.assert_called_once()


@patch("pathlib.Path.mkdir")
def test_export_report_missing_methods(mock_mkdir):
    bad_report = MagicMock()
    del bad_report.model_dump
    del bad_report.dict

    with pytest.raises(AttributeError):
        validate_cli.export_report(bad_report, Path("dummy.json"))


@patch("pathlib.Path.mkdir", side_effect=OSError("Mock Dir Error"))
def test_export_report_os_error(mock_mkdir, mock_report):
    with pytest.raises(OSError):
        validate_cli.export_report(mock_report, Path("dummy.json"))


# --- Tests for main() execution flow ---

@patch("pathlib.Path.is_file")
def test_main_input_not_file(mock_is_file, mock_args):
    mock_is_file.side_effect = [False, True]
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file")
def test_main_config_not_file(mock_is_file, mock_args):
    mock_is_file.side_effect = [True, False]
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", side_effect=ValueError("Bad CSV"))
def test_main_validation_fails_data_error(mock_read, mock_is_file, mock_args):
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", side_effect=RuntimeError("Unexpected Runtime"))
def test_main_validation_fails_runtime_error(mock_read, mock_is_file, mock_args):
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report", side_effect=TypeError("Bad Export"))
def test_main_export_fails(mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report):
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_validation_passed_false(mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report):
    # Set up failure condition for the mock report
    mock_report.passed = False
    mock_report.total_rows_affected = 5

    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance

    # Assert it returns Code 1 (Validation Failed)
    assert validate_cli.main(mock_args) == validate_cli.EXIT_VALIDATION_FAILED


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_validation_passed_true(mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report):
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance

    # Assert it returns Code 0 (Success)
    assert validate_cli.main(mock_args) == validate_cli.EXIT_SUCCESS
