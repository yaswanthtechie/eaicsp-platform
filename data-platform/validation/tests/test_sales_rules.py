import pytest
import pandas as pd
import sys
from pathlib import Path
from types import ModuleType

# ---------------------------------------------------------
# PATH RESOLUTION & MOCKING
# ---------------------------------------------------------
# 1. Guarantee PyCharm/pytest can find the 'src' directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 2. Dynamically inject a mock 'src.custom_rules' module into sys.modules.
# This prevents importlib from failing when looking for the custom escape hatches.
mock_custom_rules = ModuleType('src.custom_rules')
mock_custom_rules.check_unparseable_dates = lambda df, col: df[col] == "NOT_A_DATE"
mock_custom_rules.check_outliers = lambda df, col: df[col] > 50000

# Add the new standardizer mock
def mock_standardize(df, field='product_name', **kwargs):
    df_c = df.copy()
    if field in df_c.columns:
        df_c[field] = (
            df_c[field]
            .astype(str)
            .str.lower()
            .str.strip()
            .str.replace('-', ' ', regex=False)
        )
    return df_c
mock_custom_rules.standardize_products = mock_standardize

# Register ONLY the custom_rules mock (without overwriting the real 'src' folder)
sys.modules['src.custom_rules'] = mock_custom_rules

# 3. Now we can safely import the validator
from src.validator import DataValidator

# ---------------------------------------------------------
# TEST DATA CONFIGURATION
# ---------------------------------------------------------
YAML_CONFIG = """
rules:
  - name: order_date_not_null
    field: order_date
    type: not_null
    severity: ERROR

  - name: quantity_positive
    field: quantity_sold
    type: range
    min: 0
    max: 100000
    severity: WARNING

  - name: sku_format
    field: sku_id
    type: regex
    pattern: "^SKU-[0-9]{4}$"
    severity: ERROR

  - name: missing_quantity
    field: quantity_sold
    type: not_null
    severity: ERROR

  - name: duplicate_rows
    field: transaction_id
    type: unique
    severity: ERROR

  - name: transaction_id_not_null
    field: transaction_id
    type: not_null
    severity: ERROR

  - name: sku_id_not_null
    field: sku_id
    type: not_null
    severity: ERROR

  - name: unparseable_dates
    field: order_date
    type: custom
    function: src.custom_rules.check_unparseable_dates
    severity: ERROR

  - name: outlier_quantity
    field: quantity_sold
    type: custom
    function: src.custom_rules.check_outliers
    severity: WARNING

  - name: standardize_product_names
    field: product_name
    type: transform
    function: src.custom_rules.standardize_products
    severity: INFO
"""


@pytest.fixture
def rules_config_path(tmp_path):
    """Creates a temporary YAML file with our exact sales rules."""
    config_file = tmp_path / "sales_rules.yaml"
    config_file.write_text(YAML_CONFIG)
    return str(config_file)


# ---------------------------------------------------------
# THE TEST SUITE
# ---------------------------------------------------------
def test_full_sales_rules_suite(rules_config_path):
    # 1. Create a DataFrame deliberately designed to violate exactly one rule per row
    df = pd.DataFrame({
        "order_date": [
            "2026-07-31",  # Row 0: Valid
            None,  # Row 1: Fails order_date_not_null
            "2026-07-31",  # Row 2: Valid
            "2026-07-31",  # Row 3: Valid
            "2026-07-31",  # Row 4: Valid
            "2026-07-31",  # Row 5: Fails duplicate_rows (Part 1)
            "2026-07-31",  # Row 6: Fails duplicate_rows (Part 2)
            "2026-07-31",  # Row 7: Valid
            "2026-07-31",  # Row 8: Valid
            "NOT_A_DATE",  # Row 9: Fails unparseable_dates (custom)
            "2026-07-31",  # Row 10: Valid
        ],
        "quantity_sold": [
            10,  # Row 0: Valid
            10,  # Row 1: Valid
            -5,  # Row 2: Fails quantity_positive (WARNING)
            10,  # Row 3: Valid
            None,  # Row 4: Fails missing_quantity
            10,  # Row 5: Valid
            10,  # Row 6: Valid
            10,  # Row 7: Valid
            10,  # Row 8: Valid
            10,  # Row 9: Valid
            99999,  # Row 10: Fails outlier_quantity (custom WARNING)
        ],
        "sku_id": [
            "SKU-1234",  # Row 0: Valid
            "SKU-1234",  # Row 1: Valid
            "SKU-1234",  # Row 2: Valid
            "BAD-FORMAT",  # Row 3: Fails sku_format
            "SKU-1234",  # Row 4: Valid
            "SKU-1234",  # Row 5: Valid
            "SKU-1234",  # Row 6: Valid
            "SKU-1234",  # Row 7: Valid
            None,  # Row 8: Fails sku_id_not_null
            "SKU-1234",  # Row 9: Valid
            "SKU-1234",  # Row 10: Valid
        ],
        "transaction_id": [
            "TXN-000",  # Row 0: Valid
            "TXN-001",  # Row 1: Valid
            "TXN-002",  # Row 2: Valid
            "TXN-003",  # Row 3: Valid
            "TXN-004",  # Row 4: Valid
            "TXN-DUP",  # Row 5: Fails duplicate_rows (matches Row 6)
            "TXN-DUP",  # Row 6: Fails duplicate_rows (matches Row 5)
            None,  # Row 7: Fails transaction_id_not_null
            "TXN-008",  # Row 8: Valid
            "TXN-009",  # Row 9: Valid
            "TXN-010",  # Row 10: Valid
        ],
        "product_name": [
            " iPhone 15 ",   # Row 0: Will test standardize_products
            "iPhone 15",     # Row 1
            "GALAXY-S24",    # Row 2: Will test standardize_products
            "iPhone 15",     # Row 3
            "iPhone 15",     # Row 4
            "iPhone 15",     # Row 5
            "iPhone 15",     # Row 6
            "iPhone 15",     # Row 7
            "iPhone 15",     # Row 8
            "iPhone 15",     # Row 9
            "IPHONE-15",     # Row 10: Will test standardize_products
        ]
    })

    # 2. Initialize Validator
    validator = DataValidator.from_config(rules_config_path)

    # 3. Execute Validation
    report = validator.validate(df)

    # 4. Assert General Pipeline Status
    assert report["passed"] is False
    # Rows 1, 3, 4, 5, 6, 7, 8, 9 have ERRORs.
    # Rows 2 and 10 have WARNINGs (so they are "affected" but wouldn't fail strict cleaning)
    assert report["total_rows_affected"] == 10

    # 5. Extract reported rules for easy querying
    error_rules = {err['rule']: err['count'] for err in report['errors']}
    warning_rules = {warn['rule']: warn['count'] for warn in report['warnings']}

    # 6. Assert Exact ERROR Rule Matches
    assert error_rules.get("order_date_not_null") == 1
    assert error_rules.get("sku_format") == 1
    assert error_rules.get("missing_quantity") == 1
    assert error_rules.get("duplicate_rows") == 2  # Two rows share the duplicate ID
    assert error_rules.get("transaction_id_not_null") == 1
    assert error_rules.get("sku_id_not_null") == 1
    assert error_rules.get("unparseable_dates") == 1  # Custom rule triggered

    # 7. Assert Exact WARNING Rule Matches
    assert warning_rules.get("quantity_positive") == 1
    assert warning_rules.get("outlier_quantity") == 1  # Custom rule triggered

    # 8. Test the Strict Cleaning Engine
    clean_df = validator.clean(df, strict=True)

    # strict=True drops ERROR rows (8 rows), but keeps WARNING rows (Rows 2, 10) and perfectly valid rows (Row 0)
    assert len(clean_df) == 3

    # Verify the remaining rows are exactly the ones we expect
    assert list(clean_df.index) == [0, 2, 10]

    # 9. Verify Transformations applied properly
    # " iPhone 15 " -> "iphone 15"
    assert clean_df.loc[0, "product_name"] == "iphone 15"
    # "GALAXY-S24" -> "galaxy s24"
    assert clean_df.loc[2, "product_name"] == "galaxy s24"
    # "IPHONE-15" -> "iphone 15"
    assert clean_df.loc[10, "product_name"] == "iphone 15"


def test_validator_engine_edge_cases():
    """
    Directly tests the DataValidator engine edge cases that are not explicitly
    triggered by the standard sales_rules.yaml configuration.
    """
    from src.validator import ConfigRule, DataValidator

    # 1. Missing Column check
    rule_missing = ConfigRule(**{"name": "missing_col_rule", "field": "GHOST_COLUMN", "type": "not_null"})
    mask = rule_missing.evaluate(pd.DataFrame({"A": [1, 2]}))
    assert mask.all() == True  # Entire column fails because it doesn't exist

    # 2. Unknown rule type (Now caught by Pydantic during initialization!)
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        # Pydantic will block this instantly because 'ALIEN_TYPE' is not allowed
        rule_alien = ConfigRule(**{"name": "bad_rule", "field": "A", "type": "ALIEN_TYPE"})

    # 3. INFO severity routing
    rule_info = ConfigRule(**{"name": "info_rule", "field": "A", "type": "not_null", "severity": "INFO"})
    val_info = DataValidator([rule_info])
    report = val_info.validate(pd.DataFrame({"A": [None]}))  # Force a failure
    assert len(report['info']) == 1

    # 4. Short-circuit logic in clean()
    df = pd.DataFrame({"A": [None]})

    # Trigger first 'continue': strict=True ignores WARNING rules
    rule_warn = ConfigRule(**{"name": "warn_rule", "field": "A", "type": "not_null", "severity": "WARNING"})
    assert len(DataValidator([rule_warn]).clean(df, strict=True)) == 1

    # Trigger second 'continue': strict=False ignores rules not in target_rules
    rule_err = ConfigRule(**{"name": "err_rule", "field": "A", "type": "not_null", "severity": "ERROR"})
    assert len(DataValidator([rule_err]).clean(df, strict=False, target_rules=["other_rule"])) == 1

    # 5. Transform rule evaluation
    rule_transform = ConfigRule(**{"name": "t_rule", "type": "transform", "function": "dummy"})
    assert rule_transform.evaluate(pd.DataFrame({"A": [1, 2]})).all() == False

    # 6. Apply transform fallback
    assert rule_err.apply_transform(df).equals(df)


def test_empty_dataframe_validation(rules_config_path):
    """
    Covers the edge case:
    if df.empty:
        return report
    """
    from src.validator import DataValidator
    import pandas as pd

    # Initialize validator using the existing fixture
    validator = DataValidator.from_config(rules_config_path)

    # Create a completely empty DataFrame
    empty_df = pd.DataFrame()

    # Execute validation
    report = validator.validate(empty_df)

    # Assert it gracefully returns the default passing report
    assert report["passed"] is True
    assert report["total_rows_affected"] == 0
    assert len(report["errors"]) == 0