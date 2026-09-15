import pandas as pd
from numbers import Integral


def add_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows=None,
    group_cols=None
):
    """
    Add rolling mean and rolling standard deviation features.
    """

    data = df.copy()

    if target_col not in data.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataframe.")

    if windows is None:
        windows = [7, 30]

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
                shifted.groupby([data[col] for col in group_cols])
                .transform(lambda x: x.rolling(window).mean())
            )

            data[f"{target_col}_roll_std_{window}"] = (
                shifted.groupby([data[col] for col in group_cols])
                .transform(lambda x: x.rolling(window).std())
            )

    return data