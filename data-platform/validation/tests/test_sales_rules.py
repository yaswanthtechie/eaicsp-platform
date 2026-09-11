import pytest
import pandas as pd
import sys
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------
# PATH RESOLUTION
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.validator import DataValidator, SAFE_FUNCTION_REGISTRY


# ---------------------------------------------------------
# MOCK FUNCTIONS
# ---------------------------------------------------------
def mock_check_composite_unique(df, subset, **kwargs):
    return df.duplicated(subset=subset, keep=False)


def mock_check_unparseable_dates(df, field, **kwargs):
    return df[field] == "NOT_A_DATE"


def mock_flag_negatives(df, field='quantity_sold', **kwargs):
    df_c = df.copy()
    if 'flagged_for_review' not in df_c.columns:
        df_c['flagged_for_review'] = False
    df_c.loc[df_c[field] < 0, 'flagged_for_review'] = True
    return df_c


def mock_standardize_dates(df, field='order_date', **kwargs):
    # Dummy mock that just returns the dataframe as-is for test isolation
    return df.copy()


# ---------------------------------------------------------
# TEST DATA CONFIGURATION (Updated to sales_rules_2.yaml)
# ---------------------------------------------------------
YAML_CONFIG = """
version: "1.2.0"
profiles:
  default:
    global_max_fail_pct: 1.00  # FIX: Set to 100% so the heavily corrupted test dataframe isn't rejected
    global_drift_abs_min: 0.01
    global_drift_rel_min: 0.50
    rules:
      - name: date_not_null
        field: date
        type: not_null
        severity: ERROR

      - name: sku_format
        field: sku_id
        type: regex
        pattern: "^SKU-[0-9]{4,7}$"
        severity: ERROR
        max_fail_pct: 1.00     # FIX: Set to 100% so the test dataframe isn't rejected

      - name: warehouse_id_not_null
        field: warehouse_id
        type: not_null
        severity: ERROR

      - name: wh_01_minimum_price
        type: conditional
        condition_field: warehouse_id
        condition_value: "WH-01"
        field: unit_price
        target_type: range
        min: 15.0
        severity: WARNING
        max_fail_pct: 1.00     # FIX: Set to 100% so the test dataframe isn't rejected

      - name: quantity_positive
        field: quantity_sold
        type: range
        min: 0
        max: 100000
        severity: WARNING
        drift_abs_min: 0.05
        drift_rel_min: 1.00

      - name: unit_price_valid
        field: unit_price
        type: range
        min: 0.01
        severity: ERROR

      - name: composite_pk_unique
        type: custom
        function: src.custom_rules.check_composite_unique
        subset: ['date', 'sku_id', 'warehouse_id']
        severity: ERROR

      - name: unparseable_dates
        field: date
        type: custom
        function: src.custom_rules.check_unparseable_dates
        severity: ERROR

      - name: flag_negative_quantities
        field: quantity_sold
        type: transform
        function: src.custom_rules.flag_negatives
        severity: INFO

      - name: standardize_dates_transform
        field: date
        type: transform
        function: src.custom_rules.standardize_dates
        severity: INFO

      - name: date_in_range
        field: date
        type: range
        min: '2024-01-01'
        max: '2024-04-02'
        severity: WARNING
        depends_on: [ "unparseable_dates" ]

  strict:
    inherits: default
    global_max_fail_pct: 0.10
    rules:
      - name: quantity_positive
        field: quantity_sold
        type: range
        min: 1
        max: 12
        severity: ERROR
"""


@pytest.fixture
def rules_config_path(tmp_path):
    config_file = tmp_path / "sales_rules_subset.yaml"
    config_file.write_text(YAML_CONFIG)
    return str(config_file)


def test_sales_rules_subset(rules_config_path):
    # 1. Create a DataFrame deliberately designed to violate exactly one rule per row
    df = pd.DataFrame({
        "date": [
            "2024-02-01",  # 0: Valid Baseline (inside 2024-01-01 to 2024-04-02)
            None,  # 1: Fails date_not_null
            "2024-02-01",  # 2: Valid
            "2024-02-01",  # 3: Valid
            "2024-02-01",  # 4: Valid
            "2024-02-01",  # 5: Valid
            "2024-02-01",  # 6: Fails composite_pk_unique (Matches Row 7)
            "2024-02-01",  # 7: Fails composite_pk_unique (Matches Row 6)
            "NOT_A_DATE",  # 8: Fails unparseable_dates
            "2024-05-01",  # 9: Fails date_in_range (WARNING)
        ],
        "sku_id": [
            "SKU-1000",  # 0
            "SKU-1001",  # 1
            "BAD-SKU",  # 2: Fails sku_format
            "SKU-1003",  # 3
            "SKU-1004",  # 4
            "SKU-1005",  # 5
            "SKU-9999",  # 6: Duplicate Pair
            "SKU-9999",  # 7: Duplicate Pair
            "SKU-1008",  # 8
            "SKU-1009",  # 9
        ],
        "warehouse_id": [
            "WH-01", "WH-01", "WH-01",
            None,  # 3: Fails warehouse_id_not_null
            "WH-01",
            "WH-01",  # 5: Will fail WH-01 conditional min price
            "WH-DUP",  # 6: Duplicate Pair
            "WH-DUP",  # 7: Duplicate Pair
            "WH-01", "WH-02"
        ],
        "quantity_sold": [
            10, 10, 10, 10,
            -5,  # 4: Fails quantity_positive (WARNING) & triggers flag_negative_quantities (INFO)
            10, 10, 10, 10, 10
        ],
        "unit_price": [
            100.0, 100.0, 100.0, 100.0, 100.0,
            0.00,  # 5: Fails unit_price_valid (ERROR) AND wh_01_minimum_price (WARNING)
            100.0, 100.0, 100.0, 100.0
        ]
    })

    # Safely inject the mock functions securely for THIS TEST ONLY
    mock_registry = SAFE_FUNCTION_REGISTRY.copy()
    mock_registry.update({
        "src.custom_rules.check_composite_unique": mock_check_composite_unique,
        "src.custom_rules.check_unparseable_dates": mock_check_unparseable_dates,
        "src.custom_rules.flag_negatives": mock_flag_negatives,
        "src.custom_rules.standardize_dates": mock_standardize_dates
    })

    # 2. Execute Validation inside the safe patched context
    with patch.dict("src.validator.SAFE_FUNCTION_REGISTRY", mock_registry):
        # Automatically loads the 'default' profile
        validator = DataValidator.from_config(rules_config_path)
        report = validator.validate(df)

    # 3. Assert General Pipeline Status
    assert report.passed is False
    # 9 rows trigger ERROR/WARNING severities (Rows 1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert report.total_rows_affected == 9

    error_rules = {err['rule']: err['count'] for err in report.errors}
    warning_rules = {warn['rule']: warn['count'] for warn in report.warnings}

    assert error_rules.get("date_not_null") == 1
    assert error_rules.get("sku_format") == 1
    assert error_rules.get("warehouse_id_not_null") == 1
    assert error_rules.get("unit_price_valid") == 1
    assert error_rules.get("composite_pk_unique") == 2
    assert error_rules.get("unparseable_dates") == 1

    assert warning_rules.get("quantity_positive") == 1
    assert warning_rules.get("wh_01_minimum_price") == 1
    assert warning_rules.get("date_in_range") == 1

    # 4. Test the Strict Cleaning Engine inside the safe patched context
    with patch.dict("src.validator.SAFE_FUNCTION_REGISTRY", mock_registry):
        clean_df = validator.clean(df, strict=True)

    # strict=True drops the 7 ERROR rows (1, 2, 3, 5, 6, 7, 8)
    # It keeps WARNING rows (4, 9) and perfectly valid rows (0)
    assert len(clean_df) == 3
    assert list(clean_df.index) == [0, 4, 9]
    assert clean_df.loc[4, "flagged_for_review"]
    assert not clean_df.loc[0, "flagged_for_review"]