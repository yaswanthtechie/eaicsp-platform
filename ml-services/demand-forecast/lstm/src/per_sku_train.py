"""Compare one global LSTM against separate per-SKU LSTMs with MLflow tracking."""

import copy
import json
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset

from src.reproducibility import set_seed
from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
SEED = 42
DATA_PATH = "data/global_sku_demand_synthetic.csv"
OUTPUT_DIR = Path("output")

LOOKBACK = 45
HORIZON = 7
BATCH_SIZE = 32
VALIDATION_BATCH_SIZE = 128
LEARNING_RATE = 0.001
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
MAX_EPOCHS = 50
PATIENCE = 8

MLFLOW_EXPERIMENT = "Demand-Forecast-LSTM-Global-vs-Per-SKU"
MLFLOW_RUN_NAME = "global-vs-per-sku-comparison"


class PerSKUModel(nn.Module):
    """LSTM trained independently for one SKU."""

    def __init__(
        self,
        input_size=4,
        hidden_size=64,
        num_layers=2,
        horizon=7,
        dropout=0.2,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )

    def forward(self, x):
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :])


def get_metrics(actual, predicted):
    """Calculate regression metrics in the original sales units."""
    actual = np.asarray(actual).reshape(-1)
    predicted = np.asarray(predicted).reshape(-1)

    errors = predicted - actual
    nonzero = np.abs(actual) > 1e-8

    return {
        "MAE": float(np.mean(np.abs(errors))),
        "RMSE": float(np.sqrt(np.mean(errors ** 2))),
        "MAPE_percent": (
            float(
                np.mean(
                    np.abs(errors[nonzero] / actual[nonzero])
                ) * 100
            )
            if nonzero.any()
            else None
        ),
    }


def inverse_sales(scaler, values):
    """Convert scaled sales values back to original sales units."""
    values = np.asarray(values)
    original_shape = values.shape

    restored = scaler.inverse_transform(values.reshape(-1, 1))

    return restored.reshape(original_shape)


def sku_indices(dataset, sku_index):
    """Get dataset window positions belonging to one SKU."""
    # Dataset tuple order: x, sku, category, warehouse, y.
    sku_tensor = dataset.tensors[1]

    return torch.where(sku_tensor == sku_index)[0].tolist()


def train_one_sku(
    data,
    sku_index,
    device,
    max_epochs=MAX_EPOCHS,
    patience=PATIENCE,
):
    """Train and evaluate one SKU-specific LSTM."""
    train_ids = sku_indices(data.train, sku_index)
    val_ids = sku_indices(data.validation, sku_index)
    test_ids = sku_indices(data.test, sku_index)

    if len(train_ids) < 20 or not val_ids or not test_ids:
        return None

    train_loader = DataLoader(
        Subset(data.train, train_ids),
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    val_loader = DataLoader(
        Subset(data.validation, val_ids),
        batch_size=VALIDATION_BATCH_SIZE,
        shuffle=False,
    )

    test_loader = DataLoader(
        Subset(data.test, test_ids),
        batch_size=VALIDATION_BATCH_SIZE,
        shuffle=False,
    )

    model = PerSKUModel(
        input_size=4,
        hidden_size=HIDDEN_SIZE,
        num_layers=NUM_LAYERS,
        horizon=data.horizon,
        dropout=DROPOUT,
    ).to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    loss_fn = nn.MSELoss()

    best_loss = float("inf")
    best_state = None
    best_epoch = 0
    waiting = 0

    start = time.perf_counter()

    for epoch in range(1, max_epochs + 1):
        model.train()

        for x, _sku, _category, _warehouse, y in train_loader:
            x = x.to(device)
            y = y.to(device)

            optimizer.zero_grad()

            prediction = model(x)
            loss = loss_fn(prediction, y)

            loss.backward()

            nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0,
            )

            optimizer.step()

        model.eval()
        losses = []

        with torch.no_grad():
            for x, _sku, _category, _warehouse, y in val_loader:
                prediction = model(x.to(device))
                losses.append(
                    loss_fn(prediction, y.to(device)).item()
                )

        val_loss = float(np.mean(losses))

        if val_loss < best_loss:
            best_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            waiting = 0
        else:
            waiting += 1

        if waiting >= patience:
            break

    training_seconds = time.perf_counter() - start

    if best_state is None:
        return None

    model.load_state_dict(best_state)
    model.eval()

    predictions = []
    actual_scaled = []

    with torch.no_grad():
        for x, _sku, _category, _warehouse, y in test_loader:
            prediction = model(x.to(device))

            predictions.append(prediction.cpu().numpy())
            actual_scaled.append(y.numpy())

    predictions = np.concatenate(predictions, axis=0)
    actual_scaled = np.concatenate(actual_scaled, axis=0)

    return {
        "test_ids": test_ids,
        "actual": inverse_sales(data.scaler, actual_scaled),
        "predicted": inverse_sales(data.scaler, predictions),
        "train_windows": len(train_ids),
        "validation_windows": len(val_ids),
        "test_windows": len(test_ids),
        "training_seconds": training_seconds,
        "best_validation_mse": best_loss,
        "best_epoch": best_epoch,
    }


def log_metrics_safely(metrics, prefix):
    """Log non-null, finite numeric metrics to MLflow."""
    for name, value in metrics.items():
        if value is None:
            continue

        numeric_value = float(value)

        if np.isfinite(numeric_value):
            mlflow.log_metric(f"{prefix}_{name.lower()}", numeric_value)


def _run_comparison():
    """Execute comparison inside an active MLflow run."""
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("Device:", device)

    data = load_global_data(
        DATA_PATH,
        lookback=LOOKBACK,
        horizon=HORIZON,
    )

    # Log dataset and split information.
    mlflow.log_params({
        "dataset_path": DATA_PATH,
        "dataset_type": "synthetic",
        "lookback_days": data.lookback,
        "forecast_horizon_days": data.horizon,
        "num_skus": data.num_skus,
        "num_categories": data.num_categories,
        "num_warehouses": data.num_warehouses,
        "train_windows": len(data.train),
        "validation_windows": len(data.validation),
        "test_windows": len(data.test),
        "device": str(device),
    })

    checkpoint_path = OUTPUT_DIR / "global_best_model.pt"

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Missing {checkpoint_path}. Run src.global_train first."
        )

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device,
        weights_only=False,
    )

    model = GlobalDemandLSTM(
        num_skus=checkpoint["num_skus"],
        num_categories=checkpoint["num_categories"],
        num_warehouses=checkpoint["num_warehouses"],
        num_numeric_features=checkpoint["num_numeric_features"],
        embedding_dim=checkpoint["embedding_dim"],
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
        horizon=checkpoint["horizon"],
        dropout=checkpoint["dropout"],
    ).to(device)

    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    if (
        checkpoint["sku_mapping"] != data.sku_mapping
        or checkpoint["category_mapping"] != data.category_mapping
        or checkpoint["warehouse_mapping"] != data.warehouse_mapping
    ):
        raise ValueError(
            "Saved checkpoint mappings do not match the loaded dataset."
        )

    # Evaluate global model, preserving the original test-window order.
    global_scaled = []
    test_actual_scaled = []
    test_sku_ids = []

    test_loader = DataLoader(
        data.test,
        batch_size=VALIDATION_BATCH_SIZE,
        shuffle=False,
    )

    with torch.no_grad():
        for x, sku, category, warehouse, y in test_loader:
            prediction = model(
                x.to(device),
                sku.to(device),
                category.to(device),
                warehouse.to(device),
            )

            global_scaled.append(prediction.cpu().numpy())
            test_actual_scaled.append(y.numpy())
            test_sku_ids.extend(sku.numpy().tolist())

    global_scaled = np.concatenate(global_scaled, axis=0)
    test_actual_scaled = np.concatenate(test_actual_scaled, axis=0)

    global_actual = inverse_sales(data.scaler, test_actual_scaled)
    global_predictions = inverse_sales(data.scaler, global_scaled)

    # Fill per-SKU predictions at the corresponding test-window positions.
    per_sku_predictions = np.full_like(global_predictions, np.nan)
    per_sku_actual = np.full_like(global_actual, np.nan)

    per_sku_results = []
    skipped = []

    total_sku_training_seconds = 0.0
    start_all = time.perf_counter()

    for sku, sku_index in data.sku_mapping.items():
        print(f"\nTraining separate model for SKU: {sku}")

        result = train_one_sku(data, sku_index, device)

        if result is None:
            print("  Skipped: insufficient train/validation/test windows.")
            skipped.append(str(sku))
            continue

        ids = result["test_ids"]

        per_sku_predictions[ids] = result["predicted"]
        per_sku_actual[ids] = result["actual"]

        total_sku_training_seconds += result["training_seconds"]

        sku_metrics = get_metrics(
            result["actual"],
            result["predicted"],
        )

        sku_result = {
            "sku_id": str(sku),
            **sku_metrics,
            "train_windows": result["train_windows"],
            "validation_windows": result["validation_windows"],
            "test_windows": result["test_windows"],
            "training_seconds": round(
                result["training_seconds"], 2
            ),
            "best_validation_mse": round(
                result["best_validation_mse"], 6
            ),
            "best_epoch": result["best_epoch"],
        }

        per_sku_results.append(sku_result)

        print(
            f"  Test windows: {len(ids)} | "
            f"MAE: {sku_metrics['MAE']:.3f} | "
            f"RMSE: {sku_metrics['RMSE']:.3f}"
        )

    # Compare models only on windows with a trained per-SKU model.
    eligible = np.isfinite(per_sku_predictions[:, 0])

    if not eligible.any():
        raise RuntimeError(
            "No eligible test windows for a fair comparison."
        )

    common_actual = global_actual[eligible]
    global_common = global_predictions[eligible]
    per_sku_common = per_sku_predictions[eligible]

    if not np.allclose(
        common_actual,
        per_sku_actual[eligible],
        atol=1e-5,
    ):
        raise RuntimeError(
            "Actual test targets are not aligned between models."
        )

    global_metrics = get_metrics(common_actual, global_common)
    per_sku_metrics = get_metrics(common_actual, per_sku_common)

    per_sku_wall_clock_seconds = time.perf_counter() - start_all

    summary = {
        "dataset_type": "synthetic",
        "evaluation": (
            "chronological sliding-window test; common eligible windows"
        ),
        "lookback_days": data.lookback,
        "forecast_horizon_days": data.horizon,
        "train_end": data.split_dates["train_end"],
        "validation_end": data.split_dates["validation_end"],
        "total_test_windows": int(len(global_actual)),
        "common_test_windows": int(eligible.sum()),
        "eligible_skus": len(per_sku_results),
        "skipped_skus": skipped,
        "global_lstm_metrics": global_metrics,
        "per_sku_lstm_metrics": per_sku_metrics,
        "global_checkpoint_training_seconds": None,
        "per_sku_total_training_seconds": round(
            total_sku_training_seconds, 2
        ),
        "per_sku_wall_clock_seconds": round(
            per_sku_wall_clock_seconds, 2
        ),
        "note": (
            "Global training time is not stored in the checkpoint. "
            "Run timing was not measured for the existing global model. "
            "Compare model metrics only on common eligible test windows."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = OUTPUT_DIR / "global_vs_per_sku_summary.json"
    metrics_path = OUTPUT_DIR / "per_sku_metrics.csv"

    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    pd.DataFrame(per_sku_results).to_csv(
        metrics_path,
        index=False,
    )

    # Log comparison metrics to MLflow.
    log_metrics_safely(global_metrics, "global_lstm")
    log_metrics_safely(per_sku_metrics, "per_sku_lstm")

    mlflow.log_metrics({
        "total_test_windows": float(len(global_actual)),
        "common_test_windows": float(eligible.sum()),
        "eligible_skus": float(len(per_sku_results)),
        "skipped_skus": float(len(skipped)),
        "per_sku_total_training_seconds": float(
            total_sku_training_seconds
        ),
        "per_sku_wall_clock_seconds": float(
            per_sku_wall_clock_seconds
        ),
    })

    # Record each SKU's metrics and training information.
    for result in per_sku_results:
        sku = result["sku_id"]
        prefix = f"sku_{sku}"

        log_metrics_safely(
            {
                "MAE": result["MAE"],
                "RMSE": result["RMSE"],
                "MAPE_percent": result["MAPE_percent"],
                "training_seconds": result["training_seconds"],
                "best_validation_mse": result["best_validation_mse"],
                "best_epoch": result["best_epoch"],
            },
            prefix,
        )

    mlflow.log_dict(summary, "global_vs_per_sku_summary.json")
    mlflow.log_artifact(str(summary_path))
    mlflow.log_artifact(str(metrics_path))

    print("\n=== FAIR TEST COMPARISON (ORIGINAL SALES UNITS) ===")
    print(json.dumps(summary, indent=2))

    print("\nSaved:")
    print("  output/global_vs_per_sku_summary.json")
    print("  output/per_sku_metrics.csv")

    print("\nMLflow run ID:", mlflow.active_run().info.run_id)


def run_comparison():
    """Configure MLflow and execute one reproducible comparison run."""
    set_seed(SEED)

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    with mlflow.start_run(run_name=MLFLOW_RUN_NAME):
        mlflow.log_params({
            "seed": SEED,
            "lookback_days": LOOKBACK,
            "forecast_horizon_days": HORIZON,
            "batch_size": BATCH_SIZE,
            "validation_batch_size": VALIDATION_BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
            "max_epochs": MAX_EPOCHS,
            "early_stopping_patience": PATIENCE,
            "per_sku_minimum_train_windows": 20,
            "comparison": "global_lstm_vs_independent_per_sku_lstm",
        })

        _run_comparison()


if __name__ == "__main__":
    run_comparison()
