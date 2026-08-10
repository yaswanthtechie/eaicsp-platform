import pickle
import json
import pandas as pd

from prophet.serialize import model_from_json

from src.data import load_sales_data
from src.train_xgboost import predict_future_xgboost
from src.ensemble import (
    weighted_ensemble,
    ensemble_interval
)


def predict(horizon_months: int) -> dict:
    """
    Predict future MONTHLY demand using the
    best Prophet + XGBoost ensemble.
    """

    # -------------------------
    # Prophet
    # -------------------------

    with open("output/prophet_model.json", "r") as f:
        prophet_model = model_from_json(f.read())

    # -------------------------
    # XGBoost
    # -------------------------

    with open("models/xgb_model.pkl", "rb") as f:
        xgb_model = pickle.load(f)

    # -------------------------
    # Best Weights
    # -------------------------

    with open("models/best_weights.json", "r") as f:
        weights = json.load(f)

    prophet_weight = weights["prophet_weight"]
    xgb_weight = weights["xgb_weight"]

    # -------------------------
    # History
    # -------------------------

    history = load_sales_data()

    history = history.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y"
        }
    )

    history["ds"] = pd.to_datetime(history["ds"])

    # -------------------------
    # Prophet Forecast
    # -------------------------

    future = prophet_model.make_future_dataframe(
        periods=horizon_months,
        freq="MS"
    )

    prophet_forecast = prophet_model.predict(future)

    prophet_future = prophet_forecast.tail(
        horizon_months
    ).reset_index(drop=True)

    # -------------------------
    # XGBoost Forecast
    # -------------------------

    xgb_future = predict_future_xgboost(
        xgb_model,
        history,
        horizon_months
    )

    # -------------------------
    # Ensemble
    # -------------------------

    forecast = []

    for i in range(horizon_months):

        prophet_row = prophet_future.iloc[i]

        xgb_row = xgb_future[i]

        prediction = weighted_ensemble(
            prophet_row["yhat"],
            xgb_row["prediction"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight
        )

        lower, upper = ensemble_interval(
            prophet_row["yhat_lower"],
            prophet_row["yhat_upper"],
            xgb_row["lower"],
            xgb_row["upper"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight
        )

        forecast.append({
            "date": prophet_row["ds"].strftime("%Y-%m-%d"),
            "predicted": round(float(prediction), 2),
            "lower": round(float(lower), 2),
            "upper": round(float(upper), 2)
        })

    return {
        "forecast": forecast
    }