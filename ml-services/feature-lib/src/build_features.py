from .lag_features import add_lag_features
from .calendar_features import add_calendar_features
from .holiday_features import create_holiday_features
from .interaction_features import add_interaction_features
from numbers import Integral
import pandas as pd


def _build_v1_lag_features(
    data,
    target_col,
    lags,
    group_cols=None,
):
    """
    Frozen v1 lag feature implementation.
    """
    data = data.copy()

    if target_col not in data.columns:
        raise ValueError(
            f"Target column '{target_col}' not found in dataframe."
        )

    if not all(
        isinstance(lag, Integral)
        and not isinstance(lag, bool)
        and lag > 0
        for lag in lags
    ):
        raise ValueError(
            "All lag values must be positive integers."
        )

    if group_cols is not None:
        if not all(col in data.columns for col in group_cols):
            raise ValueError(
                "All group columns must exist in the dataframe."
            )

    for lag in lags:
        if group_cols is None:
            data[f"{target_col}_lag_{lag}"] = (
                data[target_col].shift(lag)
            )
        else:
            data[f"{target_col}_lag_{lag}"] = (
                data.groupby(group_cols)[target_col].shift(lag)
            )

    return data


def _build_v1_rolling_features(
    data,
    target_col,
    windows,
    group_cols=None,
):
    """
    Frozen v1 rolling feature implementation.
    """
    data = data.copy()

    if target_col not in data.columns:
        raise ValueError(
            f"Target column '{target_col}' not found in dataframe."
        )

    if not all(
        isinstance(window, Integral)
        and not isinstance(window, bool)
        and window > 0
        for window in windows
    ):
        raise ValueError(
            "All Rolling window values must be positive integers."
        )

    if group_cols is not None:
        if not all(col in data.columns for col in group_cols):
            raise ValueError(
                "All group columns must exist in the dataframe."
            )

    for window in windows:
        if group_cols is None:
            shifted = data[target_col].shift(1)

            data[f"{target_col}_roll_mean_{window}"] = (
                shifted.rolling(window).mean()
            )

            data[f"{target_col}_roll_std_{window}"] = (
                shifted.rolling(window).std()
            )

        else:
            shifted = data.groupby(group_cols)[target_col].shift(1)

            data[f"{target_col}_roll_mean_{window}"] = (
                shifted.groupby(
                    [data[col] for col in group_cols]
                ).transform(
                    lambda x: x.rolling(window).mean()
                )
            )

            data[f"{target_col}_roll_std_{window}"] = (
                shifted.groupby(
                    [data[col] for col in group_cols]
                ).transform(
                    lambda x: x.rolling(window).std()
                )
            )

    return data

def _build_v2_rolling_features(
    data,
    target_col,
    windows,
    group_cols=None,
):
    """
    Version 2 rolling feature implementation.

    v2 changes rolling standard deviation to population
    standard deviation (ddof=0) while preserving the same
    feature names.
    """
    data = data.copy()

    if target_col not in data.columns:
        raise ValueError(
            f"Target column '{target_col}' not found in dataframe."
        )

    if not all(
        isinstance(window, Integral)
        and not isinstance(window, bool)
        and window > 0
        for window in windows
    ):
        raise ValueError(
            "All Rolling window values must be positive integers."
        )

    if group_cols is not None:
        if not all(col in data.columns for col in group_cols):
            raise ValueError(
                "All group columns must exist in the dataframe."
            )

    for window in windows:
        if group_cols is None:
            shifted = data[target_col].shift(1)

            data[f"{target_col}_roll_mean_{window}"] = (
                shifted.rolling(window).mean()
            )

            data[f"{target_col}_roll_std_{window}"] = (
                shifted.rolling(window).std(ddof=0)
            )
        else:
            shifted = data.groupby(group_cols)[target_col].shift(1)

            data[f"{target_col}_roll_mean_{window}"] = (
                shifted.groupby(
                    [data[col] for col in group_cols]
                ).transform(
                    lambda x: x.rolling(window).mean()
                )
            )

            data[f"{target_col}_roll_std_{window}"] = (
                shifted.groupby(
                    [data[col] for col in group_cols]
                ).transform(
                    lambda x: x.rolling(window).std(ddof=0)
                )
            )

    return data

FEATURE_VERSIONS = {
    "v1": {
        "additional_windows": [],
        "roll_std_ddof": 1,
        "lag_builder": _build_v1_lag_features,
        "rolling_builder": _build_v1_rolling_features,
    },
    "v2": {
        "additional_windows": [14],
        "roll_std_ddof": 0,
        "lag_builder": add_lag_features,
        "rolling_builder": _build_v2_rolling_features,
    },
}


def build_all_features(
    df,
    date_col,
    target_col,
    config=None,
    group_cols=None,
    feature_version="v1"
):
    """
    Build all feature engineering features.
    """
    if feature_version not in FEATURE_VERSIONS:
        raise ValueError(
            f"Unsupported feature version: {feature_version}"
        )

    data = df.copy()

    if config is None:
        config = {
            "lags": [1, 7, 30],
            "windows": [7, 30]
        }

    if not isinstance(config, dict):
        raise ValueError(
            "config must be a dictionary."
        )

    required_keys = {"lags", "windows"}

    if not required_keys.issubset(config):
        raise ValueError(
            "config must contain 'lags' and 'windows'."
        )

    version_definition = FEATURE_VERSIONS[feature_version]

    version_config = {
        "lags": list(config["lags"]),
        "windows": list(
            dict.fromkeys(
                config["windows"]
                + version_definition["additional_windows"]
            )
        ),
    }

    if date_col not in data.columns:
        raise ValueError(
            f"Date column '{date_col}' not found in dataframe."
        )

    data[date_col] = pd.to_datetime(
        data[date_col],
        errors="raise"
    )

    data = data.sort_values(
        date_col
    ).reset_index(drop=True)

    lag_builder = version_definition["lag_builder"]
    rolling_builder = version_definition["rolling_builder"]

    data = lag_builder(
        data,
        target_col,
        lags=version_config["lags"],
        group_cols=group_cols,
    )

    data = rolling_builder(
        data,
        target_col,
        windows=version_config["windows"],
        group_cols=group_cols,
    )

    data = add_calendar_features(
        data,
        date_col
    )

    data = create_holiday_features(
        data,
        date_col
    )

    data = add_interaction_features(
        data
    )

    return data