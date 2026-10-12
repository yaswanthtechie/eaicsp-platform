"""Evaluate the saved global LSTM on the held-out chronological test set."""

import pickle
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


def calculate_metrics(actual, predicted):
    error = predicted - actual
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error ** 2)))
    nonzero = np.abs(actual) > 1e-8
    mape = (
        float(np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100)
        if nonzero.any()
        else float("nan")
    )
    return {"MAE": mae, "RMSE": rmse, "MAPE_percent": mape}


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint_path = Path("output/global_best_model.pt")
    scaler_path = Path("output/global_scaler.pkl")

    if not checkpoint_path.exists() or not scaler_path.exists():
        raise FileNotFoundError(
            "Train the model first with: python -m src.global_train"
        )

    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False
    )
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)

    data = load_global_data(
        "data/global_sku_demand_synthetic.csv",
        lookback=checkpoint["lookback"],
        horizon=checkpoint["horizon"],
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

    loader = DataLoader(data.test, batch_size=128, shuffle=False)
    actual_scaled, predicted_scaled, naive_scaled = [], [], []

    with torch.no_grad():
        for x, sku, category, warehouse, y in loader:
            prediction = model(
                x.to(device),
                sku.to(device),
                category.to(device),
                warehouse.to(device),
            ).cpu().numpy()

            actual_scaled.append(y.numpy())
            predicted_scaled.append(prediction)

            # Feature 0 is standardized historical sales.
            last_sales = x[:, -1, 0].numpy()
            naive_scaled.append(
                np.repeat(last_sales[:, None], y.shape[1], axis=1)
            )

    actual_scaled = np.concatenate(actual_scaled)
    predicted_scaled = np.concatenate(predicted_scaled)
    naive_scaled = np.concatenate(naive_scaled)

    actual = scaler.inverse_transform(
        actual_scaled.reshape(-1, 1)
    ).reshape(actual_scaled.shape)
    predicted = scaler.inverse_transform(
        predicted_scaled.reshape(-1, 1)
    ).reshape(predicted_scaled.shape)
    naive = scaler.inverse_transform(
        naive_scaled.reshape(-1, 1)
    ).reshape(naive_scaled.shape)

    global_metrics = calculate_metrics(actual, predicted)
    naive_metrics = calculate_metrics(actual, naive)

    print("TEST METRICS (original sales units)")
    print("Global LSTM:", global_metrics)
    print("Last-value baseline:", naive_metrics)
    print("Test forecast windows:", len(data.test))
    print("Train end:", checkpoint["train_end"])
    print("Validation end:", checkpoint["validation_end"])
    print("Test set was not used for checkpoint selection.")


if __name__ == "__main__":
    main()
