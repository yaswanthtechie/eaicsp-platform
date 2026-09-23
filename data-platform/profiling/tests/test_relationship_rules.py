import pandas as pd
import yaml
from src.rules_suggestions import (
    suggest_relationship_rules,
    write_rules_yaml,
    validate_rules_config,
)


def test_suggest_relationship_rule_for_likely_join_key():
    df_left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    df_right = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    result = suggest_relationship_rules(
        df_left,
        df_right,
    )

    assert len(result) == 1

    rule = result[0]

    assert rule["name"] == "sku_id_relationship_sku_id"
    assert rule["type"] == "relationship_match"
    assert rule["left_field"] == "sku_id"
    assert rule["right_field"] == "sku_id"
    assert rule["overlap_percentage"] == 100.0
    assert rule["severity"] == "ERROR"


def test_possible_relationship_is_not_suggested():
    df_left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    df_right = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 16)]
        + [f"OTHER{i:03d}" for i in range(1, 6)]
    })

    result = suggest_relationship_rules(
        df_left,
        df_right,
    )

    assert result == []


def test_no_relationship_returns_empty_rules():
    df_left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    df_right = pd.DataFrame({
        "product_id": [f"PROD{i:03d}" for i in range(1, 21)]
    })

    result = suggest_relationship_rules(
        df_left,
        df_right,
    )

    assert result == []

def test_write_rules_yaml_includes_relationship_rules(tmp_path):
    df_left = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    df_right = pd.DataFrame({
        "sku_id": [f"SKU{i:03d}" for i in range(1, 21)]
    })

    report = {
        "column_summary": [
            {
                "column": "sku_id",
                "null_percent": 0.0,
                "dtype": "object",
            }
        ]
    }

    output_path = tmp_path / "suggested_rules.yaml"

    write_rules_yaml(
        report,
        output_path=output_path,
        df_left=df_left,
        df_right=df_right,
    )

    with open(
        output_path,
        "r",
        encoding="utf-8",
    ) as file:
        result = yaml.safe_load(file)

    assert "relationship_rules" in result
    assert len(result["relationship_rules"]) == 1

    rule = result["relationship_rules"][0]

    assert rule["type"] == "relationship_match"
    assert rule["left_field"] == "sku_id"
    assert rule["right_field"] == "sku_id"
    assert rule["overlap_percentage"] == 100.0


def test_validate_relationship_rule():
    config = {
        "version": "1.0.0",
        "rules": [],
        "relationship_rules": [
            {
                "name": "sku_id_relationship_sku_id",
                "type": "relationship_match",
                "left_field": "sku_id",
                "right_field": "sku_id",
                "overlap_percentage": 100.0,
                "severity": "ERROR",
            }
        ],
    }

    assert validate_rules_config(config) is True


def test_validate_invalid_relationship_rule():
    config = {
        "version": "1.0.0",
        "rules": [],
        "relationship_rules": [
            {
                "name": "bad_relationship",
                "type": "relationship_match",
                "left_field": "sku_id",
                "right_field": "sku_id",
                "overlap_percentage": 150.0,
                "severity": "ERROR",
            }
        ],
    }

    try:
        validate_rules_config(config)
        assert False
    except ValueError:
        assert True