import pandas as pd


def add_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows=[7, 30]
):
    """
    Add rolling mean and rolling standard deviation features.
    """

    data = df.copy()

    for window in windows:

        data[f"{target_col}_roll_mean_{window}"] = (
            data[target_col]
            .shift(1)
            .rolling(window)
            .mean()
        )

        data[f"{target_col}_roll_std_{window}"] = (
            data[target_col]
            .shift(1)
            .rolling(window)
            .std()
        )

    return data