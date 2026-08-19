import pandas as pd
import pytest
from src.feature_usefulness import calculate_feature_correlations


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
