"""
Daily XGBoost inference utilities for multi-horizon forecasting.

This module is intentionally separate from src.inference.

src.inference.py
    -> existing R5 monthly forecasting pipeline

src.multi_horizon_inference.py
    -> Task 1 daily 1/7/30/90-day forecasting
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_COLUMN = "date"
TARGET_COLUMN = "quantity_sold"

DEFAULT_LAG_DAYS = (1, 7, 30)
DEFAULT_ROLLING_MEAN_WINDOWS = (7, 30)
DEFAULT_ROLLING_STD_WINDOWS = (7,)

FEATURES = [
    "lag_1",
    "lag_7",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_30",
    "rolling_std_7",
    "is_holiday",
    "promotion",
    "weather_index",
    "day_of_week",
    "month",
    "quarter",
    "year",
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize daily history.

    Supports both:
        date, quantity_sold

    and:
        ds, y
    """

    if not isinstance(history_df, pd.DataFrame):
        raise TypeError("history_df must be a pandas DataFrame.")

    history = history_df.copy()

    # -------------------------------------------------------
    # Normalize column names
    # -------------------------------------------------------

    if "date" in history.columns and "quantity_sold" in history.columns:
        history = history.rename(
            columns={
                "date": DATE_COLUMN,
                "quantity_sold": TARGET_COLUMN,
            }
        )

    elif "ds" in history.columns and "y" in history.columns:
        history = history.rename(
            columns={
                "ds": DATE_COLUMN,
                "y": TARGET_COLUMN,
            }
        )

    else:
        raise ValueError(
            "History must contain either "
            "('date', 'quantity_sold') or "
            "('ds', 'y') columns."
        )

    # -------------------------------------------------------
    # Parse values
    # -------------------------------------------------------

    history[DATE_COLUMN] = pd.to_datetime(
        history[DATE_COLUMN],
        errors="coerce",
    )

    history[TARGET_COLUMN] = pd.to_numeric(
        history[TARGET_COLUMN],
        errors="coerce",
    )

    if history[DATE_COLUMN].isna().any():
        raise ValueError(
            "History contains invalid dates."
        )

    if history[TARGET_COLUMN].isna().any():
        raise ValueError(
            "History contains missing/non-numeric demand values."
        )

    if not np.isfinite(
        history[TARGET_COLUMN].to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "History contains non-finite demand values."
        )

    if (history[TARGET_COLUMN] < 0).any():
        raise ValueError(
            "History contains negative demand values."
        )

    # -------------------------------------------------------
    # Sort and validate duplicates
    # -------------------------------------------------------

    history = history.sort_values(
        DATE_COLUMN
    ).reset_index(drop=True)

    if history[DATE_COLUMN].duplicated().any():
        raise ValueError(
            "History contains duplicate dates."
        )

    # -------------------------------------------------------
    # Validate daily continuity
    # -------------------------------------------------------

    if len(history) < 31:
        raise ValueError(
            "At least 31 daily observations are required "
            "for lag_30 features."
        )

    expected_dates = pd.date_range(
        start=history[DATE_COLUMN].min(),
        end=history[DATE_COLUMN].max(),
        freq="D",
    )

    actual_dates = pd.DatetimeIndex(
        history[DATE_COLUMN]
    )

    if not actual_dates.equals(expected_dates):
        raise ValueError(
            "History must contain continuous daily dates."
        )

    return history[
        [DATE_COLUMN, TARGET_COLUMN]
    ].copy()

# ---------------------------------------------------------------------------
# Default regressors
# ---------------------------------------------------------------------------

def _add_default_regressors(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add deterministic placeholder regressors when they are not supplied.

    These defaults keep Task 1 inference compatible with the M5-derived
    daily dataset. Real external regressors can be introduced later in
    Track A Task 2.
    """

    result = df.copy()

    if "is_holiday" not in result.columns:
        result["is_holiday"] = (
            (result[DATE_COLUMN].dt.month.isin([11, 12]))
            | (result[DATE_COLUMN].dt.day.isin([1, 25]))
        ).astype(int)

    if "promotion" not in result.columns:
        result["promotion"] = 0

    if "weather_index" not in result.columns:
        result["weather_index"] = 0.0

    return result


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def create_daily_features(
    df: pd.DataFrame,
    drop_missing: bool = False,
) -> pd.DataFrame:
    """
    Create daily XGBoost features.

    Features:
        lag_1
        lag_7
        lag_30
        rolling_mean_7
        rolling_mean_30
        rolling_std_7
        is_holiday
        promotion
        weather_index
        day_of_week
        month
        quarter
        year
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    result = df.copy()

    if DATE_COLUMN not in result.columns:
        raise ValueError(
            f"DataFrame must contain '{DATE_COLUMN}'."
        )

    if TARGET_COLUMN not in result.columns:
        raise ValueError(
            f"DataFrame must contain '{TARGET_COLUMN}'."
        )

    result[DATE_COLUMN] = pd.to_datetime(
        result[DATE_COLUMN],
        errors="coerce",
    )

    result[TARGET_COLUMN] = pd.to_numeric(
        result[TARGET_COLUMN],
        errors="coerce",
    )

    result = result.sort_values(
        DATE_COLUMN
    ).reset_index(drop=True)

    result = _add_default_regressors(result)

    # -------------------------------------------------------
    # Lag features
    # -------------------------------------------------------

    result["lag_1"] = result[TARGET_COLUMN].shift(1)

    result["lag_7"] = result[TARGET_COLUMN].shift(7)

    result["lag_30"] = result[TARGET_COLUMN].shift(30)

    # -------------------------------------------------------
    # Rolling features
    # -------------------------------------------------------

    result["rolling_mean_7"] = (
        result[TARGET_COLUMN]
        .shift(1)
        .rolling(window=7)
        .mean()
    )

    result["rolling_mean_30"] = (
        result[TARGET_COLUMN]
        .shift(1)
        .rolling(window=30)
        .mean()
    )

    result["rolling_std_7"] = (
        result[TARGET_COLUMN]
        .shift(1)
        .rolling(window=7)
        .std()
    )

    # -------------------------------------------------------
    # Calendar features
    # -------------------------------------------------------

    result["day_of_week"] = (
        result[DATE_COLUMN].dt.dayofweek
    )

    result["month"] = (
        result[DATE_COLUMN].dt.month
    )

    result["quarter"] = (
        result[DATE_COLUMN].dt.quarter
    )

    result["year"] = (
        result[DATE_COLUMN].dt.year
    )

    # -------------------------------------------------------
    # Clean feature values
    # -------------------------------------------------------

    result = result.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if drop_missing:
        result = result.dropna(
            subset=FEATURES
        ).reset_index(drop=True)

    return result


# ---------------------------------------------------------------------------
# Model extraction
# ---------------------------------------------------------------------------

def _get_model(model_info: Any) -> Any:
    """
    Extract the actual XGBoost model from the promoted/model package.
    """

    if model_info is None:
        raise ValueError(
            "model_info cannot be None."
        )

    if isinstance(model_info, dict):
        model = model_info.get("model")

        if model is None:
            raise ValueError(
                "XGBoost model package must contain "
                "'model'."
            )

        return model

    # Allow directly passing an XGBoost estimator.
    return model_info


def _get_residual_std(model_info: Any) -> float:
    """
    Get residual standard deviation used for prediction intervals.
    """

    if isinstance(model_info, dict):
        value = model_info.get(
            "residual_std",
            0.0,
        )
    else:
        value = 0.0

    try:
        value = float(value)
    except (
        TypeError,
        ValueError,
    ):
        value = 0.0

    if not np.isfinite(value):
        value = 0.0

    return max(0.0, value)


def _get_feature_names(model_info: Any) -> list[str]:
    """
    Get the feature order stored with the XGBoost model.

    Falls back to the Task 1 feature contract when the package
    does not explicitly store feature names.
    """

    if isinstance(model_info, dict):
        features = model_info.get("features")

        if features:
            return list(features)

    return list(FEATURES)


# ---------------------------------------------------------------------------
# Single-step prediction
# ---------------------------------------------------------------------------

def _predict_single_day(
    model_info: Any,
    history_df: pd.DataFrame,
    forecast_date: pd.Timestamp,
) -> dict[str, Any]:
    """
    Predict one future day.

    Recursive forecasting is used:
    today's prediction becomes part of history for tomorrow's
    lag/rolling features.
    """

    model = _get_model(model_info)
    residual_std = _get_residual_std(model_info)
    feature_names = _get_feature_names(model_info)

    # -------------------------------------------------------
    # Add a temporary row for the date we want to predict.
    # -------------------------------------------------------

    future_row = pd.DataFrame(
        {
            DATE_COLUMN: [forecast_date],
            TARGET_COLUMN: [np.nan],
        }
    )

    combined = pd.concat(
        [history_df, future_row],
        ignore_index=True,
    )

    combined = _add_default_regressors(combined)

    # -------------------------------------------------------
    # Feature generation
    # -------------------------------------------------------

    features = create_daily_features(
        combined,
        drop_missing=False,
    )

    current_row = features[
        features[DATE_COLUMN] == forecast_date
    ]

    if current_row.empty:
        raise ValueError(
            f"Unable to create features for "
            f"{forecast_date.strftime('%Y-%m-%d')}."
        )

    # -------------------------------------------------------
    # Ensure all model features exist.
    # -------------------------------------------------------

    missing_features = [
        feature
        for feature in feature_names
        if feature not in current_row.columns
    ]

    if missing_features:
        raise ValueError(
            "Missing XGBoost features: "
            f"{missing_features}"
        )

    X = current_row[
        feature_names
    ].copy()

    # -------------------------------------------------------
    # Final feature validation.
    # -------------------------------------------------------

    if X.isna().any().any():
        missing = X.columns[
            X.isna().any()
        ].tolist()

        raise ValueError(
            "NaN values found in XGBoost "
            f"prediction features: {missing}"
        )

    X = X.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if X.isna().any().any():
        raise ValueError(
            "Non-finite values found in XGBoost "
            "prediction features."
        )

    # -------------------------------------------------------
    # Predict
    # -------------------------------------------------------

    prediction_array = model.predict(X)

    if len(prediction_array) != 1:
        raise ValueError(
            "XGBoost single-day prediction returned "
            "an unexpected number of values."
        )

    prediction = float(
        prediction_array[0]
    )

    if not np.isfinite(prediction):
        raise ValueError(
            "XGBoost returned a non-finite prediction."
        )

    prediction = max(
        0.0,
        prediction,
    )

    # -------------------------------------------------------
    # Prediction interval
    # -------------------------------------------------------

    lower = max(
        0.0,
        prediction - residual_std,
    )

    upper = max(
        prediction,
        prediction + residual_std,
    )

    return {
        "date": forecast_date.strftime(
            "%Y-%m-%d"
        ),
        "prediction": round(
            prediction,
            2,
        ),
        "lower": round(
            lower,
            2,
        ),
        "upper": round(
            upper,
            2,
        ),
    }


# ---------------------------------------------------------------------------
# Recursive multi-day forecasting
# ---------------------------------------------------------------------------

def predict_future_xgboost(
    model_info: Any,
    history_df: pd.DataFrame,
    horizon_days: int,
) -> list[dict[str, Any]]:
    """
    Recursively forecast future daily demand using XGBoost.

    Parameters
    ----------
    model_info:
        XGBoost model package. Expected structure:

        {
            "model": trained_xgb_model,
            "features": [...],
            "residual_std": float,
        }

    history_df:
        Historical daily demand with:

        date
        quantity_sold

    horizon_days:
        Number of future daily observations to generate.

    Returns
    -------
    list[dict]
        Example:

        [
            {
                "date": "2016-04-25",
                "prediction": 39123.45,
                "lower": 37000.12,
                "upper": 41246.78,
            },
            ...
        ]
    """

    # -------------------------------------------------------
    # Validate horizon
    # -------------------------------------------------------

    if not isinstance(
        horizon_days,
        (int, np.integer),
    ):
        raise TypeError(
            "horizon_days must be an integer."
        )

    horizon_days = int(
        horizon_days
    )

    if horizon_days <= 0:
        raise ValueError(
            "horizon_days must be greater than zero."
        )

    # -------------------------------------------------------
    # Validate model
    # -------------------------------------------------------

    _get_model(model_info)

    # -------------------------------------------------------
    # Validate history
    # -------------------------------------------------------

    history = _validate_history(
        history_df
    )

    # -------------------------------------------------------
    # Recursive forecasting
    # -------------------------------------------------------

    forecasts: list[dict[str, Any]] = []

    working_history = history.copy()

    last_history_date = pd.Timestamp(
        working_history[DATE_COLUMN].max()
    )

    for step in range(
        1,
        horizon_days + 1,
    ):
        forecast_date = (
            last_history_date
            + pd.Timedelta(days=step)
        )

        forecast_row = _predict_single_day(
            model_info=model_info,
            history_df=working_history,
            forecast_date=forecast_date,
        )

        forecasts.append(
            forecast_row
        )

        # ---------------------------------------------------
        # Feed prediction back into history.
        #
        # This is what makes the forecast recursive.
        # ---------------------------------------------------

        new_history_row = pd.DataFrame(
            {
                DATE_COLUMN: [
                    forecast_date
                ],
                TARGET_COLUMN: [
                    forecast_row["prediction"]
                ],
            }
        )

        working_history = pd.concat(
            [
                working_history,
                new_history_row,
            ],
            ignore_index=True,
        )

    return forecasts


# ---------------------------------------------------------------------------
# Forecast validation helper
# ---------------------------------------------------------------------------

def validate_daily_forecast(
    forecast: list[dict[str, Any]],
    expected_days: int | None = None,
) -> None:
    """
    Validate the daily XGBoost forecast output.
    """

    if not isinstance(
        forecast,
        list,
    ):
        raise TypeError(
            "forecast must be a list."
        )

    if expected_days is not None:
        if len(forecast) != expected_days:
            raise ValueError(
                "Forecast length does not match "
                f"expected_days={expected_days}. "
                f"Actual={len(forecast)}."
            )

    if not forecast:
        raise ValueError(
            "Forecast cannot be empty."
        )

    dates = pd.to_datetime(
        [
            row["date"]
            for row in forecast
        ],
        errors="coerce",
    )

    if dates.isna().any():
        raise ValueError(
            "Forecast contains invalid dates."
        )

    if dates.duplicated().any():
        raise ValueError(
            "Forecast contains duplicate dates."
        )

    if not dates.is_monotonic_increasing:
        raise ValueError(
            "Forecast dates must be increasing."
        )

    expected_dates = pd.date_range(
        start=dates.min(),
        end=dates.max(),
        freq="D",
    )

    if not dates.equals(
        expected_dates
    ):
        raise ValueError(
            "Forecast dates are not continuous daily dates."
        )

    for row in forecast:
        prediction = float(
            row["prediction"]
        )

        lower = float(
            row["lower"]
        )

        upper = float(
            row["upper"]
        )

        if not np.isfinite(
            prediction
        ):
            raise ValueError(
                "Forecast contains non-finite prediction."
            )

        if not np.isfinite(
            lower
        ):
            raise ValueError(
                "Forecast contains non-finite lower bound."
            )

        if not np.isfinite(
            upper
        ):
            raise ValueError(
                "Forecast contains non-finite upper bound."
            )

        if prediction < 0:
            raise ValueError(
                "Forecast prediction cannot be negative."
            )

        if lower < 0:
            raise ValueError(
                "Forecast lower bound cannot be negative."
            )

        if lower > prediction:
            raise ValueError(
                "Forecast lower bound cannot exceed prediction."
            )

        if upper < prediction:
            raise ValueError(
                "Forecast upper bound cannot be below prediction."
            )


# ---------------------------------------------------------------------------
# Module smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(
        "multi_horizon_inference.py loaded successfully."
    )