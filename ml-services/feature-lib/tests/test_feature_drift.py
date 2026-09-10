import pandas as pd
import pytest

from src.feature_drift import detect_feature_drift


def test_no_drift_for_similar_distributions():
    reference = pd.DataFrame(
        {"feature_a": [10, 11, 12, 10, 13, 11, 12]}
    )

    current = pd.DataFrame(
        {"feature_a": [10, 12, 11, 13, 12, 14, 11]}
    )

    result = detect_feature_drift(
        reference,
        current,
        features=["feature_a"],
    )

    assert not result.loc[0, "is_drifted"]


def test_detects_shifted_distribution():
    reference = pd.DataFrame(
        {"feature_a": [10, 11, 12, 10, 13, 11, 12]}
    )

    current = pd.DataFrame(
        {"feature_a": [50, 52, 55, 51, 58, 54, 53]}
    )

    result = detect_feature_drift(
        reference,
        current,
        features=["feature_a"],
    )

    assert result.loc[0, "is_drifted"]


def test_handles_missing_values():
    reference = pd.DataFrame(
        {"feature_a": [10, 11, None, 12, 13, None, 11]}
    )

    current = pd.DataFrame(
        {"feature_a": [10, 12, 11, None, 13, 14, None]}
    )

    result = detect_feature_drift(
        reference,
        current,
        features=["feature_a"],
    )

    assert len(result) == 1
    assert pd.notna(result.loc[0, "p_value"])


def test_missing_feature_raises_error():
    reference = pd.DataFrame(
        {"feature_a": [1, 2, 3]}
    )

    current = pd.DataFrame(
        {"feature_b": [1, 2, 3]}
    )

    with pytest.raises(ValueError, match="feature_a"):
        detect_feature_drift(
            reference,
            current,
            features=["feature_a"],
        )


def test_invalid_significance_level_raises_error():
    reference = pd.DataFrame(
        {"feature_a": [1, 2, 3]}
    )

    current = pd.DataFrame(
        {"feature_a": [1, 2, 3]}
    )

    with pytest.raises(ValueError):
        detect_feature_drift(
            reference,
            current,
            features=["feature_a"],
            significance_level=1.5,
        )


def test_multiple_features_are_checked():
    reference = pd.DataFrame(
        {
            "feature_a": [10, 11, 12, 10, 13],
            "feature_b": [100, 101, 102, 100, 103],
        }
    )

    current = pd.DataFrame(
        {
            "feature_a": [10, 12, 11, 13, 12],
            "feature_b": [100, 101, 102, 100, 103],
        }
    )

    result = detect_feature_drift(
        reference,
        current,
        features=["feature_a", "feature_b"],
    )

    assert len(result) == 2
    assert list(result["feature"]) == [
        "feature_a",
        "feature_b",
    ]