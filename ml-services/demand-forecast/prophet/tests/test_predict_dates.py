import pandas as pd
import pytest

from src.data import load_sales_data
from src.external_regressors import add_external_regressors
from src.predict import predict, validate_forecast_dates


def test_forecast_starts_after_the_last_history_date():
    """
    Regression test: predict() previously built future dates from the
    Prophet model's own training history (ending 2013-01) and served
    forecasts three years in the past.
    """
    history = load_sales_data()
    date_col = "ds" if "ds" in history.columns else "date"
    last_actual = pd.to_datetime(history[date_col]).max()

    result = predict(horizon_months=3)
    dates = [pd.to_datetime(row["date"]) for row in result["forecast"]]

    assert len(dates) == 3
    assert dates[0] > last_actual
    assert dates == sorted(dates)


def test_validate_forecast_dates_rejects_mismatched_months():
    prophet_future = pd.DataFrame({
        "ds": pd.to_datetime(["2016-06-01", "2016-07-01"])
    })
    xgb_future = [{"date": "2013-02-01"}, {"date": "2013-03-01"}]

    with pytest.raises(ValueError, match="do not match"):
        validate_forecast_dates(prophet_future, xgb_future)


def test_validate_forecast_dates_rejects_length_mismatch():
    prophet_future = pd.DataFrame({
        "ds": pd.to_datetime(["2016-06-01", "2016-07-01"])
    })

    with pytest.raises(ValueError, match="lengths"):
        validate_forecast_dates(prophet_future, [{"date": "2016-06-01"}])


def test_validate_forecast_dates_accepts_matching_dates():
    prophet_future = pd.DataFrame({
        "ds": pd.to_datetime(["2016-06-01", "2016-07-01"])
    })
    xgb_future = [{"date": "2016-06-01"}, {"date": "2016-07-01"}]

    validate_forecast_dates(prophet_future, xgb_future)  # must not raise


def test_weather_feature_is_reproducible():
    """
    The mock weather regressor must be deterministic, or training runs
    and served forecasts cannot be reproduced.
    """
    frame = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=5, freq="MS")
    })

    first = add_external_regressors(frame.copy())["weather_index"].tolist()
    second = add_external_regressors(frame.copy())["weather_index"].tolist()

    assert first == second