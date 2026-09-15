import pandas as pd


def add_calendar_features(
    df: pd.DataFrame,
    date_col: str
):
    """
    Add calendar-based features to the dataframe.
    """

    data = df.copy()

    # Ensure datetime format
    data[date_col] = pd.to_datetime(data[date_col])

    # Calendar features
    data["day_of_week"] = data[date_col].dt.dayofweek
    data["month"] = data[date_col].dt.month
    data["day_of_month"] = data[date_col].dt.day


    # Boolean features converted to integers
    data["is_weekend"] = (
        data[date_col].dt.dayofweek >= 5
    ).astype(int)

    data["is_month_start"] = (
        data[date_col].dt.is_month_start
    ).astype(int)

    data["is_month_end"] = (
        data[date_col].dt.is_month_end
    ).astype(int)

    return data
