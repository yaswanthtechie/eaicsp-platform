from pathlib import Path

import pandas as pd
import pytest

from src.validator import ConfigRule, DataValidator, resolve_env_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = str(PROJECT_ROOT / "rules")
GOOD_ROW = {
    "date": "2024-02-03",
    "sku_id": "SKU-0001",
    "warehouse_id": "WH-02",
    "quantity_sold": 5,
    "unit_price": 20.0,
}


def _config(env):
    return str(PROJECT_ROOT / "configs" / env / "sales_rules.yaml")


# ------------------------------------------------------------------
# M1: a row we can't fully check must never pass
# ------------------------------------------------------------------

@pytest.mark.parametrize("row", [{}, {"foo": "bar"}, {k: v for k, v in GOOD_ROW.items() if k != "unit_price"}])
def test_validate_row_rejects_rows_missing_required_fields(row):
    validator = DataValidator.from_config(_config("dev"), rules_dir=RULES_DIR)

    result = validator.validate_row(row)

    assert result.passed is False
    assert result.errors[0].startswith("schema_error: Missing required columns")


def test_validate_row_good_row_passes_with_no_fixes():
    validator = DataValidator.from_config(_config("dev"), rules_dir=RULES_DIR)

    result = validator.validate_row(GOOD_ROW)

    assert result.passed is True
    assert result.remediations == []


# ------------------------------------------------------------------
# M2: row-level audit trail says what changed and why
# ------------------------------------------------------------------

@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_validate_row_records_what_was_fixed_and_why(env):
    validator = DataValidator.from_config(_config(env), rules_dir=RULES_DIR)

    result = validator.validate_row({**GOOD_ROW, "date": " Mar 18 2024 ", "sku_id": " sku-0001 "})

    assert result.passed is True
    fixes = {r["rule"]: r for r in result.remediations}
    assert fixes["standardize_dates_transform"]["original"] == " Mar 18 2024 "
    assert fixes["standardize_dates_transform"]["remediated"] == "2024-03-18"
    assert fixes["clean_sku_whitespace"]["original"] == " sku-0001 "
    assert fixes["clean_sku_whitespace"]["remediated"] == "SKU-0001"
    assert all(r["reason"] for r in result.remediations)


def test_validate_row_never_guesses_an_ambiguous_date():
    validator = DataValidator.from_config(_config("prod"), rules_dir=RULES_DIR)

    result = validator.validate_row({**GOOD_ROW, "date": "02/01/2024"})

    assert result.passed is False
    assert "unparseable_dates" in result.errors
    assert not any(r["rule"] == "standardize_dates_transform" for r in result.remediations)


def test_negative_quantity_is_flagged_not_changed():
    validator = DataValidator.from_config(_config("prod"), rules_dir=RULES_DIR)

    result = validator.validate_row({**GOOD_ROW, "quantity_sold": -3})

    assert "quantity_positive" in result.warnings
    assert not any(r["field"] == "quantity_sold" for r in result.remediations)


def test_clean_whitespace_and_case_rejects_unknown_case():
    from rules.custom_rules import clean_whitespace_and_case

    with pytest.raises(ValueError, match="target_case"):
        clean_whitespace_and_case(pd.DataFrame({"s": ["a"]}), field="s", target_case="title")


# ------------------------------------------------------------------
# M5: environments really are different
# ------------------------------------------------------------------

def _batch_with_bad_prices(n_rows=100, n_bad=20):
    """n_rows valid, unique rows, of which n_bad have an invalid (ERROR) unit_price."""
    rows = []
    for i in range(n_rows):
        rows.append({
            "date": f"2024-02-{(i % 28) + 1:02d}",
            "sku_id": f"SKU-{i:04d}",
            "warehouse_id": "WH-02",
            "quantity_sold": 5,
            "unit_price": -1.0 if i < n_bad else 20.0,
        })
    return pd.DataFrame(rows)


def test_same_file_is_accepted_in_dev_but_rejected_in_staging_and_prod():
    df = _batch_with_bad_prices()  # 20% of rows fail unit_price_valid

    results = {
        env: DataValidator.from_config(_config(env), rules_dir=RULES_DIR).validate(df.copy(), skip_sla=True)
        for env in ["dev", "staging", "prod"]
    }

    assert results["dev"].batch_rejected is False     # dev backstop is 30%
    assert results["staging"].batch_rejected is True  # staging backstop is 10%
    assert results["prod"].batch_rejected is True     # prod backstop is 10%


@pytest.mark.parametrize("env, expected", [("PROD", "prod"), (" Staging ", "staging"), (None, "dev"), ("", "dev")])
def test_resolve_env_path_normalises_env_names(env, expected):
    assert resolve_env_path("configs/sales_rules.yaml", env) == Path("configs") / expected / "sales_rules.yaml"


def test_resolve_env_path_rejects_path_tricks():
    with pytest.raises(ValueError, match="Invalid environment"):
        resolve_env_path("configs/sales_rules.yaml", "../../x")