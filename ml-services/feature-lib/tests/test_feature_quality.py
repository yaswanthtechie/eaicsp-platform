import numpy as np
import pandas as pd

from src.build_features import build_all_features
from src.feature_quality import score_feature_quality


def test_feature_quality_flags_high_null_feature():
    df = pd.DataFrame({
        "good_feature": [1, 2, 3, 4, 5],
        "risky_feature": [1, None, None, None, 5],
    })

    result = score_feature_quality(df, null_threshold=0.20)

    risky = result[result["feature"] == "risky_feature"].iloc[0]

    assert risky["risk"] == "risky"
    assert "High null rate" in risky["reason"]

def test_feature_quality_flags_unstable_feature():
    df = pd.DataFrame({
        "stable_feature": [10, 11, 10, 12, 11],
        "unstable_feature": [1, 100, 2, 200, 3],
    })

    result = score_feature_quality(
        df,
        instability_threshold=1.0,
    )

    unstable = result[
        result["feature"] == "unstable_feature"
    ].iloc[0]

    assert unstable["risk"] == "risky"
    assert "High variability" in unstable["reason"]

def test_feature_quality_flags_all_zero_feature():
    df = pd.DataFrame({
        "zero_feature": [0, 0, 0, 0, 0],
    })

    result = score_feature_quality(df)

    zero_feature = result[
        result["feature"] == "zero_feature"
    ].iloc[0]

    assert zero_feature["risk"] == "risky"
    assert "No variation" in zero_feature["reason"]


def test_feature_quality_flags_constant_feature():
    df = pd.DataFrame({
        "constant_feature": [5, 5, 5, 5, 5],
    })

    result = score_feature_quality(df)

    constant_feature = result[
        result["feature"] == "constant_feature"
    ].iloc[0]

    assert constant_feature["risk"] == "risky"
    assert "No variation" in constant_feature["reason"]


def test_feature_quality_flags_single_unique_value():
    df = pd.DataFrame({
        "single_value_feature": [10, 10, 10, 10, 10],
    })

    result = score_feature_quality(df)

    single_value_feature = result[
        result["feature"] == "single_value_feature"
    ].iloc[0]

    assert single_value_feature["risk"] == "risky"
    assert "No variation" in single_value_feature["reason"]

def test_feature_quality_flags_high_null_lag_feature():
    rng = np.random.default_rng(42)

    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60),
        "target": rng.poisson(50, 60),
    })

    config = {
        "lags": [1, 30],
        "windows": [7],
    }

    features = build_all_features(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v1",
    )

    quality = score_feature_quality(features)

    risky = quality[quality["risk"] == "risky"]

    lag_30 = risky[risky["feature"] == "target_lag_30"]

    assert not lag_30.empty
    assert lag_30.iloc[0]["null_rate"] >= 0.20

    lag_1 = quality[quality["feature"] == "target_lag_1"]

    assert not lag_1.empty
    assert lag_1.iloc[0]["risk"] == "safe"