"""
Three-Model Ensemble for Synthetic Demand Forecasting.

Models:
    - Prophet
    - XGBoost
    - LSTM

All three models use the same synthetic demand series and the same
chronological evaluation periods so their predictions can be compared fairly.
"""

import os

import joblib
import numpy as np
import pandas as pd
import torch
from prophet import Prophet
from xgboost import XGBRegressor
from itertools import product
from evaluate import calculate_metrics

from config import (
    DATASET_DAYS,
    DROPOUT,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    NUM_LAYERS,
)
from data import generate_data
from model import MultiStepLSTM
from evaluate import calculate_metrics


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

MODEL_PATH = os.path.join(
    OUTPUT_DIR,
    "best_model.pt",
)

SCALER_PATH = os.path.join(
    OUTPUT_DIR,
    "scaler.pkl",
)


# ---------------------------------------------------------------------------
# Common chronological split
# ---------------------------------------------------------------------------

def create_time_split(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
):
    """
    Create chronological train / validation / test splits.

    No shuffling is used because this is time-series forecasting.
    """

    if not 0 < train_ratio < 1:
        raise ValueError(
            "train_ratio must be between 0 and 1."
        )

    if not 0 < validation_ratio < 1:
        raise ValueError(
            "validation_ratio must be between 0 and 1."
        )

    if train_ratio + validation_ratio >= 1:
        raise ValueError(
            "train_ratio + validation_ratio must be less than 1."
        )

    n = len(df)

    train_end = int(n * train_ratio)
    validation_end = int(
        n * (train_ratio + validation_ratio)
    )

    train_df = df.iloc[:train_end].copy()
    validation_df = df.iloc[
        train_end:validation_end
    ].copy()
    test_df = df.iloc[
        validation_end:
    ].copy()

    return train_df, validation_df, test_df


# ---------------------------------------------------------------------------
# Prophet
# ---------------------------------------------------------------------------

def fit_prophet_and_predict(
    train_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Train Prophet only on the supplied training data and forecast
    exactly the dates present in forecast_df.
    """

    prophet_train = train_df[
        ["Date", "Demand"]
    ].rename(
        columns={
            "Date": "ds",
            "Demand": "y",
        }
    )

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    model.fit(prophet_train)

    future = forecast_df[
        ["Date"]
    ].rename(
        columns={
            "Date": "ds",
        }
    )

    forecast = model.predict(future)

    return forecast[
        "yhat"
    ].to_numpy(dtype=np.float64)


# ---------------------------------------------------------------------------
# XGBoost
# ---------------------------------------------------------------------------

XGB_FEATURES = [
    "lag_1",
    "lag_7",
    "lag_30",
    "rolling_mean_7",
    "rolling_mean_30",
    "rolling_std_7",
    "day_of_week",
    "month",
    "quarter",
    "year",
]


def create_xgb_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create causal time-series features for XGBoost.

    Lag and rolling features use only previous observations.
    """

    data = df.copy()

    data["lag_1"] = (
        data["Demand"].shift(1)
    )

    data["lag_7"] = (
        data["Demand"].shift(7)
    )

    data["lag_30"] = (
        data["Demand"].shift(30)
    )

    data["rolling_mean_7"] = (
        data["Demand"]
        .shift(1)
        .rolling(7)
        .mean()
    )

    data["rolling_mean_30"] = (
        data["Demand"]
        .shift(1)
        .rolling(30)
        .mean()
    )

    data["rolling_std_7"] = (
        data["Demand"]
        .shift(1)
        .rolling(7)
        .std()
    )

    data["day_of_week"] = (
        data["Date"].dt.dayofweek
    )

    data["month"] = (
        data["Date"].dt.month
    )

    data["quarter"] = (
        data["Date"].dt.quarter
    )

    data["year"] = (
        data["Date"].dt.year
    )

    return data

def fit_xgboost_and_predict(
    train_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Train XGBoost on the training portion and generate
    recursive multi-step forecasts without using future
    actual Demand values.

    For every forecast date:
    1. Build features using only historical actuals and
       previous XGBoost predictions.
    2. Predict the current day.
    3. Append that prediction to history.
    4. Use the updated history for the next day.
    """

    train_history = train_df[
        ["Date", "Demand"]
    ].copy()

    train_history["Date"] = pd.to_datetime(
        train_history["Date"]
    )

    train_history = train_history.sort_values(
        "Date"
    ).reset_index(drop=True)

    # --------------------------------------------------
    # TRAIN FEATURES
    # --------------------------------------------------

    train_features = create_xgb_features(
        train_history
    )

    train_features = (
        train_features
        .iloc[: len(train_history)]
        .dropna()
    )

    if train_features.empty:
        raise ValueError(
            "XGBoost training features are empty."
        )

    X_train = train_features[
        XGB_FEATURES
    ]

    y_train = train_features[
        "Demand"
    ]

    # --------------------------------------------------
    # TRAIN MODEL
    # --------------------------------------------------

    model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective="reg:squarederror",
    )

    model.fit(
        X_train,
        y_train,
    )

    # --------------------------------------------------
    # RECURSIVE FORECASTING
    # --------------------------------------------------

    history = train_history.copy()

    forecast_dates = pd.to_datetime(
        forecast_df["Date"]
    ).sort_values().reset_index(drop=True)

    predictions = []

    for forecast_date in forecast_dates:

        # Create a temporary row for the future date.
        # Demand is deliberately NaN because the actual
        # future Demand must NEVER be used.
        temp_history = pd.concat(
            [
                history,
                pd.DataFrame(
                    {
                        "Date": [forecast_date],
                        "Demand": [np.nan],
                    }
                ),
            ],
            ignore_index=True,
        )

        temp_features = create_xgb_features(
            temp_history
        )

        current_features = temp_features.iloc[
            -1:
        ][XGB_FEATURES]

        if current_features.isnull().any().any():
            raise ValueError(
                "XGBoost recursive forecast features "
                f"contain NaN for {forecast_date}."
            )

        prediction = float(
            model.predict(
                current_features
            )[0]
        )

        predictions.append(
            prediction
        )

        # IMPORTANT:
        # Append the prediction, NOT the actual future Demand.
        history = pd.concat(
            [
                history,
                pd.DataFrame(
                    {
                        "Date": [forecast_date],
                        "Demand": [prediction],
                    }
                ),
            ],
            ignore_index=True,
        )

    return np.asarray(
        predictions,
        dtype=np.float64,
    )

# ---------------------------------------------------------------------------
# LSTM
# ---------------------------------------------------------------------------

def load_lstm_model() -> MultiStepLSTM:
    """
    Load the trained LSTM checkpoint using the current configuration.
    """

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"LSTM model not found: {MODEL_PATH}"
        )

    model = MultiStepLSTM(
        input_size=1,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT,
        horizon=HORIZON,
        use_attention=False,
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location="cpu",
        weights_only=True,
    )

    model.load_state_dict(
        checkpoint
    )

    model.eval()

    return model


def load_lstm_scaler():
    """
    Load the scaler fitted during LSTM training.
    """

    if not os.path.exists(SCALER_PATH):
        raise FileNotFoundError(
            f"LSTM scaler not found: {SCALER_PATH}"
        )

    return joblib.load(
        SCALER_PATH
    )


def fit_lstm_and_predict(
    train_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Generate rolling one-step predictions from the trained LSTM.

    The LSTM was trained on scaled demand values, so:
        raw history
            -> scaler.transform()
            -> LSTM
            -> inverse_transform()
            -> original demand units

    Only historical observations before each forecast point are
    provided to the model.
    """

    model = load_lstm_model()
    scaler = load_lstm_scaler()

    full_df = pd.concat(
        [
            train_df[
                ["Date", "Demand"]
            ],
            forecast_df[
                ["Date", "Demand"]
            ],
        ],
        ignore_index=True,
    )

    demand = full_df[
        "Demand"
    ].to_numpy(
        dtype=np.float32
    )

    scaled_predictions = []

    forecast_start = len(train_df)
    forecast_end = len(full_df)

    for target_index in range(
        forecast_start,
        forecast_end,
    ):

        history_start = (
            target_index - LOOKBACK
        )

        if history_start < 0:
            raise ValueError(
                "Not enough historical observations "
                "for the LSTM lookback."
            )

        # Only observations before the target date.
        history = demand[
            history_start:target_index
        ]

        if len(history) != LOOKBACK:
            raise ValueError(
                f"Expected {LOOKBACK} history values, "
                f"got {len(history)}."
            )

        # IMPORTANT:
        # LSTM was trained on scaled input.
        scaled_history = scaler.transform(
            history.reshape(-1, 1)
        )

        x = torch.tensor(
            scaled_history,
            dtype=torch.float32,
        ).reshape(
            1,
            LOOKBACK,
            1,
        )

        with torch.no_grad():
            forecast = model(
                x
            ).cpu().numpy()[0]

        # Model predicts HORIZON days.
        # For common daily comparison with Prophet/XGBoost,
        # take the first day prediction.
        scaled_predictions.append(
            float(forecast[0])
        )

    # Convert LSTM predictions back to original demand units.
    predictions = scaler.inverse_transform(
        np.asarray(
            scaled_predictions,
            dtype=np.float64,
        ).reshape(-1, 1)
    ).ravel()

    return predictions.astype(
        np.float64
    )

def evaluate_predictions(
    actual: np.ndarray,
    predictions: np.ndarray,
    model_name: str,
):
    """
    Calculate and print MAE, RMSE and MAPE.
    """

    metrics = calculate_metrics(
        actual,
        predictions,
    )

    print(
        f"{model_name:<10} "
        f"MAE: {metrics['MAE']:.4f} | "
        f"RMSE: {metrics['RMSE']:.4f} | "
        f"MAPE: {metrics['MAPE']:.4f}"
    )
    return metrics

def find_best_ensemble_weights(
    y_true: np.ndarray,
    prophet_pred: np.ndarray,
    xgb_pred: np.ndarray,
    lstm_pred: np.ndarray,
    step: float = 0.05,
    min_weight: float = 0.05,
):
    """
    Find non-zero ensemble weights using validation MAE.

    All three models must contribute to the ensemble.

    Test data is NOT used for weight selection.
    """

    best_weights = None
    best_mae = float("inf")

    values = np.arange(
        min_weight,
        1.0 + step / 2,
        step,
    )

    for prophet_weight in values:
        for xgb_weight in values:

            lstm_weight = (
                1.0
                - prophet_weight
                - xgb_weight
            )

            if lstm_weight < min_weight:
                continue

            ensemble_pred = (
                prophet_weight * prophet_pred
                + xgb_weight * xgb_pred
                + lstm_weight * lstm_pred
            )

            metrics = calculate_metrics(
                y_true,
                ensemble_pred,
            )

            if metrics["MAE"] < best_mae:
                best_mae = metrics["MAE"]

                best_weights = {
                    "Prophet": float(
                        prophet_weight
                    ),
                    "XGBoost": float(
                        xgb_weight
                    ),
                    "LSTM": float(
                        lstm_weight
                    ),
                }

    if best_weights is None:
        raise RuntimeError(
            "Could not find valid non-zero ensemble weights."
        )

    return best_weights, best_mae
# ---------------------------------------------------------------------------
# Dataset preparation
# ---------------------------------------------------------------------------

def prepare_dataset():
    """
    Generate the common synthetic dataset and create chronological splits.

    This is the single data source used by all three ensemble models.
    """

    df = generate_data(
        days=DATASET_DAYS
    )

    train_df, validation_df, test_df = (
        create_time_split(df)
    )

    print("=" * 70)
    print(
        "COMMON SYNTHETIC DATASET"
    )
    print("=" * 70)

    print(
        f"Total samples      : {len(df)}"
    )

    print(
        f"Training samples   : {len(train_df)}"
    )

    print(
        f"Validation samples : {len(validation_df)}"
    )

    print(
        f"Test samples       : {len(test_df)}"
    )

    print()

    print(
        f"Train      : "
        f"{train_df['Date'].iloc[0].date()} "
        f"-> "
        f"{train_df['Date'].iloc[-1].date()}"
    )

    print(
        f"Validation : "
        f"{validation_df['Date'].iloc[0].date()} "
        f"-> "
        f"{validation_df['Date'].iloc[-1].date()}"
    )

    print(
        f"Test       : "
        f"{test_df['Date'].iloc[0].date()} "
        f"-> "
        f"{test_df['Date'].iloc[-1].date()}"
    )

    print("=" * 70)

    return (
        df,
        train_df,
        validation_df,
        test_df,
    )


# ---------------------------------------------------------------------------
# Main verification
# ---------------------------------------------------------------------------
if __name__ == "__main__":

    (
        _,
        train_df,
        validation_df,
        test_df,
    ) = prepare_dataset()

    # ================================================================
    # Generate predictions
    # ================================================================

    prophet_val = fit_prophet_and_predict(
        train_df,
        validation_df,
    )

    prophet_test = fit_prophet_and_predict(
        train_df,
        test_df,
    )

    xgb_val = fit_xgboost_and_predict(
        train_df,
        validation_df,
    )

    xgb_test = fit_xgboost_and_predict(
        train_df,
        test_df,
    )

    lstm_val = fit_lstm_and_predict(
        train_df,
        validation_df,
    )

    lstm_test = fit_lstm_and_predict(
        train_df,
        test_df,
    )

    actual_val = validation_df[
        "Demand"
    ].to_numpy(dtype=np.float64)

    actual_test = test_df[
        "Demand"
    ].to_numpy(dtype=np.float64)

    # ================================================================
    # Individual validation performance
    # ================================================================

    print("\n" + "=" * 70)
    print("VALIDATION PERFORMANCE")
    print("=" * 70)

    prophet_val_metrics = evaluate_predictions(
        actual_val,
        prophet_val,
        "Prophet",
    )

    xgb_val_metrics = evaluate_predictions(
        actual_val,
        xgb_val,
        "XGBoost",
    )

    lstm_val_metrics = evaluate_predictions(
        actual_val,
        lstm_val,
        "LSTM",
    )

    # ================================================================
    # Select ensemble weights ONLY using validation data
    # ================================================================

    best_weights, validation_ensemble_mae = (
        find_best_ensemble_weights(
            actual_val,
            prophet_val,
            xgb_val,
            lstm_val,
        )
    )

    validation_ensemble = (
        best_weights["Prophet"] * prophet_val
        + best_weights["XGBoost"] * xgb_val
        + best_weights["LSTM"] * lstm_val
    )

    validation_ensemble_metrics = (
        calculate_metrics(
            actual_val,
            validation_ensemble,
        )
    )

    print("\n" + "=" * 70)
    print("BEST THREE-MODEL ENSEMBLE WEIGHTS")
    print("=" * 70)

    print(
        f"Prophet : {best_weights['Prophet']:.2f}"
    )

    print(
        f"XGBoost : {best_weights['XGBoost']:.2f}"
    )

    print(
        f"LSTM    : {best_weights['LSTM']:.2f}"
    )

    print(
        f"Weight sum: "
        f"{sum(best_weights.values()):.2f}"
    )

    print(
        f"\nValidation Ensemble MAE: "
        f"{validation_ensemble_metrics['MAE']:.4f}"
    )

    print(
        f"Validation Ensemble RMSE: "
        f"{validation_ensemble_metrics['RMSE']:.4f}"
    )

    print(
        f"Validation Ensemble MAPE: "
        f"{validation_ensemble_metrics['MAPE']:.4f}"
    )

    # ================================================================
    # Final test evaluation
    # ================================================================

    ensemble_test = (
        best_weights["Prophet"] * prophet_test
        + best_weights["XGBoost"] * xgb_test
        + best_weights["LSTM"] * lstm_test
    )

    prophet_test_metrics = evaluate_predictions(
        actual_test,
        prophet_test,
        "Prophet",
    )

    xgb_test_metrics = evaluate_predictions(
        actual_test,
        xgb_test,
        "XGBoost",
    )

    lstm_test_metrics = evaluate_predictions(
        actual_test,
        lstm_test,
        "LSTM",
    )

    ensemble_test_metrics = evaluate_predictions(
        actual_test,
        ensemble_test,
        "Ensemble",
    )

    # ================================================================
    # Final comparison
    # ================================================================

    print("\n" + "=" * 70)
    print("FINAL TEST COMPARISON")
    print("=" * 70)

    print(
        f"Prophet Test MAE : "
        f"{prophet_test_metrics['MAE']:.4f}"
    )

    print(
        f"XGBoost Test MAE : "
        f"{xgb_test_metrics['MAE']:.4f}"
    )

    print(
        f"LSTM Test MAE    : "
        f"{lstm_test_metrics['MAE']:.4f}"
    )

    print(
        f"Ensemble Test MAE: "
        f"{ensemble_test_metrics['MAE']:.4f}"
    )

    improvement = (
        (
            prophet_test_metrics["MAE"]
            - ensemble_test_metrics["MAE"]
        )
        / prophet_test_metrics["MAE"]
        * 100
    )

    print(
        f"\nEnsemble improvement vs Prophet: "
        f"{improvement:.2f}%"
    )

    print("\n" + "=" * 70)
    print("PREDICTION COUNTS")
    print("=" * 70)

    print(
        "Prophet validation:",
        len(prophet_val),
    )

    print(
        "Prophet test:",
        len(prophet_test),
    )

    print(
        "XGBoost validation:",
        len(xgb_val),
    )

    print(
        "XGBoost test:",
        len(xgb_test),
    )

    print(
        "LSTM validation:",
        len(lstm_val),
    )

    print(
        "LSTM test:",
        len(lstm_test),
    )

    print(
        "\nFirst 5 Ensemble test predictions:",
        ensemble_test[:5],
    )