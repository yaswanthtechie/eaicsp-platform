import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yaml

from src.validator import DataValidator

# --- Configuration Constants ---
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_CONFIG_VERSION = "unknown"
CONFIG_VERSION_KEY = "version"
JSON_INDENT = 2
ENCODING = "utf-8"


# --- Logger Setup ---
def setup_logger(log_level: str = DEFAULT_LOG_LEVEL) -> logging.Logger:
    """Configures and returns a logger instance."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format=DEFAULT_LOG_FORMAT)
    return logging.getLogger(__name__)


logger = setup_logger(os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL))


# --- Core Functions ---
def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(description="Standalone Quality Gate CLI")
    parser.add_argument("--file", type=Path, required=True, help="Path to input CSV")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML rules")
    parser.add_argument("--output", type=Path, required=True, help="Path for JSON report output")
    return parser.parse_args(args)


def extract_config_version(config_path: Path) -> str:
    """Safely extracts the version string from the YAML configuration."""
    try:
        with config_path.open('r', encoding=ENCODING) as f:
            yaml_data = yaml.safe_load(f) or {}
            return yaml_data.get(CONFIG_VERSION_KEY, DEFAULT_CONFIG_VERSION)
    except (yaml.YAMLError, OSError) as e:
        logger.exception("Failed to read config version from %s: %s", config_path, e)
        raise


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

    input_path: Path = args.file
    config_path: Path = args.config
    output_path: Path = args.output

    # Validate file existence strictly as files, not just paths
    if not input_path.is_file():
        logger.error("Input file does not exist or is not a file: %s", input_path)
        return EXIT_FAILURE

    if not config_path.is_file():
        logger.error("Config file does not exist or is not a file: %s", config_path)
        return EXIT_FAILURE

    # 1. Extract config version (Fixed broad exception)
    try:
        config_version = extract_config_version(config_path)
    except (yaml.YAMLError, OSError):
        return EXIT_FAILURE

    # 2. Load Data & Validate (Fixed broad exception)
    try:
        df = pd.read_csv(input_path)
        validator = DataValidator.from_config(str(config_path))

        # Run validation
        report = validator.validate(df)

        # Inject version dynamically if the attribute exists
        if hasattr(report, 'config_version'):
            report.config_version = config_version

    except (pd.errors.EmptyDataError, pd.errors.ParserError, ValueError, OSError) as e:
        logger.exception("Validation execution failed: %s", e)
        return EXIT_FAILURE
    except RuntimeError as e:  # Catch fallback for external library runtime errors
        logger.exception("Runtime error during validation: %s", e)
        return EXIT_FAILURE

    # 3. Export JSON Report (Fixed broad exception)
    try:
        export_report(report, output_path)
    except (OSError, TypeError, ValueError, AttributeError):
        return EXIT_FAILURE

    # 4. CI/CD Exit Codes
    passed = getattr(report, 'passed', False)
    if not passed:
        rows_affected = getattr(report, 'total_rows_affected', 'unknown')
        logger.error(f"Validation FAILED. {rows_affected} rows affected (Config version:{config_version}).")
        return EXIT_FAILURE

    logger.info(f"Validation PASSED (Config version:{config_version})")
    return EXIT_SUCCESS


if __name__ == "__main__":
    # Defer sys.exit to the very edge of the application
    sys.exit(main())