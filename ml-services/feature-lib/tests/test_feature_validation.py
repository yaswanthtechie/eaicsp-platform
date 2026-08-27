import pandas as pd
import pytest
from src.build_features import build_all_features
from src.lag_features import add_lag_features
from src.rolling_features import add_rolling_features

def test_lag_features_missing_target_column():
    df = pd.DataFrame({
        "date": ["2026-01-01"],
        "sales": [100]
    })

    with pytest.raises(ValueError, match="Target column"):
        add_lag_features(df, "quantity")


@pytest.mark.parametrize("invalid_lags", [
    [0],
    [-1],
    ["7"],
])
def test_lag_features_rejects_invalid_lag(invalid_lags):
    df = pd.DataFrame({
        "sales": [100, 200, 300]
    })

    with pytest.raises(ValueError, match="positive integers"):
        add_lag_features(df, "sales", lags= invalid_lags)


def test_rolling_features_rejects_invalid_window():
    df = pd.DataFrame({
        "sales": [100, 200, 300]
    })

    with pytest.raises(ValueError, match="positive integers"):
        add_rolling_features(df, "sales", windows=[0])


def test_build_all_features_respects_config():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=20),
        "sales": range(20)
    })

    config_a = {
        "lags": [1, 7],
        "windows": [7]
    }

    config_b = {
        "lags": [1, 7, 14],
        "windows": [7, 14]
    }

    result_a = build_all_features(
        df,
        "date",
        "sales",
        config=config_a
    )

    result_b = build_all_features(
        df,
        "date",
        "sales",
        config=config_b
    )

    assert "sales_lag_14" not in result_a.columns
    assert "sales_lag_14" in result_b.columns

    assert "sales_roll_mean_14" not in result_a.columns
    assert "sales_roll_mean_14" in result_b.columns


def test_build_all_features_rejects_invalid_config_type():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=5),
        "sales": [10, 20, 30, 40, 50]
    })

    with pytest.raises(ValueError, match="config must be a dictionary"):
        build_all_features(
            df,
            "date",
            "sales",
            config=["invalid"]
        )


def test_build_all_features_rejects_missing_config_keys():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=5),
        "sales": [10, 20, 30, 40, 50]
    })

    with pytest.raises(
        ValueError,
        match="config must contain 'lags' and 'windows'"
    ):
        build_all_features(
            df,
            "date",
            "sales",
            config={"lags": [1, 7]}
        )



def test_lag_features_empty_dataframe():
    df = pd.DataFrame({
        "sales": pd.Series(dtype="float64")
    })

    result = add_lag_features(
        df,
        "sales",
        lags=[1, 7]
    )

    assert result.empty
    assert "sales_lag_1" in result.columns
    assert "sales_lag_7" in result.columns


def test_lag_features_single_row():
    df = pd.DataFrame({
        "sales": [100]
    })

    result = add_lag_features(
        df,
        "sales",
        lags=[1, 7]
    )

    assert len(result) == 1
    assert pd.isna(result.loc[0, "sales_lag_1"])
    assert pd.isna(result.loc[0, "sales_lag_7"])



def test_rolling_features_single_row():
    df = pd.DataFrame({
        "sales": [100]
    })

    result = add_rolling_features(
        df,
        "sales",
        windows=[7]
    )

    assert len(result) == 1
    assert pd.isna(result.loc[0, "sales_roll_mean_7"])
    assert pd.isna(result.loc[0, "sales_roll_std_7"])



def test_lag_features_all_nan_target():
    df = pd.DataFrame({
        "sales": [float("nan"), float("nan"), float("nan")]
    })

    result = add_lag_features(
        df,
        "sales",
        lags=[1]
    )

    assert result["sales_lag_1"].isna().all()


def test_rolling_features_all_nan_target():
    df = pd.DataFrame({
        "sales": [float("nan"), float("nan"), float("nan")]
    })

    result = add_rolling_features(
        df,
        "sales",
        windows=[2]
    )

    assert result["sales_roll_mean_2"].isna().all()
    assert result["sales_roll_std_2"].isna().all()

def test_large_lag_does_not_crash():
    df = pd.DataFrame({
        "sales": [10, 20, 30, 40, 50]
    })

    result = add_lag_features(
        df,
        target_col="sales",
        lags=[10]
    )

    assert "sales_lag_10" in result.columns
    assert result["sales_lag_10"].isna().all()

def test_tiny_dataset_does_not_crash():
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=2),
        "sales": [10, 20]
    })

    result = build_all_features(
        df,
        date_col="date",
        target_col="sales"
    )

    assert len(result) == 2
    assert "sales_lag_1" in result.columns
    assert "sales_roll_mean_7" in result.columns    
