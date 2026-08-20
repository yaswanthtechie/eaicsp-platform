import mlflow
import numpy as np
import torch
from data import generate_data, get_walk_forward_folds
from model import AttentionMultiStepLSTM, MultiStepLSTM
from train_utils import train_model


def compare_models():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Attention-Compare")

    lookback = 30
    horizon = 7
    epochs = 25
    n_folds = 5

    with mlflow.start_run(run_name="Attention-vs-Plain-5Fold"):
        mlflow.log_params({
            "lookback": lookback,
            "horizon": horizon,
            "epochs": epochs,
            "n_folds": n_folds,
        })

        df = generate_data()
        folds = get_walk_forward_folds(df, n_folds=n_folds, lookback=lookback, horizon=horizon)

        plain_maes = []
        attn_maes = []

        for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
            # Ensure 3D input shape (batch_size, lookback, 1)
            if X_te.ndim == 2:
                X_te_3d = X_te[:, :, np.newaxis]
            else:
                X_te_3d = X_te

            x_tensor = torch.tensor(X_te_3d, dtype=torch.float32)

            # 1. Plain LSTM
            torch.manual_seed(42)
            plain_model = MultiStepLSTM(1, 64, 2, horizon)
            train_model(plain_model, X_tr, y_tr, epochs=epochs)
            plain_model.eval()
            with torch.no_grad():
                pred = plain_model(x_tensor).numpy()
                pred_inv = scaler.inverse_transform(pred)
                y_inv = scaler.inverse_transform(y_te)
                mae_plain = float(np.mean(np.abs(pred_inv - y_inv)))
                plain_maes.append(mae_plain)

            # 2. Attention LSTM
            torch.manual_seed(42)
            attn_model = AttentionMultiStepLSTM(1, 64, 2, horizon)
            train_model(attn_model, X_tr, y_tr, epochs=epochs)
            attn_model.eval()
            with torch.no_grad():
                pred_at = attn_model(x_tensor).numpy()
                pred_at_inv = scaler.inverse_transform(pred_at)
                mae_attn = float(np.mean(np.abs(pred_at_inv - y_inv)))
                attn_maes.append(mae_attn)

            mlflow.log_metric(f"fold_{fold_idx}_plain_mae", mae_plain)
            mlflow.log_metric(f"fold_{fold_idx}_attn_mae", mae_attn)

        avg_plain = float(np.mean(plain_maes))
        avg_attn = float(np.mean(attn_maes))
        verdict = "Plain LSTM Won" if avg_plain <= avg_attn else "Attention LSTM Won"

        # Strictly inside active run
        mlflow.log_metric("avg_plain_mae", avg_plain)
        mlflow.log_metric("avg_attn_mae", avg_attn)
        mlflow.set_tag("verdict", verdict)

        print(f"Comparison Done -> Plain MAE: {avg_plain:.4f} | Attention MAE: {avg_attn:.4f} | Verdict: {verdict}")


if __name__ == "__main__":
    compare_models()