import mlflow
import numpy as np
import torch
from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from train_utils import train_model


def run_diagnostics():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Diagnostics")

    lookback = 30
    horizon = 7
    epochs = 25
    n_folds = 5

    with mlflow.start_run(run_name="Diagnostics-5Fold-Sanity"):
        mlflow.log_params({
            "lookback": lookback,
            "horizon": horizon,
            "epochs": epochs,
            "n_folds": n_folds,
        })

        df = generate_data()
        folds = get_walk_forward_folds(df, n_folds=n_folds, lookback=lookback, horizon=horizon)

        lstm_maes = []
        naive_maes = []

        for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
            if X_te.ndim == 2:
                X_te_3d = X_te[:, :, np.newaxis]
            else:
                X_te_3d = X_te

            x_tensor = torch.tensor(X_te_3d, dtype=torch.float32)

            torch.manual_seed(42)
            # Use positional arguments: (input_size, hidden_size, num_layers, horizon)
            model = MultiStepLSTM(1, 64, 2, horizon)
            train_model(model, X_tr, y_tr, epochs=epochs)
            model.eval()
            with torch.no_grad():
                pred = model(x_tensor).numpy()
                pred_inv = scaler.inverse_transform(pred)
                y_inv = scaler.inverse_transform(y_te)
                mae_lstm = float(np.mean(np.abs(pred_inv - y_inv)))
                lstm_maes.append(mae_lstm)

            # Persistence baseline of last lookback step
            naive_pred = np.repeat(X_te_3d[:, -1:, :], horizon, axis=1).squeeze(-1)
            naive_pred_inv = scaler.inverse_transform(naive_pred)
            mae_naive = float(np.mean(np.abs(naive_pred_inv - y_inv)))
            naive_maes.append(mae_naive)

            mlflow.log_metric(f"fold_{fold_idx}_lstm_mae", mae_lstm)
            mlflow.log_metric(f"fold_{fold_idx}_naive_mae", mae_naive)

        avg_lstm = float(np.mean(lstm_maes))
        avg_naive = float(np.mean(naive_maes))

        # Metrics contained strictly inside the active run block
        mlflow.log_metric("avg_lstm_mae", avg_lstm)
        mlflow.log_metric("avg_naive_mae", avg_naive)

        print(f"Diagnostics Done -> Avg LSTM MAE: {avg_lstm:.4f} | Avg Naive MAE: {avg_naive:.4f}")


if __name__ == "__main__":
    run_diagnostics()