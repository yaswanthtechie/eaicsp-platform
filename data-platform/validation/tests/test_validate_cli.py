import logging
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pandas as pd
import pytest

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
    report.total_rows = 10  # Prevents MagicMock > 0 integer comparison errors
    report.sla_breached = False
    report.sla_violations = []
    report.model_dump.return_value = {"status": "success"}
    report.rule_timings = {}
    del report.dict
    return report

# --- Tests for setup_logger ---

@patch("logging.FileHandler")
@patch("logging.basicConfig")
def test_setup_logger(mock_basic_config, mock_file_handler):
    logger = validate_cli.setup_logger("DEBUG", enable_file_logging=True)
    mock_basic_config.assert_called_once()
    call_kwargs = mock_basic_config.call_args.kwargs
    assert call_kwargs.get("level") == logging.DEBUG
    assert call_kwargs.get("format") == validate_cli.DEFAULT_LOG_FORMAT
    assert call_kwargs.get("force") is True
    assert "handlers" in call_kwargs
    assert len(call_kwargs["handlers"]) == 2
    assert logger.name == "src.validate_cli"


# --- Tests for parse_args ---

def test_parse_args_success(mock_args):
    args = validate_cli.parse_args(mock_args)
    assert isinstance(args.file, Path)
    assert args.file.name == "dummy.csv"
    assert args.config.name == "dummy.yaml"
    assert args.output.name == "dummy.json"
    assert args.profile is None
    assert args.list_profiles is False
    assert args.sla_time_limit is None


def test_parse_args_profiles(mock_args):
    args_with_profiles = mock_args + ["--profile", "strict", "--list-profiles"]
    args = validate_cli.parse_args(args_with_profiles)
    assert args.profile == "strict"
    assert args.list_profiles is True


def test_parse_args_sla_time_limit(mock_args):
    """Verifies that the new SLA time limit override is parsed correctly."""
    args_with_sla = mock_args + ["--sla-time-limit", "15.5"]
    args = validate_cli.parse_args(args_with_sla)
    assert args.sla_time_limit == 15.5


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
def test_main_config_not_file(mock_is_file, mock_args):
    mock_is_file.side_effect = [False]
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file")
def test_main_input_not_file(mock_is_file, mock_args):
    mock_is_file.side_effect = [True, False]
    assert validate_cli.main(mock_args) == validate_cli.EXIT_TOOL_ERROR


@patch("pathlib.Path.is_file", return_value=True)
@patch("src.validator.DataValidator.list_profiles", return_value=["default", "strict"])
def test_main_list_profiles_found(mock_list, mock_is_file, mock_args):
    args = mock_args + ["--list-profiles"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_list.assert_called_once_with("dummy.yaml")


@patch("pathlib.Path.is_file", return_value=True)
@patch("src.validator.DataValidator.list_profiles", return_value=[])
def test_main_list_profiles_not_found(mock_list, mock_is_file, mock_args):
    args = mock_args + ["--list-profiles"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_list.assert_called_once_with("dummy.yaml")


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
    mock_report.passed = False
    mock_report.total_rows_affected = 5
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    assert validate_cli.main(mock_args) == validate_cli.EXIT_VALIDATION_FAILED


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_validation_passed_with_sla_breach(mock_export, mock_validator, mock_read, mock_is_file, mock_args,
                                                mock_report):
    """Verifies that passing data with SLA violations returns the correct EXIT_SLA_BREACH code."""
    mock_report.sla_breached = True
    mock_report.sla_violations = ["Global failure rate 15.0% exceeds warning SLA (10.0%)"]

    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    assert validate_cli.main(mock_args) == validate_cli.EXIT_SLA_BREACH


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_injects_sla_time_limit(mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report):
    """Verifies that the CLI SLA override flag updates the validator engine attribute."""
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance

    args = mock_args + ["--sla-time-limit", "10.0"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    assert mock_instance.global_max_duration_seconds == 10.0


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_validation_passed_true_with_profile(mock_export, mock_validator, mock_read, mock_is_file, mock_args,
                                                  mock_report):
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    args = mock_args + ["--profile", "strict"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_validator.assert_called_once()
    assert mock_validator.call_args.kwargs.get("profile_name") == "strict"


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv", return_value=pd.DataFrame())
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
@patch("src.validate_cli.logger.info")
def test_main_rule_timings_logging(mock_info, mock_export, mock_validator, mock_read, mock_is_file, mock_args,
                                   mock_report):
    mock_report.rule_timings = {"rule_1": 0.5, "rule_2": 1.2}
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    validate_cli.main(mock_args)
    mock_info.assert_any_call("--- RULE TIMINGS (Slowest First) ---")


# --- Tests for Incremental Watermarking ---

def test_parse_args_incremental(mock_args):
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
    mock_df = pd.DataFrame({"transaction_id": [10, 20]})
    mock_read.return_value = mock_df
    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance
    mock_instance = MagicMock()
    mock_instance.validate.return_value = mock_report
    mock_validator.return_value = mock_instance
    args = mock_args + ["--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
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
    mock_df = pd.DataFrame({"transaction_id": [1, 2]})
    mock_read.return_value = mock_df
    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance
    args = mock_args + ["--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_export.assert_not_called()
    mock_wm_instance.set_watermark.assert_not_called()


# --- Tests for Streaming / Chunking ---

@patch("pathlib.Path.is_file", return_value=True)
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
def test_main_streaming_success(mock_export, mock_validator, mock_is_file, mock_args, mock_report):
    mock_instance = MagicMock()
    mock_instance.validate_stream.return_value = mock_report
    mock_validator.return_value = mock_instance
    args = mock_args + ["--chunk-size", "500"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_instance.validate_stream.assert_called_once()


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv")
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
@patch("src.watermark.WatermarkManager")
def test_main_streaming_incremental(
        mock_wm_class, mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report
):
    mock_instance = MagicMock()
    mock_instance.validate_stream.return_value = mock_report
    mock_validator.return_value = mock_instance
    mock_df = pd.DataFrame({"transaction_id": [10, 20]})
    mock_read.return_value = [mock_df]
    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance
    args = mock_args + ["--chunk-size", "500", "--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS
    mock_instance.validate_stream.assert_called_once()
    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("pathlib.Path.is_file", return_value=True)
@patch("pandas.read_csv")
@patch("src.validator.DataValidator.from_config")
@patch("src.validate_cli.export_report")
@patch("src.watermark.WatermarkManager")
def test_main_streaming_incremental_no_rows_processed(
        mock_wm_class, mock_export, mock_validator, mock_read, mock_is_file, mock_args, mock_report
):
    """Verifies that watermark streaming gracefully skips if total_rows is 0."""
    mock_report.total_rows = 0  # Simulate no rows passing validation

    mock_instance = MagicMock()
    mock_instance.validate_stream.return_value = mock_report
    mock_validator.return_value = mock_instance

    args = mock_args + ["--chunk-size", "500", "--incremental", "--watermark-col", "transaction_id"]
    assert validate_cli.main(args) == validate_cli.EXIT_SUCCESS

    # Ensure it did NOT attempt to stream the watermark column
    mock_read.assert_not_called()