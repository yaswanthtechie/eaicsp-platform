import json
import math

import numpy as np
import pandas as pd
import pytest
import torch
from torch.utils.data import DataLoader

import src.global_evaluation as evaluation
from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM, CHECKPOINT_KEYS


@pytest.fixture
def small_df():
    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    rows = []

    for sku_index in range(3):
        for i, date in enumerate(dates):
            rows.append({
                "date": date,
                "sku_id": f"SKU{sku_index + 1}",
                "category": f"Category{sku_index % 2}",
                "warehouse_id": f"WH{sku_index % 2}",
                "sales": float(20 + sku_index * 5 + i * 0.2 + np.sin(i / 5)),
                "promotion": float(i % 7 == 0),
                "day_of_week": date.dayofweek,
            })

    return pd.DataFrame(rows)


def test_run_evaluation_writes_full_test_metrics(small_df, tmp_path, monkeypatch):
    torch.manual_seed(42)
    np.random.seed(42)

    lookback = 5
    horizon = 2

    data_path = tmp_path / "small_global_data.csv"
    small_df.to_csv(data_path, index=False)

    data = load_global_data(data_path, lookback=lookback, horizon=horizon)

    config = {
        "num_skus": data.num_skus,
        "num_categories": data.num_categories,
        "num_warehouses": data.num_warehouses,
        "num_numeric_features": 4,
        "embedding_dim": 2,
        "hidden_size": 4,
        "num_layers": 1,
        "horizon": horizon,
        "dropout": 0.0,
    }

    model = GlobalDemandLSTM(**config)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = torch.nn.MSELoss()

    model.train()
    train_loader = DataLoader(data.train, batch_size=8, shuffle=False)

    for x, sku, category, warehouse, y in train_loader:
        optimizer.zero_grad()
        prediction = model(x, sku, category, warehouse)
        loss = loss_fn(prediction, y)
        loss.backward()
        optimizer.step()

    checkpoint = {
        "state_dict": model.state_dict(),
        "config": config,
        "scaler_mean": data.scaler.mean_.tolist(),
        "scaler_scale": data.scaler.scale_.tolist(),
        "sku_mapping": data.sku_mapping,
        "category_mapping": data.category_mapping,
        "warehouse_mapping": data.warehouse_mapping,
        "lookback": lookback,
        "training_seconds": 1.0,
        "best_epoch": 1,
        "best_validation_mse": 0.5,
    }

    assert CHECKPOINT_KEYS.issubset(checkpoint.keys())

    checkpoint_path = tmp_path / "global_best_model.pt"
    torch.save(checkpoint, checkpoint_path)

    summary_path = tmp_path / "summary.json"

    monkeypatch.setattr(evaluation, "CHECKPOINT_PATH", checkpoint_path)
    monkeypatch.setattr(evaluation, "SUMMARY_PATH", summary_path)
    monkeypatch.setattr(evaluation, "DATA_PATH", data_path)
    monkeypatch.setattr(evaluation, "LOOKBACK", lookback)
    monkeypatch.setattr(evaluation, "HORIZON", horizon)
    monkeypatch.setattr(evaluation, "BATCH_SIZE", 8)

    evaluation.run_evaluation()

    assert summary_path.exists()

    with summary_path.open("r", encoding="utf-8") as file:
        summary = json.load(file)

    assert "global_lstm_full_test_metrics" in summary

    mae = summary["global_lstm_full_test_metrics"]["MAE"]
    assert math.isfinite(mae)
    assert mae >= 0
    assert summary["total_test_windows"] > 0
