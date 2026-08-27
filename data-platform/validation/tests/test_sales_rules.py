import pytest
import pandas as pd
import sys
from pathlib import Path
from types import ModuleType

# ---------------------------------------------------------
# PATH RESOLUTION & MOCKING
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Dynamically inject a mock 'src.custom_rules' module into sys.modules
mock_custom_rules = ModuleType('src.custom_rules')

# Mock Validation Rules
mock_custom_rules.check_composite_unique = lambda df, subset, **kwargs: df.duplicated(subset=subset, keep=False)
mock_custom_rules.check_unparseable_dates = lambda df, field, **kwargs: df[field] == "NOT_A_DATE"
mock_custom_rules.check_outliers = lambda *args, **kwargs: None
mock_custom_rules.check_negatives = lambda *args, **kwargs: None
mock_custom_rules.check_duplicate_rows = lambda *args, **kwargs: None
mock_custom_rules.standardize_products = lambda *args, **kwargs: None
mock_custom_rules.standardize_dates = lambda *args, **kwargs: None
mock_custom_rules.drop_duplicate_rows = lambda *args, **kwargs: None


# Mock Transformation Rules
def mock_flag_negatives(df, field='quantity_sold', **kwargs):
    df_c = df.copy()
    df_c['flagged_for_review'] = df_c[field] < 0
    return df_c


mock_custom_rules.flag_negatives = mock_flag_negatives

# Register the mock module
sys.modules['src.custom_rules'] = mock_custom_rules

from src.validator import DataValidator, SAFE_FUNCTION_REGISTRY

# --- SECURITY REGISTRY PATCH ---
# Inject the mock functions into the safe registry so the test is allowed to execute them
SAFE_FUNCTION_REGISTRY.update({
    "src.custom_rules.check_composite_unique": mock_custom_rules.check_composite_unique,
    "src.custom_rules.check_unparseable_dates": mock_custom_rules.check_unparseable_dates,
    "src.custom_rules.flag_negatives": mock_custom_rules.flag_negatives
})

# ---------------------------------------------------------
# TEST DATA CONFIGURATION
# ---------------------------------------------------------
YAML_CONFIG = """
rules:
  - name: date_not_null
    field: date
    type: not_null
    severity: ERROR

  - name: sku_format
    field: sku_id
    type: regex
    pattern: "^SKU-[0-9]{4}$"
    severity: ERROR

  - name: warehouse_id_not_null
    field: warehouse_id
    type: not_null
    severity: ERROR

  - name: quantity_positive
    field: quantity_sold
    type: range
    min: 0
    max: 100000
    severity: WARNING

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
"""


@pytest.fixture
def rules_config_path(tmp_path):
    config_file = tmp_path / "sales_rules_subset.yaml"
    config_file.write_text(YAML_CONFIG)
    return str(config_file)


# ---------------------------------------------------------
# THE TEST SUITE
# ---------------------------------------------------------
def test_sales_rules_subset(rules_config_path):
    # 1. Create a DataFrame deliberately designed to violate exactly one rule per row
    df = pd.DataFrame({
        "date": [
            "2026-08-01",  # 0: Valid Baseline
            None,  # 1: Fails date_not_null
            "2026-08-01",  # 2: Valid
            "2026-08-01",  # 3: Valid
            "2026-08-01",  # 4: Valid
            "2026-08-01",  # 5: Valid
            "2026-08-01",  # 6: Fails composite_pk_unique (Matches Row 7)
            "2026-08-01",  # 7: Fails composite_pk_unique (Matches Row 6)
            "NOT_A_DATE",  # 8: Fails unparseable_dates
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
        ],
        "warehouse_id": [
            "WH-01", "WH-01", "WH-01",
            None,  # 3: Fails warehouse_id_not_null
            "WH-01", "WH-01",
            "WH-DUP",  # 6: Duplicate Pair
            "WH-DUP",  # 7: Duplicate Pair
            "WH-01"
        ],
        "quantity_sold": [
            10, 10, 10, 10,
            -5,  # 4: Fails quantity_positive (WARNING) & triggers flag_negative_quantities (INFO)
            10, 10, 10, 10
        ],
        "unit_price": [
            100.0, 100.0, 100.0, 100.0, 100.0,
            0.00,  # 5: Fails unit_price_valid (min is 0.01)
            100.0, 100.0, 100.0
        ]
    })

    # 2. Initialize Validator
    validator = DataValidator.from_config(rules_config_path)

    # 3. Execute Validation
    report = validator.validate(df)

    # 4. Assert General Pipeline Status
    assert report.passed is False

    # 8 rows trigger ERROR/WARNING severities (Rows 1, 2, 3, 4, 5, 6, 7, 8)
    assert report.total_rows_affected == 8

    # 5. Extract reported rules for easy querying
    error_rules = {err['rule']: err['count'] for err in report.errors}
    warning_rules = {warn['rule']: warn['count'] for warn in report.warnings}

    # 6. Assert Exact ERROR Rule Matches
    assert error_rules.get("date_not_null") == 1
    assert error_rules.get("sku_format") == 1
    assert error_rules.get("warehouse_id_not_null") == 1
    assert error_rules.get("unit_price_valid") == 1
    assert error_rules.get("composite_pk_unique") == 2
    assert error_rules.get("unparseable_dates") == 1

    # 7. Assert Exact WARNING Rule Matches
    assert warning_rules.get("quantity_positive") == 1

    # 8. Test the Strict Cleaning Engine
    clean_df = validator.clean(df, strict=True)

    # strict=True drops the 7 ERROR rows, but keeps WARNING rows (4) and perfectly valid rows (0)
    assert len(clean_df) == 2
    assert list(clean_df.index) == [0, 4]

    # 9. Verify Transformations applied properly
    assert clean_df.loc[4, "flagged_for_review"]
    assert not clean_df.loc[0, "flagged_for_review"]