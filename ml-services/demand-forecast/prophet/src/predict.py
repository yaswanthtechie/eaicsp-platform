import json
import pickle

import pandas as pd

from prophet.serialize import model_from_json

from src.data import load_sales_data
from src.inference import predict_future_xgboost
from src.ensemble import (
    weighted_ensemble,
    ensemble_interval,
)


def validate_prediction_history(history: pd.DataFrame) -> None:
    """
    Validate historical data before forecasting.

    Raises ValueError with a clear message when
    the input data is invalid.
    """

    required_columns = ["ds", "y"]

    # Required columns
    for column in required_columns:
        if column not in history.columns:
            raise ValueError(
                f"Invalid input: missing required column '{column}'."
            )

    # Empty input
    if history.empty:
        raise ValueError(
            "Invalid input: history data is empty."
        )

    # Missing dates
    if history["ds"].isna().any():
        raise ValueError(
            "Invalid input: missing dates found."
        )

    # Missing demand
    if history["y"].isna().any():
        raise ValueError(
            "Invalid input: missing demand values found."
        )

    # Non-numeric demand
    if not pd.api.types.is_numeric_dtype(history["y"]):
        raise ValueError(
            "Invalid input: demand values must be numeric."
        )

    # Negative demand
    if (history["y"] < 0).any():
        raise ValueError(
            "Invalid input: negative demand values found."
        )

    # Duplicate dates
    if history["ds"].duplicated().any():
        raise ValueError(
            "Invalid input: duplicate dates found."
        )

    # Infinite values
    if not history["y"].map(
        lambda value: pd.notna(value)
        and value != float("inf")
        and value != float("-inf")
    ).all():
        raise ValueError(
            "Invalid input: demand contains infinite values."
        )


def validate_horizon(horizon_months: int) -> None:
    """
    Validate forecast horizon.
    """

    if not isinstance(horizon_months, int):
        raise ValueError(
            "horizon_months must be an integer."
        )

    if horizon_months <= 0:
        raise ValueError(
            "horizon_months must be greater than 0."
        )

    if horizon_months > 120:
        raise ValueError(
            "horizon_months cannot exceed 120."
        )


def predict(
    horizon_months: int,
    history_df: pd.DataFrame | None = None,
) -> dict:
    """
    Predict future MONTHLY demand using the
    Prophet + XGBoost ensemble.

    If history_df is provided, it is validated and used.
    Otherwise, the existing sales dataset is loaded.
    """

    # --------------------------------------------------
    # Validate horizon
    # --------------------------------------------------

    validate_horizon(horizon_months)

    # --------------------------------------------------
    # Prophet model
    # --------------------------------------------------

    with open(
        "output/prophet_model.json",
        "r",
    ) as f:
        prophet_model = model_from_json(
            f.read()
        )

    # --------------------------------------------------
    # XGBoost model
    # --------------------------------------------------

    with open(
        "models/xgb_model.pkl",
        "rb",
    ) as f:
        xgb_model = pickle.load(f)

    # --------------------------------------------------
    # Ensemble weights
    # --------------------------------------------------

    with open(
        "models/best_weights.json",
        "r",
    ) as f:
        weights = json.load(f)

    prophet_weight = weights["prophet_weight"]
    xgb_weight = weights["xgb_weight"]

    # --------------------------------------------------
    # History
    # --------------------------------------------------

    if history_df is None:

        history = load_sales_data()

        history = history.rename(
            columns={
                "date": "ds",
                "quantity_sold": "y",
            }
        )

    else:

        history = history_df.copy()

    history["ds"] = pd.to_datetime(
        history["ds"],
        errors="coerce",
    )

    # --------------------------------------------------
    # Robustness validation
    # --------------------------------------------------

    validate_prediction_history(
        history
    )

    # Sort history
    history = history.sort_values(
        "ds"
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------
    # Prophet Forecast
    # --------------------------------------------------

    future = prophet_model.make_future_dataframe(
        periods=horizon_months,
        freq="MS",
    )

    prophet_forecast = prophet_model.predict(
        future
    )

    prophet_future = prophet_forecast.tail(
        horizon_months
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------
    # XGBoost Forecast
    # --------------------------------------------------

    xgb_future = predict_future_xgboost(
        xgb_model,
        history,
        horizon_months,
    )

    # --------------------------------------------------
    # Ensemble
    # --------------------------------------------------

    forecast = []

    for i in range(horizon_months):

        prophet_row = prophet_future.iloc[i]

        xgb_row = xgb_future[i]

        prediction = weighted_ensemble(
            prophet_row["yhat"],
            xgb_row["prediction"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight,
        )

        lower, upper = ensemble_interval(
            prophet_row["yhat_lower"],
            prophet_row["yhat_upper"],
            xgb_row["lower"],
            xgb_row["upper"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight,
        )

        # --------------------------------------------------
        # Interval sanity check
        # --------------------------------------------------

        if not (
            lower <= prediction <= upper
        ):
            raise ValueError(
                "Prediction interval sanity check failed: "
                "lower <= predicted <= upper is not satisfied."
            )

        forecast.append(
            {
                "date": prophet_row[
                    "ds"
                ].strftime("%Y-%m-%d"),

                "predicted": round(
                    float(prediction),
                    2,
                ),

                "lower": round(
                    float(lower),
                    2,
                ),

                "upper": round(
                    float(upper),
                    2,
                ),
            }
        )

    return {
        "forecast": forecast
    }