import os
import pickle
import math
import json

import mlflow
import mlflow.prophet
import mlflow.xgboost

import numpy as np
import pandas as pd

from prophet import Prophet
from prophet.serialize import model_to_json
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error

from src.data import load_sales_data
from src.inference import create_features


# ============================================================
# CONFIGURATION
# ============================================================

WINDOW_MONTHS = 120
VALIDATION_MONTHS = 12

DATA_FREQUENCY = "MS"
RETRAIN_FREQUENCY = "YS"

EXPERIMENT_NAME = "R5_Automated_Retraining"

PROMOTED_DIR = "models/promoted"

MODEL_VERSION = "R5"


# ============================================================
# R5 ENSEMBLE WEIGHT GRID
# ============================================================

WEIGHT_GRID = [
    (0.0, 1.0),
    (0.1, 0.9),
    (0.2, 0.8),
    (0.3, 0.7),
    (0.4, 0.6),
    (0.5, 0.5),
    (0.6, 0.4),
    (0.7, 0.3),
    (0.8, 0.2),
    (0.9, 0.1),
    (1.0, 0.0),
]


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

    print("\nDataset validation passed.")

    print("\nDataset prepared successfully.")

    print(
        "Date range:",
        df["ds"].min(),
        "to",
        df["ds"].max(),
    )

    print(
        "Total rows:",
        len(df),
    )

    return df


# ============================================================
# MAPE
# ============================================================

def calculate_mape(actual, predicted):
    actual = np.asarray(
        actual,
        dtype=float,
    )

    predicted = np.asarray(
        predicted,
        dtype=float,
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
        y_train,
    )

    # --------------------------------------------------------
    # Residual standard deviation is calculated ONLY from
    # training predictions.
    # --------------------------------------------------------

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

    validation_features = (
        validation_features
        .sort_values("ds")
        .reset_index(drop=True)
    )

    validation_df_sorted = (
        validation_df
        .sort_values("ds")
        .reset_index(drop=True)
    )

    if not validation_features["ds"].equals(
        validation_df_sorted["ds"]
    ):
        raise ValueError(
            "Validation dates are not aligned."
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
    prophet_weight,
    xgb_weight,
):
    if prophet_weight < 0 or xgb_weight < 0:
        raise ValueError(
            "Ensemble weights cannot be negative."
        )

    if not math.isclose(
        prophet_weight + xgb_weight,
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "Ensemble weights must sum to 1."
        )

    return (
        prophet_weight * prophet_prediction
        + xgb_weight * xgb_prediction
    )


# ============================================================
# EVALUATE ONE WEIGHT COMBINATION
# ============================================================

def evaluate_weight_combination(
    prophet_prediction,
    xgb_prediction,
    actual,
    prophet_weight,
    xgb_weight,
):
    ensemble_prediction = (
        create_ensemble_prediction(
            prophet_prediction,
            xgb_prediction,
            prophet_weight,
            xgb_weight,
        )
    )

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

    return {
        "prophet_weight": prophet_weight,
        "xgb_weight": xgb_weight,
        "mape": mape,
        "rmse": rmse,
        "prediction": ensemble_prediction,
    }


# ============================================================
# FIND BEST GRID RESULT
# ============================================================

def select_best_result(results):
    if not results:
        raise ValueError(
            "No ensemble weight combinations were evaluated."
        )

    # Primary metric: MAPE
    # Secondary metric: RMSE

    return min(
        results,
        key=lambda result: (
            result["mape"],
            result["rmse"],
        )
    )


# ============================================================
# TRAIN MODELS + GRID SEARCH
# ============================================================

def train_and_tune(
    train_df,
    validation_df,
    yearly_run,
):
    print(
        "\n----------------------------------------"
    )

    print(
        "Training candidate models"
    )

    print(
        "----------------------------------------"
    )

    # ========================================================
    # PROPHET
    # ========================================================

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

    # ========================================================
    # XGBOOST
    # ========================================================

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

    # ========================================================
    # ACTUAL VALUES
    # ========================================================

    actual = (
        validation_df
        .sort_values("ds")["y"]
        .to_numpy()
    )

    # ========================================================
    # GRID SEARCH
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "ENSEMBLE WEIGHT GRID SEARCH"
    )

    print(
        "========================================"
    )

    print(
        f"Total combinations: {len(WEIGHT_GRID)}"
    )

    results = []

    for index, (
        prophet_weight,
        xgb_weight,
    ) in enumerate(
        WEIGHT_GRID,
        start=1,
    ):
        print(
            "\n----------------------------------------"
        )

        print(
            f"Combination {index}/{len(WEIGHT_GRID)}"
        )

        print(
            f"Prophet weight: {prophet_weight}"
        )

        print(
            f"XGBoost weight: {xgb_weight}"
        )

        result = evaluate_weight_combination(
            prophet_prediction,
            xgb_prediction,
            actual,
            prophet_weight,
            xgb_weight,
        )

        results.append(result)

        # ----------------------------------------------------
        # Every grid combination is logged in MLflow
        # ----------------------------------------------------

        with mlflow.start_run(
            run_name=(
                "grid_"
                f"prophet_{prophet_weight:.2f}_"
                f"xgb_{xgb_weight:.2f}"
            ),
            nested=True,
        ):
            mlflow.log_params(
                {
                    "search_type":
                        "ensemble_weight_grid",

                    "prophet_weight":
                        prophet_weight,

                    "xgb_weight":
                        xgb_weight,

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
                }
            )

            mlflow.log_metrics(
                {
                    "validation_mape":
                        result["mape"],

                    "validation_rmse":
                        result["rmse"],
                }
            )

            mlflow.set_tag(
                "run_type",
                "grid_search",
            )

            mlflow.set_tag(
                "parent_retraining_run",
                yearly_run.info.run_id,
            )

        print(
            f"MAPE: {result['mape']:.4f}%"
        )

        print(
            f"RMSE: {result['rmse']:.4f}"
        )

    # ========================================================
    # BEST COMBINATION
    # ========================================================

    best_result = select_best_result(
        results
    )

    print(
        "\n========================================"
    )

    print(
        "GRID SEARCH WINNER"
    )

    print(
        "========================================"
    )

    print(
        "Prophet weight:",
        best_result["prophet_weight"],
    )

    print(
        "XGBoost weight:",
        best_result["xgb_weight"],
    )

    print(
        f"MAPE: {best_result['mape']:.4f}%"
    )

    print(
        f"RMSE: {best_result['rmse']:.4f}"
    )

    return {
        "prophet_model":
            prophet_model,

        "xgb_model":
            xgb_model,

        "residual_std":
            residual_std,

        "prophet_weight":
            best_result["prophet_weight"],

        "xgb_weight":
            best_result["xgb_weight"],

        "mape":
            best_result["mape"],

        "rmse":
            best_result["rmse"],

        "grid_results":
            results,
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
    """
    Decide whether a candidate model should replace
    the currently promoted model.

    Priority:
        1. Lower MAPE
        2. Lower RMSE when MAPE is tied
    """

    # No existing baseline.
    if old_mape == float("inf"):
        return True

    # Primary metric.
    if new_mape < old_mape:
        return True

    # Secondary metric for MAPE ties.
    if math.isclose(
        new_mape,
        old_mape,
        rel_tol=1e-6,
        abs_tol=1e-6,
    ):
        return new_rmse < old_rmse

    return False


# ============================================================
# LOAD EXISTING PROMOTED BASELINE
# ============================================================

def load_existing_baseline():
    metadata_path = os.path.join(
        PROMOTED_DIR,
        "model_metadata.json",
    )

    if not os.path.exists(
        metadata_path
    ):
        print(
            "\nNo previous promoted model found."
        )

        print(
            "Starting with empty baseline."
        )

        return (
            float("inf"),
            float("inf"),
        )

    try:
        with open(
            metadata_path,
            "r",
        ) as file:
            metadata = json.load(file)

        old_mape = float(
            metadata.get(
                "mape",
                float("inf"),
            )
        )

        old_rmse = float(
            metadata.get(
                "rmse",
                float("inf"),
            )
        )

        print(
            "\nExisting promoted baseline found."
        )

        print(
            f"Previous MAPE: {old_mape:.4f}%"
        )

        print(
            f"Previous RMSE: {old_rmse:.4f}"
        )

        print(
            "Baseline will be used for "
            "auto-promotion comparison."
        )

        return old_mape, old_rmse

    except Exception as exc:
        print(
            "\nWARNING: Could not read "
            "previous promoted metadata."
        )

        print(
            "Reason:",
            exc,
        )

        print(
            "Starting with empty baseline."
        )

        return (
            float("inf"),
            float("inf"),
        )


# ============================================================
# SAVE PROMOTED MODEL
# ============================================================

def promote_model(candidate):
    os.makedirs(
        PROMOTED_DIR,
        exist_ok=True,
    )

    # ========================================================
    # PROPHET
    # ========================================================

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

    # ========================================================
    # XGBOOST
    # ========================================================

    xgb_path = os.path.join(
        PROMOTED_DIR,
        "xgb_model.pkl",
    )

    xgb_package = {
        "model":
            candidate["xgb_model"],

        "features":
            FEATURES,

        "residual_std":
            candidate["residual_std"],
    }

    with open(
        xgb_path,
        "wb",
    ) as file:
        pickle.dump(
            xgb_package,
            file,
        )

    # ========================================================
    # ENSEMBLE WEIGHTS
    # ========================================================

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

    with open(
        weights_path,
        "w",
    ) as file:
        json.dump(
            weights,
            file,
            indent=4,
        )

    # ========================================================
    # METADATA
    # ========================================================

    metadata_path = os.path.join(
        PROMOTED_DIR,
        "model_metadata.json",
    )

    metadata = {
        "model_version":
            MODEL_VERSION,

        "status":
            "promoted",

        "mape":
            candidate["mape"],

        "rmse":
            candidate["rmse"],

        "prophet_weight":
            candidate["prophet_weight"],

        "xgb_weight":
            candidate["xgb_weight"],
    }

    with open(
        metadata_path,
        "w",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=4,
        )

    print(
        "\nNEW MODEL PROMOTED."
    )

    print(
        "Saved:",
        PROMOTED_DIR,
    )

    print(
        "Selected Prophet weight:",
        candidate["prophet_weight"],
    )

    print(
        "Selected XGBoost weight:",
        candidate["xgb_weight"],
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
    # ========================================================
    # DATA AVAILABLE UNTIL TRIGGER DATE
    # ========================================================

    available = data[
        data["ds"] <= trigger_date
    ].copy()

    required_rows = (
        WINDOW_MONTHS
        + VALIDATION_MONTHS
    )

    if len(available) < required_rows:
        print(
            f"\n{trigger_date.strftime('%Y-%m-%d')}: "
            "Not enough data. SKIP."
        )

        return old_mape, old_rmse

    # ========================================================
    # SLIDING WINDOW
    # ========================================================

    window = available.tail(
        required_rows
    ).copy()

    train_df = window.iloc[
        :WINDOW_MONTHS
    ].copy()

    validation_df = window.iloc[
        WINDOW_MONTHS:
    ].copy()

    # ========================================================
    # DISPLAY
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "YEARLY RETRAINING:",
        trigger_date.strftime("%Y-%m-%d"),
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

    # ========================================================
    # MLflow PARENT RUN
    # ========================================================

    mlflow.set_experiment(
        EXPERIMENT_NAME
    )

    run_name = (
        "yearly_retrain_"
        + trigger_date.strftime("%Y")
    )

    with mlflow.start_run(
        run_name=run_name
    ) as yearly_run:

        candidate = train_and_tune(
            train_df,
            validation_df,
            yearly_run,
        )

        new_mape = candidate["mape"]
        new_rmse = candidate["rmse"]

        # ====================================================
        # PARAMETERS
        # ====================================================

        mlflow.log_params(
            {
                "model_version":
                    MODEL_VERSION,

                "window_months":
                    WINDOW_MONTHS,

                "validation_months":
                    VALIDATION_MONTHS,

                "data_frequency":
                    DATA_FREQUENCY,

                "retrain_frequency":
                    "yearly",

                "grid_combinations":
                    len(WEIGHT_GRID),

                "selected_prophet_weight":
                    candidate["prophet_weight"],

                "selected_xgb_weight":
                    candidate["xgb_weight"],

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
            }
        )

        # ====================================================
        # METRICS
        # ====================================================

        mlflow.log_metrics(
            {
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
            }
        )

        # ====================================================
        # GRID SEARCH SUMMARY
        # ====================================================

        grid_df = pd.DataFrame(
            [
                {
                    "prophet_weight":
                        result["prophet_weight"],

                    "xgb_weight":
                        result["xgb_weight"],

                    "mape":
                        result["mape"],

                    "rmse":
                        result["rmse"],
                }
                for result in candidate["grid_results"]
            ]
        )

        os.makedirs(
            PROMOTED_DIR,
            exist_ok=True,
        )

        grid_filename = (
            f"grid_search_results_"
            f"{trigger_date.strftime('%Y')}.csv"
        )

        grid_path = os.path.join(
            PROMOTED_DIR,
            grid_filename,
        )

        grid_df.to_csv(
            grid_path,
            index=False,
        )

        mlflow.log_artifact(
            grid_path,
            artifact_path="grid_search",
        )

        # ====================================================
        # LOG WINNING MODELS
        # ====================================================

        mlflow.prophet.log_model(
            candidate["prophet_model"],
            name="prophet_model",
        )

        mlflow.xgboost.log_model(
            candidate["xgb_model"],
            name="xgb_model",
        )

        # ====================================================
        # SINGLE AUTO-PROMOTION DECISION
        # ====================================================

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

            mlflow.set_tag(
                "grid_search_status",
                "winner_selected",
            )

            print(
                "\nSTATUS: PROMOTED"
            )

            if old_mape != float("inf"):
                print(
                    f"Old MAPE: {old_mape:.4f}%"
                )

                print(
                    f"Old RMSE: {old_rmse:.4f}"
                )
            else:
                print(
                    "Old MAPE: NONE"
                )

                print(
                    "Old RMSE: NONE"
                )

            print(
                f"New MAPE: {new_mape:.4f}%"
            )

            print(
                f"New RMSE: {new_rmse:.4f}"
            )

            print(
                "Auto-promotion decision: ACCEPT"
            )

            return new_mape, new_rmse

        # ====================================================
        # REJECT
        # ====================================================

        mlflow.set_tag(
            "promotion_status",
            "rejected",
        )

        mlflow.set_tag(
            "grid_search_status",
            "winner_rejected",
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

        print(
            "Auto-promotion decision: REJECT"
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
        "R5 AUTOMATED RETRAINING"
    )

    print(
        "========================================"
    )

    data = prepare_data()

    required_rows = (
        WINDOW_MONTHS
        + VALIDATION_MONTHS
    )

    if len(data) < required_rows:
        raise ValueError(
            f"Need at least {required_rows} rows, "
            f"but dataset contains {len(data)} rows."
        )

    # ========================================================
    # FIRST ELIGIBLE POINT
    # ========================================================

    first_index = (
        required_rows - 1
    )

    first_date = data.iloc[
        first_index
    ]["ds"]

    # ========================================================
    # YEARLY TRIGGER DATES
    # ========================================================

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
        "months",
    )

    print(
        "Validation window:",
        VALIDATION_MONTHS,
        "months",
    )

    print(
        "Total yearly cycles:",
        len(yearly_dates),
    )

    print(
        "Grid combinations:",
        len(WEIGHT_GRID),
    )

    # ========================================================
    # LOAD PREVIOUS PROMOTED BASELINE
    # ========================================================

    best_mape, best_rmse = (
        load_existing_baseline()
    )

    # ========================================================
    # YEARLY CYCLES
    # ========================================================

    promoted_count = 0
    rejected_count = 0

    for trigger_date in yearly_dates:

        old_mape = best_mape
        old_rmse = best_rmse

        new_mape, new_rmse = (
            retrain_once(
                data,
                trigger_date,
                old_mape,
                old_rmse,
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Do NOT duplicate the promotion criteria here.
        #
        # retrain_once() already makes the actual decision
        # using is_better_model().
        #
        # We only classify the result here using the SAME
        # shared decision function.
        # ----------------------------------------------------

        promoted = is_better_model(
            new_mape,
            new_rmse,
            old_mape,
            old_rmse,
        )

        if promoted:
            promoted_count += 1
            # Only a promoted candidate becomes the new comparison baseline.
            # A rejected one must not the next cycle still has to beat the
            # model that's actually on disk.
            best_mape = new_mape
            best_rmse = new_rmse
        else:
            rejected_count += 1

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n========================================"
    )

    print(
        "R5 RETRAINING SIMULATION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        f"Promoted cycles: {promoted_count}"
    )

    print(
        f"Rejected cycles: {rejected_count}"
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
            PROMOTED_DIR,
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