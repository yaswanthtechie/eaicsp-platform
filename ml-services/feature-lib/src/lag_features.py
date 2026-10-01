import pandas as pd
from numbers import Integral


def add_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags=None,
    group_cols=None
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
                data.groupby(group_cols)[target_col]
                .shift(lag)
            )

    return data
