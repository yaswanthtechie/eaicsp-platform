import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from src.make_messy_data import generate_messy_data, MessyDataConfig
from src.validator import DataValidator

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO", log_dir: Optional[Path] = None) -> None:
    """Configures structured logging to stdout and a timestamped file."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Always keep console logging (standard for CI/CD and Docker containers)
    log_handlers = [logging.StreamHandler(sys.stdout)]
    log_file = None
    # Add file handler if a log directory is provided
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"perf_test_{timestamp}.log"
        log_handlers.append(logging.FileHandler(log_file))

    # Reset root logger handlers to apply new configuration
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=log_handlers,
        force=True  # Ensures basicConfig applies even if logging was already initialized
    )

    if log_dir:
        logger.info(f"File logging enabled. Writing to: {log_file}")


def run_performance_test(
        data_path: Path,
        config_path: Path,
        n_rows: int,
        time_threshold: float
) -> int:
    """
    Executes the performance benchmark for the DataValidator.

    Returns:
        int: 0 for success/pass, 1 for failure/exception.
    """
    try:
        # 1. Safely handle directories and generate data
        data_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Generating {n_rows:,} rows of messy data at '{data_path}'...")

        cfg = MessyDataConfig(n_base=n_rows)
        generate_messy_data(filepath=data_path, config=cfg)

        logger.info("Loading generated data into memory...")
        df = pd.read_csv(data_path)

        # 2. Setup Validator
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        logger.info(f"Loading validator configuration from '{config_path}'...")
        validator = DataValidator.from_config(str(config_path))

        # 3. Benchmark Validation
        logger.info("Starting vectorized validation pass...")
        start_time = time.perf_counter()
        report = validator.validate(df)
        end_time = time.perf_counter()

        duration = end_time - start_time

        # 4. Log Results
        logger.info("--- PERFORMANCE METRICS ---")
        logger.info(f"Rows processed: {len(df):,}")
        logger.info(f"Rules evaluated: {len(validator.rules)}")
        logger.info(f"Total Execution Time: {duration:.4f} seconds")

        status = 'PASSED' if report.passed else 'FAILED'
        logger.info(f"Status: {status} (Found {report.total_rows_affected:,} bad rows)")

        if report.rule_timings:
            logger.info("--- RULE PERFORMANCE BREAKDOWN (Slowest to Fastest) ---")
            sorted_timings = sorted(report.rule_timings.items(), key=lambda x: x[1], reverse=True)
            for rule_name, rule_duration in sorted_timings:
                logger.info(f"  • {rule_name:30s} : {rule_duration:.6f}s")

            if report.slowest_rule:
                logger.info(
                    f"Slowest Rule: '{report.slowest_rule['rule']}' ({report.slowest_rule['duration_seconds']:.6f}s)")

        if duration > time_threshold:
            logger.warning(
                f"Performance bottleneck detected: Validation took {duration:.2f}s, "
                f"exceeding the threshold of {time_threshold}s for {n_rows:,} rows."
            )

        return 0

    except Exception as e:
        logger.exception(f"An error occurred during the performance test: {e}")
        return 1


def main() -> None:
    """Parses command-line arguments and triggers the test suite."""
    parser = argparse.ArgumentParser(description="Run performance tests for DataValidator.")

    parser.add_argument("--data-path", type=Path, default=Path("data/perf_100k_sales.csv"),
                        help="Path where test data will be generated and read from.")
    parser.add_argument("--config-path", type=Path, default=Path("configs/sales_rules.yaml"),
                        help="Path to the validation rules YAML configuration.")
    parser.add_argument("--n-rows", type=int, default=100000,
                        help="Number of rows to generate for the test.")
    parser.add_argument("--time-threshold", type=float, default=3.0,
                        help="Maximum acceptable duration in seconds before triggering a warning.")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level.")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"),
                        help="Directory to store timestamped log files. Set to empty string to disable file logging.")

    args = parser.parse_args()

    # Pass the log directory to our setup function
    setup_logging(args.log_level, args.log_dir)

    exit_code = run_performance_test(
        data_path=args.data_path,
        config_path=args.config_path,
        n_rows=args.n_rows,
        time_threshold=args.time_threshold
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()