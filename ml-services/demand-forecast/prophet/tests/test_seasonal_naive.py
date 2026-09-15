import pandas as pd
import pytest

from src.seasonal_naive import (
    seasonal_naive_forecast,
)


def test_seasonal_naive_forecast():

    # ----------------------------------------
    # 12 months of historical data
    # ----------------------------------------

    dates = pd.date_range(
        start="2015-01-01",
        periods=12,
        freq="MS",
    )

    demand = list(
        range(100, 112)
    )

    df = pd.DataFrame(
        {
            "ds": dates,
            "y": demand,
        }
    )

    # ----------------------------------------
    # Forecast next 3 months
    # ----------------------------------------

    result = seasonal_naive_forecast(
        df,
        horizon_months=3,
        season_length=12,
    )

    # ----------------------------------------
    # Validate forecast count
    # ----------------------------------------

    assert len(result) == 3

    # ----------------------------------------
    # 2016-01
    # Same month previous year = 2015-01
    # ----------------------------------------

    assert result[0]["date"] == "2016-01-01"

    assert (
        result[0]["prediction"]
        == 100
    )

    # ----------------------------------------
    # 2016-02
    # Same month previous year = 2015-02
    # ----------------------------------------

    assert result[1]["date"] == "2016-02-01"

    assert (
        result[1]["prediction"]
        == 101
    )

    # ----------------------------------------
    # 2016-03
    # Same month previous year = 2015-03
    # ----------------------------------------

    assert result[2]["date"] == "2016-03-01"

    assert (
        result[2]["prediction"]
        == 102
    )


def test_empty_data_fails():

    df = pd.DataFrame(
        columns=[
            "ds",
            "y",
        ]
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):

        seasonal_naive_forecast(
            df,
            horizon_months=3,
        )


def test_insufficient_history_fails():

    dates = pd.date_range(
        start="2015-01-01",
        periods=6,
        freq="MS",
    )

    df = pd.DataFrame(
        {
            "ds": dates,
            "y": [
                100,
                200,
                300,
                400,
                500,
                600,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="Not enough history",
    ):

        seasonal_naive_forecast(
            df,
            horizon_months=3,
        )


def test_invalid_horizon_fails():

    dates = pd.date_range(
        start="2015-01-01",
        periods=12,
        freq="MS",
    )

    df = pd.DataFrame(
        {
            "ds": dates,
            "y": list(
                range(100, 112)
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="greater than 0",
    ):

        seasonal_naive_forecast(
            df,
            horizon_months=0,
        )


def test_missing_demand_fails():

    dates = pd.date_range(
        start="2015-01-01",
        periods=12,
        freq="MS",
    )

    df = pd.DataFrame(
        {
            "ds": dates,
            "y": list(
                range(100, 112)
            ),
        }
    )

    df.loc[5, "y"] = None

    with pytest.raises(
        ValueError,
        match="Missing demand values",
    ):

        seasonal_naive_forecast(
            df,
            horizon_months=3,
        )