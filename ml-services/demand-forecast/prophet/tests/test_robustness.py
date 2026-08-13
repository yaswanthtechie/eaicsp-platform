import numpy as np
import pandas as pd
import pytest

from src.predict import predict


def valid_history():

    dates = pd.date_range(
        start="1992-01-01",
        periods=60,
        freq="MS",
    )

    return pd.DataFrame(
        {
            "ds": dates,
            "y": np.random.randint(
                100,
                1000,
                size=60,
            ).astype(float),
        }
    )


def test_missing_demand_fails_gracefully():

    history = valid_history()

    history.loc[10, "y"] = np.nan

    with pytest.raises(
        ValueError,
        match="missing demand values",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_negative_demand_fails_gracefully():

    history = valid_history()

    history.loc[10, "y"] = -500

    with pytest.raises(
        ValueError,
        match="negative demand",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_missing_date_fails_gracefully():

    history = valid_history()

    history.loc[10, "ds"] = pd.NaT

    with pytest.raises(
        ValueError,
        match="missing dates",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_duplicate_dates_fail_gracefully():

    history = valid_history()

    history.loc[10, "ds"] = history.loc[9, "ds"]

    with pytest.raises(
        ValueError,
        match="duplicate dates",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_non_numeric_demand_fails_gracefully():

    history = valid_history()

    # Convert column to object before inserting string
    # to avoid pandas FutureWarning.
    history["y"] = history["y"].astype(object)

    history.loc[10, "y"] = "invalid"

    with pytest.raises(
        ValueError,
        match="demand values must be numeric",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_empty_history_fails_gracefully():

    history = pd.DataFrame(
        columns=["ds", "y"]
    )

    with pytest.raises(
        ValueError,
        match="history data is empty",
    ):
        predict(
            horizon_months=3,
            history_df=history,
        )


def test_invalid_horizon_fails_gracefully():

    history = valid_history()

    with pytest.raises(
        ValueError,
        match="greater than 0",
    ):
        predict(
            horizon_months=0,
            history_df=history,
        )


def test_prediction_interval_is_valid():

    history = valid_history()

    result = predict(
        horizon_months=3,
        history_df=history,
    )

    assert len(
        result["forecast"]
    ) == 3

    for row in result["forecast"]:

        assert (
            row["lower"]
            <= row["predicted"]
            <= row["upper"]
        )