"""
Daily multi-horizon forecasting.

This module contains inference only.

Training code lives in:
    src.train_multi_horizon

Prediction code must never import training code.
"""

from __future__ import annotations

import json
import pickle

import holidays
import numpy as np
import pandas as pd
from prophet.serialize import model_from_json

from src.ensemble import weighted_ensemble
from src.multi_horizon_config import (
    HORIZONS,
    INTERVALS_PATH,
    MAX_FORECAST_DAYS,
    PROPHET_MODEL_PATH,
    WEIGHTS_PATH,
    XGB_MODEL_PATH,
)
from src.multi_horizon_data import load_daily_data
from src.multi_horizon_inference import predict_future_xgboost


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROPHET_COMPONENTS = (
    "trend",
    "weekly",
    "yearly",
    # Prophet was trained with add_regressor("is_holiday"), so its
    # holiday effect is the "is_holiday" column, not "holidays".
    "is_holiday",
)

_US_HOLIDAYS = holidays.US()


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_prophet_model():
    """Load the promoted daily Prophet model."""

    if not PROPHET_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Prophet model not found: {PROPHET_MODEL_PATH}. "
            "Run: python -m src.train_multi_horizon"
        )

    with PROPHET_MODEL_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return model_from_json(f.read())


def load_xgb_model():
    """Load the promoted daily XGBoost model package."""

    if not XGB_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"XGBoost model not found: {XGB_MODEL_PATH}. "
            "Run: python -m src.train_multi_horizon"
        )

    with XGB_MODEL_PATH.open("rb") as f:
        return pickle.load(f)

def parse_ensemble_weights(weights) -> dict[str, float]:
    """
    Validate ensemble weights and return {"prophet": w, "xgb": w}.

    Accepts both formats that exist in this repo:
      - {"prophet": 0.7, "xgb": 0.3}               (this PR)
      - {"prophet_weight": 0.7, "xgb_weight": 0.3}  (written by
        automated_retraining.py when it promotes a model)
    """

    if not isinstance(weights, dict):
        raise ValueError(
            "Ensemble weights must be a dictionary."
        )

    if "prophet" in weights and "xgb" in weights:
        prophet_weight = float(weights["prophet"])
        xgb_weight = float(weights["xgb"])
    elif "prophet_weight" in weights and "xgb_weight" in weights:
        prophet_weight = float(weights["prophet_weight"])
        xgb_weight = float(weights["xgb_weight"])
    else:
        raise ValueError(
            "Ensemble weights must contain 'prophet'/'xgb' "
            "or 'prophet_weight'/'xgb_weight'."
        )

    if not (np.isfinite(prophet_weight) and np.isfinite(xgb_weight)):
        raise ValueError(
            "Ensemble weights must be finite."
        )

    if prophet_weight < 0 or xgb_weight < 0:
        raise ValueError(
            "Ensemble weights cannot be negative."
        )

    if not np.isclose(
        prophet_weight + xgb_weight,
        1.0,
        atol=1e-6,
    ):
        raise ValueError(
            "Prophet and XGBoost ensemble weights "
            "must sum to 1.0."
        )

    return {
        "prophet": prophet_weight,
        "xgb": xgb_weight,
    }


def load_ensemble_weights() -> dict[str, float]:
    """Load promoted Prophet/XGBoost ensemble weights (either format)."""

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Ensemble weights not found: {WEIGHTS_PATH}."
        )

    with WEIGHTS_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        return parse_ensemble_weights(json.load(f))

# ---------------------------------------------------------------------------
# History preparation
# ---------------------------------------------------------------------------

def prepare_history(
    history_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize history into Prophet-compatible columns.

    Accepted input:

        date, quantity_sold

    or:

        ds, y

    This function prepares and normalizes the data. Daily continuity
    validation is performed separately by validate_history().
    """

    if not isinstance(
        history_df,
        pd.DataFrame,
    ):
        raise TypeError(
            "history_df must be a pandas DataFrame."
        )

    history = history_df.copy()

    if (
        "date" in history.columns
        and "quantity_sold" in history.columns
    ):
        history = history.rename(
            columns={
                "date": "ds",
                "quantity_sold": "y",
            }
        )

    elif (
        "ds" in history.columns
        and "y" in history.columns
    ):
        history = history.copy()

    else:
        raise ValueError(
            "History must contain either "
            "('date', 'quantity_sold') or "
            "('ds', 'y') columns."
        )

    history["ds"] = pd.to_datetime(
        history["ds"],
        errors="coerce",
    )

    history["y"] = pd.to_numeric(
        history["y"],
        errors="coerce",
    )

    if history["ds"].isna().any():
        raise ValueError(
            "History contains invalid dates."
        )

    if history["y"].isna().any():
        raise ValueError(
            "History contains missing/non-numeric demand values."
        )

    if not np.isfinite(
        history["y"].to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "History contains non-finite demand values."
        )

    if (history["y"] < 0).any():
        raise ValueError(
            "History contains negative demand values."
        )

    history = (
        history.sort_values("ds")
        .reset_index(drop=True)
    )

    if history["ds"].duplicated().any():
        raise ValueError(
            "History contains duplicate dates."
        )

    if len(history) < 31:
        raise ValueError(
            "At least 31 daily observations are required "
            "for lag_30 features."
        )

    return history[
        ["ds", "y"]
    ].copy()


def validate_history(
    history_df: pd.DataFrame,
) -> None:
    """Validate the prepared Prophet history."""

    if not isinstance(
        history_df,
        pd.DataFrame,
    ):
        raise TypeError(
            "history_df must be a pandas DataFrame."
        )

    required_columns = {
        "ds",
        "y",
    }

    missing = (
        required_columns
        - set(history_df.columns)
    )

    if missing:
        raise ValueError(
            f"History missing columns: {sorted(missing)}"
        )

    if history_df.empty:
        raise ValueError(
            "History cannot be empty."
        )

    if history_df["ds"].isna().any():
        raise ValueError(
            "History contains invalid dates."
        )

    if history_df["y"].isna().any():
        raise ValueError(
            "History contains missing demand values."
        )

    if not np.isfinite(
        history_df["y"].to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "History contains non-finite demand values."
        )

    if (history_df["y"] < 0).any():
        raise ValueError(
            "History contains negative demand values."
        )

    if history_df["ds"].duplicated().any():
        raise ValueError(
            "History contains duplicate dates."
        )

    expected_dates = pd.date_range(
        start=history_df["ds"].min(),
        end=history_df["ds"].max(),
        freq="D",
    )

    actual_dates = pd.DatetimeIndex(
        history_df["ds"]
    )

    if not actual_dates.equals(
        expected_dates
    ):
        raise ValueError(
            "History must contain continuous daily dates."
        )


# ---------------------------------------------------------------------------
# Model/history compatibility
# ---------------------------------------------------------------------------

def check_history_matches_model(
    prophet_model,
    history: pd.DataFrame,
) -> None:
    """
    Ensure prediction history ends where the saved model was trained.

    This prevents silently forecasting from data newer/older than
    the saved model's training window.
    """

    trained_until = pd.Timestamp(
        prophet_model.history["ds"].max()
    )

    history_end = pd.Timestamp(
        history["ds"].max()
    )

    if history_end != trained_until:
        raise ValueError(
            f"History ends {history_end.date()} but the models "
            f"were trained up to {trained_until.date()}. "
            "Retrain (python -m src.train_multi_horizon) "
            "before forecasting from different data."
        )


# ---------------------------------------------------------------------------
# Horizon interval calibration
# ---------------------------------------------------------------------------

def load_interval_calibration() -> dict:
    """
    Load empirical horizon interval calibration produced
    by the training backtest.
    """

    if not INTERVALS_PATH.exists():
        raise FileNotFoundError(
            f"Horizon interval calibration not found: "
            f"{INTERVALS_PATH}. "
            "Run: python -m src.train_multi_horizon"
        )

    with INTERVALS_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        calibration = json.load(f)

    if not isinstance(
        calibration,
        dict,
    ):
        raise ValueError(
            "Interval calibration must be a dictionary."
        )

    if "ratio_quantiles" not in calibration:
        raise ValueError(
            "Interval calibration missing 'ratio_quantiles'."
        )

    missing = (
        set(HORIZONS)
        - set(calibration["ratio_quantiles"])
    )

    if missing:
        raise ValueError(
            "Interval calibration missing horizons: "
            f"{sorted(missing)}"
        )

    return calibration


# ---------------------------------------------------------------------------
# Prophet forecasting
# ---------------------------------------------------------------------------

def prophet_daily_forecast(
    model,
    history_df: pd.DataFrame,
    horizon_days: int,
) -> list[dict]:
    """
    Generate daily Prophet forecasts.

    Prophet was trained with `is_holiday` as a regressor.
    Therefore the same regressor must be supplied at prediction time.
    """

    if not 0 < horizon_days <= MAX_FORECAST_DAYS:
        raise ValueError(
            f"horizon_days must be between "
            f"1 and {MAX_FORECAST_DAYS}."
        )

    future_dates = pd.date_range(
        start=history_df["ds"].max()
        + pd.Timedelta(days=1),
        periods=horizon_days,
        freq="D",
    )

    future = pd.DataFrame(
        {
            "ds": future_dates,
        }
    )

    future["is_holiday"] = (
        future["ds"]
        .dt.date
        .map(
            lambda d: int(
                d in _US_HOLIDAYS
            )
        )
    )

    forecast = model.predict(
        future
    )

    return [
        {
            "date": row["ds"].strftime(
                "%Y-%m-%d"
            ),
            "prediction": max(
                0.0,
                float(row["yhat"]),
            ),
            "components": {
                name: float(row[name])
                for name in PROPHET_COMPONENTS
                if name in forecast.columns
            },
        }
        for _, row in forecast.iterrows()
    ]


# ---------------------------------------------------------------------------
# Common daily forecast path
# ---------------------------------------------------------------------------

def forecast_daily_path(
    prophet_model,
    xgb_package,
    history: pd.DataFrame,
    weights: dict[str, float],
    days: int = MAX_FORECAST_DAYS,
) -> list[dict]:
    """
    Generate one common daily forecast path.

    Every requested horizon is derived from this same daily path.
    Therefore the 1/7/30/90-day horizons cannot contradict each other.
    """

    prophet_rows = prophet_daily_forecast(
        prophet_model,
        history,
        days,
    )

    xgb_rows = predict_future_xgboost(
        model_info=xgb_package,
        history_df=history,
        horizon_days=days,
    )

    if len(prophet_rows) != len(xgb_rows):
        raise ValueError(
            "Prophet and XGBoost returned different "
            "numbers of forecast rows."
        )

    path: list[dict] = []

    for p, x in zip(
        prophet_rows,
        xgb_rows,
        strict=True,
    ):
        if p["date"] != x["date"]:
            raise ValueError(
                "Prophet and XGBoost forecast dates "
                "are not aligned."
            )

        prediction = weighted_ensemble(
            p["prediction"],
            x["prediction"],
            weights["prophet"],
            weights["xgb"],
        )

        path.append(
            {
                "date": p["date"],
                "prediction": max(
                    0.0,
                    float(prediction),
                ),
                "prophet_components": (
                    p["components"]
                ),
                "xgb_contributions": (
                    x["contributions"]
                ),
            }
        )

    return path


# ---------------------------------------------------------------------------
# Horizon reconciliation
# ---------------------------------------------------------------------------

def reconcile_horizons(
    daily_path: list[dict],
) -> dict:
    """
    Bottom-up temporal reconciliation.

    Each horizon total is calculated from the common daily path.
    """

    if len(daily_path) < MAX_FORECAST_DAYS:
        raise ValueError(
            f"Expected {MAX_FORECAST_DAYS} daily rows, "
            f"got {len(daily_path)}."
        )

    horizons: dict = {}

    for name, days in HORIZONS.items():
        rows = daily_path[:days]

        if not rows:
            raise ValueError(
                f"No daily forecast rows available for {name}."
            )

        horizons[name] = {
            "start_date": rows[0]["date"],
            "end_date": rows[-1]["date"],
            "days": days,
            "predicted": round(
                sum(
                    r["prediction"]
                    for r in rows
                ),
                2,
            ),
        }

    return horizons


# ---------------------------------------------------------------------------
# Horizon intervals
# ---------------------------------------------------------------------------

def add_intervals(
    horizons: dict,
    calibration: dict,
) -> dict:
    """
    Add empirical prediction intervals to each horizon.

    Intervals are calibrated from backtest errors.
    Daily bounds are NOT summed.
    """

    ratio_quantiles = calibration[
        "ratio_quantiles"
    ]

    interval_label = calibration.get(
        "interval_label",
        "80% empirical interval",
    )

    for name, horizon in horizons.items():
        if name not in ratio_quantiles:
            raise ValueError(
                f"Missing calibration for horizon '{name}'."
            )

        q = ratio_quantiles[name]

        low = float(q["low"])
        high = float(q["high"])

        if not np.isfinite(low):
            raise ValueError(
                f"{name}: lower calibration is not finite."
            )

        if not np.isfinite(high):
            raise ValueError(
                f"{name}: upper calibration is not finite."
            )

        if low > high:
            raise ValueError(
                f"{name}: lower calibration exceeds upper calibration."
            )

        horizon["lower"] = round(
            horizon["predicted"] * low,
            2,
        )

        horizon["upper"] = round(
            horizon["predicted"] * high,
            2,
        )

        horizon["interval"] = interval_label

    return horizons


# ---------------------------------------------------------------------------
# Horizon explanations
# ---------------------------------------------------------------------------

def explain_horizons(
    daily_path: list[dict],
    horizons: dict,
    weights: dict[str, float],
    top_n: int = 5,
) -> dict:
    """
    Calculate top drivers for every forecast horizon.

    Prophet components and XGBoost SHAP contributions are combined
    using the promoted ensemble weights.
    """

    if top_n <= 0:
        raise ValueError(
            "top_n must be greater than zero."
        )

    for name, horizon in horizons.items():
        drivers: dict[str, float] = {}

        for row in daily_path[
            :horizon["days"]
        ]:
            for key, value in row[
                "prophet_components"
            ].items():
                driver_name = (
                    f"prophet.{key}"
                )

                drivers[driver_name] = (
                    drivers.get(
                        driver_name,
                        0.0,
                    )
                    + weights["prophet"]
                    * float(value)
                )

            for key, value in row[
                "xgb_contributions"
            ].items():
                driver_name = (
                    f"xgb.{key}"
                )

                drivers[driver_name] = (
                    drivers.get(
                        driver_name,
                        0.0,
                    )
                    + weights["xgb"]
                    * float(value)
                )

        top = sorted(
            drivers.items(),
            key=lambda item: abs(
                item[1]
            ),
            reverse=True,
        )[:top_n]

        horizon["explanation"] = {
            "top_drivers": [
                {
                    "driver": key,
                    "contribution": round(
                        value,
                        2,
                    ),
                }
                for key, value in top
            ],
        }

    return horizons


# ---------------------------------------------------------------------------
# Reconciliation validation
# ---------------------------------------------------------------------------

def validate_reconciliation(
    horizons: dict,
    daily_path: list[dict],
) -> None:
    """
    Validate horizon totals and prediction intervals.

    Interval-width validation is performed before checking individual
    bounds so a shrinking interval is reported as a calibration problem.
    """

    # First validate that each horizon total matches the common path.
    for name, days in HORIZONS.items():
        if name not in horizons:
            raise ValueError(
                f"Missing horizon '{name}'."
            )

        horizon = horizons[name]

        expected = sum(
            row["prediction"]
            for row in daily_path[:days]
        )

        if not np.isclose(
            horizon["predicted"],
            expected,
            atol=0.01,
        ):
            raise ValueError(
                f"{name}: total "
                f"{horizon['predicted']} != sum of first "
                f"{days} daily forecasts "
                f"({expected:.2f})"
            )

    # Check interval widths BEFORE individual bound checks.
    widths = [
        horizons[name]["upper"]
        - horizons[name]["lower"]
        for name in HORIZONS
    ]

    if any(
        later < earlier
        for earlier, later in zip(
            widths,
            widths[1:],
        )
    ):
        raise ValueError(
            "Interval width shrinks as the horizon grows, "
            "recalibrate intervals."
        )

    # Validate individual interval bounds.
    for name in HORIZONS:
        horizon = horizons[name]

        if horizon["lower"] > horizon["upper"]:
            raise ValueError(
                f"{name}: lower bound above upper bound."
            )

        if horizon["lower"] > horizon["predicted"]:
            raise ValueError(
                f"{name}: lower bound exceeds prediction."
            )

        if horizon["upper"] < horizon["predicted"]:
            raise ValueError(
                f"{name}: upper bound below prediction."
            )


# ---------------------------------------------------------------------------
# Public prediction API
# ---------------------------------------------------------------------------

def predict(
    history_df: pd.DataFrame | None = None,
) -> dict:
    """
    Public multi-horizon prediction API.

    Loads saved models and calibration.
    Never trains models.
    """

    if history_df is None:
        history = prepare_history(
            load_daily_data()
        )
    else:
        history = prepare_history(
            history_df
        )

    validate_history(
        history
    )

    prophet_model = load_prophet_model()

    check_history_matches_model(
        prophet_model,
        history,
    )

    xgb_package = load_xgb_model()

    weights = load_ensemble_weights()

    calibration = load_interval_calibration()

    daily_path = forecast_daily_path(
        prophet_model=prophet_model,
        xgb_package=xgb_package,
        history=history,
        weights=weights,
        days=MAX_FORECAST_DAYS,
    )

    horizons = reconcile_horizons(
        daily_path
    )

    horizons = add_intervals(
        horizons,
        calibration,
    )

    explain_horizons(
        daily_path,
        horizons,
        weights,
    )

    validate_reconciliation(
        horizons,
        daily_path,
    )

    return {
        "trained_until": str(
            pd.Timestamp(
                prophet_model.history["ds"].max()
            ).date()
        ),
        "forecast": [
            {
                "date": row["date"],
                "prediction": round(
                    row["prediction"],
                    2,
                ),
            }
            for row in daily_path
        ],
        "horizons": horizons,
        "weights": weights,
    }


# ---------------------------------------------------------------------------
# Module smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = predict()

    print()
    print("=" * 60)
    print("Multi-horizon forecast")
    print("=" * 60)

    print(
        f"Trained until: "
        f"{result['trained_until']}"
    )

    print()
    print("Ensemble weights:")
    print(
        f"  Prophet: "
        f"{result['weights']['prophet']}"
    )
    print(
        f"  XGBoost: "
        f"{result['weights']['xgb']}"
    )

    print()
    print("Horizons:")

    for name, horizon in result[
        "horizons"
    ].items():
        print(
            f"  {name}: "
            f"{horizon['predicted']:.2f}"
            f" "
            f"[{horizon['lower']:.2f}, "
            f"{horizon['upper']:.2f}]"
        )

        print(
            f"    Dates: "
            f"{horizon['start_date']} "
            f"to "
            f"{horizon['end_date']}"
        )

        print(
            "    Top drivers:"
        )

        for driver in horizon[
            "explanation"
        ]["top_drivers"]:
            print(
                f"      {driver['driver']}: "
                f"{driver['contribution']:.2f}"
            )

    print()
    print(
        f"Daily forecast rows: "
        f"{len(result['forecast'])}"
    )

    print("=" * 60)