from pathlib import Path

import pandas as pd
import pytest
import json

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


# ------------------------------------------------------------------
# --env must work with the CLI's default config path
# ------------------------------------------------------------------

@pytest.mark.parametrize("base, env, expected", [
    # The CLI default is configs/dev/...; --env prod must switch folders.
    ("configs/dev/sales_rules.yaml", "prod", "configs/prod/sales_rules.yaml"),
    ("configs/dev/sales_rules.yaml", "staging", "configs/staging/sales_rules.yaml"),
    # No --env: a path already inside an environment folder is used as given.
    ("configs/prod/sales_rules.yaml", None, "configs/prod/sales_rules.yaml"),
    # Only the folder directly above the file counts, not e.g. C:/Users/dev/...
    ("home/dev/proj/configs/sales_rules.yaml", "dev", "home/dev/proj/configs/dev/sales_rules.yaml"),
])
def test_resolve_env_path_switches_env_folder(base, env, expected):
    assert resolve_env_path(base, env) == Path(expected)


def test_cli_env_prod_uses_prod_config_with_default_config_path(tmp_path):
    from src import validate_cli

    output = tmp_path / "report.json"
    code = validate_cli.main([
        "--file", str(PROJECT_ROOT / "tests" / "data" / "messy_sales_500.csv"),
        "--output", str(output),
        "--env", "prod",
    ])

    assert code != validate_cli.EXIT_TOOL_ERROR  # config was found
    report = json.loads(output.read_text())
    assert report["config_version"].startswith("prod")


# ------------------------------------------------------------------
# M1: a crashed rule fails the row in validate_row AND validate()
# ------------------------------------------------------------------

def test_crashed_rule_fails_row_same_as_batch():
    validator = DataValidator.from_config(_config("prod"), rules_dir=RULES_DIR)
    bad_row = {**GOOD_ROW, "quantity_sold": "abc"}  # makes quantity_positive crash

    row_result = validator.validate_row(bad_row)
    batch_result = validator.validate(pd.DataFrame([bad_row]), skip_sla=True)

    assert row_result.passed is False
    assert "quantity_positive" in [s["rule"] for s in row_result.skipped_rules]
    assert batch_result.passed is False


# ------------------------------------------------------------------
# M2: the audit trail can always be turned into JSON
# ------------------------------------------------------------------

def test_row_audit_is_json_serialisable_for_numeric_input():
    validator = DataValidator.from_config(_config("prod"), rules_dir=RULES_DIR)

    result = validator.validate_row({**GOOD_ROW, "sku_id": 1234})

    payload = json.loads(result.model_dump_json())
    fix = next(r for r in payload["remediations"] if r["rule"] == "clean_sku_whitespace")
    assert fix["original"] == 1234
    assert fix["remediated"] == "1234"


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_date_fix_reason_is_documented_in_every_env(env):
    validator = DataValidator.from_config(_config(env), rules_dir=RULES_DIR)

    result = validator.validate_row({**GOOD_ROW, "date": "Mar 18 2024"})

    fix = next(r for r in result.remediations if r["rule"] == "standardize_dates_transform")
    assert "exactly one possible meaning" in fix["reason"]


def test_dev_bulk_profile_is_looser_than_dev_default():
    default = DataValidator.from_config(_config("dev"), rules_dir=RULES_DIR)
    bulk = DataValidator.from_config(_config("dev"), profile_name="bulk", rules_dir=RULES_DIR)

    assert bulk.global_max_fail_pct > default.global_max_fail_pct


# ------------------------------------------------------------------
# M2: date_order is opt-in, set from the config, and audited
# ------------------------------------------------------------------

def test_dayfirst_source_fixes_ambiguous_date_with_audit():
    rules = [
        ConfigRule(
            name="standardize_dates_transform",
            field="date",
            type="transform",
            function="standardize_dates",
            date_order="dayfirst",
            description="Source writes DD/MM/YYYY, so 02/01/2024 is read as 2 January 2024",
            severity="INFO",
        ),
    ]
    validator = DataValidator(rules)

    result = validator.validate_row({**GOOD_ROW, "date": "02/01/2024"})

    fix = result.remediations[0]
    assert fix["original"] == "02/01/2024"
    assert fix["remediated"] == "2024-01-02"
    assert "DD/MM/YYYY" in fix["reason"]


def test_shipped_configs_never_guess_ambiguous_dates():
    """No environment turns on date_order by accident."""
    for env in ["dev", "staging", "prod"]:
        validator = DataValidator.from_config(_config(env), rules_dir=RULES_DIR)
        result = validator.validate_row({**GOOD_ROW, "date": "02/01/2024"})
        assert "unparseable_dates" in result.errors, env