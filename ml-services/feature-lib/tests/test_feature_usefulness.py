import pandas as pd
import pytest
from src.build_features import build_all_features
from src.feature_usefulness import calculate_feature_correlations,calculate_model_feature_importance,calculate_feature_significance,select_top_features


def test_feature_correlations_returns_sorted_numeric_features():
    df = pd.DataFrame({
        "sales": [10, 20, 30, 40, 50],
        "feature_strong": [1, 2, 3, 4, 5],
        "feature_weak": [5, 3, 4, 2, 1],
        "category": ["A", "B", "A", "B", "A"]
    })

    result = calculate_feature_correlations(
        df,
        "sales"
    )

    assert "feature_strong" in result.index
    assert "feature_weak" in result.index
    assert "category" not in result.index

    assert "correlation" in result.columns

    assert result.index[0] == "feature_strong"

def test_feature_correlations_rejects_missing_target():
    df = pd.DataFrame({
        "sales": [10, 20, 30],
        "feature": [1, 2, 3]
    })

    with pytest.raises(ValueError, match="Target column"):
        calculate_feature_correlations(
            df,
            "quantity"
        )

def test_feature_correlations_excludes_constant_features():
    df = pd.DataFrame({
        "sales": [10, 20, 30, 40, 50],
        "useful_feature": [1, 2, 3, 4, 5],
        "constant_feature": [1, 1, 1, 1, 1]
    })

    result = calculate_feature_correlations(
        df,
        "sales"
    )

    assert "useful_feature" in result.index
    assert "constant_feature" not in result.index

def test_model_feature_importance():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3, 4, 5],
        "feature_2": [5, 4, 3, 2, 1],
        "target": [2, 4, 6, 8, 10]
    })

    result = calculate_model_feature_importance(
        df,
        target_col="target"
    )

    assert list(result.columns) == ["importance"]
    assert set(result.index) == {"feature_1", "feature_2"}
    assert (result["importance"] >= 0).all()


def test_model_feature_importance_invalid_target():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3],
        "target": ["a", "b", "c"]
    })

    with pytest.raises(ValueError, match="must be numeric"):
        calculate_model_feature_importance(
            df,
            target_col="target"
        )


def test_select_top_features_selects_useful_feature_over_noise():
    df = pd.DataFrame({
        "useful_feature": [10, 20, 30, 40, 50],
        "noise_feature": [73, 12, 91, 34, 6],
        "target": [1, 2, 3, 4, 5]
    })

    result = select_top_features(
        df,
        target_col="target",
        n_features=1
    )

    assert "useful_feature" in result.index
    assert "noise_feature" not in result.index

def test_select_top_features_invalid_n_features():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3],
        "target": [2, 4, 6]
    })

    with pytest.raises(
        ValueError,
        match="n_features must be greater than 0"
    ):
        select_top_features(
            df,
            target_col="target",
            n_features=0
        )

def test_select_top_features_more_than_available():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3, 4, 5],
        "feature_2": [2, 4, 6, 8, 10],
        "feature_3": [5, 4, 3, 2, 1],
        "target": [2, 4, 6, 8, 10]
    })

    result = select_top_features(
        df,
        target_col="target",
        n_features=10
    )

    assert len(result) == 3

def test_model_feature_importance_ignores_all_nan_feature():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3, 4, 5],
        "feature_2": [float("nan")] * 5,
        "target": [2, 4, 6, 8, 10]
    })

    result = calculate_model_feature_importance(
        df,
        target_col="target"
    )

    assert "feature_1" in result.index
    assert "feature_2" not in result.index
    assert (result["importance"] >= 0).all()

def test_model_feature_importance_rejects_invalid_n_estimators():
    df = pd.DataFrame({
        "feature_1": [1, 2, 3, 4, 5],
        "target": [2, 4, 6, 8, 10]
    })

    with pytest.raises(
        ValueError,
        match="n_estimators must be greater than 0"
    ):
        calculate_model_feature_importance(
            df,
            target_col="target",
            n_estimators=0
        )

def test_select_top_features_end_to_end_with_tiny_dataset():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=2),
        "quantity_sold": [10, 20],
    })

    features = build_all_features(
        df,
        date_col="date",
        target_col="quantity_sold",
        config={
            "lags": [1],
            "windows": [1],
        },
    )

    selected = select_top_features(
        features,
        target_col="quantity_sold",
        n_features=1,
    )

    assert not selected.empty

def test_calculate_feature_significance():
    df = pd.DataFrame(
        {
            "target": [1, 2, 3, 4, 5],
            "strong_feature": [2, 4, 6, 8, 10],
            "weak_feature": [5, 1, 4, 2, 3],
        }
    )

    result = calculate_feature_significance(
        df,
        target_col="target",
    )

    assert "feature" in result.columns
    assert "correlation" in result.columns
    assert "p_value" in result.columns
    assert "is_significant" in result.columns

    strong = result[result["feature"] == "strong_feature"].iloc[0]

    assert strong["correlation"] == 1.0
    assert strong["p_value"] < 0.05
    assert bool(strong["is_significant"]) is True


def test_calculate_feature_significance_handles_missing_values():
    df = pd.DataFrame(
        {
            "target": [1, 2, 3, 4, 5],
            "feature": [2, 4, None, 8, 10],
        }
    )

    result = calculate_feature_significance(
        df,
        target_col="target",
    )

    assert not result.empty
    assert result.iloc[0]["feature"] == "feature"


def test_calculate_feature_significance_rejects_invalid_significance_level():
    df = pd.DataFrame(
        {
            "target": [1, 2, 3],
            "feature": [2, 4, 6],
        }
    )

    with pytest.raises(ValueError, match="significance_level"):
        calculate_feature_significance(
            df,
            target_col="target",
            significance_level=1.5,
        )


def test_calculate_feature_significance_requires_numeric_target():
    df = pd.DataFrame(
        {
            "target": ["a", "b", "c"],
            "feature": [1, 2, 3],
        }
    )

    with pytest.raises(ValueError, match="numeric"):
        calculate_feature_significance(
            df,
            target_col="target",
    )

def test_calculate_feature_significance_marks_significant_and_insignificant_features():
    df = pd.DataFrame(
        {
            "target": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "strong_feature": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            "weak_feature": [7, 2, 9, 1, 6, 3, 8, 4, 10, 5],
        }
    )

    result = calculate_feature_significance(
        df,
        target_col="target",
        significance_level=0.05,
    )

    strong = result[result["feature"] == "strong_feature"].iloc[0]
    weak = result[result["feature"] == "weak_feature"].iloc[0]

    assert strong["is_significant"]
    assert strong["p_value"] < 0.05

    assert not weak["is_significant"]
    assert weak["p_value"] >= 0.05


def test_select_top_features_includes_statistical_backing():
    df = pd.DataFrame(
        {
            "target": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "useful_feature": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
            "noise_feature": [7, 2, 9, 1, 6, 3, 8, 4, 10, 5],
        }
    )

    selected = select_top_features(
        df,
        target_col="target",
        n_features=2,
    )

    assert "p_value" in selected.columns
    assert "is_significant" in selected.columns
    assert selected.loc["useful_feature", "is_significant"]