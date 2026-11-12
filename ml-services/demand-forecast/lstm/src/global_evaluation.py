
"""Evaluate global multi-SKU LSTM using a safe, self-contained checkpoint."""

import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.global_data import load_global_data
from src.global_model import load_global_checkpoint
from src.config import (
    GLOBAL_DATA_PATH as DATA_PATH,
    GLOBAL_LOOKBACK as LOOKBACK,
    GLOBAL_HORIZON as HORIZON,
    GLOBAL_VALIDATION_BATCH_SIZE as BATCH_SIZE,
)


CHECKPOINT_PATH = Path("output/global_best_model.pt")
SUMMARY_PATH = Path("output/global_vs_per_sku_summary.json")



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

    model, checkpoint = load_global_checkpoint(
        CHECKPOINT_PATH,
        map_location="cpu",
    )

    if "training_seconds" not in checkpoint:
        raise ValueError(
            "Checkpoint is missing training_seconds metadata. "
            "Retrain with the updated global_train.py."
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

    coverage = {
        "skus_with_train_windows": data.skus_with_train_windows,
        "skus_mapped_to_unk": data.skus_mapped_to_unk,
        "too_short_skipped_skus": data.too_short_skipped,
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
