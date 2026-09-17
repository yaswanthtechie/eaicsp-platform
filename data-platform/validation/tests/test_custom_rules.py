import pytest
import pandas as pd
from pathlib import Path
import yaml

# --- 1. NEW IMPORTS FOR DYNAMIC REGISTRY ---
from src.validator import DataValidator, ConfigRule
from src.registry import RULE_REGISTRY, discover_rules, clear_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def setup_dynamic_registry():
    """Cleans registry state before and after each test."""
    clear_registry()
    yield
    clear_registry()


@pytest.fixture
def mock_sales_yaml(tmp_path):
    """Creates a temporary YAML config mimicking sales_rules.yaml."""
    config_file = tmp_path / "mock_sales_rules.yaml"
    config_data = {
        "version": "2.0",
        "profiles": {
            "default": {
                "global_max_fail_pct": 0.50,
                "rules": [
                    {
                        "name": "require_transaction_id",
                        "type": "not_null",
                        "field": "transaction_id",
                        "severity": "ERROR"
                    },
                    {
                        "name": "check_negative_qty",
                        "type": "custom",
                        "field": "quantity_sold",
                        "severity": "ERROR",
                        "function": "check_negatives"  # Uses flat name for dynamic registry
                    }
                ]
            }
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


@pytest.fixture
def sample_sales_data():
    """Provides a sample DataFrame for testing validations."""
    return pd.DataFrame({
        "transaction_id": [101, 102, None, 104],
        "quantity_sold": [10, -5, 20, 15]
    })


# ==========================================
# TESTS
# ==========================================

def test_registry_loads_custom_rules():
    """Verify that the dynamic registry successfully discovered our rules folder."""
    # Explicitly trigger discovery for this specific test
    discover_rules(PROJECT_ROOT / "rules")

    assert "check_negatives" in RULE_REGISTRY, "check_negatives was not found in the dynamic RULE_REGISTRY!"
    assert "standardize_products" in RULE_REGISTRY, "standardize_products was not found in the dynamic RULE_REGISTRY!"


def test_validator_from_config(mock_sales_yaml):
    """Test that DataValidator correctly instantiates from a YAML config."""
    # We pass the rules_dir as empty here because the fixture already loaded them,
    # or you can pass str(PROJECT_ROOT / "rules").
    validator = DataValidator.from_config(
        yaml_path=str(mock_sales_yaml),
        profile_name="default",
        rules_dir=str(PROJECT_ROOT / "rules")
    )

    assert validator.version == "2.0"
    assert len(validator.rules) == 2
    assert validator.rules[0].name == "require_transaction_id"
    assert validator.rules[1].type == "custom"


def test_validator_execution(mock_sales_yaml, sample_sales_data):
    """Test that the validator correctly evaluates data and catches errors."""
    validator = DataValidator.from_config(
        yaml_path=str(mock_sales_yaml),
        profile_name="default",
        rules_dir=str(PROJECT_ROOT / "rules")
    )

    report = validator.validate(sample_sales_data)

    # 1 row has a missing transaction_id, 1 row has a negative quantity
    assert report.passed is False
    assert report.total_rows == 4
    assert report.total_rows_affected == 2

    # Verify specific errors were logged
    error_rules = [err["rule"] for err in report.errors]
    assert "require_transaction_id" in error_rules
    assert "check_negative_qty" in error_rules


def test_validator_clean(mock_sales_yaml, sample_sales_data):
    """Test that the validator correctly drops bad rows in strict mode."""
    validator = DataValidator.from_config(
        yaml_path=str(mock_sales_yaml),
        profile_name="default",
        rules_dir=str(PROJECT_ROOT / "rules")
    )

    clean_df = validator.clean(sample_sales_data, strict=True)

    # Original length 4, 2 bad rows should be dropped
    assert len(clean_df) == 2
    # Ensure remaining rows are the valid ones (indices 0 and 3)
    assert list(clean_df.index) == [0, 3]