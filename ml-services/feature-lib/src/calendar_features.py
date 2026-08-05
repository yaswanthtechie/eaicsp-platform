import pandas as pd


def add_calendar_features(
    df: pd.DataFrame,
    date_col: str
):
    """
    Add calendar-based features to the dataframe.
    """

    data = df.copy()

    data[date_col] = pd.to_datetime(data[date_col])

    data["day_of_week"] = data[date_col].dt.dayofweek

    data["month"] = data[date_col].dt.month

    data["is_weekend"] = (
        data[date_col]
        .dt
        .dayofweek
        .isin([5, 6])
    )

    data["is_month_start"] = (
        data[date_col]
        .dt
        .is_month_start
    )

    data["is_month_end"] = (
        data[date_col]
        .dt
        .is_month_end
    )

    return data