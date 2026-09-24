import pandas as pd
import pytest

from src.quality_scorecard import (
    calculate_completeness,
    calculate_validity,
    calculate_consistency,
    calculate_uniqueness,
    generate_quality_scorecard,
)


def test_completeness_with_missing_values():
    df = pd.DataFrame(
        {
            "name": ["A", "B", None, "D"],
            "age": [20, 21, 22, None],
        }
    )

    score = calculate_completeness(df)

    assert score == 75.0


def test_completeness_with_no_missing_values():
    df = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "age": [20, 21, 22],
        }
    )

    score = calculate_completeness(df)

    assert score == 100.0


def test_validity_with_rules():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, -5, 30],
        }
    )

    rules = {
        "quantity": lambda s: s.ge(0),
    }

    score = calculate_validity(df, rules)

    assert score == 75.0


def test_validity_without_rules():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, -5],
        }
    )

    score = calculate_validity(df)

    assert score == 100.0


def test_consistency_with_rule():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, -5, 30],
        }
    )

    rules = [
        lambda data: data["quantity"].ge(0),
    ]

    score = calculate_consistency(df, rules)

    assert score == 75.0


def test_consistency_without_rules():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, -5],
        }
    )

    score = calculate_consistency(df)

    assert score == 100.0


def test_uniqueness_for_key_column():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 3],
        }
    )

    score = calculate_uniqueness(df, ["id"])

    assert score == 75.0


def test_uniqueness_without_columns():
    df = pd.DataFrame(
        {
            "warehouse": ["WH1", "WH1", "WH2"],
        }
    )

    score = calculate_uniqueness(df)

    assert score == 100.0


def test_generate_quality_scorecard():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 3],
            "quantity": [10, 20, 30, -5],
        }
    )

    validity_rules = {
        "quantity": lambda s: s.ge(0),
    }

    consistency_rules = [
        lambda data: data["quantity"].ge(0),
    ]

    scorecard = generate_quality_scorecard(
        df,
        version=1,
        validity_rules=validity_rules,
        consistency_rules=consistency_rules,
        uniqueness_columns=["id"],
    )

    assert scorecard["version"] == 1

    assert "overall_score" in scorecard

    assert "components" in scorecard

    assert set(scorecard["components"]) == {
        "completeness",
        "validity",
        "consistency",
        "uniqueness",
    }

    assert 0 <= scorecard["overall_score"] <= 100


def test_empty_dataframe():
    df = pd.DataFrame()

    scorecard = generate_quality_scorecard(df)

    assert scorecard["overall_score"] == 100.0


def test_invalid_validity_rule_result():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, 30],
        }
    )

    rules = {
        "quantity": lambda s: True,
    }

    with pytest.raises(ValueError):
        calculate_validity(df, rules)


def test_invalid_consistency_rule_result():
    df = pd.DataFrame(
        {
            "quantity": [10, 20, 30],
        }
    )

    rules = [
        lambda data: True,
    ]

    with pytest.raises(ValueError):
        calculate_consistency(df, rules)