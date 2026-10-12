"""Train the global multi-SKU LSTM using chronological validation."""

import copy
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def run_training():
    set_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    data = load_global_data(
        "data/global_sku_demand_synthetic.csv",
        lookback=45,
        horizon=7,
    )

    train_loader = DataLoader(
        data.train, batch_size=32, shuffle=True
    )
    val_loader = DataLoader(
        data.validation, batch_size=128, shuffle=False
    )

    model = GlobalDemandLSTM(
        num_skus=data.num_skus,
        num_categories=data.num_categories,
        num_warehouses=data.num_warehouses,
        num_numeric_features=4,
        embedding_dim=8,
        hidden_size=64,
        num_layers=2,
        horizon=data.horizon,
        dropout=0.2,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None
    patience = 8
    patience_count = 0
    epochs = 50
    start = time.perf_counter()

    for epoch in range(1, epochs + 1):
        model.train()
        train_losses = []

        for x, sku, category, warehouse, y in train_loader:
            x = x.to(device)
            sku = sku.to(device)
            category = category.to(device)
            warehouse = warehouse.to(device)
            y = y.to(device)

            optimizer.zero_grad()
            prediction = model(x, sku, category, warehouse)
            loss = loss_fn(prediction, y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        val_losses = []
        with torch.no_grad():
            for x, sku, category, warehouse, y in val_loader:
                prediction = model(
                    x.to(device),
                    sku.to(device),
                    category.to(device),
                    warehouse.to(device),
                )
                val_losses.append(
                    loss_fn(prediction, y.to(device)).item()
                )

        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses))
        print(
            f"Epoch {epoch:02d}/{epochs} | "
            f"train_loss={train_loss:.5f} | "
            f"val_loss={val_loss:.5f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            patience_count = 0
        else:
            patience_count += 1

        if patience_count >= patience:
            print("Early stopping: validation loss did not improve.")
            break

    if best_state is None:
        raise RuntimeError("Training did not produce a model checkpoint.")

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "global_best_model.pt"

    torch.save(
        {
            "model_state_dict": best_state,
            "num_skus": data.num_skus,
            "num_categories": data.num_categories,
            "num_warehouses": data.num_warehouses,
            "num_numeric_features": 4,
            "embedding_dim": 8,
            "hidden_size": 64,
            "num_layers": 2,
            "horizon": data.horizon,
            "lookback": data.lookback,
            "dropout": 0.2,
            "sku_mapping": data.sku_mapping,
            "category_mapping": data.category_mapping,
            "warehouse_mapping": data.warehouse_mapping,
            "train_end": data.split_dates["train_end"],
            "validation_end": data.split_dates["validation_end"],
            "best_validation_loss": best_val_loss,
        },
        checkpoint_path,
    )

    # Keep scaler separate for later inverse-transforming predictions.
    import pickle

    with open(output_dir / "global_scaler.pkl", "wb") as f:
        pickle.dump(data.scaler, f)

    elapsed = time.perf_counter() - start
    print("\nTRAINING COMPLETE")
    print("Best validation MSE:", round(best_val_loss, 6))
    print("Training time (seconds):", round(elapsed, 2))
    print("Checkpoint:", checkpoint_path)
    print("Scaler:", output_dir / "global_scaler.pkl")


if __name__ == "__main__":
    run_training()
