import pandas as pd
from numbers import Integral


def add_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags=None
):
    """
    Add lag features to the dataframe.
    """

    data = df.copy()

    if target_col not in data.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataframe.")

    if lags is None:
        lags = [1,7,30]

    if not all(
        isinstance(lag, Integral)
        and not isinstance(lag, bool)
        and lag > 0
        for lag in lags
    ):
        raise ValueError(
            "All lag values must be positive integers."
        )

    for lag in lags:
        data[f"{target_col}_lag_{lag}"] = (
            data[target_col].shift(lag)
        )

    return data
