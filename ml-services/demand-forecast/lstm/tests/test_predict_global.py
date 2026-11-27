import numpy as np
import pandas as pd
import pytest
import torch

from src.predict_global import (
    DEFAULT_CHECKPOINT,
    DEFAULT_DATA,
    forecast_sku,
    load_model,
    make_input,
)


def test_forecast_sku_runs_on_saved_checkpoint():
    result = forecast_sku("SKU001")

    values = [row["predicted_sales"] for row in result["forecast"]]
    assert len(values) == result["forecast_horizon_days"] == 7
    assert all(value >= 0 for value in values)

    history = pd.read_csv(DEFAULT_DATA)
    last_date = pd.to_datetime(history.loc[history["sku_id"] == "SKU001", "date"]).max()
    assert result["forecast"][0]["date"] == (last_date + pd.Timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )
    assert result["metadata"]["sku_embedding_used"] is True


def test_embedding_effect_uses_clipped_unk_forecast():
    model, checkpoint = load_model(DEFAULT_CHECKPOINT)
    model.eval()

    history = pd.read_csv(DEFAULT_DATA)
    history = history[history["sku_id"] == "SKU001"]
    mean = np.asarray(checkpoint["scaler_mean"], dtype=np.float32)
    scale = np.asarray(checkpoint["scaler_scale"], dtype=np.float32)
    x = make_input(history, int(checkpoint["lookback"]), mean, scale)

    category = torch.tensor(
        [checkpoint["category_mapping"][str(history["category"].iloc[0])]]
    )
    warehouse = torch.tensor(
        [checkpoint["warehouse_mapping"][str(history["warehouse_id"].iloc[0])]]
    )
    with torch.no_grad():
        sku = model(
            x,
            torch.tensor([checkpoint["sku_mapping"]["SKU001"]]),
            category,
            warehouse,
        ).numpy()[0]
        unk = model(x, torch.tensor([0]), category, warehouse).numpy()[0]

    forecast = np.maximum(sku * scale[0] + mean[0], 0)
    unk = np.maximum(unk * scale[0] + mean[0], 0)
    expected = (forecast - unk).mean()

    result = forecast_sku("SKU001")
    reason = next(r for r in result["reasons"] if "embedding" in r)
    assert f"average {expected:.2f} " in reason


def test_make_input_rejects_gaps_in_history():
    history = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=50, freq="D"),
            "sales": np.arange(50, dtype=float),
            "promotion": 0,
        }
    ).drop(index=30)

    with pytest.raises(ValueError, match="continuous"):
        make_input(history, 45, np.array([0.0]), np.array([1.0]))
