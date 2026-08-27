import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.perf_test import setup_logging, run_performance_test, main


class TestSetupLogging:
    """Test suite for setup_logging function."""

    def test_setup_logging_with_log_dir(self, tmp_path: Path) -> None:
        """Verify logging setup creates log directory and timestamped log file when log_dir is provided."""
        log_dir = tmp_path / "logs"

        setup_logging(log_level="DEBUG", log_dir=log_dir)

        assert log_dir.exists()
        log_files = list(log_dir.glob("perf_test_*.log"))
        assert len(log_files) == 1
        assert log_files[0].is_file()

    def test_setup_logging_without_log_dir(self) -> None:
        """Verify logging setup executes cleanly without file handlers when log_dir is None."""
        with patch("logging.basicConfig") as mock_basic_config:
            setup_logging(log_level="WARNING", log_dir=None)

            mock_basic_config.assert_called_once()
            _, kwargs = mock_basic_config.call_args
            assert kwargs["level"] == logging.WARNING
            assert len(kwargs["handlers"]) == 1  # Only StreamHandler


class TestRunPerformanceTest:
    """Test suite for run_performance_test core logic."""

    @patch("src.perf_test.generate_messy_data")
    @patch("src.perf_test.pd.read_csv")
    @patch("src.perf_test.DataValidator")
    def test_run_performance_test_success_within_threshold(
            self,
            mock_validator_cls: MagicMock,
            mock_read_csv: MagicMock,
            mock_generate_data: MagicMock,
            tmp_path: Path,
    ) -> None:
        """Verify successful test execution when duration is within the threshold and rules pass."""
        # Arrange
        data_path = tmp_path / "data" / "test.csv"
        config_path = tmp_path / "configs" / "rules.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()

        # Mock Validator and Report
        mock_validator = MagicMock()
        mock_report = MagicMock()
        mock_report.passed = True
        mock_report.total_rows_affected = 0
        mock_report.rule_timings = {"fast_rule": 0.0001}
        mock_report.slowest_rule = {"rule": "fast_rule", "duration_seconds": 0.0001}
        mock_validator.validate.return_value = mock_report
        mock_validator.rules = [MagicMock(), MagicMock()]
        mock_validator_cls.from_config.return_value = mock_validator

        # Mock DataFrame
        mock_df = MagicMock()
        mock_df.__len__.return_value = 100
        mock_read_csv.return_value = mock_df

        # Act
        result = run_performance_test(
            data_path=data_path,
            config_path=config_path,
            n_rows=100,
            time_threshold=10.0,
        )

        # Assert
        assert result == 0
        mock_generate_data.assert_called_once()
        mock_validator_cls.from_config.assert_called_once_with(str(config_path))
        mock_validator.validate.assert_called_once_with(mock_df)

    @patch("src.perf_test.time.perf_counter")
    @patch("src.perf_test.generate_messy_data")
    @patch("src.perf_test.pd.read_csv")
    @patch("src.perf_test.DataValidator")
    @patch("src.perf_test.logger.warning")
    def test_run_performance_test_exceeding_threshold_and_failed_validation(
            self,
            mock_logger_warning: MagicMock,
            mock_validator_cls: MagicMock,
            mock_read_csv: MagicMock,
            mock_generate_data: MagicMock,
            mock_perf_counter: MagicMock,
            tmp_path: Path,
    ) -> None:
        """Verify warning logger trigger when validation execution duration exceeds time threshold."""
        # Arrange
        data_path = tmp_path / "data" / "test.csv"
        config_path = tmp_path / "configs" / "rules.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()

        # Simulate 5.0 seconds duration
        mock_perf_counter.side_effect = [10.0, 15.0]

        mock_validator = MagicMock()
        mock_report = MagicMock()
        mock_report.passed = False
        mock_report.total_rows_affected = 25
        mock_report.rule_timings = {"slow_rule": 4.9}
        mock_report.slowest_rule = {"rule": "slow_rule", "duration_seconds": 4.9}
        mock_validator.validate.return_value = mock_report
        mock_validator.rules = [MagicMock()]
        mock_validator_cls.from_config.return_value = mock_validator

        mock_df = MagicMock()
        mock_df.__len__.return_value = 100
        mock_read_csv.return_value = mock_df

        # Act
        result = run_performance_test(
            data_path=data_path,
            config_path=config_path,
            n_rows=100,
            time_threshold=2.0,
        )

        # Assert
        assert result == 0
        mock_logger_warning.assert_called_once()
        assert "Performance bottleneck detected" in mock_logger_warning.call_args[0][0]

    def test_run_performance_test_missing_config_returns_failure(
            self, tmp_path: Path
    ) -> None:
        """Verify script catches FileNotFoundError and returns 1 when config file is missing."""
        # Arrange
        data_path = tmp_path / "data" / "test.csv"
        non_existent_config = tmp_path / "configs" / "missing.yaml"

        with patch("src.perf_test.generate_messy_data"), patch("src.perf_test.pd.read_csv"):
            # Act
            result = run_performance_test(
                data_path=data_path,
                config_path=non_existent_config,
                n_rows=10,
                time_threshold=3.0,
            )

        # Assert
        assert result == 1


class TestMainCLI:
    """Test suite for CLI argument parsing and main execution entry point."""

    @patch("src.perf_test.setup_logging")
    @patch("src.perf_test.run_performance_test", return_value=0)
    def test_main_executes_with_cli_args(
            self,
            mock_run_test: MagicMock,
            mock_setup_logging: MagicMock,
            monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify main() parses arguments and invokes setup_logging and run_performance_test correctly."""
        # Arrange
        custom_args = [
            "perf_test.py",
            "--n-rows", "5000",
            "--time-threshold", "1.5",
            "--log-level", "DEBUG",
        ]
        monkeypatch.setattr(sys, "argv", custom_args)

        # Act & Assert
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_setup_logging.assert_called_once()
        mock_run_test.assert_called_once_with(
            data_path=Path("data/perf_100k_sales.csv"),
            config_path=Path("configs/sales_rules.yaml"),
            n_rows=5000,
            time_threshold=1.5,
        )