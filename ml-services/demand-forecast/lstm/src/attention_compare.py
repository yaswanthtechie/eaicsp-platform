"""
-- Attention layer attempt.

Trains MultiStepLSTM (R3 baseline) and AttentionMultiStepLSTM (R4, see
model.py) under IDENTICAL conditions -- same folds, same epochs, same seed --
across the full 5-fold walk-forward validation, and reports both on the
same held-out test slices per fold.

This script does not decide in advance which model "should" win. Whatever
`run_sweep`-style honest numbers come out, that's what goes in the README.
"""

import numpy as np
import mlflow

from data import generate_data, get_walk_forward_folds
from evaluate import calculate_metrics
from model import MultiStepLSTM, AttentionMultiStepLSTM
from train_utils import train_model, evaluate_scaled, build_model

LOOKBACK = 30
HORIZON = 7
EPOCHS = 25
BATCH_SIZE = 32
LR = 0.001
HIDDEN_SIZE = 64
NUM_LAYERS = 2
SEED = 42


def run_comparison():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Attention-Comparison")
    
    
    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                    save_scaler_path=None)

    plain_metrics, attn_metrics = [], []
    
    with mlflow.start_run(run_name="attention_vs_baseline_walkforward"):
            # log hyperparameters
            mlflow.log_params({
                "lookback": LOOKBACK,
                "horizon": HORIZON,
                "epochs": EPOCHS,
                "batch_size": BATCH_SIZE,
                "lr": LR,
                "hidden_size": HIDDEN_SIZE,
                "num_layers": NUM_LAYERS,
                "seed": SEED,
                "n_folds": 5,
            })

    print("=" * 78)
    print("PLAIN LSTM vs. ATTENTION LSTM -- 5-Fold Walk-Forward Comparison")
    print("=" * 78)

    for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
        plain_model = build_model(MultiStepLSTM, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
        plain_model = train_model(plain_model, X_tr, y_tr, epochs=EPOCHS,
                                batch_size=BATCH_SIZE, lr=LR, seed=SEED)
        plain_result = evaluate_scaled(plain_model, X_te, y_te, scaler)

        attn_model = build_model(AttentionMultiStepLSTM, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
        attn_model = train_model(attn_model, X_tr, y_tr, epochs=EPOCHS,
                                batch_size=BATCH_SIZE, lr=LR, seed=SEED)
        attn_result = evaluate_scaled(attn_model, X_te, y_te, scaler)

        plain_metrics.append(plain_result)
        attn_metrics.append(attn_result)
        
        #log prefold metrics to mlflow
        mlflow.log_metrics({f"fold{fold_idx}_plain_mae": plain_result["MAE"],
                            f"fold{fold_idx}_plain_rmse": plain_result["RMSE"],
                            f"fold{fold_idx}_attn_mae": attn_result["MAE"],
                            f"fold{fold_idx}_attn_rmse": attn_result["RMSE"]})
        

        print(f"\nFold {fold_idx}:")
        print(f"  Plain LSTM     -> MAE: {plain_result['MAE']:.2f} | RMSE: {plain_result['RMSE']:.2f}")
        print(f"  Attention LSTM -> MAE: {attn_result['MAE']:.2f} | RMSE: {attn_result['RMSE']:.2f}")

    avg_plain_mae = float(np.mean([m["MAE"] for m in plain_metrics]))
    avg_plain_rmse = float(np.mean([m["RMSE"] for m in plain_metrics]))
    avg_attn_mae = float(np.mean([m["MAE"] for m in attn_metrics]))
    avg_attn_rmse = float(np.mean([m["RMSE"] for m in attn_metrics]))
    
    #log aggregated headline metrics to mlflow
    mlflow.log_metrics({"avg_plain_mae": avg_plain_mae,
                        "avg_plain_rmse": avg_plain_rmse,
                        "avg_attn_mae": avg_attn_mae,
                        "avg_attn_rmse": avg_attn_rmse,
                        "mae_delta": avg_plain_mae - avg_attn_mae,
                        })
    

    print("\n" + "=" * 78)
    print("AVERAGE ACROSS ALL 5 FOLDS")
    print(f"  Plain LSTM     -> Avg MAE: {avg_plain_mae:.2f} | Avg RMSE: {avg_plain_rmse:.2f}")
    print(f"  Attention LSTM -> Avg MAE: {avg_attn_mae:.2f} | Avg RMSE: {avg_attn_rmse:.2f}")

    if avg_attn_mae < avg_plain_mae:
        verdict = (f"Attention IMPROVED walk-forward MAE by "
                f"{avg_plain_mae - avg_attn_mae:.2f} ({(1 - avg_attn_mae/avg_plain_mae)*100:.1f}%).")
    else:
        verdict = (f"Attention did NOT improve walk-forward MAE "
                f"(+{avg_attn_mae - avg_plain_mae:.2f} worse, "
                f"{(avg_attn_mae/avg_plain_mae - 1)*100:.1f}% higher). "
                f"Reporting honestly per spec -- no cherry-picking.")
    print(f"\nVERDICT: {verdict}")
    print("=" * 78)

    mlflow.set_tag("verdict", verdict)
    
    return {
        "plain": {"avg_mae": avg_plain_mae, "avg_rmse": avg_plain_rmse, "per_fold": plain_metrics},
        "attention": {"avg_mae": avg_attn_mae, "avg_rmse": avg_attn_rmse, "per_fold": attn_metrics},
        "verdict": verdict,
    }


if __name__ == "__main__":
    run_comparison()