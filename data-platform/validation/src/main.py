import argparse
import logging
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# ---------------------------------------------------------
# PATH RESOLUTION & MODULE FIX
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure Python can find the 'src' module no matter where you run this from
sys.path.append(str(PROJECT_ROOT))

from src.make_messy_data import generate_messy_data
from src.validator import DataValidator

# ---------------------------------------------------------
# LOGGER SETUP
# ---------------------------------------------------------
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filepath = LOG_DIR / f"validation_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filepath, mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def log_issues(issues: List[Dict[str, Any]], severity_label: str, report: Dict[str, Any]):
    """Helper to cleanly log both errors and warnings without repeating code."""
    log_func = logger.error if severity_label == "ERROR" else logger.warning

    for item in issues:
        log_func(f"{severity_label} -> Rule: {item['rule']} | Field: {item['field']} | Count: {item['count']}")
        if item['rule'] in report['sample_bad_rows']:
            logger.info(f"     -> Samples for '{item['rule']}':")
            for sample in report['sample_bad_rows'][item['rule']]:
                logger.info(f"         Row {sample['row_index']}: [{sample['failed_value']}]")


def main():
    # Setup CLI Arguments to remove hardcoded paths
    parser = argparse.ArgumentParser(description="Run the Config-Driven Data Validation Pipeline.")
    parser.add_argument("--config", type=str, default=str(PROJECT_ROOT / "configs" / "sales_rules.yaml"),
                        help="Path to the YAML rules config.")
    parser.add_argument("--input", type=str, default=str(PROJECT_ROOT / "data" / "messy_sales.csv"),
                        help="Path to input data.")
    parser.add_argument("--output", type=str, default=str(PROJECT_ROOT / "data" / "clean_sales.csv"),
                        help="Path to save cleaned data.")
    parser.add_argument("--skip-generate", action="store_true", help="Skip auto-generating data and use existing input file.")
    parser.add_argument("--no-strict", action="store_false", dest="strict", help="Disable strict cleaning mode.")
    args = parser.parse_args()

    config_path = Path(args.config)
    input_path = Path(args.input)
    output_path = Path(args.output)

    logger.info(f"Pipeline started. Check {log_filepath} for details...")

    if not config_path.exists():
        logger.error(f"FATAL ERROR: Config file not found at {config_path}")
        return

    # 1. Simulate the client data (Auto-generate by default unless skipped)
    if not args.skip_generate or not input_path.exists():
        if args.skip_generate and not input_path.exists():
            logger.info(f"Input file not found at {input_path}. Overriding --skip-generate and auto-generating data...")
        else:
            logger.info(f"Generating simulated messy data at {input_path} (Default behavior)...")
        generate_messy_data(filepath=input_path)

    # 2. Load data
    try:
        df = pd.read_csv(input_path)
        logger.info(f"Loaded {len(df)} rows from {input_path.name}")
    except FileNotFoundError:
        logger.error(f"FATAL ERROR: The input file was not found at {input_path}.")
        return
    except Exception as e:
        logger.error(f"FATAL ERROR: An unexpected error occurred while reading the data: {e}")
        return

    # 3. Initialize the config-driven Validator
    logger.info(f"Loading rules from {config_path.name}...")
    try:
        dv = DataValidator.from_config(str(config_path))
    except Exception as e:
        logger.error(f"FATAL ERROR: Failed to initialize validator: {e}")
        return

    # 4. Execute validation
    logger.info("Running validation pass...")
    try:
        report = dv.validate(df)
    except Exception as e:
        logger.error(f"FATAL ERROR: Validation crashed during execution: {e}")
        return

    logger.info(f"Validation Passed: {report['passed']}")
    logger.info(f"Total Rows Affected: {report['total_rows_affected']}")

    log_issues(report['errors'], "ERROR", report)
    log_issues(report['warnings'], "WARNING", report)

    # 5. Clean the data
    logger.info(f"Executing cleaning sequence (Strict Mode: {args.strict})...")
    try:
        clean_df = dv.clean(df, strict=args.strict)
        logger.info(f"Cleaning complete. {len(clean_df)} rows remain.")
    except Exception as e:
        logger.error(f"FATAL ERROR: Cleaning crashed during execution: {e}")
        return

    # 6. Save the file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clean_df.to_csv(output_path, index=False)
        logger.info(f"Successfully wrote sanitized dataset to {output_path}")
    except Exception as e:
        logger.error(f"FATAL ERROR: Failed to save cleaned data to {output_path}: {e}")
        return

    logger.info("Pipeline finished!")


if __name__ == "__main__":
    main()