"""
Unified Hyperparameter Sweep (Plain LSTM vs. Attention LSTM)
Strictly selects winner on validation MAE (no test data leakage).
"""

import itertools
import os
import mlflow
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from config import (
    BATCH_SIZE,
    EPOCHS,
    HORIZON,
    LOOKBACK,
    N_FOLDS,
    RANDOM_SEED,
)
from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from train_utils import chronological_train_val_split


def set_seed(seed=RANDOM_SEED):
    torch.manual_seed(seed)
    np.random.seed(seed)


def run_systematic_sweep():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-R5-Systematic-Sweep")

    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=N_FOLDS, lookback=LOOKBACK, horizon=HORIZON)

    # Search Space includes Attention alongside core architectures
    grid = {
        "hidden_size": [32, 64],
        "num_layers": [1, 2],
        "dropout": [0.1, 0.2],
        "lr": [0.001, 0.005],
        "use_attention": [False, True],
    }

    keys, values = zip(*grid.items())
    configurations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    print("=" * 95)
    print(f"STARTING SYSTEMATIC HYPERPARAMETER SWEEP ({len(configurations)} Configurations)")
    print("=" * 95)

    results = []

    for idx, config in enumerate(configurations, 1):
        val_maes, val_rmses = [], []
        test_maes, test_rmses = [], []

        attn_label = "Attn" if config["use_attention"] else "Plain"
        run_name = f"cfg_{idx:02d}_{attn_label}_h{config['hidden_size']}_l{config['num_layers']}_lr{config['lr']}"

        with mlflow.start_run(run_name=run_name):
            mlflow.log_params({
                **config,
                "epochs": EPOCHS,
                "batch_size": BATCH_SIZE,
                "n_folds": N_FOLDS,
                "lookback": LOOKBACK,
                "horizon": HORIZON,
                "seed": RANDOM_SEED,
            })

            for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
                # Chronological train/val split to prevent test leakage
                X_inner_tr, y_inner_tr, X_val, y_val = chronological_train_val_split(
                    X_tr, y_tr, val_fraction=0.2
                )

                # Format training tensors
                X_train_t = torch.tensor(X_inner_tr, dtype=torch.float32)
                if X_train_t.ndim == 2:
                    X_train_t = X_train_t.unsqueeze(-1)
                y_train_t = torch.tensor(y_inner_tr, dtype=torch.float32)

                # Format validation tensors (used for ranking & winner selection)
                X_val_t = torch.tensor(X_val, dtype=torch.float32)
                if X_val_t.ndim == 2:
                    X_val_t = X_val_t.unsqueeze(-1)

                # Format test tensors (reference only)
                X_test_t = torch.tensor(X_te, dtype=torch.float32)
                if X_test_t.ndim == 2:
                    X_test_t = X_test_t.unsqueeze(-1)

                # Deterministic initialization for batching and model weights
                set_seed(RANDOM_SEED)

                dataset = TensorDataset(X_train_t, y_train_t)
                loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

                model = MultiStepLSTM(
                    input_size=1,
                    hidden_size=config["hidden_size"],
                    num_layers=config["num_layers"],
                    horizon=HORIZON,
                    dropout=config["dropout"],
                    use_attention=config["use_attention"],
                )
                optimizer = torch.optim.Adam(model.parameters(), lr=config["lr"])
                criterion = nn.MSELoss()

                model.train()
                for _ in range(EPOCHS):
                    for bx, by in loader:
                        optimizer.zero_grad()
                        pred = model(bx)
                        loss = criterion(pred, by)
                        loss.backward()
                        optimizer.step()

                model.eval()
                with torch.no_grad():
                    val_preds_scaled = model(X_val_t).numpy()
                    test_preds_scaled = model(X_test_t).numpy()

                # Invert scaling
                val_preds = scaler.inverse_transform(val_preds_scaled.reshape(-1, 1)).reshape(val_preds_scaled.shape)
                y_val_true = scaler.inverse_transform(y_val.reshape(-1, 1)).reshape(y_val.shape)

                test_preds = scaler.inverse_transform(test_preds_scaled.reshape(-1, 1)).reshape(test_preds_scaled.shape)
                y_test_true = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)

                # Compute fold metrics
                val_maes.append(mean_absolute_error(y_val_true, val_preds))
                val_rmses.append(np.sqrt(mean_squared_error(y_val_true, val_preds)))

                test_maes.append(mean_absolute_error(y_test_true, test_preds))
                test_rmses.append(np.sqrt(mean_squared_error(y_test_true, test_preds)))

            avg_val_mae = float(np.mean(val_maes))
            avg_val_rmse = float(np.mean(val_rmses))
            avg_test_mae = float(np.mean(test_maes))
            avg_test_rmse = float(np.mean(test_rmses))

            mlflow.log_metrics({
                "avg_val_mae": avg_val_mae,
                "avg_val_rmse": avg_val_rmse,
                "avg_test_mae_reference_only": avg_test_mae,
                "avg_test_rmse_reference_only": avg_test_rmse,
            })

            res_entry = {
                **config,
                "run_name": run_name,
                "avg_val_mae": avg_val_mae,
                "avg_val_rmse": avg_val_rmse,
                "avg_test_mae": avg_test_mae,
                "avg_test_rmse": avg_test_rmse,
            }
            results.append(res_entry)

            attn_str = "ATTENTION" if config["use_attention"] else "PLAIN"
            print(f"[{idx:02d}/{len(configurations):02d}] {attn_str:<9} | Hidden: {config['hidden_size']:2d} | Layers: {config['num_layers']} | LR: {config['lr']} | Val MAE: {avg_val_mae:.2f} | (Test MAE Ref: {avg_test_mae:.2f})")

    # Winner is strictly selected on validation MAE
    results.sort(key=lambda x: x["avg_val_mae"])
    winner = results[0]

    print("\n" + "=" * 95)
    print("SWEEP RESULTS (Ranked by Validation MAE -- Test MAE shown for reference only)")
    print("=" * 95)
    print(f"{'Rank':<5} {'Architecture':<12} {'Hidden':<8} {'Layers':<8} {'Dropout':<9} {'LR':<8} {'Val MAE':<10} {'Test MAE(Ref)':<14}")
    print("-" * 95)
    for r, c in enumerate(results[:5], 1):
        arch = "Attention" if c["use_attention"] else "Plain"
        marker = " <-- WINNER" if r == 1 else ""
        print(f"{r:<5} {arch:<12} {c['hidden_size']:<8} {c['num_layers']:<8} {c['dropout']:<9} {c['lr']:<8} {c['avg_val_mae']:<10.2f} {c['avg_test_mae']:<14.2f}{marker}")
    print("=" * 95)
    print(f"\nWinner selected on validation split: {winner['run_name']} (Val MAE: {winner['avg_val_mae']:.2f})\n")


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    run_systematic_sweep()