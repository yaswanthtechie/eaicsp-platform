import holidays
import pandas as pd


def create_holiday_features(df, date_col="date"):
    data = df.copy()

    data[date_col] = pd.to_datetime(data[date_col])

    years = data[date_col].dt.year.unique()

    # The holidays library supports India holidays from 2001 to 2035.
    supported_years = [
        year for year in years
        if 2001 <= year <= 2035
    ]

    india_holidays = holidays.India(years=supported_years)

    data["is_holiday"] = (
        data[date_col]
        .dt.date
        .apply(
            lambda date: (
                date in india_holidays
                if 2001 <= date.year <= 2035
                else False
            )
        )
        .astype(int)
    )

    return data