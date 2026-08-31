"""
Unified Hyperparameter Sweep (Plain LSTM vs. Attention LSTM)
"""

import itertools
import mlflow
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch.utils.data import DataLoader, TensorDataset

from config import HORIZON, LOOKBACK
from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM


def set_seed(seed=42):
    torch.manual_seed(seed)
    np.random.seed(seed)


def run_systematic_sweep():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-R5-Systematic-Sweep")

    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=3, lookback=LOOKBACK, horizon=HORIZON)

    # Search Space includes Attention alongside architectures
    grid = {
        "hidden_size": [32, 64],
        "num_layers": [1, 2],
        "dropout": [0.1, 0.2],
        "lr": [0.001, 0.005],
        "use_attention": [False, True],
    }

    keys, values = zip(*grid.items())
    configurations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    print("=" * 85)
    print(f"STARTING SYSTEMATIC HYPERPARAMETER SWEEP ({len(configurations)} Configurations)")
    print("=" * 85)

    results = []

    for idx, config in enumerate(configurations, 1):
        set_seed(42)
        fold_maes, fold_rmses = [], []

        with mlflow.start_run(run_name=f"Config_{idx}_Attn_{config['use_attention']}"):
            mlflow.log_params(config)

            for fold_idx, (X_tr, y_tr, X_te, y_te, scaler) in enumerate(folds, 1):
                X_train_t = torch.tensor(X_tr, dtype=torch.float32)
                if X_train_t.ndim == 2:
                    X_train_t = X_train_t.unsqueeze(-1)
                y_train_t = torch.tensor(y_tr, dtype=torch.float32)

                X_test_t = torch.tensor(X_te, dtype=torch.float32)
                if X_test_t.ndim == 2:
                    X_test_t = X_test_t.unsqueeze(-1)

                dataset = TensorDataset(X_train_t, y_train_t)
                loader = DataLoader(dataset, batch_size=32, shuffle=True)

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
                for _ in range(50):
                    for bx, by in loader:
                        optimizer.zero_grad()
                        pred = model(bx)
                        loss = criterion(pred, by)
                        loss.backward()
                        optimizer.step()

                model.eval()
                with torch.no_grad():
                    preds_scaled = model(X_test_t).numpy()

                preds = scaler.inverse_transform(preds_scaled.reshape(-1, 1)).reshape(preds_scaled.shape)
                y_true = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)

                fold_maes.append(mean_absolute_error(y_true, preds))
                fold_rmses.append(np.sqrt(mean_squared_error(y_true, preds)))

            avg_mae = float(np.mean(fold_maes))
            avg_rmse = float(np.mean(fold_rmses))

            mlflow.log_metrics({"avg_mae": avg_mae, "avg_rmse": avg_rmse})

            res_entry = {**config, "avg_mae": avg_mae, "avg_rmse": avg_rmse}
            results.append(res_entry)

            attn_str = "ATTENTION" if config["use_attention"] else "PLAIN"
            print(f"[{idx:02d}/{len(configurations):02d}] {attn_str:<9} | Hidden: {config['hidden_size']} | Layers: {config['num_layers']} | LR: {config['lr']} | MAE: {avg_mae:.2f} | RMSE: {avg_rmse:.2f}")

    # Sort results by MAE
    results.sort(key=lambda x: x["avg_mae"])

    print("\n" + "=" * 85)
    print("TOP 5 PERFORMING CONFIGURATIONS (FIRST-CLASS COMPARISON)")
    print("=" * 85)
    print(f"{'Rank':<5} {'Attention':<10} {'Hidden':<8} {'Layers':<8} {'Dropout':<9} {'LR':<8} {'Avg MAE':<10} {'Avg RMSE':<10}")
    print("-" * 85)
    for r, c in enumerate(results[:5], 1):
        print(f"{r:<5} {str(c['use_attention']):<10} {c['hidden_size']:<8} {c['num_layers']:<8} {c['dropout']:<9} {c['lr']:<8} {c['avg_mae']:<10.2f} {c['avg_rmse']:<10.2f}")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    run_systematic_sweep()