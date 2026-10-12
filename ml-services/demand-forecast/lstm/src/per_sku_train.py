"""Compare one global LSTM against separate per-SKU LSTMs."""

import copy
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset

from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class PerSKUModel(nn.Module):
    def __init__(self, input_size=4, hidden_size=64,
                 num_layers=2, horizon=7, dropout=0.2):
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
    actual = np.asarray(actual).reshape(-1)
    predicted = np.asarray(predicted).reshape(-1)
    errors = predicted - actual
    nonzero = np.abs(actual) > 1e-8

    return {
        "MAE": float(np.mean(np.abs(errors))),
        "RMSE": float(np.sqrt(np.mean(errors ** 2))),
        "MAPE_percent": (
            float(np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100)
            if nonzero.any() else None
        ),
    }


def inverse_sales(scaler, values):
    values = np.asarray(values)
    original_shape = values.shape
    restored = scaler.inverse_transform(values.reshape(-1, 1))
    return restored.reshape(original_shape)


def sku_indices(dataset, sku_index):
    # Dataset tuple order: x, sku, category, warehouse, y.
    sku_tensor = dataset.tensors[1]
    return torch.where(sku_tensor == sku_index)[0].tolist()


def train_one_sku(data, sku_index, device, max_epochs=50, patience=8):
    train_ids = sku_indices(data.train, sku_index)
    val_ids = sku_indices(data.validation, sku_index)
    test_ids = sku_indices(data.test, sku_index)

    if len(train_ids) < 20 or not val_ids or not test_ids:
        return None

    train_loader = DataLoader(
        Subset(data.train, train_ids), batch_size=32, shuffle=True
    )
    val_loader = DataLoader(
        Subset(data.validation, val_ids), batch_size=128, shuffle=False
    )
    test_loader = DataLoader(
        Subset(data.test, test_ids), batch_size=128, shuffle=False
    )

    model = PerSKUModel(horizon=data.horizon).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()

    best_loss = float("inf")
    best_state = None
    waiting = 0
    start = time.perf_counter()

    for epoch in range(1, max_epochs + 1):
        model.train()
        for x, _sku, _category, _warehouse, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

        model.eval()
        losses = []
        with torch.no_grad():
            for x, _sku, _category, _warehouse, y in val_loader:
                pred = model(x.to(device))
                losses.append(loss_fn(pred, y.to(device)).item())

        val_loss = float(np.mean(losses))
        if val_loss < best_loss:
            best_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            waiting = 0
        else:
            waiting += 1

        if waiting >= patience:
            break

    if best_state is None:
        return None

    model.load_state_dict(best_state)
    model.eval()
    predictions = []
    actual_scaled = []

    with torch.no_grad():
        for x, _sku, _category, _warehouse, y in test_loader:
            predictions.append(model(x.to(device)).cpu().numpy())
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
        "training_seconds": time.perf_counter() - start,
        "best_validation_mse": best_loss,
    }


def run_comparison():
    set_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    data = load_global_data(
        "data/global_sku_demand_synthetic.csv",
        lookback=45,
        horizon=7,
    )

    checkpoint_path = Path("output/global_best_model.pt")
    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Missing {checkpoint_path}. Run src.global_train first."
        )

    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False
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

    # Keep global predictions aligned to the original test dataset row order.
    global_scaled = []
    test_actual_scaled = []
    test_sku_ids = []

    test_loader = DataLoader(data.test, batch_size=128, shuffle=False)
    with torch.no_grad():
        for x, sku, category, warehouse, y in test_loader:
            pred = model(
                x.to(device),
                sku.to(device),
                category.to(device),
                warehouse.to(device),
            )
            global_scaled.append(pred.cpu().numpy())
            test_actual_scaled.append(y.numpy())
            test_sku_ids.extend(sku.numpy().tolist())

    global_scaled = np.concatenate(global_scaled, axis=0)
    test_actual_scaled = np.concatenate(test_actual_scaled, axis=0)

    global_actual = inverse_sales(data.scaler, test_actual_scaled)
    global_predictions = inverse_sales(data.scaler, global_scaled)

    # Fill per-SKU predictions into the same test-window positions.
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

        sku_metrics = get_metrics(result["actual"], result["predicted"])
        per_sku_results.append({
            "sku_id": str(sku),
            **sku_metrics,
            "train_windows": result["train_windows"],
            "validation_windows": result["validation_windows"],
            "test_windows": result["test_windows"],
            "training_seconds": round(result["training_seconds"], 2),
            "best_validation_mse": round(result["best_validation_mse"], 6),
        })

        print(
            f"  Test windows: {len(ids)} | "
            f"MAE: {sku_metrics['MAE']:.3f} | "
            f"RMSE: {sku_metrics['RMSE']:.3f}"
        )

    # Compare both models only on test windows with a trained per-SKU model.
    eligible = np.isfinite(per_sku_predictions[:, 0])
    if not eligible.any():
        raise RuntimeError("No eligible test windows for a fair comparison.")

    common_actual = global_actual[eligible]
    global_common = global_predictions[eligible]
    per_sku_common = per_sku_predictions[eligible]

    # Verify actual values align before calculating comparative metrics.
    if not np.allclose(common_actual, per_sku_actual[eligible], atol=1e-5):
        raise RuntimeError("Actual test targets are not aligned between models.")

    summary = {
        "dataset_type": "synthetic",
        "evaluation": "chronological sliding-window test; common eligible windows",
        "lookback_days": data.lookback,
        "forecast_horizon_days": data.horizon,
        "train_end": data.split_dates["train_end"],
        "validation_end": data.split_dates["validation_end"],
        "total_test_windows": int(len(global_actual)),
        "common_test_windows": int(eligible.sum()),
        "eligible_skus": len(per_sku_results),
        "skipped_skus": skipped,
        "global_lstm_metrics": get_metrics(common_actual, global_common),
        "per_sku_lstm_metrics": get_metrics(common_actual, per_sku_common),
        "global_checkpoint_training_seconds": None,
        "per_sku_total_training_seconds": round(total_sku_training_seconds, 2),
        "per_sku_wall_clock_seconds": round(time.perf_counter() - start_all, 2),
        "note": (
            "Global training time is not stored in the checkpoint. "
            "Run timing was not measured for the existing global model. "
            "Compare model metrics only on common eligible test windows."
        ),
    }

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "global_vs_per_sku_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    pd.DataFrame(per_sku_results).to_csv(
        output_dir / "per_sku_metrics.csv", index=False
    )

    print("\n=== FAIR TEST COMPARISON (ORIGINAL SALES UNITS) ===")
    print(json.dumps(summary, indent=2))
    print("\nSaved:")
    print("  output/global_vs_per_sku_summary.json")
    print("  output/per_sku_metrics.csv")


if __name__ == "__main__":
    run_comparison()
