import os
import pandas as pd
import logging
from src.make_messy_data import generate_messy_data
from src.validator import DataValidator
from src.rules import (
    check_dates, check_strings, check_missing,
    check_negatives, check_outliers, check_duplicates
)

# Ensure the logs directory exists before we try to write to it
os.makedirs("../logs", exist_ok=True)

# Configure logging to write to a file INSTEAD of the console
logging.basicConfig(
    filename="../logs/validation.log",  # <--- Routes output to this file
    filemode="w",  # <--- "w" overwrites the log every run. Change to "a" to append.
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)
logger = logging.getLogger(__name__)


def main():
    # A quick console print so you know the script is actually running!
    print("Pipeline started. Check ../logs/validation.log for details...")

    # 1. Simulate the client
    logger.info("Generating simulated messy data...")
    generate_messy_data("../data/messy_sales.csv")

    # 2. Load and validate
    df = pd.read_csv("../data/messy_sales.csv")
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
    df_clean.to_csv("../data/clean_sales.csv", index=False)
    logger.info("Successfully wrote sanitized dataset to data/clean_sales.csv")

    print("Pipeline finished successfully! Clean data saved to data/clean_sales.csv")


if __name__ == "__main__":
    main()