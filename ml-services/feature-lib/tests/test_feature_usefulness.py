import pandas as pd
import pytest
from src.feature_usefulness import calculate_feature_correlations,calculate_model_feature_importance,select_top_features


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