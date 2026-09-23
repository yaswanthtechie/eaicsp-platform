import pandas as pd

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