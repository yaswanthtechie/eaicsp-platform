import pandas as pd


def add_lag_features(
    df: pd.DataFrame,
    target_col: str,
    lags=[1, 7, 30]
):
    """
    Add lag features to the dataframe.
    """

    data = df.copy()

    for lag in lags:
        data[f"{target_col}_lag_{lag}"] = (
            data[target_col].shift(lag)
        )

    return data