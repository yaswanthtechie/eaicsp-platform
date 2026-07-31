import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.make_messy_data import generate_messy_data
from src.rules import (
    check_dates, check_strings, check_missing,
    check_negatives, check_outliers, check_duplicates
)
from src.validator import DataValidator

# 1. Anchor paths dynamically based on this file's location
# __file__ is src/main.py -> parent is src/ -> parent.parent is the validation/ root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 2. Create a unique, timestamped log filename for this run
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filepath = LOG_DIR / f"validation_{timestamp}.log"

# 3. Configure logging to write to a file INSTEAD of the console
logging.basicConfig(
    filename=str(log_filepath),  # <--- Routes output to this file
    filemode="w",  # <--- "w" overwrites the log every run. Change to "a" to append.
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)
logger = logging.getLogger(__name__)


def main():
    # A quick console print so you know the script is actually running!
    print("Pipeline started. Check {log_filepath.relative_to(PROJECT_ROOT)} for details...")

    # Define absolute paths for our data files
    messy_csv_path = DATA_DIR / "messy_sales.csv"
    clean_csv_path = DATA_DIR / "clean_sales.csv"

    # 1. Simulate the client
    logger.info("Generating simulated messy data...")
    generate_messy_data(filepath=str(messy_csv_path))

    # 2. Load and validate
    df = pd.read_csv(messy_csv_path)
    logger.info(f"Loaded {len(df)} rows from messy_sales.csv")

    rules = [check_dates, check_strings, check_missing, check_negatives, check_outliers, check_duplicates]
    dv = DataValidator(rules=rules)

    logger.info("Running initial validation pass...")
    val_results = dv.validate(df)
    issues = val_results['issues']

    total_issues = sum(issue['count'] for issue in issues.values())
    categories = len(issues)

    logger.warning(f"Found {total_issues} issues across {categories} categories.")
    for key, data in issues.items():
        logger.info(f"Issue Breakdown -> {key}: {data['count']} instances")

    # 3. Clean
    logger.info("Executing cleaning sequence...")
    df_clean = dv.clean(df)

    if 'flagged_for_review' in df_clean.columns:
        flagged_count = int(df_clean['flagged_for_review'].sum())
    else:
        flagged_count = 0

    logger.info(f"Cleaning complete. {len(df_clean)} rows remain. {flagged_count} rows flagged for review.")

    # 4. Save output
    df_clean.to_csv(clean_csv_path, index=False)
    logger.info(f"Successfully wrote sanitized dataset to {clean_csv_path.relative_to(PROJECT_ROOT)}")

    print("Pipeline finished successfully! Clean data saved to data/clean_sales.csv")


if __name__ == "__main__":
    main()