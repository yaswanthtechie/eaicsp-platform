import holidays
import pandas as pd


def create_holiday_features(df, date_col="date"):
    df[date_col] = pd.to_datetime(df[date_col])

    years = df[date_col].dt.year.unique()
    india_holidays = holidays.India(years=years)

    df["is_holiday"] = (
        df[date_col]
        .dt.date
        .apply(lambda date: date in india_holidays)
        .astype(int)
    )

    return df
