import pandas as pd

from src.holiday_features import create_holiday_features


def test_indian_holidays_and_non_holiday():
    df = pd.DataFrame({
        "date": pd.to_datetime([
            "2026-01-26",  # Republic Day
            "2026-08-15",  # Independence Day
            "2026-10-02",  # Gandhi Jayanti
            "2026-01-27",  # Normal day
        ])
    })

    result = create_holiday_features(
        df,
        date_col="date"
    )

    assert result.loc[0, "is_holiday"] == 1
    assert result.loc[1, "is_holiday"] == 1
    assert result.loc[2, "is_holiday"] == 1
    assert result.loc[3, "is_holiday"] == 0


def test_holiday_features_outside_supported_year_range():
    df = pd.DataFrame({
        "date": ["1992-01-26", "2036-01-26"]
    })

    result = create_holiday_features(df)

    assert result["is_holiday"].tolist() == [0, 0]

def test_create_holiday_features_does_not_mutate_input():
    df = pd.DataFrame({"date": ["2026-01-26", "2026-01-27"]})

    create_holiday_features(df)

    assert "is_holiday" not in df.columns
    assert not pd.api.types.is_datetime64_any_dtype(df["date"])