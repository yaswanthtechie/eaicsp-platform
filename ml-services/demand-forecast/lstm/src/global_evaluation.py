
"""Evaluate global multi-SKU LSTM using a safe, self-contained checkpoint."""

import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


DATA_PATH = "data/global_sku_demand_synthetic.csv"
CHECKPOINT_PATH = Path("output/global_best_model.pt")
SUMMARY_PATH = Path("output/global_vs_per_sku_summary.json")

LOOKBACK = 45
HORIZON = 7
BATCH_SIZE = 128


def get_metrics(actual, predicted):
    """Calculate MAE, RMSE and MAPE in original sales units."""
    actual = np.asarray(actual, dtype=np.float64).reshape(-1)
    predicted = np.asarray(predicted, dtype=np.float64).reshape(-1)

    if actual.size == 0 or actual.shape != predicted.shape:
        raise ValueError("Actual and predicted arrays must be non-empty and aligned.")

    errors = predicted - actual
    nonzero = np.abs(actual) > 1e-8

    return {
        "MAE": float(np.mean(np.abs(errors))),
        "RMSE": float(np.sqrt(np.mean(errors ** 2))),
        "MAPE_percent": (
            float(np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100)
            if nonzero.any()
            else None
        ),
    }



def inverse_sales(values, scaler_mean, scaler_scale):
    return values * float(scaler_scale) + float(scaler_mean)



def run_evaluation():
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {CHECKPOINT_PATH}. "
            "Run python -m src.global_train first."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    # weights_only=True avoids unrestricted pickle-style object loading.
    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location="cpu",
        weights_only=True,
    )

    required_keys = {
        "state_dict",
        "config",
        "scaler_mean",
        "scaler_scale",
        "sku_mapping",
        "category_mapping",
        "warehouse_mapping",
        "lookback",
        "training_seconds",
    }
    missing = required_keys - set(checkpoint)
    if missing:
        raise ValueError(
            "Checkpoint is an old or incomplete format. Missing keys: "
            f"{sorted(missing)}. Retrain with the updated global_train.py."
        )

    config = checkpoint["config"]

    if int(checkpoint["lookback"]) != LOOKBACK:
        raise ValueError("Checkpoint lookback does not match evaluation settings.")
    if int(config["horizon"]) != HORIZON:
        raise ValueError("Checkpoint horizon does not match evaluation settings.")

    scaler_mean = checkpoint["scaler_mean"]
    scaler_scale = checkpoint["scaler_scale"]

    if (
        len(scaler_mean) != 1
        or len(scaler_scale) != 1
        or not np.isfinite(scaler_mean[0])
        or not np.isfinite(scaler_scale[0])
        or float(scaler_scale[0]) <= 0
    ):
        raise ValueError("Invalid scaler parameters in checkpoint.")

    data = load_global_data(
        DATA_PATH,
        lookback=LOOKBACK,
        horizon=HORIZON,
    )

    # Fail fast if this checkpoint belongs to different category/SKU mappings.
    expected_mappings = (
        ("sku_mapping", data.sku_mapping),
        ("category_mapping", data.category_mapping),
        ("warehouse_mapping", data.warehouse_mapping),
    )
    for key, current_mapping in expected_mappings:
        saved_mapping = checkpoint[key]
        normalized_current = {
            str(k): int(v) for k, v in current_mapping.items()
        }
        if saved_mapping != normalized_current:
            raise ValueError(
                f"{key} in checkpoint does not match the current dataset. "
                "Use the matching dataset or retrain the model."
            )

    model = GlobalDemandLSTM(
        num_skus=int(config["num_skus"]),
        num_categories=int(config["num_categories"]),
        num_warehouses=int(config["num_warehouses"]),
        num_numeric_features=int(config["num_numeric_features"]),
        embedding_dim=int(config["embedding_dim"]),
        hidden_size=int(config["hidden_size"]),
        num_layers=int(config["num_layers"]),
        horizon=int(config["horizon"]),
        dropout=float(config["dropout"]),
    ).to(device)

    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()

    test_loader = DataLoader(
        data.test,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    all_predictions = []
    all_actual = []
    all_last_values = []
    all_sku_ids = []

    with torch.no_grad():
        for x, sku, category, warehouse, y in test_loader:
            x_device = x.to(device)

            prediction = model(
                x_device,
                sku.to(device),
                category.to(device),
                warehouse.to(device),
            )

            all_predictions.append(prediction.cpu().numpy())
            all_actual.append(y.numpy())

            # Last observed sales value in each input window (scaled).
            all_last_values.append(x[:, -1, 0].numpy())
            all_sku_ids.extend(sku.numpy().tolist())

    if not all_predictions:
        raise RuntimeError("Test dataset produced no forecast windows.")

    scaled_predictions = np.concatenate(all_predictions, axis=0)
    scaled_actual = np.concatenate(all_actual, axis=0)
    scaled_last_values = np.concatenate(all_last_values, axis=0)

    actual = inverse_sales(scaled_actual, scaler_mean[0], scaler_scale[0])
    predictions = inverse_sales(
        scaled_predictions, scaler_mean[0], scaler_scale[0]
    )

    # Repeat the last observed value across the 7-day horizon.
    baseline_scaled = np.repeat(
        scaled_last_values[:, None],
        repeats=HORIZON,
        axis=1,
    )
    baseline_predictions = inverse_sales(
        baseline_scaled, scaler_mean[0], scaler_scale[0]
    )

    global_metrics = get_metrics(actual, predictions)
    baseline_metrics = get_metrics(actual, baseline_predictions)

    all_skus = set(data.sku_mapping.keys())
    trained_skus = set(data.sku_mapping.keys())

    # The dataset loader maps SKUs without training windows to ID 0.
    # Identify their names using the original CSV and split boundaries.
    import pandas as pd

    raw_df = pd.read_csv(DATA_PATH)
    raw_df["date"] = pd.to_datetime(raw_df["date"])
    raw_df["sku_id"] = raw_df["sku_id"].astype(str)
    all_skus = set(raw_df["sku_id"].unique())

    # Reproduce the training eligibility rule: at least one training window.
    train_sku_ids = data.train.tensors[1].numpy()
    trained_ids = set(int(v) for v in np.unique(train_sku_ids))
    trained_skus = {
        str(sku) for sku, idx in data.sku_mapping.items()
        if int(idx) in trained_ids
    }

    # Too-short SKUs are those that cannot generate a training window.
    train_end = pd.Timestamp(data.split_dates["train_end"])
    too_short = set()

    for sku, group in raw_df.groupby("sku_id", sort=False):
        group = group.sort_values("date")
        train_group = group[group["date"] <= train_end]
        if len(train_group) < LOOKBACK + HORIZON:
            too_short.add(str(sku))

    mapped_to_unk = sorted(all_skus - trained_skus - too_short)

    coverage = {
        "skus_with_train_windows": sorted(trained_skus),
        "skus_mapped_to_unk": mapped_to_unk,
        "too_short_skipped_skus": sorted(too_short),
    }

    print("\nTEST METRICS (original sales units)")
    print("Global LSTM:", global_metrics)
    print("Last-value baseline:", baseline_metrics)
    print("Test forecast windows:", len(actual))
    print("Train end:", data.split_dates["train_end"])
    print("Validation end:", data.split_dates["validation_end"])
    print("SKU coverage:", coverage)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    if SUMMARY_PATH.exists():
        with SUMMARY_PATH.open("r", encoding="utf-8") as f:
            summary = json.load(f)
    else:
        summary = {}

    # Keep the existing common-window global-vs-per-SKU comparison intact.
    summary.update({
        "dataset_type": "synthetic",
        "lookback_days": data.lookback,
        "forecast_horizon_days": data.horizon,
        "train_end": data.split_dates["train_end"],
        "validation_end": data.split_dates["validation_end"],
        "total_test_windows": int(len(actual)),
        "global_lstm_full_test_metrics": global_metrics,
        "last_value_full_test_metrics": baseline_metrics,
        "sku_coverage": coverage,
        "global_checkpoint_training_seconds": float(
            checkpoint["training_seconds"]
        ),
        "best_epoch": int(checkpoint["best_epoch"]),
        "best_validation_mse": float(checkpoint["best_validation_mse"]),
        "note": (
            "Full-test metrics use all test windows. Any global-vs-per-SKU "
            "comparison must use the same common eligible test windows. "
            "The test set was not used for checkpoint selection."
        ),
    })

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Updated summary:", SUMMARY_PATH)
    print("Test set was not used for checkpoint selection.")


if __name__ == "__main__":
    run_evaluation()
