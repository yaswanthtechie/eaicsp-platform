"""
-- Real hyperparameter sweep.

"""

import itertools
import os
from typing import List, Dict

import numpy as np

import mlflow_logger as mlog
from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from train_utils import train_model, evaluate_scaled, chronological_train_val_split, build_model

HORIZON = 7
EPOCHS = 25
BATCH_SIZE = 32
LR = 0.001
VAL_FRACTION = 0.2
SWEEP_FOLDS = (4, 5)  # 1-indexed, matches data.py's fold numbering (n_folds=5)

HIDDEN_SIZES = [32, 64]
NUM_LAYERS = [1, 2]
LOOKBACKS = [14, 30, 45]


def build_grid() -> List[Dict]:
    grid = []
    for hidden_size, num_layers, lookback in itertools.product(HIDDEN_SIZES, NUM_LAYERS, LOOKBACKS):
        grid.append({"hidden_size": hidden_size, "num_layers": num_layers, "lookback": lookback})
    return grid


def run_sweep() -> List[Dict]:
    df = generate_data(days=1000)
    grid = build_grid()
    print(f"Sweeping {len(grid)} configurations "
        f"(hidden_size x num_layers x lookback), scored on folds {SWEEP_FOLDS}\n")

    results = []

    for cfg_idx, config in enumerate(grid, 1):
        lookback = config["lookback"]
        # Fold boundaries depend on lookback (create_sequences windows on it),
        # so folds must be rebuilt per-config rather than reused.
        folds = get_walk_forward_folds(df, n_folds=5, lookback=lookback, horizon=HORIZON,
                                        save_scaler_path=None)

        run_name = f"sweep_h{config['hidden_size']}_l{config['num_layers']}_lb{lookback}"
        mlog.start_experiment("Demand-Forecast-LSTM-Sweep")
        mlog.log_params({**config, "epochs": EPOCHS, "batch_size": BATCH_SIZE, "lr": LR})

        val_maes, val_rmses = [], []
        test_maes, test_rmses = [], []  # reference only -- NOT used for selection

        for fold_num in SWEEP_FOLDS:
            X_tr, y_tr, X_te, y_te, scaler = folds[fold_num - 1]

            X_inner_tr, y_inner_tr, X_val, y_val = chronological_train_val_split(
                X_tr, y_tr, val_fraction=VAL_FRACTION
            )

            model = build_model(MultiStepLSTM, config["hidden_size"], config["num_layers"], HORIZON)
            model = train_model(model, X_inner_tr, y_inner_tr, epochs=EPOCHS, batch_size=BATCH_SIZE, lr=LR)

            val_metrics = evaluate_scaled(model, X_val, y_val, scaler)
            test_metrics = evaluate_scaled(model, X_te, y_te, scaler)  # reference only

            val_maes.append(val_metrics["MAE"])
            val_rmses.append(val_metrics["RMSE"])
            test_maes.append(test_metrics["MAE"])
            test_rmses.append(test_metrics["RMSE"])

            mlog.log_metrics({
                f"fold_{fold_num}_val_mae": val_metrics["MAE"],
                f"fold_{fold_num}_val_rmse": val_metrics["RMSE"],
                f"fold_{fold_num}_test_mae_reference_only": test_metrics["MAE"],
            })

        avg_val_mae = float(np.mean(val_maes))
        avg_val_rmse = float(np.mean(val_rmses))
        avg_test_mae_ref = float(np.mean(test_maes))
        avg_test_rmse_ref = float(np.mean(test_rmses))

        mlog.log_metrics({
            "avg_val_mae": avg_val_mae,
            "avg_val_rmse": avg_val_rmse,
            "avg_test_mae_reference_only": avg_test_mae_ref,
            "avg_test_rmse_reference_only": avg_test_rmse_ref,
        })
        mlog.end_run()

        print(f"[{cfg_idx}/{len(grid)}] {run_name:30s} "
            f"val_MAE={avg_val_mae:6.2f}  val_RMSE={avg_val_rmse:6.2f}  "
            f"(test_MAE ref only={avg_test_mae_ref:6.2f})")

        results.append({
            **config,
            "run_name": run_name,
            "avg_val_mae": avg_val_mae,
            "avg_val_rmse": avg_val_rmse,
            "avg_test_mae_reference_only": avg_test_mae_ref,
            "avg_test_rmse_reference_only": avg_test_rmse_ref,
        })

    return results


def select_winner(results: List[Dict]) -> Dict:
    """Winner = lowest avg_val_mae. Test metrics are never part of this comparison."""
    return min(results, key=lambda r: r["avg_val_mae"])


def print_results_table(results: List[Dict], winner: Dict) -> None:
    print("\n" + "=" * 100)
    print("SWEEP RESULTS (sorted by validation MAE -- winner selection criterion)")
    print("=" * 100)
    header = f"{'run_name':30s} {'hidden':>7s} {'layers':>7s} {'lookback':>9s} {'val_MAE':>9s} {'val_RMSE':>9s} {'test_MAE(ref)':>14s}"
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda r: r["avg_val_mae"]):
        marker = "  <-- WINNER (best val MAE)" if r["run_name"] == winner["run_name"] else ""
        print(f"{r['run_name']:30s} {r['hidden_size']:7d} {r['num_layers']:7d} {r['lookback']:9d} "
            f"{r['avg_val_mae']:9.2f} {r['avg_val_rmse']:9.2f} {r['avg_test_mae_reference_only']:14.2f}{marker}")
    print("=" * 100)
    print(f"\nWinner justified on VALIDATION data: {winner['run_name']} "
        f"(avg_val_mae={winner['avg_val_mae']:.2f})")
    print("Test MAE column is shown for reference only -- it was never used to pick the winner.\n")


if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    all_results = run_sweep()
    best = select_winner(all_results)
    print_results_table(all_results, best)