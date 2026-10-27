"""Five-fold walk-forward comparison: global LSTM vs per-SKU LSTMs.

Run from ml-services/demand-forecast/lstm:
    python -m src.walk_forward_comparison
"""

import json
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.common import fit_with_early_stopping, set_seed
from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM

DATA = Path("data/global_sku_demand_synthetic.csv")
OUT = Path("output")
LOOKBACK = 45
HORIZON = 7
FOLDS = 5
EPOCHS = 50
PATIENCE = 8
BATCH = 32
MIN_TRAIN = 20
SEED = 42
LEARNING_RATE = 0.001
VALIDATION_BATCH = 128
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
EMBEDDING_DIM = 8
MLFLOW_EXPERIMENT = "Demand-Forecast-LSTM-Walk-Forward"
MLFLOW_RUN_NAME = "five-fold-global-vs-per-sku"


class PerSKUModel(nn.Module):
    """LSTM trained independently for one SKU."""

    def __init__(self, input_size=4, hidden_size=64, num_layers=2,
                 horizon=7, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers, batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )

    def forward(self, x):
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :])


def score(actual, predicted):
    actual = np.asarray(actual, dtype=float).reshape(-1)
    predicted = np.asarray(predicted, dtype=float).reshape(-1)
    if actual.size != predicted.size:
        raise ValueError("actual and predicted must have the same number of values")
    if not actual.size:
        return {"MAE": None, "RMSE": None, "MAPE_percent": None}
    error = predicted - actual
    nonzero = np.abs(actual) > 1e-8
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE_percent": float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100)
        if nonzero.any() else None,
    }


def inverse_scale(scaler, values):
    values = np.asarray(values)
    return scaler.inverse_transform(values.reshape(-1, 1)).reshape(values.shape)


def _global_forward(model, batch, device):
    x, sku, category, warehouse, y = batch
    prediction = model(x.to(device), sku.to(device), category.to(device), warehouse.to(device))
    return prediction, y.to(device)


def _sku_forward(model, batch, device):
    x, y = batch
    return model(x.to(device)), y.to(device)


def fit(model, train_loader, val_loader, device, global_model):
    """Use shared early stopping for both model types."""
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.MSELoss()
    started = time.perf_counter()
    result = fit_with_early_stopping(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        loss_fn=loss_fn,
        device=device,
        epochs=EPOCHS,
        patience=PATIENCE,
        forward_batch=_global_forward if global_model else _sku_forward,
    )
    return model, time.perf_counter() - started, result["best_val_loss"], result["best_epoch"]


def predict_global(model, dataset, device, scaler):
    model.eval()
    actuals, predictions, sku_ids = [], [], []
    with torch.no_grad():
        loader = DataLoader(dataset, batch_size=VALIDATION_BATCH, shuffle=False)
        for x, sku, category, warehouse, y in loader:
            prediction = model(x.to(device), sku.to(device), category.to(device), warehouse.to(device))
            actuals.append(y.numpy())
            predictions.append(prediction.cpu().numpy())
            sku_ids.append(sku.numpy())
    if not actuals:
        return np.array([]), np.array([]), np.array([], dtype=int)
    return (
        inverse_scale(scaler, np.concatenate(actuals)),
        inverse_scale(scaler, np.concatenate(predictions)),
        np.concatenate(sku_ids),
    )


def predict_sku(model, dataset, device, scaler):
    model.eval()
    actuals, predictions = [], []
    with torch.no_grad():
        for x, y in DataLoader(dataset, batch_size=VALIDATION_BATCH, shuffle=False):
            predictions.append(model(x.to(device)).cpu().numpy())
            actuals.append(y.numpy())
    if not actuals:
        return np.array([]), np.array([])
    return inverse_scale(scaler, np.concatenate(actuals)), inverse_scale(scaler, np.concatenate(predictions))


def log_metric_values(prefix, metric_values, step):
    for name, value in metric_values.items():
        if value is not None and np.isfinite(float(value)):
            mlflow.log_metric(f"{prefix}_{name.lower()}", float(value), step=step)


def _dataset_sku_counts(dataset, sku_mapping):
    """Count windows for each known trained SKU in a shared TensorDataset."""
    counts = {sku: {part: 0 for part in ("train", "validation", "test")} for sku in sku_mapping}
    return counts


def run_walk_forward():
    if not DATA.exists():
        raise FileNotFoundError(f"{DATA} not found; run from the lstm folder")

    df = pd.read_csv(DATA)
    required = {"date", "sku_id", "category", "warehouse_id", "sales", "promotion", "day_of_week"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df["sales"] = pd.to_numeric(df["sales"], errors="raise")
    df["promotion"] = pd.to_numeric(df["promotion"], errors="raise")
    df["day_of_week"] = pd.to_numeric(df["day_of_week"], errors="raise")
    for col in ("sku_id", "category", "warehouse_id"):
        df[col] = df[col].astype(str)
    dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    chunk = int(np.ceil(len(dates) * 0.08))
    starts = [int(len(dates) * 0.60) + i * chunk for i in range(FOLDS)]
    if starts[-1] >= len(dates):
        raise ValueError("Not enough dates for five folds")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    OUT.mkdir(parents=True, exist_ok=True)
    fold_rows, sku_rows, global_sku_rows, folds = [], [], [], []
    mlflow.log_params({
        "dataset_path": str(DATA), "dataset_type": "synthetic", "seed": SEED,
        "folds": FOLDS, "lookback_days": LOOKBACK, "forecast_horizon_days": HORIZON,
        "epochs_max": EPOCHS, "early_stopping_patience": PATIENCE, "batch_size": BATCH,
        "validation_batch_size": VALIDATION_BATCH, "learning_rate": LEARNING_RATE,
        "hidden_size": HIDDEN_SIZE, "num_layers": NUM_LAYERS, "dropout": DROPOUT,
        "embedding_dim": EMBEDDING_DIM, "minimum_per_sku_train_windows": MIN_TRAIN,
        "num_rows": len(df), "num_skus": int(df.sku_id.nunique()),
        "num_dates": len(dates), "device": str(device),
        "evaluation": "expanding_window_walk_forward",
    })
    print(f"Device={device}; rows={len(df)}; SKUs={df.sku_id.nunique()}; dates={len(dates)}")

    for fold, test_start in enumerate(starts, 1):
        val_start = test_start - chunk
        train_end = pd.Timestamp(dates[val_start - 1])
        val_end = pd.Timestamp(dates[test_start - 1])
        test_end = pd.Timestamp(dates[min(test_start + chunk, len(dates)) - 1])
        print(f"\nFold {fold}: train <= {train_end.date()}, validation <= {val_end.date()}, test <= {test_end.date()}")

        # load_global_data must support these optional fold-specific date arguments.
        data = load_global_data(
            DATA, lookback=LOOKBACK, horizon=HORIZON,
            train_end=train_end, validation_end=val_end, test_end=test_end,
        )
        train, validation, test = data.train, data.validation, data.test
        if min(len(train), len(validation), len(test)) == 0:
            raise ValueError(f"Fold {fold} has an empty split")

        set_seed(SEED + fold)
        global_model = GlobalDemandLSTM(
            num_skus=data.num_skus, num_categories=data.num_categories,
            num_warehouses=data.num_warehouses, num_numeric_features=4,
            embedding_dim=EMBEDDING_DIM, hidden_size=HIDDEN_SIZE,
            num_layers=NUM_LAYERS, horizon=HORIZON, dropout=DROPOUT,
        )
        global_model, global_seconds, global_best_loss, global_best_epoch = fit(
            global_model,
            DataLoader(train, batch_size=BATCH, shuffle=True),
            DataLoader(validation, batch_size=VALIDATION_BATCH, shuffle=False),
            device, True,
        )
        global_actual, global_predicted, global_skus = predict_global(global_model, test, device, data.scaler)

        eligible_ids, per_actual_parts, per_pred_parts = set(), [], []
        per_sku_seconds = 0.0
        # data.sku_mapping contains SKUs with training windows; unknown IDs are reserved as 0.
        id_to_sku = {idx: sku for sku, idx in data.sku_mapping.items()}
        split_datasets = {"train": train, "validation": validation, "test": test}
        counts = {}
        for sku, sku_id in data.sku_mapping.items():
            counts[sku] = {
                name: int((dataset.tensors[1] == sku_id).sum().item())
                for name, dataset in split_datasets.items()
            }
            mask = global_skus == sku_id
            metrics = score(global_actual[mask], global_predicted[mask])
            global_sku_rows.append({
                "row_type": "global_sku_detail", "fold": fold, "sku_id": sku,
                "status": "evaluated" if mask.any() else "not_evaluated",
                "reason": "" if mask.any() else "no_test_windows",
                "train_windows": counts[sku]["train"],
                "validation_windows": counts[sku]["validation"],
                "test_windows": counts[sku]["test"], **metrics,
            })

        for sku, sku_id in data.sku_mapping.items():
            c = counts[sku]
            train_ids = torch.where(train.tensors[1] == sku_id)[0]
            val_ids = torch.where(validation.tensors[1] == sku_id)[0]
            test_ids = torch.where(test.tensors[1] == sku_id)[0]
            status, reason = "eligible", ""
            seconds = best_mse = best_epoch = None
            metrics = score([], [])
            if len(train_ids) < MIN_TRAIN:
                status, reason = "not_trained", "insufficient_training_windows"
            elif len(val_ids) == 0:
                status, reason = "not_trained", "no_validation_windows"
            elif len(test_ids) == 0:
                status, reason = "not_evaluated", "no_test_windows"
            else:
                set_seed(SEED + fold * 100 + sku_id)
                sku_train = TensorDataset(train.tensors[0][train_ids], train.tensors[4][train_ids])
                sku_val = TensorDataset(validation.tensors[0][val_ids], validation.tensors[4][val_ids])
                sku_test = TensorDataset(test.tensors[0][test_ids], test.tensors[4][test_ids])
                model = PerSKUModel(hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, horizon=HORIZON, dropout=DROPOUT)
                model, seconds, best_mse, best_epoch = fit(
                    model, DataLoader(sku_train, batch_size=BATCH, shuffle=True),
                    DataLoader(sku_val, batch_size=VALIDATION_BATCH, shuffle=False), device, False,
                )
                actual, predicted = predict_sku(model, sku_test, device, data.scaler)
                metrics = score(actual, predicted)
                eligible_ids.add(sku_id)
                per_actual_parts.append(actual)
                per_pred_parts.append(predicted)
                per_sku_seconds += seconds
            sku_rows.append({
                "row_type": "sku_detail", "fold": fold, "sku_id": sku,
                "status": status, "reason": reason,
                "train_windows": c["train"], "validation_windows": c["validation"],
                "test_windows": c["test"], "training_seconds": seconds,
                "best_validation_mse": best_mse, "best_epoch": best_epoch, **metrics,
            })

        common_mask = np.isin(global_skus, list(eligible_ids))
        global_common = score(global_actual[common_mask], global_predicted[common_mask])
        per_common = score(
            np.concatenate(per_actual_parts) if per_actual_parts else [],
            np.concatenate(per_pred_parts) if per_pred_parts else [],
        )
        global_all = score(global_actual, global_predicted)
        fold_info = {
            "fold": fold, "train_end": str(train_end.date()),
            "validation_end": str(val_end.date()), "test_end": str(test_end.date()),
            "train_windows": len(train), "validation_windows": len(validation), "test_windows": len(test),
            "eligible_skus": len(eligible_ids), "global_training_seconds": float(global_seconds),
            "global_best_validation_mse": float(global_best_loss), "global_best_epoch": int(global_best_epoch),
            "per_sku_total_training_seconds": float(per_sku_seconds),
            "global_all_test_metrics": global_all, "global_common_sku_metrics": global_common,
            "per_sku_common_metrics": per_common,
        }
        folds.append(fold_info)
        prefix = f"fold_{fold}"
        mlflow.log_metrics({
            f"{prefix}_train_windows": float(len(train)), f"{prefix}_validation_windows": float(len(validation)),
            f"{prefix}_test_windows": float(len(test)), f"{prefix}_eligible_skus": float(len(eligible_ids)),
            f"{prefix}_global_training_seconds": float(global_seconds),
            f"{prefix}_global_best_validation_mse": float(global_best_loss),
            f"{prefix}_global_best_epoch": float(global_best_epoch),
            f"{prefix}_per_sku_training_seconds": float(per_sku_seconds),
        })
        log_metric_values(f"{prefix}_global_all", global_all, fold)
        log_metric_values(f"{prefix}_global_common", global_common, fold)
        log_metric_values(f"{prefix}_per_sku_common", per_common, fold)
        for name, seconds, metrics, n_skus in [
            ("global_all_test_skus", global_seconds, global_all, len(data.sku_mapping)),
            ("global_common_eligible_skus", global_seconds, global_common, len(eligible_ids)),
            ("per_sku_common_eligible_skus", per_sku_seconds, per_common, len(eligible_ids)),
        ]:
            fold_rows.append({"row_type": "fold_comparison", "fold": fold, "model": name,
                              "training_seconds": float(seconds), "eligible_skus": n_skus, **metrics})
        print(f"Global/common MAE={global_common['MAE']}; Per-SKU/common MAE={per_common['MAE']}; global={global_seconds:.1f}s; per-SKU={per_sku_seconds:.1f}s; eligible SKUs={len(eligible_ids)}")

    metrics_path = OUT / "walk_forward_fold_metrics.csv"
    summary_path = OUT / "walk_forward_summary.json"
    pd.DataFrame(fold_rows + global_sku_rows + sku_rows).to_csv(metrics_path, index=False)

    def mean_metrics(key):
        result = {}
        for metric in ("MAE", "RMSE", "MAPE_percent"):
            vals = [fold[key][metric] for fold in folds if fold[key][metric] is not None]
            result[metric] = float(np.mean(vals)) if vals else None
        return result

    summary = {
        "evaluation": "five-fold expanding-window walk-forward", "dataset": str(DATA),
        "lookback": LOOKBACK, "horizon": HORIZON, "folds": folds,
        "mean_fold_metrics": {
            "global_all_test_skus": mean_metrics("global_all_test_metrics"),
            "global_common_eligible_skus": mean_metrics("global_common_sku_metrics"),
            "per_sku_common_eligible_skus": mean_metrics("per_sku_common_metrics"),
        },
        "mean_training_seconds": {
            "global": float(np.mean([f["global_training_seconds"] for f in folds])),
            "per_sku_total": float(np.mean([f["per_sku_total_training_seconds"] for f in folds])),
        },
        "notes": [
            "Scaler is fit only on each fold training period.",
            "Validation and test target horizons stay inside their split.",
            "Common-SKU metrics compare eligible per-SKU models on the same test windows.",
            "Short-history SKUs excluded by global_data are not assigned a trained SKU embedding.",
            "MAPE excludes zero-valued actuals.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for name, metrics in summary["mean_fold_metrics"].items():
        log_metric_values(f"mean_{name}", metrics, FOLDS)
    mlflow.log_metrics({
        "mean_global_training_seconds": summary["mean_training_seconds"]["global"],
        "mean_per_sku_training_seconds": summary["mean_training_seconds"]["per_sku_total"],
    })
    mlflow.log_artifact(str(metrics_path))
    mlflow.log_artifact(str(summary_path))
    print(f"\nSaved {metrics_path}\nSaved {summary_path}")
    print(json.dumps(summary["mean_fold_metrics"], indent=2))
    print("Review results before marking the milestone complete.")
    print("MLflow run ID:", mlflow.active_run().info.run_id)


def main():
    set_seed(SEED)
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name=MLFLOW_RUN_NAME):
        run_walk_forward()


if __name__ == "__main__":
    main()
