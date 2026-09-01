import pandas as pd
from pathlib import Path

from src.validator import DataValidator

# Dynamically resolve the absolute path to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_golden_regression():
    # 1. Load the fixed "golden" dataset and rules using absolute paths
    data_path = PROJECT_ROOT / "tests" / "data" / "messy_sales_500.csv"
    config_path = PROJECT_ROOT / "configs" / "sales_rules.yaml"

    df = pd.read_csv(data_path)
    validator = DataValidator.from_config(str(config_path))

    # 2. Execute
    report = validator.validate(df)

    # 3. Assert specific, known outcomes
    assert report.passed is False
    assert report.total_rows_affected == 103

    # Assert specific rules caught the exact right number of rows
    error_counts = {e['rule']: e['count'] for e in report.errors}
    warning_counts = {w['rule']: w['count'] for w in report.warnings}

    assert error_counts.get('unparseable_dates') is None
    assert error_counts.get('unit_price_valid') is None
    assert error_counts.get('date_not_null') == 5
    assert error_counts.get('sku_format') == 7
    assert error_counts.get('warehouse_id_not_null') == 6
    assert error_counts.get('composite_pk_unique') == 45
    assert warning_counts.get('quantity_positive') == 2
    assert warning_counts.get('date_in_range') == 43