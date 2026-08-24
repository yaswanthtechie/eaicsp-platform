"""
Walk-Forward Training & MLflow Experiment Logging
------------------------------------------------------------
Executes 5-Fold Walk-Forward Validation, logs metrics to MLflow,
and exports the final trained PyTorch model weights.
"""

import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import mlflow

from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from evaluate import calculate_metrics, predict_naive_baseline
from config import LOOKBACK, HORIZON, HIDDEN_SIZE, NUM_LAYERS, DROPOUT, LR, EPOCHS, BATCH_SIZE

torch.manual_seed(42)  # For reproducibility


def train_and_evaluate():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-WalkForward")

    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON)

    lstm_fold_metrics = []
    naive_fold_metrics = []

    with mlflow.start_run(run_name="LSTM_5Fold_WalkForward_Validation"):
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
            "epochs": EPOCHS,
            "batch_size": BATCH_SIZE,
            "learning_rate": LR,
            "forecast_style": "Direct"
        })

        print("\n" + "="*70)
        print("STARTING 5-FOLD TIME-SERIES WALK-FORWARD VALIDATION")
        print("="*70)

        for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
            # X_tr and X_te are already 3D (samples, lookback, 1) from data.py
            X_train_t = torch.tensor(X_tr, dtype=torch.float32)
            if X_train_t.ndim == 2:
                X_train_t = X_train_t.unsqueeze(-1)

            y_train_t = torch.tensor(y_tr, dtype=torch.float32)

            X_test_t = torch.tensor(X_te, dtype=torch.float32)
            if X_test_t.ndim == 2:
                X_test_t = X_test_t.unsqueeze(-1)

            # 1. Instantiate dataset FIRST
            dataset = TensorDataset(X_train_t, y_train_t)

            # 2. Build DataLoader with shuffle=True for stochastic training
            loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

            model = MultiStepLSTM(
                input_size=1,
                hidden_size=HIDDEN_SIZE,
                num_layers=NUM_LAYERS,
                horizon=HORIZON,
                dropout=DROPOUT
            )
            criterion = nn.MSELoss()
            optimizer = optim.Adam(model.parameters(), lr=LR)

            model.train()
            for epoch in range(EPOCHS):
                for batch_x, batch_y in loader:
                    optimizer.zero_grad()
                    out = model(batch_x)
                    loss = criterion(out, batch_y)
                    loss.backward()
                    optimizer.step()

            model.eval()
            with torch.no_grad():
                lstm_preds_scaled = model(X_test_t).numpy()

            lstm_preds = scaler.inverse_transform(lstm_preds_scaled.reshape(-1, 1)).reshape(lstm_preds_scaled.shape)
            y_test_orig = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)

            lstm_metrics = calculate_metrics(y_test_orig, lstm_preds)
            
            naive_preds_scaled = predict_naive_baseline(X_te, HORIZON)
            naive_preds = scaler.inverse_transform(naive_preds_scaled.reshape(-1, 1)).reshape(naive_preds_scaled.shape)
            naive_metrics = calculate_metrics(y_test_orig, naive_preds)

            lstm_fold_metrics.append(lstm_metrics)
            naive_fold_metrics.append(naive_metrics)

            print(f"\n--- FOLD {fold_idx} RESULTS ---")
            print(f"LSTM  -> MAE: {lstm_metrics['MAE']:.2f} | RMSE: {lstm_metrics['RMSE']:.2f}")
            print(f"NAIVE -> MAE: {naive_metrics['MAE']:.2f} | RMSE: {naive_metrics['RMSE']:.2f}")

            mlflow.log_metrics({
                f"fold_{fold_idx}_lstm_mae": lstm_metrics["MAE"],
                f"fold_{fold_idx}_lstm_rmse": lstm_metrics["RMSE"],
                f"fold_{fold_idx}_naive_mae": naive_metrics["MAE"],
            })

        avg_lstm_mae = float(np.mean([m["MAE"] for m in lstm_fold_metrics]))
        avg_lstm_rmse = float(np.mean([m["RMSE"] for m in lstm_fold_metrics]))
        avg_naive_mae = float(np.mean([m["MAE"] for m in naive_fold_metrics]))
        avg_naive_rmse = float(np.mean([m["RMSE"] for m in naive_fold_metrics]))

        print("\n" + "="*70)
        print("AVERAGE METRICS ACROSS ALL 5 FOLDS")
        print(f"LSTM Model  -> Avg MAE: {avg_lstm_mae:.2f} | Avg RMSE: {avg_lstm_rmse:.2f}")
        print(f"Naive Model -> Avg MAE: {avg_naive_mae:.2f} | Avg RMSE: {avg_naive_rmse:.2f}")
        print("="*70 + "\n")

        mlflow.log_metrics({
            "avg_lstm_mae": avg_lstm_mae,
            "avg_lstm_rmse": avg_lstm_rmse,
            "avg_naive_mae": avg_naive_mae,
            "avg_naive_rmse": avg_naive_rmse,
        })

        os.makedirs("output", exist_ok=True)
        model_path = "output/best_model.pt"
        torch.save(model.state_dict(), model_path)
        mlflow.log_artifact(model_path)
        print(f"Saved PyTorch weights to {model_path}")


if __name__ == "__main__":
    train_and_evaluate()