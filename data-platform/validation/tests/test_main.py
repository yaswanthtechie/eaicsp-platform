from unittest.mock import patch, MagicMock
import pandas as pd
from src import main


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.generate_messy_data")
@patch("pandas.read_csv")
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
def test_main_standard_flow(mock_to_csv, mock_validator, mock_read, mock_generate, mock_args, mock_exists):
    """Tests the default end-to-end execution of main.py."""
    # 1. Setup CLI arguments
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.input = "dummy_input.csv"
    args.output = "dummy_output.csv"
    args.skip_generate = False
    args.strict = True
    args.incremental = False
    mock_args.return_value = args

    # 2. Setup DataValidator & DataFrame mock
    mock_df = pd.DataFrame({"transaction_id": [1, 2]})
    mock_read.return_value = mock_df

    mock_instance = MagicMock()
    mock_report = MagicMock()
    mock_report.passed = True
    mock_report.total_rows_affected = 0
    mock_report.model_dump.return_value = {}
    mock_instance.validate.return_value = mock_report
    mock_instance.clean.return_value = mock_df
    mock_validator.return_value = mock_instance

    # 3. Execute
    main.main()

    # 4. Assert core pipeline steps were called
    mock_generate.assert_called_once()
    mock_read.assert_called_once()
    mock_validator.assert_called_once()
    mock_instance.validate.assert_called_once()
    mock_instance.clean.assert_called_once()
    mock_to_csv.assert_called_once()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv")
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
@patch("src.watermark.WatermarkManager")
def test_main_incremental_flow(mock_wm_class, mock_to_csv, mock_validator, mock_read, mock_args, mock_exists):
    """Tests the incremental appending and watermarking logic."""
    args = MagicMock()
    args.incremental = True
    args.skip_generate = True
    args.watermark_col = "transaction_id"
    mock_args.return_value = args

    mock_df = pd.DataFrame({"transaction_id": [10, 20]})
    mock_read.return_value = mock_df

    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True)
    mock_instance.clean.return_value = mock_df
    mock_validator.return_value = mock_instance

    main.main()

    # Assert watermark was updated based on clean data
    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("pathlib.Path.exists", return_value=False)
@patch("src.main.argparse.ArgumentParser.parse_args")
def test_main_config_missing(mock_args, mock_exists):
    """Hits the early exit when the config file does not exist."""
    mock_args.return_value = MagicMock()
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", side_effect=FileNotFoundError)
def test_main_read_csv_fails(mock_read, mock_args, mock_exists):
    """Hits the except FileNotFoundError block during data loading."""
    mock_args.return_value = MagicMock(skip_generate=True)
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config", side_effect=ValueError("Bad Config"))
def test_main_validator_init_fails(mock_validator, mock_read, mock_args, mock_exists):
    """Hits the except Exception block during DataValidator instantiation."""
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False)
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
def test_main_validate_fails(mock_validator, mock_read, mock_args, mock_exists):
    """Hits the except Exception block during validation execution."""
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False)
    mock_instance = MagicMock()
    mock_instance.validate.side_effect = RuntimeError("Validation Crashed")
    mock_validator.return_value = mock_instance
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
def test_main_clean_fails(mock_validator, mock_read, mock_args, mock_exists):
    """Hits the except Exception block during data cleaning."""
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False)
    mock_instance = MagicMock()
    # Mocking rule_timings to also hit the performance profiling loop
    mock_instance.validate.return_value = MagicMock(passed=True, rule_timings={"r1": 0.1})
    mock_instance.clean.side_effect = RuntimeError("Clean Crashed")
    mock_validator.return_value = mock_instance
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv", side_effect=OSError("Disk Full"))
def test_main_save_fails(mock_to_csv, mock_validator, mock_read, mock_args, mock_exists):
    """Hits the except Exception block when writing output files."""
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False)
    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True, rule_timings={})
    mock_instance.clean.return_value = pd.DataFrame({"id": [1]})
    mock_validator.return_value = mock_instance
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"wrong_col": [1]}))
@patch("src.watermark.WatermarkManager")
def test_main_incremental_missing_col(mock_wm_class, mock_read, mock_args, mock_exists):
    """Hits the early exit when the watermark column is missing from the data."""
    args = MagicMock(skip_generate=True, incremental=True, watermark_col="id")
    mock_args.return_value = args
    main.main()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.filter_incremental", return_value=pd.DataFrame())
@patch("src.watermark.WatermarkManager")
def test_main_incremental_no_new_data(mock_wm_class, mock_filter, mock_read, mock_args, mock_exists):
    """Hits the early exit when filtering results in an empty DataFrame."""
    args = MagicMock(skip_generate=True, incremental=True, watermark_col="id")
    mock_args.return_value = args

    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    main.main()


@patch("src.main.logger.error")
@patch("src.main.logger.info")
def test_log_issues_direct(mock_info, mock_error):
    """Directly tests the log_issues helper function and its sample iteration."""
    issues = [{"rule": "test_rule", "field": "col_A", "count": 5}]
    report = {
        "sample_bad_rows": {
            "test_rule": [{"row_index": 99, "failed_value": "bad_data"}]
        }
    }

    # 1. Test ERROR severity
    main.log_issues(issues, "ERROR", report)
    mock_error.assert_called_with("ERROR -> Rule: test_rule | Field: col_A | Count: 5")
    mock_info.assert_any_call("         Row 99: [bad_data]")

    # 2. Test WARNING severity (uses logger.warning)
    with patch("src.main.logger.warning") as mock_warning:
        main.log_issues(issues, "WARNING", report)
        mock_warning.assert_called_with("WARNING -> Rule: test_rule | Field: col_A | Count: 5")


def custom_exists_side_effect(self):
    """Helper to mock Path.exists(): config exists, but input data does not."""
    if "dummy_config" in str(self):
        return True
    if "dummy_input" in str(self):
        return False
    return True


@patch("pathlib.Path.exists", autospec=True, side_effect=custom_exists_side_effect)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.generate_messy_data")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
def test_main_skip_generate_override(mock_to_csv, mock_validator, mock_read, mock_generate, mock_args, mock_exists):
    """Hits the fallback warning when --skip-generate is requested but no data file exists."""
    # Explicitly set the mock arguments to standard strings to trigger the side effect correctly
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.input = "dummy_input.csv"
    args.output = "dummy_output.csv"
    args.skip_generate = True
    args.incremental = False
    mock_args.return_value = args

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True)
    mock_instance.clean.return_value = pd.DataFrame({"id": [1]})
    mock_validator.return_value = mock_instance

    main.main()

    # Verify generate_messy_data was called anyway to prevent a crash
    mock_generate.assert_called_once()


@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", side_effect=Exception("Unexpected Read Error"))
def test_main_read_csv_generic_exception(mock_read, mock_args, mock_exists):
    """Hits the generic `except Exception as e:` block during data loading."""
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False)
    main.main()