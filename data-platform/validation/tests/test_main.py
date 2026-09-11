from unittest.mock import patch, MagicMock
import logging
import pandas as pd
from src import main


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.generate_messy_data")
@patch("pandas.read_csv")
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
@patch("src.main.ReportComparator")
def test_main_standard_flow(mock_comparator, mock_to_csv, mock_validator, mock_read, mock_generate, mock_args,
                            mock_exists, mock_setup_logging):
    """Tests the default end-to-end execution of main.py."""
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.input = "dummy_input.csv"
    args.output = "dummy_output.csv"
    args.skip_generate = False
    args.strict = True
    args.incremental = False
    args.list_profiles = False
    args.profile = None
    mock_args.return_value = args

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

    mock_comp_instance = MagicMock()
    mock_comp_instance.evaluate_drift.return_value = ["drift alert 1"]
    mock_comparator.return_value = mock_comp_instance

    main.main()

    mock_generate.assert_called_once()
    mock_read.assert_called_once()
    mock_validator.assert_called_once()
    mock_instance.validate.assert_called_once()
    mock_instance.clean.assert_called_once()
    mock_to_csv.assert_called_once()

    mock_comp_instance.evaluate_drift.assert_called_once_with(mock_report, mock_instance)
    mock_comp_instance.save_report.assert_called_once_with(mock_report)


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv")
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
@patch("src.watermark.WatermarkManager")
@patch("src.main.ReportComparator")
def test_main_incremental_flow(mock_comparator, mock_wm_class, mock_to_csv, mock_validator, mock_read, mock_args,
                               mock_exists, mock_setup_logging):
    args = MagicMock()
    args.incremental = True
    args.skip_generate = True
    args.watermark_col = "transaction_id"
    args.list_profiles = False
    args.profile = None
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

    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", autospec=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv")
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
@patch("src.watermark.WatermarkManager")
@patch("src.main.ReportComparator")
def test_main_incremental_flow_new_output(mock_comparator, mock_wm_class, mock_to_csv, mock_validator, mock_read,
                                          mock_args, mock_exists, mock_setup_logging):
    args = MagicMock()
    args.incremental = True
    args.skip_generate = True
    args.watermark_col = "transaction_id"
    args.list_profiles = False
    args.profile = None
    args.output = "new_output.csv"
    mock_args.return_value = args

    def custom_exists(self_path):
        if "new_output" in str(self_path):
            return False
        return True

    mock_exists.side_effect = custom_exists

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

    mock_to_csv.assert_called_once()
    mock_wm_instance.set_watermark.assert_called_once_with(20)


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=False)
@patch("src.main.argparse.ArgumentParser.parse_args")
def test_main_config_missing(mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(list_profiles=False, profile=None)
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.DataValidator.list_profiles", return_value=["default", "strict"])
def test_main_list_profiles_found(mock_list, mock_args, mock_exists, mock_setup_logging):
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.list_profiles = True
    mock_args.return_value = args
    main.main()
    mock_list.assert_called_once_with("dummy_config.yaml")


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.DataValidator.list_profiles", return_value=[])
def test_main_list_profiles_not_found(mock_list, mock_args, mock_exists, mock_setup_logging):
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.list_profiles = True
    mock_args.return_value = args
    main.main()
    mock_list.assert_called_once_with("dummy_config.yaml")


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", side_effect=FileNotFoundError)
def test_main_read_csv_fails(mock_read, mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, list_profiles=False, profile=None)
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config", side_effect=ValueError("Bad Config"))
def test_main_validator_init_fails(mock_validator, mock_read, mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False, list_profiles=False, profile=None)
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
def test_main_validate_fails(mock_validator, mock_read, mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False, list_profiles=False, profile=None)
    mock_instance = MagicMock()
    mock_instance.validate.side_effect = RuntimeError("Validation Crashed")
    mock_validator.return_value = mock_instance
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
@patch("src.main.ReportComparator")
def test_main_clean_fails(mock_comparator, mock_validator, mock_read, mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False, list_profiles=False, profile=None)
    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True, rule_timings={"r1": 0.1})
    mock_instance.clean.side_effect = RuntimeError("Clean Crashed")
    mock_validator.return_value = mock_instance
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv", side_effect=OSError("Disk Full"))
@patch("src.main.ReportComparator")
def test_main_save_fails(mock_comparator, mock_to_csv, mock_validator, mock_read, mock_args, mock_exists,
                         mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False, list_profiles=False, profile=None)
    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True, rule_timings={})
    mock_instance.clean.return_value = pd.DataFrame({"id": [1]})
    mock_validator.return_value = mock_instance
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"wrong_col": [1]}))
@patch("src.watermark.WatermarkManager")
def test_main_incremental_missing_col(mock_wm_class, mock_read, mock_args, mock_exists, mock_setup_logging):
    args = MagicMock(skip_generate=True, incremental=True, watermark_col="id", list_profiles=False, profile=None)
    mock_args.return_value = args
    main.main()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.filter_incremental", return_value=pd.DataFrame())
@patch("src.watermark.WatermarkManager")
def test_main_incremental_no_new_data(mock_wm_class, mock_filter, mock_read, mock_args, mock_exists,
                                      mock_setup_logging):
    args = MagicMock(skip_generate=True, incremental=True, watermark_col="id", list_profiles=False, profile=None)
    mock_args.return_value = args

    mock_wm_instance = MagicMock()
    mock_wm_instance.get_watermark.return_value = 5
    mock_wm_class.return_value = mock_wm_instance

    main.main()


@patch("src.main.logger.error")
@patch("src.main.logger.info")
def test_log_issues_direct(mock_info, mock_error):
    issues = [{"rule": "test_rule", "field": "col_A", "count": 5}]
    report = {
        "sample_bad_rows": {
            "test_rule": [{"row_index": 99, "failed_value": "bad_data"}]
        }
    }

    main.log_issues(issues, "ERROR", report)
    mock_error.assert_called_with("ERROR -> Rule: test_rule | Field: col_A | Count: 5")
    mock_info.assert_any_call("         Row 99: [bad_data]")

    with patch("src.main.logger.warning") as mock_warning:
        main.log_issues(issues, "WARNING", report)
        mock_warning.assert_called_with("WARNING -> Rule: test_rule | Field: col_A | Count: 5")


def custom_exists_side_effect(self):
    if "dummy_config" in str(self):
        return True
    if "dummy_input" in str(self):
        return False
    return True


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", autospec=True, side_effect=custom_exists_side_effect)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("src.main.generate_messy_data")
@patch("pandas.read_csv", return_value=pd.DataFrame({"id": [1]}))
@patch("src.main.DataValidator.from_config")
@patch("pandas.DataFrame.to_csv")
@patch("src.main.ReportComparator")
def test_main_skip_generate_override(mock_comparator, mock_to_csv, mock_validator, mock_read, mock_generate, mock_args,
                                     mock_exists, mock_setup_logging):
    args = MagicMock()
    args.config = "dummy_config.yaml"
    args.input = "dummy_input.csv"
    args.output = "dummy_output.csv"
    args.skip_generate = True
    args.incremental = False
    args.list_profiles = False
    args.profile = None
    mock_args.return_value = args

    mock_instance = MagicMock()
    mock_instance.validate.return_value = MagicMock(passed=True)
    mock_instance.clean.return_value = pd.DataFrame({"id": [1]})
    mock_validator.return_value = mock_instance

    main.main()

    mock_generate.assert_called_once()


@patch("src.main.setup_logging", return_value="dummy_log.log")
@patch("pathlib.Path.exists", return_value=True)
@patch("src.main.argparse.ArgumentParser.parse_args")
@patch("pandas.read_csv", side_effect=Exception("Unexpected Read Error"))
def test_main_read_csv_generic_exception(mock_read, mock_args, mock_exists, mock_setup_logging):
    mock_args.return_value = MagicMock(skip_generate=True, incremental=False, list_profiles=False, profile=None)
    main.main()


def test_setup_logging_execution(monkeypatch):
    # 1. Prevent real directories from being created
    monkeypatch.setattr("pathlib.Path.mkdir", lambda *args, **kwargs: None)

    # 2. Prevent FileHandler from creating the empty file on disk
    monkeypatch.setattr(logging, "FileHandler", lambda *args, **kwargs: logging.NullHandler())

    # 3. Prevent basicConfig from executing
    monkeypatch.setattr(logging, "basicConfig", lambda *args, **kwargs: None)

    # Execute the function
    log_path = main.setup_logging()

    # Assert it calculated the correct file path format
    assert "validation_" in log_path
    assert log_path.endswith(".log")

