import os
import pickle
import math

import mlflow
import mlflow.prophet
import mlflow.xgboost

import numpy as np
import pandas as pd

from prophet import Prophet
from prophet.serialize import model_to_json
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error

from data import load_sales_data
from train_xgboost import create_features


# ============================================================
# CONFIGURATION
# ============================================================

WINDOW_MONTHS = 120
VALIDATION_MONTHS = 12

# Dataset is monthly
DATA_FREQUENCY = "MS"

# Retraining happens once per year
RETRAIN_FREQUENCY = "YS"

EXPERIMENT_NAME = "R4_Automated_Retraining"

PROMOTED_DIR = "models/promoted"

MODEL_VERSION = "R4"


# ============================================================
# ENSEMBLE WEIGHTS
# ============================================================

PROPHET_WEIGHT = 0.3
XGB_WEIGHT = 0.7


# ============================================================
# XGBOOST CONFIGURATION
# ============================================================

FEATURES = [
    "lag_1",
    "lag_7",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_30",
    "rolling_std_7",
    "is_holiday",
    "day_of_week",
    "month",
    "quarter",
    "year",
]

XGB_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.03,
    "max_depth": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "reg:squarederror",
    "random_state": 42,
}


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_data():

    df = load_sales_data()

    df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y",
        }
    )

    required_columns = ["ds", "y"]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df["ds"] = pd.to_datetime(df["ds"])

    df = (
        df
        .sort_values("ds")
        .drop_duplicates(subset=["ds"])
        .reset_index(drop=True)
    )

    if df.empty:
        raise ValueError("Dataset is empty.")

    if df["y"].isnull().any():
        raise ValueError(
            "Target column contains missing values."
        )

    if (df["y"] < 0).any():
        raise ValueError(
            "Target column contains negative values."
        )

    print("\nDataset prepared successfully.")

    print(
        "Date range:",
        df["ds"].min(),
        "to",
        df["ds"].max()
    )

    print(
        "Total rows:",
        len(df)
    )

    return df


# ============================================================
# MAPE
# ============================================================

def calculate_mape(actual, predicted):

    actual = np.asarray(
        actual,
        dtype=float
    )

    predicted = np.asarray(
        predicted,
        dtype=float
    )

    mask = actual != 0

    if not np.any(mask):
        return float("inf")

    return float(
        np.mean(
            np.abs(
                (
                    actual[mask]
                    - predicted[mask]
                )
                / actual[mask]
            )
        )
        * 100
    )


# ============================================================
# PROPHET
# ============================================================

def train_prophet_model(train_df):

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    model.fit(
        train_df[["ds", "y"]]
    )

    return model


# ============================================================
# XGBOOST
# ============================================================

def train_xgb_model(train_df):

    feature_df = create_features(
        train_df.copy(),
        drop_missing=True,
    )

    if feature_df.empty:
        raise ValueError(
            "Not enough data to create XGBoost features."
        )

    X_train = feature_df[FEATURES]

    y_train = feature_df["y"]

    model = XGBRegressor(
        **XGB_PARAMS
    )

    model.fit(
        X_train,
        y_train
    )

    # Training residuals
    train_predictions = model.predict(
        X_train
    )

    residuals = (
        y_train.to_numpy()
        - train_predictions
    )

    residual_std = float(
        np.std(residuals)
    )

    return model, residual_std


# ============================================================
# XGBOOST VALIDATION
# ============================================================

def predict_xgb_validation(
    xgb_model,
    train_df,
    validation_df,
):

    combined = pd.concat(
        [
            train_df,
            validation_df,
        ],
        ignore_index=True,
    )

    combined = (
        combined
        .sort_values("ds")
        .reset_index(drop=True)
    )

    feature_df = create_features(
        combined,
        drop_missing=True,
    )

    validation_dates = set(
        validation_df["ds"]
    )

    validation_features = feature_df[
        feature_df["ds"].isin(
            validation_dates
        )
    ].copy()

    if len(validation_features) != len(
        validation_df
    ):
        raise ValueError(
            "Could not create XGBoost "
            "features for all validation dates."
        )

    return xgb_model.predict(
        validation_features[FEATURES]
    )


# ============================================================
# ENSEMBLE
# ============================================================

def create_ensemble_prediction(
    prophet_prediction,
    xgb_prediction,
):

    if (
        PROPHET_WEIGHT < 0
        or XGB_WEIGHT < 0
    ):
        raise ValueError(
            "Ensemble weights cannot be negative."
        )

    if not math.isclose(
        PROPHET_WEIGHT + XGB_WEIGHT,
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "Ensemble weights must sum to 1."
        )

    return (
        PROPHET_WEIGHT * prophet_prediction
        +
        XGB_WEIGHT * xgb_prediction
    )


# ============================================================
# TRAIN + EVALUATE
# ============================================================

def train_and_evaluate(
    train_df,
    validation_df,
):

    print(
        "\n----------------------------------------"
    )

    print(
        "Training candidate model"
    )

    print(
        "----------------------------------------"
    )

    # --------------------------------------------------------
    # Prophet
    # --------------------------------------------------------

    prophet_model = train_prophet_model(
        train_df
    )

    prophet_forecast = prophet_model.predict(
        validation_df[["ds"]]
    )

    prophet_prediction = (
        prophet_forecast["yhat"]
        .to_numpy()
    )

    # --------------------------------------------------------
    # XGBoost
    # --------------------------------------------------------

    xgb_model, residual_std = (
        train_xgb_model(
            train_df
        )
    )

    xgb_prediction = (
        predict_xgb_validation(
            xgb_model,
            train_df,
            validation_df,
        )
    )

    # --------------------------------------------------------
    # Ensemble
    # --------------------------------------------------------

    ensemble_prediction = (
        create_ensemble_prediction(
            prophet_prediction,
            xgb_prediction,
        )
    )

    actual = (
        validation_df["y"]
        .to_numpy()
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    mape = calculate_mape(
        actual,
        ensemble_prediction,
    )

    rmse = float(
        np.sqrt(
            mean_squared_error(
                actual,
                ensemble_prediction,
            )
        )
    )

    print(
        f"MAPE: {mape:.4f}%"
    )

    print(
        f"RMSE: {rmse:.4f}"
    )

    return {
        "prophet_model": prophet_model,
        "xgb_model": xgb_model,
        "residual_std": residual_std,
        "prophet_weight": PROPHET_WEIGHT,
        "xgb_weight": XGB_WEIGHT,
        "mape": mape,
        "rmse": rmse,
    }


# ============================================================
# PROMOTION DECISION
# ============================================================

def is_better_model(
    new_mape,
    new_rmse,
    old_mape,
    old_rmse,
):

    if old_mape == float("inf"):
        return True

    # Primary metric
    if new_mape < old_mape:
        return True

    # RMSE tie breaker
    if math.isclose(
        new_mape,
        old_mape,
        rel_tol=1e-6,
        abs_tol=1e-6,
    ):
        return new_rmse < old_rmse

    return False


# ============================================================
# SAVE PROMOTED MODEL
# ============================================================

def promote_model(candidate):

    os.makedirs(
        PROMOTED_DIR,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Prophet
    # --------------------------------------------------------

    prophet_path = os.path.join(
        PROMOTED_DIR,
        "prophet_model.json",
    )

    with open(
        prophet_path,
        "w",
    ) as file:

        file.write(
            model_to_json(
                candidate["prophet_model"]
            )
        )

    # --------------------------------------------------------
    # XGBoost
    # --------------------------------------------------------

    xgb_path = os.path.join(
        PROMOTED_DIR,
        "xgb_model.pkl",
    )

    xgb_package = {
        "model": candidate["xgb_model"],
        "features": FEATURES,
        "residual_std": candidate["residual_std"],
    }

    with open(
        xgb_path,
        "wb",
    ) as file:

        pickle.dump(
            xgb_package,
            file,
        )

    # --------------------------------------------------------
    # Ensemble weights
    # --------------------------------------------------------

    weights_path = os.path.join(
        PROMOTED_DIR,
        "ensemble_weights.json",
    )

    weights = {
        "prophet_weight":
            candidate["prophet_weight"],

        "xgb_weight":
            candidate["xgb_weight"],
    }

    pd.Series(
        weights
    ).to_json(
        weights_path
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata_path = os.path.join(
        PROMOTED_DIR,
        "model_metadata.json",
    )

    metadata = {
        "model_version":
            MODEL_VERSION,

        "mape":
            candidate["mape"],

        "rmse":
            candidate["rmse"],

        "prophet_weight":
            candidate["prophet_weight"],

        "xgb_weight":
            candidate["xgb_weight"],
    }

    pd.Series(
        metadata
    ).to_json(
        metadata_path
    )

    print(
        "\nNEW MODEL PROMOTED."
    )

    print(
        "Saved:",
        PROMOTED_DIR
    )


# ============================================================
# ONE YEARLY RETRAINING CYCLE
# ============================================================

def retrain_once(
    data,
    trigger_date,
    old_mape,
    old_rmse,
):

    # --------------------------------------------------------
    # Data available until trigger date
    # --------------------------------------------------------

    available = data[
        data["ds"] <= trigger_date
    ].copy()

    required_rows = (
        WINDOW_MONTHS
        +
        VALIDATION_MONTHS
    )

    if len(available) < required_rows:

        print(
            f"\n{trigger_date.strftime('%Y-%m-%d')}: "
            "Not enough data. SKIP."
        )

        return old_mape, old_rmse

    # --------------------------------------------------------
    # SLIDING WINDOW
    # --------------------------------------------------------

    window = available.tail(
        required_rows
    ).copy()

    train_df = window.iloc[
        :WINDOW_MONTHS
    ].copy()

    validation_df = window.iloc[
        WINDOW_MONTHS:
    ].copy()

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "YEARLY RETRAINING:",
        trigger_date.strftime("%Y-%m-%d")
    )

    print(
        "========================================"
    )

    print(
        "Training:",
        train_df["ds"].min().strftime(
            "%Y-%m-%d"
        ),
        "to",
        train_df["ds"].max().strftime(
            "%Y-%m-%d"
        ),
    )

    print(
        "Validation:",
        validation_df["ds"].min().strftime(
            "%Y-%m-%d"
        ),
        "to",
        validation_df["ds"].max().strftime(
            "%Y-%m-%d"
        ),
    )

    # --------------------------------------------------------
    # MLflow
    # --------------------------------------------------------

    mlflow.set_experiment(
        EXPERIMENT_NAME
    )

    run_name = (
        "yearly_retrain_"
        +
        trigger_date.strftime("%Y")
    )

    with mlflow.start_run(
        run_name=run_name
    ):

        candidate = train_and_evaluate(
            train_df,
            validation_df,
        )

        new_mape = candidate["mape"]
        new_rmse = candidate["rmse"]

        # ----------------------------------------------------
        # PARAMETERS
        # ----------------------------------------------------

        mlflow.log_params({

            "window_months":
                WINDOW_MONTHS,

            "validation_months":
                VALIDATION_MONTHS,

            "data_frequency":
                DATA_FREQUENCY,

            "retrain_frequency":
                "yearly",

            "prophet_weight":
                PROPHET_WEIGHT,

            "xgb_weight":
                XGB_WEIGHT,

            "training_start":
                train_df["ds"]
                .min()
                .strftime("%Y-%m-%d"),

            "training_end":
                train_df["ds"]
                .max()
                .strftime("%Y-%m-%d"),

            "validation_start":
                validation_df["ds"]
                .min()
                .strftime("%Y-%m-%d"),

            "validation_end":
                validation_df["ds"]
                .max()
                .strftime("%Y-%m-%d"),
        })

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        mlflow.log_metrics({

            "new_mape":
                new_mape,

            "new_rmse":
                new_rmse,

            "old_mape":
                (
                    old_mape
                    if old_mape != float("inf")
                    else new_mape
                ),

            "old_rmse":
                (
                    old_rmse
                    if old_rmse != float("inf")
                    else new_rmse
                ),
        })

        # ----------------------------------------------------
        # MODELS
        # ----------------------------------------------------

        mlflow.prophet.log_model(
            candidate["prophet_model"],
            name="prophet_model",
        )

        mlflow.xgboost.log_model(
            candidate["xgb_model"],
            name="xgb_model",
        )

        # ----------------------------------------------------
        # PROMOTION
        # ----------------------------------------------------

        better = is_better_model(
            new_mape,
            new_rmse,
            old_mape,
            old_rmse,
        )

        if better:

            promote_model(
                candidate
            )

            mlflow.set_tag(
                "promotion_status",
                "promoted",
            )

            print(
                "\nSTATUS: PROMOTED"
            )

            print(
                f"New MAPE: {new_mape:.4f}%"
            )

            print(
                f"New RMSE: {new_rmse:.4f}"
            )

            return new_mape, new_rmse

        else:

            mlflow.set_tag(
                "promotion_status",
                "rejected",
            )

            print(
                "\nSTATUS: REJECTED"
            )

            print(
                f"Old MAPE: {old_mape:.4f}%"
            )

            print(
                f"New MAPE: {new_mape:.4f}%"
            )

            print(
                f"Old RMSE: {old_rmse:.4f}"
            )

            print(
                f"New RMSE: {new_rmse:.4f}"
            )

            return old_mape, old_rmse


# ============================================================
# YEARLY AUTOMATED RETRAINING
# ============================================================

def run_retraining():

    print(
        "\n========================================"
    )

    print(
        "R4 AUTOMATED RETRAINING"
    )

    print(
        "========================================"
    )

    data = prepare_data()

    required_rows = (
        WINDOW_MONTHS
        +
        VALIDATION_MONTHS
    )

    if len(data) < required_rows:

        raise ValueError(
            f"Need at least {required_rows} rows, "
            f"but dataset contains {len(data)} rows."
        )

    # --------------------------------------------------------
    # First eligible point
    # --------------------------------------------------------

    first_index = required_rows - 1

    first_date = data.iloc[
        first_index
    ]["ds"]

    # --------------------------------------------------------
    # YEARLY trigger dates
    # --------------------------------------------------------

    yearly_dates = pd.date_range(
        start=first_date,
        end=data["ds"].max(),
        freq=RETRAIN_FREQUENCY,
    )

    print(
        "\nRetraining frequency: Yearly"
    )

    print(
        "Training window:",
        WINDOW_MONTHS,
        "months"
    )

    print(
        "Validation window:",
        VALIDATION_MONTHS,
        "months"
    )

    print(
        "Total yearly cycles:",
        len(yearly_dates)
    )

    # --------------------------------------------------------
    # Initial baseline
    # --------------------------------------------------------

    best_mape = float("inf")
    best_rmse = float("inf")

    # --------------------------------------------------------
    # Run yearly cycles
    # --------------------------------------------------------

    for trigger_date in yearly_dates:

        best_mape, best_rmse = (
            retrain_once(
                data,
                trigger_date,
                best_mape,
                best_rmse,
            )
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "RETRAINING SIMULATION COMPLETE"
    )

    print(
        "========================================"
    )

    if best_mape != float("inf"):

        print(
            f"Best MAPE: {best_mape:.4f}%"
        )

        print(
            f"Best RMSE: {best_rmse:.4f}"
        )

        print(
            "Promoted model directory:",
            PROMOTED_DIR
        )

    else:

        print(
            "No model was promoted."
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run_retraining()