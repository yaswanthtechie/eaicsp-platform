import pandas as pd


def add_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows= None
):
    """
    Add rolling mean and rolling standard deviation features.
    """

    data = df.copy()

    if target_col not in data.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataframe.")

    if windows is None:
        windows=[7,30]

    if not all(isinstance(window, int) and window > 0 for window in windows):
            raise ValueError(
                "All Rolling window values must be positive integers."
            )

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
