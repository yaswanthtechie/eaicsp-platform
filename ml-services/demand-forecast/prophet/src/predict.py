import json
import math
import pickle
from pathlib import Path

import pandas as pd
from prophet.serialize import model_from_json

from src.data import load_sales_data
from src.inference import predict_future_xgboost
from src.ensemble import (
    weighted_ensemble,
    ensemble_interval,
)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROMOTED_DIR = (
    PROJECT_ROOT / "models" / "promoted"
)

# R5 promoted artifacts
PROMOTED_PROPHET_MODEL_PATH = (
    PROMOTED_DIR / "prophet_model.json"
)

PROMOTED_XGB_MODEL_PATH = (
    PROMOTED_DIR / "xgb_model.pkl"
)

PROMOTED_WEIGHTS_PATH = (
    PROMOTED_DIR / "ensemble_weights.json"
)

# Legacy / fallback artifacts
FALLBACK_PROPHET_MODEL_PATH = (
    PROJECT_ROOT / "output" / "prophet_model.json"
)

FALLBACK_XGB_MODEL_PATH = (
    PROJECT_ROOT / "models" / "xgb_model.pkl"
)

FALLBACK_WEIGHTS_PATH = (
    PROJECT_ROOT / "models" / "best_weights.json"
)


# ============================================================
# VALIDATE HISTORY
# ============================================================

def validate_prediction_history(
    history: pd.DataFrame,
) -> None:
    """
    Validate historical data before forecasting.

    Raises ValueError with a clear message when
    the input data is invalid.
    """

    required_columns = ["ds", "y"]

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    for column in required_columns:

        if column not in history.columns:

            raise ValueError(
                f"Invalid input: missing required column "
                f"'{column}'."
            )

    # --------------------------------------------------------
    # Empty input
    # --------------------------------------------------------

    if history.empty:

        raise ValueError(
            "Invalid input: history data is empty."
        )

    # --------------------------------------------------------
    # Missing dates
    # --------------------------------------------------------

    if history["ds"].isna().any():

        raise ValueError(
            "Invalid input: missing dates found."
        )

    # --------------------------------------------------------
    # Missing demand
    # --------------------------------------------------------

    if history["y"].isna().any():

        raise ValueError(
            "Invalid input: missing demand values found."
        )

    # --------------------------------------------------------
    # Numeric demand
    # --------------------------------------------------------

    if not pd.api.types.is_numeric_dtype(
        history["y"]
    ):

        raise ValueError(
            "Invalid input: demand values must be numeric."
        )

    # --------------------------------------------------------
    # Negative demand
    # --------------------------------------------------------

    if (history["y"] < 0).any():

        raise ValueError(
            "Invalid input: negative demand values found."
        )

    # --------------------------------------------------------
    # Duplicate dates
    # --------------------------------------------------------

    if history["ds"].duplicated().any():

        raise ValueError(
            "Invalid input: duplicate dates found."
        )

    # --------------------------------------------------------
    # Infinite values
    # --------------------------------------------------------

    if not history["y"].map(
        lambda value: (
            pd.notna(value)
            and math.isfinite(float(value))
        )
    ).all():

        raise ValueError(
            "Invalid input: demand contains "
            "infinite values."
        )


# ============================================================
# VALIDATE HORIZON
# ============================================================

def validate_horizon(
    horizon_months: int,
) -> None:
    """
    Validate forecast horizon.
    """

    if not isinstance(
        horizon_months,
        int,
    ):

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


# ============================================================
# LOAD PROPHET MODEL
# ============================================================

def load_prophet_model():
    """
    Load Prophet model.

    Priority:

        1. models/promoted/prophet_model.json
        2. output/prophet_model.json

    The promoted model is preferred for production.
    The output model is used as a fallback so that
    clean checkouts and tests do not fail when promoted
    artifacts are not committed.
    """

    if PROMOTED_PROPHET_MODEL_PATH.exists():

        model_path = PROMOTED_PROPHET_MODEL_PATH

        print(
            "\nUsing promoted Prophet model:"
        )

    elif FALLBACK_PROPHET_MODEL_PATH.exists():

        model_path = FALLBACK_PROPHET_MODEL_PATH

        print(
            "\nPromoted Prophet model not found."
        )

        print(
            "Using fallback Prophet model:"
        )

    else:

        raise FileNotFoundError(
            "No Prophet model found. Checked:\n"
            f"- {PROMOTED_PROPHET_MODEL_PATH}\n"
            f"- {FALLBACK_PROPHET_MODEL_PATH}"
        )

    try:

        with open(
            model_path,
            "r",
            encoding="utf-8",
        ) as file:

            model_json = file.read()

        model = model_from_json(
            model_json
        )

    except Exception as exc:

        raise RuntimeError(
            "Failed to load Prophet model: "
            f"{model_path}"
        ) from exc

    return model


# ============================================================
# LOAD XGBOOST MODEL
# ============================================================

def load_xgb_package():
    """
    Load XGBoost model.

    Priority:

        1. models/promoted/xgb_model.pkl
        2. models/xgb_model.pkl

    R5 promoted artifact is expected to be a dictionary:

        {
            "model": XGBRegressor,
            "features": [...],
            "residual_std": ...
        }

    The fallback artifact may be the older raw XGBoost
    model. In that case it is wrapped into a compatible
    package.
    """

    if PROMOTED_XGB_MODEL_PATH.exists():

        model_path = PROMOTED_XGB_MODEL_PATH

        print(
            "Using promoted XGBoost model:"
        )

    elif FALLBACK_XGB_MODEL_PATH.exists():

        model_path = FALLBACK_XGB_MODEL_PATH

        print(
            "Promoted XGBoost model not found."
        )

        print(
            "Using fallback XGBoost model:"
        )

    else:

        raise FileNotFoundError(
            "No XGBoost model found. Checked:\n"
            f"- {PROMOTED_XGB_MODEL_PATH}\n"
            f"- {FALLBACK_XGB_MODEL_PATH}"
        )

    try:

        with open(
            model_path,
            "rb",
        ) as file:

            package = pickle.load(file)

    except Exception as exc:

        raise RuntimeError(
            "Failed to load XGBoost model: "
            f"{model_path}"
        ) from exc

    # --------------------------------------------------------
    # R5 promoted package
    # --------------------------------------------------------

    if isinstance(
        package,
        dict,
    ):

        if "model" not in package:

            raise ValueError(
                "Invalid XGBoost artifact: "
                "missing 'model'."
            )

        if "features" not in package:

            raise ValueError(
                "Invalid XGBoost artifact: "
                "missing 'features'."
            )

        if "residual_std" not in package:

            raise ValueError(
                "Invalid XGBoost artifact: "
                "missing 'residual_std'."
            )

        return package

    # --------------------------------------------------------
    # Legacy raw XGBoost model
    # --------------------------------------------------------

    print(
        "Legacy raw XGBoost model detected."
    )

    return {
        "model": package,
        "features": None,
        "residual_std": 0.0,
    }


# ============================================================
# LOAD ENSEMBLE WEIGHTS
# ============================================================

def load_ensemble_weights():
    """
    Load ensemble weights.

    Priority:

        1. models/promoted/ensemble_weights.json
        2. models/best_weights.json
    """

    if PROMOTED_WEIGHTS_PATH.exists():

        weights_path = PROMOTED_WEIGHTS_PATH

        print(
            "Using promoted ensemble weights:"
        )

    elif FALLBACK_WEIGHTS_PATH.exists():

        weights_path = FALLBACK_WEIGHTS_PATH

        print(
            "Promoted ensemble weights not found."
        )

        print(
            "Using fallback ensemble weights:"
        )

    else:

        raise FileNotFoundError(
            "No ensemble weights found. Checked:\n"
            f"- {PROMOTED_WEIGHTS_PATH}\n"
            f"- {FALLBACK_WEIGHTS_PATH}"
        )

    try:

        with open(
            weights_path,
            "r",
            encoding="utf-8",
        ) as file:

            weights = json.load(file)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Invalid JSON in ensemble weights: "
            f"{weights_path}"
        ) from exc

    # --------------------------------------------------------
    # Required keys
    # --------------------------------------------------------

    if "prophet_weight" not in weights:

        raise ValueError(
            "Ensemble weights missing "
            "'prophet_weight'."
        )

    if "xgb_weight" not in weights:

        raise ValueError(
            "Ensemble weights missing "
            "'xgb_weight'."
        )

    # --------------------------------------------------------
    # Convert to float
    # --------------------------------------------------------

    try:

        prophet_weight = float(
            weights["prophet_weight"]
        )

        xgb_weight = float(
            weights["xgb_weight"]
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            "Ensemble weights must be numeric."
        ) from exc

    # --------------------------------------------------------
    # Finite values
    # --------------------------------------------------------

    if not math.isfinite(
        prophet_weight
    ):

        raise ValueError(
            "Prophet weight must be finite."
        )

    if not math.isfinite(
        xgb_weight
    ):

        raise ValueError(
            "XGBoost weight must be finite."
        )

    # --------------------------------------------------------
    # Negative values
    # --------------------------------------------------------

    if prophet_weight < 0:

        raise ValueError(
            "Prophet weight cannot be negative."
        )

    if xgb_weight < 0:

        raise ValueError(
            "XGBoost weight cannot be negative."
        )

    # --------------------------------------------------------
    # Sum validation
    # --------------------------------------------------------

    if not math.isclose(
        prophet_weight + xgb_weight,
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):

        raise ValueError(
            "Ensemble weights must sum to 1. "
            f"Received: "
            f"{prophet_weight} + {xgb_weight} = "
            f"{prophet_weight + xgb_weight}"
        )

    return (
        prophet_weight,
        xgb_weight,
    )


# ============================================================
# PREDICT
# ============================================================

def predict(
    horizon_months: int,
    history_df: pd.DataFrame | None = None,
) -> dict:
    """
    Predict future MONTHLY demand using the
    currently available Prophet + XGBoost ensemble.

    Model priority:

        Promoted R5 models
                ↓
        Legacy fallback models

    IMPORTANT:
    Input history is validated BEFORE model loading.
    This guarantees that invalid input raises the expected
    ValueError even when promoted model artifacts are absent.
    """

    # ========================================================
    # 1. Validate Horizon
    # ========================================================

    validate_horizon(
        horizon_months
    )

    # ========================================================
    # 2. Load History
    # ========================================================

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

    # ========================================================
    # 3. Convert Date
    # ========================================================

    if "ds" in history.columns:

        history["ds"] = pd.to_datetime(
            history["ds"],
            errors="coerce",
        )

    # ========================================================
    # 4. Validate History BEFORE Models
    # ========================================================

    validate_prediction_history(
        history
    )

    # ========================================================
    # 5. Sort History
    # ========================================================

    history = (
        history
        .sort_values("ds")
        .reset_index(drop=True)
    )

    # ========================================================
    # 6. Load Prophet
    # ========================================================

    prophet_model = (
        load_prophet_model()
    )

    # ========================================================
    # 7. Load XGBoost
    # ========================================================

    xgb_package = (
        load_xgb_package()
    )

    # ========================================================
    # 8. Load Ensemble Weights
    # ========================================================

    (
        prophet_weight,
        xgb_weight,
    ) = load_ensemble_weights()

    print(
        "\nUsing ensemble:"
    )

    print(
        f"Prophet weight : {prophet_weight}"
    )

    print(
        f"XGBoost weight : {xgb_weight}"
    )

    # ========================================================
    # 9. Prophet Forecast
    # ========================================================

    future = (
        prophet_model.make_future_dataframe(
            periods=horizon_months,
            freq="MS",
        )
    )

    prophet_forecast = (
        prophet_model.predict(
            future
        )
    )

    prophet_future = (
        prophet_forecast
        .tail(horizon_months)
        .reset_index(drop=True)
    )

    # ========================================================
    # 10. XGBoost Forecast
    # ========================================================

    xgb_future = (
        predict_future_xgboost(
            xgb_package,
            history,
            horizon_months,
        )
    )

    # ========================================================
    # 11. Forecast Length Validation
    # ========================================================

    if len(prophet_future) != horizon_months:

        raise ValueError(
            "Prophet forecast length mismatch. "
            f"Expected {horizon_months}, "
            f"received {len(prophet_future)}."
        )

    if len(xgb_future) != horizon_months:

        raise ValueError(
            "XGBoost forecast length mismatch. "
            f"Expected {horizon_months}, "
            f"received {len(xgb_future)}."
        )

    # ========================================================
    # 12. Ensemble Forecast
    # ========================================================

    forecast = []

    for i in range(
        horizon_months
    ):

        prophet_row = (
            prophet_future.iloc[i]
        )

        xgb_row = (
            xgb_future[i]
        )

        # ----------------------------------------------------
        # Ensemble prediction
        # ----------------------------------------------------

        prediction = weighted_ensemble(
            prophet_row["yhat"],
            xgb_row["prediction"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight,
        )

        # ----------------------------------------------------
        # Prediction interval
        # ----------------------------------------------------

        lower, upper = ensemble_interval(
            prophet_row["yhat_lower"],
            prophet_row["yhat_upper"],
            xgb_row["lower"],
            xgb_row["upper"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight,
        )

        # ----------------------------------------------------
        # Convert to float
        # ----------------------------------------------------

        prediction = float(
            prediction
        )

        lower = float(
            lower
        )

        upper = float(
            upper
        )

        # ----------------------------------------------------
        # Finite validation
        # ----------------------------------------------------

        if not math.isfinite(
            prediction
        ):

            raise ValueError(
                "Predicted value is not finite."
            )

        if not math.isfinite(
            lower
        ):

            raise ValueError(
                "Lower prediction bound is not finite."
            )

        if not math.isfinite(
            upper
        ):

            raise ValueError(
                "Upper prediction bound is not finite."
            )

        # ----------------------------------------------------
        # Interval validation
        # ----------------------------------------------------

        if lower > upper:

            raise ValueError(
                "Prediction interval invalid: "
                "lower bound is greater than upper bound."
            )

        if not (
            lower
            <= prediction
            <= upper
        ):

            raise ValueError(
                "Prediction interval sanity check failed: "
                "lower <= predicted <= upper "
                "is not satisfied."
            )

        # ----------------------------------------------------
        # Add forecast
        # ----------------------------------------------------

        forecast.append(
            {
                "date": prophet_row[
                    "ds"
                ].strftime(
                    "%Y-%m-%d"
                ),

                "predicted": round(
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
        )

    # ========================================================
    # 13. Return
    # ========================================================

    return {
        "forecast": forecast
    }