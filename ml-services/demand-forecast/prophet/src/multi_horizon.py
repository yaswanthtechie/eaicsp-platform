from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from prophet.serialize import model_from_json
from src.multi_horizon_inference import predict_future_xgboost
from src.ensemble import weighted_ensemble

from src.train_multi_horizon import (
    load_daily_data,
    train_all,
    PROPHET_MODEL_PATH,
    XGB_MODEL_PATH,
)


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

WEIGHTS_PATH = (
    PROJECT_ROOT
    / "models"
    / "promoted"
    / "ensemble_weights.json"
)

SUPPORTED_HORIZONS = (1, 7, 30, 90)
MAX_FORECAST_DAYS = 90


# ============================================================
# Model loading
# ============================================================

def load_prophet_model():
    """Load the trained daily Prophet model."""

    if not PROPHET_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Prophet model not found: {PROPHET_MODEL_PATH}"
        )

    with PROPHET_MODEL_PATH.open("r", encoding="utf-8") as f:
        model_json = json.load(f)

    return model_from_json(json.dumps(model_json))


def load_xgb_model():
    """Load the trained daily XGBoost model package."""

    if not XGB_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"XGBoost model not found: {XGB_MODEL_PATH}"
        )

    with XGB_MODEL_PATH.open("rb") as f:
        return pickle.load(f)


def load_ensemble_weights() -> dict[str, float]:
    """
    Load promoted Prophet/XGBoost ensemble weights.

    Existing promoted configuration:

        prophet_weight = 0.7
        xgb_weight = 0.3
    """

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Ensemble weights not found: {WEIGHTS_PATH}"
        )

    with WEIGHTS_PATH.open("r", encoding="utf-8") as f:
        weights = json.load(f)

    # Existing project format
    prophet_weight = float(weights["prophet_weight"])
    xgb_weight = float(weights["xgb_weight"])

    values = [
        prophet_weight,
        xgb_weight,
    ]

    # Validate finite values
    if not all(np.isfinite(value) for value in values):
        raise ValueError(
            "Ensemble weights must be finite."
        )

    # Validate non-negative values
    if any(value < 0 for value in values):
        raise ValueError(
            "Ensemble weights must be non-negative."
        )

    # Validate sum
    total = prophet_weight + xgb_weight

    if not np.isclose(total, 1.0):
        raise ValueError(
            f"Ensemble weights must sum to 1.0, got {total}"
        )

    # Return normalized internal names
    return {
        "prophet": prophet_weight,
        "xgb": xgb_weight,
    }


# ============================================================
# History preparation
# ============================================================

def prepare_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily input data into Prophet-compatible format.

    Supports both:
        date, quantity_sold

    and:
        ds, y
    """

    history = history_df.copy()

    # --------------------------------------------------------
    # Case 1: already in Prophet format
    # --------------------------------------------------------

    if {"ds", "y"}.issubset(history.columns):

        history["ds"] = pd.to_datetime(
            history["ds"],
            errors="coerce",
        )

        history["y"] = pd.to_numeric(
            history["y"],
            errors="coerce",
        )

        history = history[
            ["ds", "y"]
        ].copy()

    # --------------------------------------------------------
    # Case 2: raw daily dataset format
    # --------------------------------------------------------

    elif {"date", "quantity_sold"}.issubset(
        history.columns
    ):

        history["date"] = pd.to_datetime(
            history["date"],
            errors="coerce",
        )

        history["quantity_sold"] = pd.to_numeric(
            history["quantity_sold"],
            errors="coerce",
        )

        history = history.rename(
            columns={
                "date": "ds",
                "quantity_sold": "y",
            }
        )

        history = history[
            ["ds", "y"]
        ].copy()

    # --------------------------------------------------------
    # Invalid format
    # --------------------------------------------------------

    else:

        raise ValueError(
            "History must contain either "
            "['date', 'quantity_sold'] or "
            "['ds', 'y'] columns."
        )

    # --------------------------------------------------------
    # Validate converted values
    # --------------------------------------------------------

    if history.empty:
        raise ValueError(
            "History dataframe is empty."
        )

    if history["ds"].isna().any():
        raise ValueError(
            "History contains invalid dates."
        )

    if history["y"].isna().any():
        raise ValueError(
            "History contains missing or invalid demand values."
        )

    history = (
        history
        .sort_values("ds")
        .reset_index(drop=True)
    )

    return history

# ============================================================
# History validation
# ============================================================

def validate_history(history_df: pd.DataFrame) -> None:
    """Validate daily forecasting history."""

    required_columns = {
        "ds",
        "y",
    }

    missing = required_columns - set(history_df.columns)

    if missing:
        raise ValueError(
            f"Missing required history columns: {sorted(missing)}"
        )

    if history_df.empty:
        raise ValueError(
            "History dataframe is empty."
        )

    if history_df["ds"].isna().any():
        raise ValueError(
            "History contains missing dates."
        )

    if history_df["y"].isna().any():
        raise ValueError(
            "History contains missing demand values."
        )

    if history_df["ds"].duplicated().any():
        raise ValueError(
            "History contains duplicate dates."
        )

    if (history_df["y"] < 0).any():
        raise ValueError(
            "Demand cannot contain negative values."
        )

    if not np.isfinite(history_df["y"]).all():
        raise ValueError(
            "Demand contains non-finite values."
        )

    sorted_dates = history_df["ds"].sort_values()

    gaps = sorted_dates.diff().dropna()

    if not (gaps == pd.Timedelta(days=1)).all():
        raise ValueError(
            "History must contain continuous daily dates."
        )


# ============================================================
# Prophet daily forecast
# ============================================================

def prophet_daily_forecast(
    model,
    history_df: pd.DataFrame,
    horizon_days: int = MAX_FORECAST_DAYS,
) -> list[dict]:
    """
    Generate daily Prophet forecasts.

    A common 90-day daily path is generated first.
    Individual horizons are later derived from this same path.
    """

    if horizon_days <= 0:
        raise ValueError(
            "horizon_days must be greater than zero."
        )

    if horizon_days > MAX_FORECAST_DAYS:
        raise ValueError(
            f"horizon_days cannot exceed {MAX_FORECAST_DAYS}."
        )

    last_date = history_df["ds"].max()

    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )

    future = pd.DataFrame(
        {
            "ds": future_dates,
        }
    )

    # Same default regressors used during daily model training.
    future["is_holiday"] = (
        (future["ds"].dt.month.isin([11, 12]))
        | (future["ds"].dt.day.isin([1, 25]))
    ).astype(int)

    future["promotion"] = 0

    future["weather_index"] = 0.0

    forecast = model.predict(future)

    result = []

    for _, row in forecast.iterrows():

        prediction = max(
            0.0,
            float(row["yhat"]),
        )

        lower = max(
            0.0,
            float(row["yhat_lower"]),
        )

        upper = max(
            prediction,
            float(row["yhat_upper"]),
        )

        result.append(
            {
                "date": row["ds"].strftime("%Y-%m-%d"),
                "prediction": prediction,
                "lower": lower,
                "upper": upper,
            }
        )

    return result


# ============================================================
# Horizon reconciliation
# ============================================================

def reconcile_horizons(
    daily_forecast: list[dict],
) -> dict:
    """
    Reconcile 1/7/30/90 day horizons from one common
    daily forecast path.

    This guarantees that shorter horizons are contained
    within longer horizons.
    """

    if len(daily_forecast) < MAX_FORECAST_DAYS:
        raise ValueError(
            f"Expected at least {MAX_FORECAST_DAYS} daily "
            f"forecast rows, got {len(daily_forecast)}."
        )

    horizon_map = {
        "1_day": 1,
        "7_day": 7,
        "30_day": 30,
        "90_day": 90,
    }

    result = {}

    for horizon_name, days in horizon_map.items():

        rows = daily_forecast[:days]

        predicted = sum(
            float(row["prediction"])
            for row in rows
        )

        lower = sum(
            float(row["lower"])
            for row in rows
        )

        upper = sum(
            float(row["upper"])
            for row in rows
        )

        result[horizon_name] = {
            "start_date": rows[0]["date"],
            "end_date": rows[-1]["date"],
            "days": days,
            "predicted": round(predicted, 2),
            "lower": round(lower, 2),
            "upper": round(upper, 2),
        }

    return result


# ============================================================
# Reconciliation validation
# ============================================================

def validate_reconciliation(
    horizons: dict,
) -> None:
    """Validate that horizon totals do not contradict each other."""

    expected_order = [
        "1_day",
        "7_day",
        "30_day",
        "90_day",
    ]

    previous_prediction = None

    for horizon_name in expected_order:

        if horizon_name not in horizons:
            raise ValueError(
                f"Missing horizon: {horizon_name}"
            )

        row = horizons[horizon_name]

        predicted = float(
            row["predicted"]
        )

        lower = float(
            row["lower"]
        )

        upper = float(
            row["upper"]
        )

        # Interval sanity
        if lower > predicted:
            raise ValueError(
                f"{horizon_name}: lower > predicted"
            )

        if predicted > upper:
            raise ValueError(
                f"{horizon_name}: predicted > upper"
            )

        # Horizon totals must not decrease
        if (
            previous_prediction is not None
            and predicted < previous_prediction
        ):
            raise ValueError(
                "Horizon reconciliation failed: "
                f"{horizon_name} prediction is smaller "
                "than the previous horizon."
            )

        previous_prediction = predicted


# ============================================================
# Main multi-horizon prediction
# ============================================================

def predict_multi_horizon(
    history_df: pd.DataFrame | None = None,
    retrain: bool = False,
) -> dict:
    """
    Generate reconciled 1/7/30/90 day forecasts.

    Workflow:

        Daily history
             ↓
        Prophet daily forecast
             +
        XGBoost daily forecast
             ↓
        0.7 Prophet + 0.3 XGBoost
             ↓
        Common 90-day daily path
             ↓
        1 / 7 / 30 / 90 day totals
    """

    # --------------------------------------------------------
    # Load history
    # --------------------------------------------------------

    if history_df is None:
        history_df = load_daily_data()

    history = prepare_history(
        history_df
    )

    validate_history(
        history
    )

    # --------------------------------------------------------
    # Optional retraining
    # --------------------------------------------------------

    if retrain:
        train_all()

    # --------------------------------------------------------
    # Load models
    # --------------------------------------------------------

    prophet_model = load_prophet_model()

    xgb_model_info = load_xgb_model()

    # --------------------------------------------------------
    # Load promoted ensemble weights
    # --------------------------------------------------------

    weights = load_ensemble_weights()

    prophet_weight = weights["prophet"]
    xgb_weight = weights["xgb"]

    print(
        f"Prophet weight: {prophet_weight}"
    )

    print(
        f"XGB weight    : {xgb_weight}"
    )

    # --------------------------------------------------------
    # Generate 90-day Prophet forecast
    # --------------------------------------------------------

    prophet_forecast = prophet_daily_forecast(
        model=prophet_model,
        history_df=history,
        horizon_days=MAX_FORECAST_DAYS,
    )

    # --------------------------------------------------------
    # Generate 90-day XGBoost forecast
    # --------------------------------------------------------

    xgb_forecast = predict_future_xgboost(
        model_info=xgb_model_info,
        history_df=history,
        horizon_days=MAX_FORECAST_DAYS,
    )

    if len(prophet_forecast) != MAX_FORECAST_DAYS:
        raise ValueError(
            "Prophet forecast did not return "
            f"{MAX_FORECAST_DAYS} days."
        )

    if len(xgb_forecast) != MAX_FORECAST_DAYS:
        raise ValueError(
            "XGBoost forecast did not return "
            f"{MAX_FORECAST_DAYS} days."
        )

    # --------------------------------------------------------
    # Align Prophet and XGBoost forecasts
    # --------------------------------------------------------

    daily_forecast = []

    for prophet_row, xgb_row in zip(
        prophet_forecast,
        xgb_forecast,
    ):

        if prophet_row["date"] != xgb_row["date"]:
            raise ValueError(
                "Prophet and XGBoost forecast dates "
                "are not aligned."
            )

        prediction = weighted_ensemble(
            prophet_row["prediction"],
            xgb_row["prediction"],
            prophet_weight,
            xgb_weight,
        )

        lower = weighted_ensemble(
            prophet_row["lower"],
            xgb_row["lower"],
            prophet_weight,
            xgb_weight,
        )

        upper = weighted_ensemble(
            prophet_row["upper"],
            xgb_row["upper"],
            prophet_weight,
            xgb_weight,
        )

        prediction = max(
            0.0,
            float(prediction),
        )

        lower = max(
            0.0,
            float(lower),
        )

        upper = max(
            prediction,
            float(upper),
        )

        daily_forecast.append(
            {
                "date": prophet_row["date"],
                "prediction": prediction,
                "lower": lower,
                "upper": upper,
            }
        )

    # --------------------------------------------------------
    # Reconcile horizons
    # --------------------------------------------------------

    horizons = reconcile_horizons(
        daily_forecast
    )

    validate_reconciliation(
        horizons
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {
        "forecast": daily_forecast,
        "horizons": horizons,
        "weights": {
            "prophet": prophet_weight,
            "xgb": xgb_weight,
        },
    }


# ============================================================
# Public prediction API
# ============================================================

def predict(
    history_df: pd.DataFrame | None = None,
) -> dict:
    """Public multi-horizon prediction function."""

    return predict_multi_horizon(
        history_df=history_df,
        retrain=False,
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    result = predict()

    print()
    print("=" * 60)
    print("Multi-Horizon Forecast Results")
    print("=" * 60)

    for horizon_name, horizon in result["horizons"].items():

        print()
        print(
            f"{horizon_name}:"
        )

        print(
            f"  Start date : {horizon['start_date']}"
        )

        print(
            f"  End date   : {horizon['end_date']}"
        )

        print(
            f"  Days       : {horizon['days']}"
        )

        print(
            f"  Predicted  : {horizon['predicted']}"
        )

        print(
            f"  Lower      : {horizon['lower']}"
        )

        print(
            f"  Upper      : {horizon['upper']}"
        )

    print()
    print("=" * 60)
    print("Daily forecast rows:", len(result["forecast"]))
    print("=" * 60)