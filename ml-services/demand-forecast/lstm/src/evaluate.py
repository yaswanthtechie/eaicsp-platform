import os
import numpy as np
import torch
import joblib
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    mean_absolute_percentage_error,
)

from data import generate_data, load_scaler, scale_test_data
from features import create_sequences
from model import DemandLSTM
import mlflow_logger  # MLflow wrapper import


def evaluate_model():
    LOOKBACK = 30
    HORIZON = 7
    TRAIN_SPLIT = 800  # First 800 days were used for training

    # -----------------------
    # 1. Load Data & Persisted Scaler (Fixes Data Leakage)
    # -----------------------
    df = generate_data()
    raw_series = df["Demand"].values

    # Load fitted scaler from training step
    scaler_path = "output/scaler.pkl"
    scaler = load_scaler(scaler_path)

    # We evaluate on the held-out test data (days 800 to 1000)
    # Include LOOKBACK history from train data so sequence generation starts at day 800
    test_raw_with_history = raw_series[TRAIN_SPLIT - LOOKBACK :]
    test_scaled = scale_test_data(test_raw_with_history, scaler)

    # Create sequences strictly for the test set
    X_test, y_test = create_sequences(
        test_scaled, lookback=LOOKBACK, horizon=HORIZON
    )

    # -----------------------
    # 2. Load Model
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
    # 3. Walk-Forward Validation Loop
    # -----------------------
    predictions = []

    # Step through time step by step over the test set
    for i in range(len(X_test)):
        # Extract single input window
        sample = torch.tensor(
            X_test[i : i + 1], dtype=torch.float32
        )

        with torch.no_grad():
            pred = model(sample)

        predictions.append(pred.numpy()[0])

    predictions = np.array(predictions)

    # -----------------------
    # 4. Inverse Scaling
    # -----------------------
    pred_inv = scaler.inverse_transform(
        predictions.reshape(-1, 1)
    ).reshape(predictions.shape)

    actual_inv = scaler.inverse_transform(
        y_test.reshape(-1, 1)
    ).reshape(y_test.shape)

    # -----------------------
    # 5. Model Metrics
    # -----------------------
    mae = mean_absolute_error(actual_inv.flatten(), pred_inv.flatten())
    rmse = np.sqrt(mean_squared_error(actual_inv.flatten(), pred_inv.flatten()))
    mape = mean_absolute_percentage_error(actual_inv.flatten(), pred_inv.flatten())

    print("\n--- LSTM RESULTS (Held-Out Test Set) ---")
    print(f"MAE  : {mae:.4f}")
    print(f"RMSE : {rmse:.4f}")
    print(f"MAPE : {mape:.4f}")

    # -----------------------
    # 6. Naive Baseline Comparison
    # -----------------------
    naive = []
    for row in X_test:
        last_val = row[-1]
        naive.append(np.repeat(last_val, HORIZON))

    naive = np.array(naive)
    naive_inv = scaler.inverse_transform(
        naive.reshape(-1, 1)
    ).reshape(naive.shape)

    naive_mae = mean_absolute_error(actual_inv.flatten(), naive_inv.flatten())
    naive_rmse = np.sqrt(mean_squared_error(actual_inv.flatten(), naive_inv.flatten()))

    print("\n--- NAIVE BASELINE ---")
    print(f"MAE  : {naive_mae:.4f}")
    print(f"RMSE : {naive_rmse:.4f}")

    # -----------------------
    # 7. Log Results to MLflow
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