from .lag_features import add_lag_features
from .rolling_features import add_rolling_features
from .calendar_features import add_calendar_features
from .holiday_features import create_holiday_features
from .interaction_features import add_interaction_features
import pandas as pd

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
    if feature_version not in {"v1", "v2"}:
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
        raise ValueError("config must be a dictionary.")

    required_keys = {"lags", "windows"}

    if not required_keys.issubset(config):
        raise ValueError(
        "config must contain 'lags' and 'windows'."
    )
    # Version-specific feature definition
    if feature_version == "v1":
        version_config = config
    else:  # v2
        version_config = {
            "lags": config["lags"],
            "windows": list(
                dict.fromkeys(config["windows"] + [14])
            ),
        }
    if date_col not in data.columns:
        raise ValueError(f"Date column '{date_col}' not found in dataframe.")

    data[date_col] = pd.to_datetime(
        data[date_col],
        errors="raise"
    )

    data = data.sort_values(date_col).reset_index(drop=True)

    data = add_lag_features(
        data,
        target_col,
        lags=version_config["lags"],
        group_cols=group_cols
    )

    data = add_rolling_features(
        data,
        target_col,
        windows=version_config["windows"],
        group_cols=group_cols
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
