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

PROPHET_MODEL_PATH = (
    PROMOTED_DIR / "prophet_model.json"
)

XGB_MODEL_PATH = (
    PROMOTED_DIR / "xgb_model.pkl"
)

ENSEMBLE_WEIGHTS_PATH = (
    PROMOTED_DIR / "ensemble_weights.json"
)


# ============================================================
# VALIDATE HISTORY
# ============================================================

def validate_prediction_history(
    history: pd.DataFrame,
) -> None:
    """
    Validate historical data before forecasting.
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
# LOAD PROMOTED PROPHET MODEL
# ============================================================

def load_promoted_prophet_model():
    """
    Load the currently promoted Prophet model.

    File:
        models/promoted/prophet_model.json
    """

    if not PROPHET_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Promoted Prophet model not found: "
            f"{PROPHET_MODEL_PATH}"
        )

    try:
        with open(
            PROPHET_MODEL_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            model_json = file.read()

        model = model_from_json(
            model_json
        )

    except Exception as exc:
        raise RuntimeError(
            "Failed to load promoted Prophet model: "
            f"{PROPHET_MODEL_PATH}"
        ) from exc

    return model


# ============================================================
# LOAD PROMOTED XGBOOST PACKAGE
# ============================================================

def load_promoted_xgb_package():
    """
    Load the promoted XGBoost package.

    The R5 retraining pipeline stores:

        {
            "model": XGBRegressor,
            "features": FEATURES,
            "residual_std": residual_std
        }

    File:
        models/promoted/xgb_model.pkl
    """

    if not XGB_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Promoted XGBoost model not found: "
            f"{XGB_MODEL_PATH}"
        )

    try:
        with open(
            XGB_MODEL_PATH,
            "rb",
        ) as file:

            package = pickle.load(file)

    except Exception as exc:
        raise RuntimeError(
            "Failed to load promoted XGBoost model: "
            f"{XGB_MODEL_PATH}"
        ) from exc

    # --------------------------------------------------------
    # Validate package
    # --------------------------------------------------------

    if not isinstance(
        package,
        dict,
    ):
        raise ValueError(
            "Invalid promoted XGBoost artifact. "
            "Expected a dictionary package."
        )

    if "model" not in package:
        raise ValueError(
            "Invalid promoted XGBoost artifact: "
            "missing 'model'."
        )

    if "features" not in package:
        raise ValueError(
            "Invalid promoted XGBoost artifact: "
            "missing 'features'."
        )

    if "residual_std" not in package:
        raise ValueError(
            "Invalid promoted XGBoost artifact: "
            "missing 'residual_std'."
        )

    return package


# ============================================================
# LOAD PROMOTED ENSEMBLE WEIGHTS
# ============================================================

def load_promoted_ensemble_weights():
    """
    Load ensemble weights selected by R5
    automated retraining.

    File:

        models/promoted/ensemble_weights.json

    Example:

        {
            "prophet_weight": 0.3,
            "xgb_weight": 0.7
        }
    """

    if not ENSEMBLE_WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            "Promoted ensemble weights not found: "
            f"{ENSEMBLE_WEIGHTS_PATH}"
        )

    try:
        with open(
            ENSEMBLE_WEIGHTS_PATH,
            "r",
            encoding="utf-8",
        ) as file:

            weights = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid JSON in promoted ensemble weights: "
            f"{ENSEMBLE_WEIGHTS_PATH}"
        ) from exc

    # --------------------------------------------------------
    # Required keys
    # --------------------------------------------------------

    if "prophet_weight" not in weights:
        raise ValueError(
            "Promoted weights missing "
            "'prophet_weight'."
        )

    if "xgb_weight" not in weights:
        raise ValueError(
            "Promoted weights missing "
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
            "Promoted ensemble weights must be numeric."
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
    # Negative weights
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
    currently promoted Prophet + XGBoost ensemble.

    Promoted artifacts:

        models/promoted/
            prophet_model.json
            xgb_model.pkl
            ensemble_weights.json

    The prediction service does NOT use:

        models/best_weights.json
        output/prophet_model.json
        models/xgb_model.pkl
    """

    # ========================================================
    # 1. Validate Horizon
    # ========================================================

    validate_horizon(
        horizon_months
    )

    # ========================================================
    # 2. Load Promoted Prophet
    # ========================================================

    prophet_model = (
        load_promoted_prophet_model()
    )

    # ========================================================
    # 3. Load Promoted XGBoost Package
    # ========================================================

    # IMPORTANT:
    #
    # R5 saves the COMPLETE XGBoost package:
    #
    # {
    #     "model": XGBRegressor,
    #     "features": [...],
    #     "residual_std": ...
    # }
    #
    # predict_future_xgboost() expects this
    # complete dictionary package.
    #
    # DO NOT extract xgb_package["model"] here.

    xgb_package = (
        load_promoted_xgb_package()
    )

    # ========================================================
    # 4. Load Promoted Ensemble Weights
    # ========================================================

    (
        prophet_weight,
        xgb_weight,
    ) = load_promoted_ensemble_weights()

    print(
        "\nUsing promoted ensemble:"
    )

    print(
        f"Prophet weight : {prophet_weight}"
    )

    print(
        f"XGBoost weight : {xgb_weight}"
    )

    # ========================================================
    # 5. Load History
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
    # 6. Convert Date
    # ========================================================

    history["ds"] = pd.to_datetime(
        history["ds"],
        errors="coerce",
    )

    # ========================================================
    # 7. Validate History
    # ========================================================

    validate_prediction_history(
        history
    )

    # ========================================================
    # 8. Sort History
    # ========================================================

    history = (
        history
        .sort_values("ds")
        .reset_index(drop=True)
    )

    # ========================================================
    # 9. Prophet Future Forecast
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
    # 10. XGBoost Future Forecast
    # ========================================================

    # IMPORTANT:
    # Pass the COMPLETE package, not only the raw model.

    xgb_future = (
        predict_future_xgboost(
            xgb_package,
            history,
            horizon_months,
        )
    )

    # ========================================================
    # 11. Validate Forecast Length
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
        # Ensemble Prediction
        # ----------------------------------------------------

        prediction = weighted_ensemble(
            prophet_row["yhat"],
            xgb_row["prediction"],
            prophet_weight=prophet_weight,
            xgb_weight=xgb_weight,
        )

        # ----------------------------------------------------
        # Ensemble Prediction Interval
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
        # Finite Validation
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
        # Interval Validation
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
        # Add Forecast
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