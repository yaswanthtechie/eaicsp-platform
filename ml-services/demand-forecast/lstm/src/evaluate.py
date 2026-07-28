import os
import numpy as np
import torch
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    mean_absolute_percentage_error,
)

from data import generate_data
from model import DemandLSTM
import mlflow_logger  # MLflow wrapper import


def evaluate_model():
    LOOKBACK = 30
    HORIZON = 7
    TRAIN_SPLIT = 800  # First 800 days were used for training

    # -----------------------
    # 1. Load Raw Data
    # -----------------------
    df = generate_data()
    raw_series = df["Demand"].values

    # -----------------------
    # 2. Load Model Checkpoint
    # -----------------------
    model_path = "output/best_model.pt"
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model checkpoint not found at {model_path}")

    model = DemandLSTM(
        input_size=1,
        hidden_size=64,
        num_layers=2,
        horizon=HORIZON
    )
    model.load_state_dict(torch.load(model_path))
    model.eval()

    # -----------------------
    # 3. True Walk-Forward Validation Loop
    # -----------------------
    predictions = []
    actuals = []
    naive_preds = []

    # Rolling/Expanding boundary through the test set (from TRAIN_SPLIT to end of series)
    for t in range(TRAIN_SPLIT, len(raw_series) - HORIZON + 1):
        # 1. Historical train window strictly up to time t (No Data Leakage)
        train_history = raw_series[:t]

        # 2. Extract sequence input (t - LOOKBACK to t) and true ground truth (t to t + HORIZON)
        input_seq_raw = raw_series[t - LOOKBACK : t]
        actual_target_raw = raw_series[t : t + HORIZON]

        # 3. Fit scaler strictly on history available up to step t
        scaler =MinMaxScaler ()
        scaler.fit(train_history.reshape(-1, 1))

        # 4. Scale sequence input
        input_seq_scaled = scaler.transform(input_seq_raw.reshape(-1, 1))
        input_tensor = torch.tensor(
            input_seq_scaled.reshape(1, LOOKBACK, 1), dtype=torch.float32
        )

        # 5. Predict via model
        with torch.no_grad():
            pred_scaled = model(input_tensor)

        # 6. Unscale prediction with current step's scaler
        pred_unscaled = scaler.inverse_transform(
            pred_scaled.numpy().reshape(-1, 1)
        ).flatten()

        # Save model predictions & actuals
        predictions.append(pred_unscaled)
        actuals.append(actual_target_raw)

        # 7. Naive Baseline (Repeat last observed value across HORIZON)
        last_observed_val = input_seq_raw[-1]
        naive_preds.append(np.repeat(last_observed_val, HORIZON))

    predictions = np.array(predictions)
    actuals = np.array(actuals)
    naive_preds = np.array(naive_preds)

    # -----------------------
    # 4. Model Metrics
    # -----------------------
    mae = mean_absolute_error(actuals.flatten(), predictions.flatten())
    rmse = np.sqrt(mean_squared_error(actuals.flatten(), predictions.flatten()))
    mape = mean_absolute_percentage_error(actuals.flatten(), predictions.flatten())

    print("\n--- LSTM RESULTS (True Walk-Forward Test Set) ---")
    print(f"MAE  : {mae:.4f}")
    print(f"RMSE : {rmse:.4f}")
    print(f"MAPE : {mape:.4f}")

    # -----------------------
    # 5. Naive Baseline Comparison
    # -----------------------
    naive_mae = mean_absolute_error(actuals.flatten(), naive_preds.flatten())
    naive_rmse = np.sqrt(mean_squared_error(actuals.flatten(), naive_preds.flatten()))

    print("\n--- NAIVE BASELINE ---")
    print(f"MAE  : {naive_mae:.4f}")
    print(f"RMSE : {naive_rmse:.4f}")

    # -----------------------
    # 6. Log Results to MLflow
    # -----------------------
    mlflow_logger.start_experiment("demand_forecast_lstm")
    mlflow_logger.log_metrics({
        "test_mae": mae,
        "test_rmse": rmse,
        "test_mape": mape,
        "naive_mae": naive_mae,
        "naive_rmse": naive_rmse,
    })


if __name__ == "__main__":
    evaluate_model()