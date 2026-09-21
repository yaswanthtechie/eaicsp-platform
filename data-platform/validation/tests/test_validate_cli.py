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

@patch("logging.FileHandler")
@patch("logging.basicConfig")
def test_setup_logger(mock_basic_config, mock_file_handler):
    # Pass enable_file_logging=True to test the logic, but the mocked FileHandler prevents disk writes
    logger = validate_cli.setup_logger("DEBUG", enable_file_logging=True)

    # 1. Verify basicConfig was called exactly once
    mock_basic_config.assert_called_once()

    # 2. Extract the keyword arguments it was called with
    call_kwargs = mock_basic_config.call_args.kwargs

    # 3. Assert the specific configurations we expect
    assert call_kwargs.get("level") == logging.DEBUG
    assert call_kwargs.get("format") == validate_cli.DEFAULT_LOG_FORMAT
    assert call_kwargs.get("force") is True
    assert "handlers" in call_kwargs
    assert len(call_kwargs["handlers"]) == 2  # Should contain StreamHandler and our Mocked FileHandler

    # 4. Verify the function returns the correct named logger
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

# --- Tests for Incremental Watermarking ---

def test_parse_args_incremental(mock_args):
    """Verifies that the new incremental arguments are parsed correctly."""
    args_with_inc = mock_args + ["--incremental", "--watermark-col", "test_id", "--watermark-file", "state.json"]
    args = validate_cli.parse_args(args_with_inc)

    assert args.incremental is True
    assert args.watermark_col == "test_id"
    assert args.watermark_file.name == "state.json"


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv")
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
@patch("src.watermark.WatermarkManager")
def test_main_incremental_updates_watermark(
        mock_wm_class, mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report
):
    """Verifies that processing new data in incremental mode correctly updates the watermark."""
    # 1. Setup mock DataFrame with new rows
    mock_df = pd.DataFrame({"transaction_id": [10, 20]})
    mock_read.return_value = mock_df

    # 2. Setup mocked WatermarkManager (Previous watermark was 5)
    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    # 3. Setup Validator
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance

    # Run main with incremental arguments
    args = mock_args + ["--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS

    # 4. Assert watermark was read and then updated to the new max (20)
    mock_wm_instance.get_watermark.assert_called_once()
    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv")
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
@patch("src.watermark.WatermarkManager")
def test_main_incremental_no_new_data(
        mock_wm_class, mock_export, mock_validator, mock_read, mock_is_file, mock_args
):
    """Verifies that the script exits early cleanly if no new incremental data is found."""
    # 1. Setup mock DataFrame with old rows
    mock_df = pd.DataFrame({"transaction_id": [1, 2]})
    mock_read.return_value = mock_df

    # 2. Setup mocked WatermarkManager (Previous watermark was 5 - higher than data)
    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    # Run main with incremental arguments
    args = mock_args + ["--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS

    # 3. Assert validation, exporting, and saving were completely bypassed
    mock_validator.assert_not_called()
    mock_export.assert_not_called()
    mock_wm_instance.set_watermark.assert_not_called()
