from .lag_features import add_lag_features
from .rolling_features import add_rolling_features
from .calendar_features import add_calendar_features


def build_all_features(
    df,
    date_col,
    target_col
):
    """
    Build all feature engineering features.
    """

    data = df.copy()

    # Ensure data is sorted by date
    data = data.sort_values(date_col).reset_index(drop=True)

    data = add_lag_features(
        data,
        target_col
    )

    data = add_rolling_features(
        data,
        target_col
    )

    data = add_calendar_features(
        data,
        date_col
    )

    return data