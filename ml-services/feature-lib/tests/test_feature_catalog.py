import pandas as pd

from src.feature_catalog import generate_feature_catalog


def test_feature_catalog_contains_generated_features():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30),
        "target": range(30),
    })

    catalog = generate_feature_catalog(
        df,
        date_col="date",
        target_col="target",
        config={
            "lags": [1, 7],
            "windows": [7],
        },
        feature_version="v1",
    )

    assert not catalog.empty
    assert "feature" in catalog.columns
    assert "type" in catalog.columns
    assert "meaning" in catalog.columns
    assert "version" in catalog.columns

    assert "target_lag_1" in catalog["feature"].values
    assert "target_roll_mean_7" in catalog["feature"].values