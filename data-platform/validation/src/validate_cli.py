import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.validator import DataValidator

# --- PATH RESOLUTION ---
# Ensure the script can be invoked directly by path (e.g., python src/validate_cli.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# --- Configuration Constants ---
EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILED = 1
EXIT_TOOL_ERROR = 2  # New exit code for tool crashes

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_CONFIG_VERSION = "unknown"
CONFIG_VERSION_KEY = "version"
JSON_INDENT = 2
ENCODING = "utf-8"


# --- Logger Setup ---
def setup_logger(log_level: str = DEFAULT_LOG_LEVEL, enable_file_logging: bool = False) -> logging.Logger:
    """Configures and returns a logger instance with optional file logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # 1. Always configure the console handler
    log_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    # 2. Conditionally configure the file handler
    if enable_file_logging:
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"cli_validation_{timestamp}.log"
        log_handlers.append(logging.FileHandler(log_file, mode="w", encoding=ENCODING))

    # 3. Apply configuration
    logging.basicConfig(
        level=numeric_level,
        format=DEFAULT_LOG_FORMAT,
        handlers=log_handlers,
        force=True
    )

    custom_logger = logging.getLogger(__name__)
    if enable_file_logging:
        custom_logger.info("File logging enabled. Writing to: %s", log_file)

    return custom_logger

# Define globally so all functions can reference 'logger'
logger = logging.getLogger(__name__)


# --- Core Functions ---
def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="Standalone Quality Gate CLI")
    parser.add_argument("--file", type=Path, required=True, help="Path to input CSV")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML rules")
    parser.add_argument("--output", type=Path, required=True, help="Path for JSON report output")
    # --- ADD INCREMENTAL ARGUMENTS ---
    parser.add_argument("--incremental", action="store_true", help="Only process new rows since the last run.")
    parser.add_argument("--watermark-col", type=str, default="transaction_id", help="Column for watermarking.")
    parser.add_argument("--watermark-file", type=Path, default=PROJECT_ROOT / ".watermark_cli.json",
                        help="Path to state tracking file.")
    parser.add_argument("--log-to-file", action="store_true", help="Enable timestamped file logging.")
    return parser.parse_args(args)


def export_report(report: Any, output_path: Path) -> None:
    """Exports the validation report to JSON, handling Pydantic V1/V2 differences."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Dynamically resolve Pydantic V2 (model_dump) or V1 (dict) method
        dump_method = getattr(report, "model_dump", getattr(report, "dict", None))
        if not callable(dump_method):
            raise AttributeError("Report object lacks Pydantic export methods (model_dump/dict)")

        with output_path.open('w', encoding=ENCODING) as f:
            json.dump(dump_method(), f, indent=JSON_INDENT)

        logger.info("JSON report generated at: %s", output_path)
    except (OSError, TypeError, ValueError, AttributeError) as e:
        logger.exception("Failed to write JSON output to %s: %s", output_path, e)
        raise


def main(cli_args: Optional[list[str]] = None) -> int:
    """Main execution flow. Returns an integer exit code."""
    args = parse_args(cli_args)
    # Initialize the handlers when the script actually runs
    setup_logger(os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL), enable_file_logging=args.log_to_file)

    input_path: Path = args.file
    config_path: Path = args.config
    output_path: Path = args.output

    # Validate file existence strictly as files, not just paths
    if not input_path.is_file():
        logger.error("Input file does not exist or is not a file: %s", input_path)
        return EXIT_TOOL_ERROR

    if not config_path.is_file():
        logger.error("Config file does not exist or is not a file: %s", config_path)
        return EXIT_TOOL_ERROR


    # Load Data & Validate (Fixed broad exception)
    try:
        df = pd.read_csv(input_path)
        # --- WATERMARK FILTERING ---
        if args.incremental:
            from src.watermark import WatermarkManager
            wm = WatermarkManager(args.watermark_file)
            current_watermark = wm.get_watermark()

            df = DataValidator.filter_incremental(df, args.watermark_col, current_watermark)

            if df.empty:
                logger.info("Incremental Mode: No new data to process. Exiting cleanly.")
                return EXIT_SUCCESS
            logger.info(f"Incremental Mode: Identified {len(df)} new rows to validate.")
        validator = DataValidator.from_config(str(config_path))

        # Run validation
        report = validator.validate(df)

    except (pd.errors.EmptyDataError, pd.errors.ParserError, ValueError, OSError) as e:
        logger.exception("Validation execution failed: %s", e)
        return EXIT_TOOL_ERROR
    except RuntimeError as e:  # Catch fallback for external library runtime errors
        logger.exception("Runtime error during validation: %s", e)
        return EXIT_TOOL_ERROR

    # 3. Export JSON Report (Fixed broad exception)
    try:
        export_report(report, output_path)
        # --- WATERMARK SAVING ---
        if args.incremental and not df.empty:
            logger.warning(
                "LIMITATION: Watermark advances past failed rows. Bad rows are not filtered from this check.")
            new_wm = df[args.watermark_col].max()
            new_wm = new_wm.item() if hasattr(new_wm, 'item') else new_wm
            wm.set_watermark(new_wm)
            logger.info(f"Watermark updated to: {new_wm}")
    except (OSError, TypeError, ValueError, AttributeError):
        return EXIT_TOOL_ERROR

    if hasattr(report, "rule_timings") and report.rule_timings:
        logger.info("--- RULE TIMINGS (Slowest First) ---")
        sorted_timings = sorted(report.rule_timings.items(), key=lambda x: x[1], reverse=True)
        for rule_name, rule_duration in sorted_timings:
            logger.info(f"  • {rule_name:30s} : {rule_duration:.6f}s")

    # 4. CI/CD Exit Codes
    passed = getattr(report, 'passed', False)
    # Extract the version natively from the generated report
    config_ver = getattr(report, 'config_version', 'unknown')
    if not passed:
        rows_affected = getattr(report, 'total_rows_affected', 'unknown')
        logger.error(f"Validation FAILED. {rows_affected} rows affected (Config version:{config_ver}).")
        return EXIT_VALIDATION_FAILED

    logger.info(f"Validation PASSED (Config version:{config_ver})")
    return EXIT_SUCCESS


if __name__ == "__main__":
    # Defer sys.exit to the very edge of the application
    sys.exit(main())