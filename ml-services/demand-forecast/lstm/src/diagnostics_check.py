import os
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from config import EPOCHS, HIDDEN_SIZE, HORIZON, LOOKBACK, LOSS_CURVE_PATH, NUM_LAYERS, OUTPUT_DIR, RANDOM_SEED
from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM


def train_and_track_loss(model, X_train, y_train, epochs=EPOCHS, lr=0.001):
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    if X_train.ndim == 2:
        X_train_3d = X_train[:, :, np.newaxis]
    elif X_train.ndim == 4:
        X_train_3d = X_train.squeeze(-1)
    else:
        X_train_3d = X_train

    x_tensor = torch.tensor(X_train_3d, dtype=torch.float32)
    y_tensor = torch.tensor(y_train, dtype=torch.float32)

    model.train()
    history = []
    for _ in range(epochs):
        optimizer.zero_grad()
        out = model(x_tensor)
        loss = criterion(out, y_tensor)
        loss.backward()
        optimizer.step()
        history.append(loss.item())
    return history


def run_diagnostics():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Diagnostics")

    n_folds = 5
    with mlflow.start_run(run_name="Diagnostics-5Fold-Sanity"):
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "epochs": EPOCHS,
            "n_folds": n_folds,
            "seed": RANDOM_SEED,
        })

        df = generate_data()
        folds = get_walk_forward_folds(df, n_folds=n_folds, lookback=LOOKBACK, horizon=HORIZON)

        lstm_maes, lstm_rmses = [], []
        naive_maes, naive_rmses = [], []
        loss_histories = []

        print("\n--- Diagnostic Checks 1-3 & Baseline Sanity ---")
        for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
            if X_te.ndim == 2:
                X_te_3d = X_te[:, :, np.newaxis]
            elif X_te.ndim == 4:
                X_te_3d = X_te.squeeze(-1)
            else:
                X_te_3d = X_te

            x_tensor = torch.tensor(X_te_3d, dtype=torch.float32)

            torch.manual_seed(RANDOM_SEED)
            model = MultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
            history = train_and_track_loss(model, X_tr, y_tr, epochs=EPOCHS)
            loss_histories.append(history)

            model.eval()
            with torch.no_grad():
                pred = model(x_tensor).numpy()
                pred_inv = scaler.inverse_transform(pred)
                y_inv = scaler.inverse_transform(y_te)
                mae_l = float(np.mean(np.abs(pred_inv - y_inv)))
                rmse_l = float(np.sqrt(np.mean((pred_inv - y_inv) ** 2)))
                lstm_maes.append(mae_l)
                lstm_rmses.append(rmse_l)

            # Persistence Naive Baseline
            naive_pred = np.repeat(X_te_3d[:, -1:, :], HORIZON, axis=1).squeeze(-1)
            naive_inv = scaler.inverse_transform(naive_pred)
            mae_n = float(np.mean(np.abs(naive_inv - y_inv)))
            rmse_n = float(np.sqrt(np.mean((naive_inv - y_inv) ** 2)))
            naive_maes.append(mae_n)
            naive_rmses.append(rmse_n)

            mlflow.log_metric(f"fold_{fold_idx}_lstm_mae", mae_l)
            mlflow.log_metric(f"fold_{fold_idx}_naive_mae", mae_n)

        avg_lstm_mae = float(np.mean(lstm_maes))
        avg_lstm_rmse = float(np.mean(lstm_rmses))
        avg_naive_mae = float(np.mean(naive_maes))
        avg_naive_rmse = float(np.mean(naive_rmses))

        mlflow.log_metric("avg_lstm_mae", avg_lstm_mae)
        mlflow.log_metric("avg_lstm_rmse", avg_lstm_rmse)
        mlflow.log_metric("avg_naive_mae", avg_naive_mae)
        mlflow.log_metric("avg_naive_rmse", avg_naive_rmse)

        # Generate loss curve plot
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        plt.figure(figsize=(8, 4))
        for i, hist in enumerate(loss_histories, 1):
            plt.plot(hist, label=f"Fold {i}")
        plt.title("Training Loss Curve Across Folds")
        plt.xlabel("Epoch")
        plt.ylabel("MSE Loss")
        plt.legend()
        plt.tight_layout()
        plt.savefig(LOSS_CURVE_PATH)
        plt.close()
        mlflow.log_artifact(LOSS_CURVE_PATH)

        print(f"Avg LSTM MAE: {avg_lstm_mae:.4f} | RMSE: {avg_lstm_rmse:.4f}")
        print(f"Avg Naive MAE: {avg_naive_mae:.4f} | RMSE: {avg_naive_rmse:.4f}")
        print(f"Loss curve saved to {LOSS_CURVE_PATH}\n")


if __name__ == "__main__":
    run_diagnostics()