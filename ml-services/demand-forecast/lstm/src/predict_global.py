
"""Load the trained global LSTM and forecast demand for one SKU."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from src.global_model import GlobalDemandLSTM


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = PROJECT_ROOT / "output" / "global_best_model.pt"
DEFAULT_DATA = PROJECT_ROOT / "data" / "global_sku_demand_synthetic.csv"


def load_model(checkpoint_path):
    """Load checkpoint, model configuration, scaler, and categorical mappings."""
    checkpoint_path = Path(checkpoint_path)

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # This is a trusted checkpoint produced by our own training script.
    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=True,
    )

    config = checkpoint["config"]

    model = GlobalDemandLSTM(**config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    return model, checkpoint


def make_input(history, lookback, scaler_mean, scaler_scale):
    """Build the four input features expected by the trained model."""
    history = history.sort_values("date").tail(lookback).copy()

    if len(history) < lookback:
        raise ValueError(
            f"Need at least {lookback} days of history; "
            f"received {len(history)}."
        )

    dates = pd.to_datetime(history["date"])
    sales = history["sales"].to_numpy(dtype=np.float32)

    # Use the exact scaler parameters learned during training.
    scaled_sales = (sales - scaler_mean[0]) / scaler_scale[0]

    day_of_week = dates.dt.dayofweek.to_numpy()
    dow_sin = np.sin(2 * np.pi * day_of_week / 7)
    dow_cos = np.cos(2 * np.pi * day_of_week / 7)

    promotion = history["promotion"].to_numpy(dtype=np.float32)

    features = np.column_stack(
        [scaled_sales, promotion, dow_sin, dow_cos]
    ).astype(np.float32)

    return torch.from_numpy(features).unsqueeze(0)


def forecast_sku(
    sku_id,
    data_path=DEFAULT_DATA,
    checkpoint_path=DEFAULT_CHECKPOINT,
    warehouse_id=None,
    category=None,
):
    """Return a 7-day forecast and approximate model-based explanations."""
    model, checkpoint = load_model(checkpoint_path)

    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])

    required = {
        "date", "sku_id", "category", "warehouse_id",
        "sales", "promotion",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")

    history = df[df["sku_id"].astype(str) == str(sku_id)].copy()

    if warehouse_id is not None:
        history = history[
            history["warehouse_id"].astype(str) == str(warehouse_id)
        ]

    if category is not None:
        history = history[history["category"].astype(str) == str(category)]

    if history.empty:
        raise ValueError(
            f"No historical rows found for SKU={sku_id}, "
            f"warehouse={warehouse_id}, category={category}."
        )

    # If multiple warehouses/categories remain, require an explicit choice.
    if history["warehouse_id"].nunique() != 1:
        raise ValueError(
            "This SKU exists in multiple warehouses. "
            "Pass --warehouse to select one."
        )
    if history["category"].nunique() != 1:
        raise ValueError(
            "This SKU exists in multiple categories. Pass --category."
        )

    selected_warehouse = str(history["warehouse_id"].iloc[0])
    selected_category = str(history["category"].iloc[0])

    sku_mapping = checkpoint["sku_mapping"]
    category_mapping = checkpoint["category_mapping"]
    warehouse_mapping = checkpoint["warehouse_mapping"]

    # Index 0 is reserved for UNK.
    mapped_sku = sku_mapping.get(str(sku_id), 0)
    mapped_category = category_mapping.get(selected_category, 0)
    mapped_warehouse = warehouse_mapping.get(selected_warehouse, 0)

    lookback = int(checkpoint["lookback"])
    scaler_mean = np.asarray(checkpoint["scaler_mean"], dtype=np.float32)
    scaler_scale = np.asarray(checkpoint["scaler_scale"], dtype=np.float32)

    x = make_input(
        history,
        lookback,
        scaler_mean,
        scaler_scale,
    )

    sku_tensor = torch.tensor([mapped_sku], dtype=torch.long)
    category_tensor = torch.tensor([mapped_category], dtype=torch.long)
    warehouse_tensor = torch.tensor([mapped_warehouse], dtype=torch.long)

    # Evaluation mode disables training-only SKU dropout.
    model.eval()
    with torch.no_grad():
        scaled_prediction = model(
            x, sku_tensor, category_tensor, warehouse_tensor
        ).cpu().numpy()[0]

        # Convert predictions back to the original sales units.
        forecast = scaled_prediction * scaler_scale[0] + scaler_mean[0]
        forecast = np.maximum(forecast, 0)

        # Compare against UNK SKU embedding while holding other inputs fixed.
        # This is a model sensitivity estimate, not a causal explanation.
        if mapped_sku != 0:
            unk_prediction = model(
                x,
                torch.tensor([0], dtype=torch.long),
                category_tensor,
                warehouse_tensor,
            ).cpu().numpy()[0]
            unk_prediction = (
                unk_prediction * scaler_scale[0] + scaler_mean[0]
            )
            embedding_effect = forecast - unk_prediction
        else:
            embedding_effect = np.zeros_like(forecast)

    history = history.sort_values("date")
    recent_sales = history["sales"].tail(7).to_numpy(dtype=float)

    if len(recent_sales) >= 2:
        recent_trend = float(recent_sales[-1] - recent_sales[0])
    else:
        recent_trend = 0.0

    last_date = pd.Timestamp(history["date"].max())
    forecast_dates = pd.date_range(
        start=pd.Timestamp(last_date).normalize() + pd.DateOffset(days=1),
        periods=len(forecast),
        freq="D",
    )

    reasons = [
        f"Recent 7-day sales change: {recent_trend:.2f} units "
        "(last observed minus first observed).",
        f"SKU embedding sensitivity: average {embedding_effect.mean():.2f} "
        "units/day compared with replacing the SKU ID with UNK.",
        "Forecast uses the recent sales sequence, promotion history, "
        "day-of-week features, and SKU/category/warehouse embeddings.",
    ]

    return {
        "sku_id": str(sku_id),
        "category": selected_category,
        "warehouse_id": selected_warehouse,
        "forecast_horizon_days": len(forecast),
        "forecast": [
            {
                "date": date.strftime("%Y-%m-%d"),
                "predicted_sales": round(float(value), 2),
            }
            for date, value in zip(forecast_dates, forecast)
        ],
        "reasons": reasons,
        "metadata": {
            "model": "GlobalDemandLSTM",
            "checkpoint": str(checkpoint_path),
            "best_epoch": checkpoint.get("best_epoch"),
            "sku_embedding_used": mapped_sku != 0,
            "unknown_category": mapped_category == 0,
            "unknown_warehouse": mapped_warehouse == 0,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Forecast the next 7 days for a SKU using the global LSTM."
    )
    parser.add_argument("--sku", required=True, help="SKU ID, e.g. SKU001")
    parser.add_argument("--warehouse", help="Warehouse ID, e.g. WH01")
    parser.add_argument("--category", help="Category, e.g. Electronics")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    args = parser.parse_args()

    result = forecast_sku(
        sku_id=args.sku,
        data_path=args.data,
        checkpoint_path=args.checkpoint,
        warehouse_id=args.warehouse,
        category=args.category,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
