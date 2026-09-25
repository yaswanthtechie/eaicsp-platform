import re
from pathlib import Path

import pandas as pd

from src.validator import DataValidator

# Dynamically resolve the absolute path to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "tests" / "data" / "messy_sales_500.csv"
DEV_CONFIG = PROJECT_ROOT / "configs" / "dev" / "sales_rules.yaml"
PROD_CONFIG = PROJECT_ROOT / "configs" / "prod" / "sales_rules.yaml"


def test_golden_regression():
    # 1. Load the fixed "golden" dataset and rules using absolute paths
    df = pd.read_csv(DATA_PATH)

    validator = DataValidator.from_config(
        str(DEV_CONFIG),
        rules_dir=str(PROJECT_ROOT / "rules")
    )

    # 2. Execute
    report = validator.validate(df)

    # 3. Assert specific, known outcomes
    assert report.passed is False
    assert report.batch_rejected is True

    assert report.total_rows_affected == 178

    # Assert specific rules caught the exact right number of rows
    error_counts = {e['rule']: e['count'] for e in report.errors}
    warning_counts = {w['rule']: w['count'] for w in report.warnings}

    # 67 genuinely ambiguous dates (e.g. 02/01/2024) + 4 'NOT_A_DATE'.
    # Unambiguous dates (Mar 18 2024, 24/03/2024, 05/05/2024) are fixed, not flagged.
    assert error_counts.get('unparseable_dates') == 71
    assert error_counts.get('unit_price_valid') == 1
    assert error_counts.get('date_not_null') == 5
    assert error_counts.get('sku_format') == 7
    assert error_counts.get('warehouse_id_not_null') == 6
    assert error_counts.get('composite_pk_unique') == 39
    assert warning_counts.get('quantity_positive') == 2
    assert warning_counts.get('date_in_range') == 52
    assert warning_counts.get('wh_01_minimum_price') == 2


def test_golden_only_ambiguous_or_invalid_dates_are_flagged():
    """Every date left unfixed must be one a human genuinely has to decide."""
    df = pd.read_csv(DATA_PATH)
    validator = DataValidator.from_config(str(DEV_CONFIG), rules_dir=str(PROJECT_ROOT / "rules"))

    cleaned = df.copy()
    for rule in validator.rules:
        if rule.name == "standardize_dates_transform":
            cleaned = rule.apply_transform(cleaned)

    still_raw = cleaned["date"].dropna()
    still_raw = still_raw[~still_raw.astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")]

    def is_ambiguous(value):
        match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/\d{4}", value)
        return bool(match) and int(match[1]) <= 12 and int(match[2]) <= 12 and match[1] != match[2]

    assert len(still_raw) == 71
    for value in still_raw:
        assert value == "NOT_A_DATE" or is_ambiguous(value), f"{value!r} is unambiguous and should have been fixed"


def test_golden_regression_deep_profile():
    """The 'deep' profile is default plus the full-dataset outlier rule."""
    df = pd.read_csv(DATA_PATH)

    validator = DataValidator.from_config(
        str(PROD_CONFIG),
        profile_name="deep",
        rules_dir=str(PROJECT_ROOT / "rules")
    )

    report = validator.validate(df)

    warning_counts = {w['rule']: w['count'] for w in report.warnings}

    assert warning_counts.get('detect_quantity_outliers') == 2
    # Everything default catches is still caught
    assert warning_counts.get('date_in_range') == 52