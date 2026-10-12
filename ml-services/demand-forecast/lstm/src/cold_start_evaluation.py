"""Evaluate a cold-start global LSTM on short-history SKUs."""

import copy
import json
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.global_data import load_global_data


DATA_PATH = "data/global_sku_demand_synthetic.csv"
LOOKBACK = 30
HORIZON = 7
EPOCHS = 50
PATIENCE = 8
BATCH_SIZE = 128
SEED = 42
SHORT_SKUS = {f"SKU{i:03d}" for i in range(10, 16)}


class ColdStartLSTM(nn.Module):
    """Global LSTM without SKU-specific embeddings."""

    def __init__(self, num_categories, num_warehouses, horizon=7):
        super().__init__()
        self.category_embedding = nn.Embedding(num_categories, 8)
        self.warehouse_embedding = nn.Embedding(num_warehouses, 8)
        self.lstm = nn.LSTM(
            input_size=4,
            hidden_size=64,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
        )
        self.head = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(64 + 16, 64),
            nn.ReLU(),
            nn.Linear(64, horizon),
        )

    def forward(self, x, sku, category, warehouse):
        # SKU ID is deliberately not used by this model.
        _, (hidden, _) = self.lstm(x)
        category_vector = self.category_embedding(category.long())
        warehouse_vector = self.warehouse_embedding(warehouse.long())
        combined = torch.cat(
            [hidden[-1], category_vector, warehouse_vector], dim=1
        )
        return self.head(combined)


def metrics(actual, predicted):
    error = predicted - actual
    nonzero = np.abs(actual) > 1e-8
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE_percent": (
            float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100)
            if nonzero.any()
            else None
        ),
    }


def main():
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    output = Path("output")
    output.mkdir(exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = load_global_data(
        DATA_PATH, lookback=LOOKBACK, horizon=HORIZON
    )

    train_loader = DataLoader(
        data.train, batch_size=BATCH_SIZE, shuffle=True
    )
    val_loader = DataLoader(
        data.validation, batch_size=BATCH_SIZE, shuffle=False
    )
    test_loader = DataLoader(
        data.test, batch_size=BATCH_SIZE, shuffle=False
    )

    model = ColdStartLSTM(
        num_categories=data.num_categories,
        num_warehouses=data.num_warehouses,
        horizon=HORIZON,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()
    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0
    patience_count = 0
    start_time = time.perf_counter()

    for epoch in range(1, EPOCHS + 1):
        model.train()
        for x, sku, category, warehouse, y in train_loader:
            x, category, warehouse, y = (
                x.to(device), category.to(device),
                warehouse.to(device), y.to(device)
            )
            optimizer.zero_grad()
            prediction = model(
                x, torch.zeros_like(category), category, warehouse
            )
            loss = loss_fn(prediction, y)
            loss.backward()
            optimizer.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for x, sku, category, warehouse, y in val_loader:
                x, category, warehouse, y = (
                    x.to(device), category.to(device),
                    warehouse.to(device), y.to(device)
                )
                prediction = model(
                    x, torch.zeros_like(category), category, warehouse
                )
                val_losses.append(loss_fn(prediction, y).item())

        val_loss = float(np.mean(val_losses))
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            patience_count = 0
        else:
            patience_count += 1

        if epoch == 1 or epoch % 5 == 0:
            print(
                f"Epoch {epoch:02d}: validation MSE={val_loss:.5f}"
            )

        if patience_count >= PATIENCE:
            print(f"Early stopping at epoch {epoch}")
            break

    training_seconds = time.perf_counter() - start_time
    if best_state is None:
        raise RuntimeError("Training did not produce a valid checkpoint.")

    model.load_state_dict(best_state)
    model.eval()

    all_sku, all_actual, all_predicted, all_naive = [], [], [], []

    with torch.no_grad():
        for x, sku, category, warehouse, y in test_loader:
            prediction = model(
                x.to(device),
                torch.zeros_like(sku).to(device),
                category.to(device),
                warehouse.to(device),
            ).cpu().numpy()

            # Feature 0 contains standardized sales.
            naive = np.repeat(x[:, -1, 0].numpy()[:, None], HORIZON, axis=1)

            all_sku.append(sku.numpy())
            all_actual.append(y.numpy())
            all_predicted.append(prediction)
            all_naive.append(naive)

    sku_ids = np.concatenate(all_sku)
    actual_scaled = np.concatenate(all_actual)
    predicted_scaled = np.concatenate(all_predicted)
    naive_scaled = np.concatenate(all_naive)

    def inverse(values):
        return data.scaler.inverse_transform(
            values.reshape(-1, 1)
        ).reshape(values.shape)

    actual = inverse(actual_scaled)
    predicted = inverse(predicted_scaled)
    naive = inverse(naive_scaled)

    reverse_sku = {v: k for k, v in data.sku_mapping.items()}
    short_ids = {
        data.sku_mapping[s]
        for s in SHORT_SKUS if s in data.sku_mapping
    }
    selected = np.isin(sku_ids, list(short_ids))

    if not selected.any():
        raise RuntimeError("No short-history SKU test windows were found.")

    rows = []
    for sku_idx in sorted(short_ids):
        mask = sku_ids == sku_idx
        if not mask.any():
            rows.append({
                "sku_id": reverse_sku[sku_idx],
                "test_windows": 0,
                "cold_start_MAE": None,
                "cold_start_RMSE": None,
                "cold_start_MAPE_percent": None,
                "last_value_MAE": None,
                "last_value_RMSE": None,
                "last_value_MAPE_percent": None,
            })
            continue

        cm = metrics(actual[mask], predicted[mask])
        bm = metrics(actual[mask], naive[mask])
        rows.append({
            "sku_id": reverse_sku[sku_idx],
            "test_windows": int(mask.sum()),
            "cold_start_MAE": cm["MAE"],
            "cold_start_RMSE": cm["RMSE"],
            "cold_start_MAPE_percent": cm["MAPE_percent"],
            "last_value_MAE": bm["MAE"],
            "last_value_RMSE": bm["RMSE"],
            "last_value_MAPE_percent": bm["MAPE_percent"],
        })

    pd.DataFrame(rows).to_csv(
        output / "short_history_cold_start_metrics.csv", index=False
    )

    cold_metrics = metrics(actual[selected], predicted[selected])
    baseline_metrics = metrics(actual[selected], naive[selected])

    checkpoint = {
        "model_state_dict": best_state,
        "lookback": LOOKBACK,
        "horizon": HORIZON,
        "num_categories": data.num_categories,
        "num_warehouses": data.num_warehouses,
        "best_epoch": best_epoch,
        "train_end": data.split_dates["train_end"],
        "validation_end": data.split_dates["validation_end"],
        "model_type": "cold_start_no_sku_embedding",
    }
    torch.save(checkpoint, output / "cold_start_best_model.pt")
    with open(output / "cold_start_scaler.pkl", "wb") as f:
        pickle.dump(data.scaler, f)

    summary = {
        "dataset_type": "synthetic",
        "model_type": "global LSTM without SKU embedding",
        "lookback_days": LOOKBACK,
        "forecast_horizon_days": HORIZON,
        "train_end": data.split_dates["train_end"],
        "validation_end": data.split_dates["validation_end"],
        "short_history_skus": sorted(SHORT_SKUS),
        "short_history_test_windows": int(selected.sum()),
        "best_epoch": best_epoch,
        "best_validation_mse": best_val_loss,
        "training_seconds": round(training_seconds, 2),
        "cold_start_lstm_metrics": cold_metrics,
        "last_value_baseline_metrics": baseline_metrics,
        "note": (
            "Metrics are on short-history SKU test windows only. "
            "Model selection used validation loss, not test metrics. "
            "MAPE can be unstable for low or zero sales."
        ),
    }
    with open(output / "short_history_cold_start_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\nSHORT-HISTORY COLD-START RESULTS")
    print(json.dumps(summary, indent=2))
    print("\nPer-SKU metrics:")
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\nSaved:")
    print("output/cold_start_best_model.pt")
    print("output/cold_start_scaler.pkl")
    print("output/short_history_cold_start_summary.json")
    print("output/short_history_cold_start_metrics.csv")


if __name__ == "__main__":
    main()
