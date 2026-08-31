import mlflow
import numpy as np
import torch
from config import EPOCHS, HIDDEN_SIZE, HORIZON, LOOKBACK, NUM_LAYERS, RANDOM_SEED
from data import generate_data, get_walk_forward_folds
from model import AttentionMultiStepLSTM, MultiStepLSTM
from train_utils import train_model


def compare_models():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Attention-Compare")

    n_folds = 5
    with mlflow.start_run(run_name="Attention-vs-Plain-5Fold"):
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "epochs": EPOCHS,
            "n_folds": n_folds,
            "seed": RANDOM_SEED,
        })

        df = generate_data()
        folds = get_walk_forward_folds(df, n_folds=n_folds, lookback=LOOKBACK, horizon=HORIZON)

        plain_maes, plain_rmses = [], []
        attn_maes, attn_rmses = [], []

        print("\n" + "=" * 65)
        print(f"{'Fold':<6}{'Plain MAE':<12}{'Plain RMSE':<12}{'Attn MAE':<12}{'Attn RMSE':<12}")
        print("-" * 65)

        for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
            # Ensure strictly 3D shape (samples, lookback, 1)
            if X_te.ndim == 2:
                X_te_3d = X_te[:, :, np.newaxis]
            elif X_te.ndim == 4:
                X_te_3d = X_te.squeeze(-1)
            else:
                X_te_3d = X_te
                
            x_tensor = torch.tensor(X_te_3d, dtype=torch.float32)

            # 1. Plain LSTM
            torch.manual_seed(RANDOM_SEED)
            plain_model = MultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
            train_model(plain_model, X_tr, y_tr, epochs=EPOCHS)
            plain_model.eval()
            with torch.no_grad():
                pred_p = plain_model(x_tensor).numpy()
                pred_p_inv = scaler.inverse_transform(pred_p)
                y_inv = scaler.inverse_transform(y_te)
                mae_p = float(np.mean(np.abs(pred_p_inv - y_inv)))
                rmse_p = float(np.sqrt(np.mean((pred_p_inv - y_inv) ** 2)))
                plain_maes.append(mae_p)
                plain_rmses.append(rmse_p)

            # 2. Attention LSTM
            torch.manual_seed(RANDOM_SEED)
            attn_model = AttentionMultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
            train_model(attn_model, X_tr, y_tr, epochs=EPOCHS)
            attn_model.eval()
            with torch.no_grad():
                pred_a = attn_model(x_tensor).numpy()
                pred_a_inv = scaler.inverse_transform(pred_a)
                mae_a = float(np.mean(np.abs(pred_a_inv - y_inv)))
                rmse_a = float(np.sqrt(np.mean((pred_a_inv - y_inv) ** 2)))
                attn_maes.append(mae_a)
                attn_rmses.append(rmse_a)

            print(f"{fold_idx:<6}{mae_p:<12.4f}{rmse_p:<12.4f}{mae_a:<12.4f}{rmse_a:<12.4f}")
            mlflow.log_metric(f"fold_{fold_idx}_plain_mae", mae_p)
            mlflow.log_metric(f"fold_{fold_idx}_plain_rmse", rmse_p)
            mlflow.log_metric(f"fold_{fold_idx}_attn_mae", mae_a)
            mlflow.log_metric(f"fold_{fold_idx}_attn_rmse", rmse_a)

        avg_p_mae, avg_p_rmse = float(np.mean(plain_maes)), float(np.mean(plain_rmses))
        avg_a_mae, avg_a_rmse = float(np.mean(attn_maes)), float(np.mean(attn_rmses))
        verdict = "Plain LSTM Won" if avg_p_mae <= avg_a_mae else "Attention LSTM Won"

        print("=" * 65)
        print(f"AVG   {avg_p_mae:<12.4f}{avg_p_rmse:<12.4f}{avg_a_mae:<12.4f}{avg_a_rmse:<12.4f}")
        print(f"Verdict: {verdict}\n")

        mlflow.log_metric("avg_plain_mae", avg_p_mae)
        mlflow.log_metric("avg_plain_rmse", avg_p_rmse)
        mlflow.log_metric("avg_attn_mae", avg_a_mae)
        mlflow.log_metric("avg_attn_rmse", avg_a_rmse)
        mlflow.set_tag("verdict", verdict)


if __name__ == "__main__":
    compare_models()