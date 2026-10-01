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

def test_feature_catalog_documents_versioned_roll_std():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30),
        "target": range(30),
    })

    config = {
        "lags": [1],
        "windows": [7],
    }

    v1_catalog = generate_feature_catalog(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v1",
    )

    v2_catalog = generate_feature_catalog(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v2",
    )

    v1_std_meaning = v1_catalog.loc[
        v1_catalog["feature"] == "target_roll_std_7",
        "meaning",
    ].iloc[0]

    v2_std_meaning = v2_catalog.loc[
        v2_catalog["feature"] == "target_roll_std_7",
        "meaning",
    ].iloc[0]

    assert "Sample standard deviation (ddof=1)" in v1_std_meaning
    assert "Population standard deviation (ddof=0)" in v2_std_meaning


def test_feature_catalog_documents_v2_only_features():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30),
        "target": range(30),
    })

    config = {
        "lags": [1],
        "windows": [7],
    }

    v1_catalog = generate_feature_catalog(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v1",
    )

    v2_catalog = generate_feature_catalog(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v2",
    )

    v1_features = set(v1_catalog["feature"])
    v2_features = set(v2_catalog["feature"])

    assert "target_roll_mean_14" not in v1_features
    assert "target_roll_std_14" not in v1_features

    assert "target_roll_mean_14" in v2_features
    assert "target_roll_std_14" in v2_features