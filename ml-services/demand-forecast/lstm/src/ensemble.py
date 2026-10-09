"""
Three-Model Ensemble for Synthetic Demand Forecasting.

Models:
    - Prophet
    - XGBoost
    - LSTM

Every model follows the same contract:

    fit_<model>_and_predict(history_df, forecast_df)

    * trains ONLY on history_df
    * forecasts every date in forecast_df
    * never reads forecast_df["Demand"]
    * forecast_df must start the day after history_df ends

Validation: models trained on train, forecast validation -> pick weights.
Test:       models trained on train + validation, forecast test -> report.
"""

import os
import random

import mlflow
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from prophet import Prophet
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBRegressor

from config import (
    BATCH_SIZE,
    DATASET_DAYS,
    DROPOUT,
    EPOCHS,
    HIDDEN_SIZE,
    HORIZON,
    LOOKBACK,
    LR,
    NUM_LAYERS,
    OUTPUT_DIR,
    RANDOM_SEED,
)
from data import create_sequences, generate_data
from evaluate import calculate_metrics
from model import MultiStepLSTM


MODEL_NAMES = ("Prophet", "XGBoost", "LSTM")


def set_seeds(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


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
        raise ValueError("train_ratio must be between 0 and 1.")

    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1.")

    if train_ratio + validation_ratio >= 1:
        raise ValueError("train_ratio + validation_ratio must be less than 1.")

    n = len(df)
    train_end = int(n * train_ratio)
    validation_end = int(n * (train_ratio + validation_ratio))

    train_df = df.iloc[:train_end].copy()
    validation_df = df.iloc[train_end:validation_end].copy()
    test_df = df.iloc[validation_end:].copy()

    return train_df, validation_df, test_df


def check_contiguous(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> None:
    """
    Fail loudly if the forecast window does not start the day after the
    history ends. Lag features and LSTM windows are row-based, so a gap
    silently feeds them values from the wrong dates.
    """

    last_history = pd.Timestamp(history_df["Date"].iloc[-1])
    first_forecast = pd.Timestamp(forecast_df["Date"].iloc[0])

    if first_forecast != last_history + pd.Timedelta(1, unit="D"):
        raise ValueError(
            f"Forecast starts {first_forecast.date()} but history ends "
            f"{last_history.date()}. Pass the full history up to the day "
            "before the forecast window."
        )


# ---------------------------------------------------------------------------
# Prophet
# ---------------------------------------------------------------------------

def fit_prophet_and_predict(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Train Prophet only on history_df and forecast the dates in forecast_df.
    """

    check_contiguous(history_df, forecast_df)

    prophet_train = history_df[["Date", "Demand"]].rename(
        columns={"Date": "ds", "Demand": "y"}
    )

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )
    model.fit(prophet_train)

    future = forecast_df[["Date"]].rename(columns={"Date": "ds"})
    forecast = model.predict(future)

    return forecast["yhat"].to_numpy(dtype=np.float64)


# ---------------------------------------------------------------------------
# XGBoost
# ---------------------------------------------------------------------------

# "year" was removed: the test period is a year the trees never saw in
# training, so the feature cannot help and only adds noise.
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
]


def create_xgb_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create causal time-series features for XGBoost.

    Lag and rolling features use only previous observations.
    """

    data = df.copy()
    shifted = data["Demand"].shift(1)

    data["lag_1"] = shifted
    data["lag_7"] = data["Demand"].shift(7)
    data["lag_30"] = data["Demand"].shift(30)
    data["rolling_mean_7"] = shifted.rolling(7).mean()
    data["rolling_mean_30"] = shifted.rolling(30).mean()
    data["rolling_std_7"] = shifted.rolling(7).std()
    data["day_of_week"] = data["Date"].dt.dayofweek
    data["month"] = data["Date"].dt.month
    data["quarter"] = data["Date"].dt.quarter

    return data


def fit_xgboost_and_predict(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Train XGBoost on history_df and generate recursive multi-step forecasts
    without using future actual Demand values.

    For every forecast date:
    1. Build features from historical actuals + previous XGBoost predictions.
    2. Predict the current day.
    3. Append that prediction to history.
    """

    check_contiguous(history_df, forecast_df)

    history = history_df[["Date", "Demand"]].copy()
    history["Date"] = pd.to_datetime(history["Date"])
    history = history.sort_values("Date").reset_index(drop=True)

    train_features = create_xgb_features(history).dropna()

    if train_features.empty:
        raise ValueError("XGBoost training features are empty.")

    model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=RANDOM_SEED,
        objective="reg:squarederror",
    )
    model.fit(train_features[XGB_FEATURES], train_features["Demand"])

    forecast_dates = pd.to_datetime(forecast_df["Date"]).sort_values()
    predictions = []

    for forecast_date in forecast_dates:
        # Demand is NaN on purpose: the actual future value must never be used.
        temp_history = pd.concat(
            [history, pd.DataFrame({"Date": [forecast_date], "Demand": [np.nan]})],
            ignore_index=True,
        )

        current_features = create_xgb_features(temp_history).iloc[-1:][XGB_FEATURES]

        if current_features.isnull().any().any():
            raise ValueError(
                f"XGBoost recursive forecast features contain NaN for {forecast_date}."
            )

        prediction = float(model.predict(current_features)[0])
        predictions.append(prediction)

        # Append the prediction, NOT the actual future Demand.
        history = pd.concat(
            [history, pd.DataFrame({"Date": [forecast_date], "Demand": [prediction]})],
            ignore_index=True,
        )

    return np.asarray(predictions, dtype=np.float64)


# ---------------------------------------------------------------------------
# LSTM
# ---------------------------------------------------------------------------

def train_lstm(history_df: pd.DataFrame):
    """
    Train a fresh LSTM on history_df only.

    The saved output/best_model.pt is NOT used here: it was trained on
    rows 0-829, which overlaps the ensemble's validation window.
    The scaler is also fit on history_df only.
    """

    set_seeds()

    values = history_df["Demand"].to_numpy(dtype=np.float32).reshape(-1, 1)

    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(values)

    X, y = create_sequences(scaled, lookback=LOOKBACK, horizon=HORIZON)

    if len(X) == 0:
        raise ValueError("Not enough history to build LSTM training windows.")

    loader = DataLoader(
        TensorDataset(torch.tensor(X), torch.tensor(y)),
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    model = MultiStepLSTM(
        input_size=1,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        dropout=DROPOUT,
        horizon=HORIZON,
        use_attention=False,
    )
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    model.train()
    for _ in range(EPOCHS):
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()

    model.eval()
    return model, scaler


def fit_lstm_and_predict(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> np.ndarray:
    """
    Train the LSTM on history_df, then forecast recursively in HORIZON-day
    chunks, feeding its own predictions back in.

    This is the same task Prophet and XGBoost do: no actual Demand from
    the forecast window is ever read.
    """

    check_contiguous(history_df, forecast_df)

    if len(history_df) < LOOKBACK:
        raise ValueError("Not enough historical observations for the LSTM lookback.")

    model, scaler = train_lstm(history_df)

    window = scaler.transform(
        history_df["Demand"].to_numpy(dtype=np.float64).reshape(-1, 1)
    ).ravel()[-LOOKBACK:].tolist()

    n_steps = len(forecast_df)
    scaled_predictions = []

    while len(scaled_predictions) < n_steps:
        x = torch.tensor(window[-LOOKBACK:], dtype=torch.float32).reshape(1, LOOKBACK, 1)

        with torch.no_grad():
            chunk = model(x).cpu().numpy()[0].tolist()

        scaled_predictions.extend(chunk)
        window.extend(chunk)

    scaled_predictions = np.asarray(scaled_predictions[:n_steps]).reshape(-1, 1)

    return scaler.inverse_transform(scaled_predictions).ravel().astype(np.float64)


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

def combine(predictions: dict, weights: dict) -> np.ndarray:
    return sum(weights[name] * predictions[name] for name in MODEL_NAMES)


def find_best_ensemble_weights(
    y_true: np.ndarray,
    predictions: dict,
    step: float = 0.05,
    min_weight: float = 0.05,
):
    """
    Grid-search weights (summing to 1) that minimise validation MAE.

    Works on integer grid units, so float error never drops a valid split.
    min_weight=0.0 gives the unconstrained best for an honest comparison.

    Test data is NOT used for weight selection.
    """

    units = int(round(1 / step))
    min_units = int(round(min_weight / step))

    best_weights = None
    best_mae = float("inf")

    for p_units in range(min_units, units + 1):
        for x_units in range(min_units, units - p_units + 1):
            l_units = units - p_units - x_units

            if l_units < min_units:
                continue

            weights = {
                "Prophet": p_units / units,
                "XGBoost": x_units / units,
                "LSTM": l_units / units,
            }

            mae = calculate_metrics(y_true, combine(predictions, weights))["MAE"]

            if mae < best_mae:
                best_mae = mae
                best_weights = weights

    if best_weights is None:
        raise RuntimeError("Could not find valid ensemble weights.")

    return best_weights, best_mae


def explain_predictions(
    dates: pd.Series,
    predictions: dict,
    weights: dict,
) -> pd.DataFrame:
    """
    Per-date explanation: each model's raw forecast and its contribution
    (weight x forecast) to the ensemble value. Contributions sum to the
    ensemble prediction exactly.
    """

    table = pd.DataFrame({"Date": pd.to_datetime(dates).to_numpy()})

    for name in MODEL_NAMES:
        table[f"{name}_forecast"] = predictions[name]
        table[f"{name}_contribution"] = weights[name] * predictions[name]

    table["Ensemble"] = combine(predictions, weights)
    table["top_contributor"] = table[
        [f"{name}_contribution" for name in MODEL_NAMES]
    ].idxmax(axis=1).str.replace("_contribution", "", regex=False)

    return table


def predict_all(history_df: pd.DataFrame, forecast_df: pd.DataFrame) -> dict:
    return {
        "Prophet": fit_prophet_and_predict(history_df, forecast_df),
        "XGBoost": fit_xgboost_and_predict(history_df, forecast_df),
        "LSTM": fit_lstm_and_predict(history_df, forecast_df),
    }


def evaluate_all(actual: np.ndarray, predictions: dict, title: str) -> dict:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    results = {}
    for name, pred in predictions.items():
        metrics = calculate_metrics(actual, pred)
        results[name] = metrics
        print(
            f"{name:<26} MAE: {metrics['MAE']:.4f} | "
            f"RMSE: {metrics['RMSE']:.4f} | MAPE: {metrics['MAPE']:.4f}"
        )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_ensemble():
    set_seeds()

    df = generate_data(days=DATASET_DAYS)
    train_df, validation_df, test_df = create_time_split(df)
    train_val_df = pd.concat([train_df, validation_df], ignore_index=True)

    print(f"Train      : {train_df['Date'].iloc[0].date()} -> {train_df['Date'].iloc[-1].date()}")
    print(f"Validation : {validation_df['Date'].iloc[0].date()} -> {validation_df['Date'].iloc[-1].date()}")
    print(f"Test       : {test_df['Date'].iloc[0].date()} -> {test_df['Date'].iloc[-1].date()}")

    actual_val = validation_df["Demand"].to_numpy(dtype=np.float64)
    actual_test = test_df["Demand"].to_numpy(dtype=np.float64)

    # 1. Validation: models see train only.
    val_preds = predict_all(train_df, validation_df)

    weights, _ = find_best_ensemble_weights(actual_val, val_preds, min_weight=0.05)
    free_weights, _ = find_best_ensemble_weights(actual_val, val_preds, min_weight=0.0)

    val_report = dict(val_preds)
    val_report["Ensemble (forced 3)"] = combine(val_preds, weights)
    val_report["Ensemble (unconstrained)"] = combine(val_preds, free_weights)
    val_metrics = evaluate_all(actual_val, val_report, "VALIDATION (trained on train)")

    print(f"\nForced weights        : {weights}")
    print(f"Unconstrained weights : {free_weights}")

    # 2. Test: refit on train + validation so there is no 150-day gap.
    test_preds = predict_all(train_val_df, test_df)

    test_report = dict(test_preds)
    test_report["Ensemble (forced 3)"] = combine(test_preds, weights)
    test_report["Ensemble (unconstrained)"] = combine(test_preds, free_weights)
    test_metrics = evaluate_all(actual_test, test_report, "TEST (trained on train + validation)")

    best_single = min(MODEL_NAMES, key=lambda name: test_metrics[name]["MAE"])
    ensemble_mae = test_metrics["Ensemble (forced 3)"]["MAE"]
    best_mae = test_metrics[best_single]["MAE"]
    change = (best_mae - ensemble_mae) / best_mae * 100

    print(f"\nBest single model on test: {best_single} (MAE {best_mae:.4f})")
    print(f"Ensemble vs {best_single}: {change:+.2f}% MAE (positive = ensemble better)")

    explanation = explain_predictions(test_df["Date"], test_preds, weights)
    explanation_path = os.path.join(OUTPUT_DIR, "ensemble_test_explanations.csv")
    explanation.to_csv(explanation_path, index=False)
    print(f"\nPer-date explanations written to {explanation_path}")
    print(explanation.head().to_string(index=False))

    # 3. Log everything to MLflow.
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-Three-Model-Ensemble")

    with mlflow.start_run(run_name="prophet_xgboost_lstm_ensemble"):
        mlflow.log_params({
            "dataset_days": DATASET_DAYS,
            "random_seed": RANDOM_SEED,
            "train_rows": len(train_df),
            "validation_rows": len(validation_df),
            "test_rows": len(test_df),
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "weight_step": 0.05,
            "min_weight": 0.05,
            **{f"weight_{k}": v for k, v in weights.items()},
            **{f"free_weight_{k}": v for k, v in free_weights.items()},
        })

        for split, metrics in (("val", val_metrics), ("test", test_metrics)):
            for name, values in metrics.items():
                key = name.replace(" ", "_").replace("(", "").replace(")", "")
                for metric, value in values.items():
                    mlflow.log_metric(f"{split}_{key}_{metric}", value)

        mlflow.log_metric("test_ensemble_vs_best_single_pct", change)
        mlflow.log_artifact(explanation_path)

    return weights, test_metrics


if __name__ == "__main__":
    run_ensemble()