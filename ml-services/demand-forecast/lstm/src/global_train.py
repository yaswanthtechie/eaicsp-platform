
"""Train global multi-SKU LSTM and save a self-contained safe checkpoint."""

import time
from pathlib import Path

import mlflow
import torch
from torch import nn
from torch.utils.data import DataLoader

from src.common import set_seed, fit_with_early_stopping
from src.global_data import load_global_data
from src.global_model import GlobalDemandLSTM


SEED = 42
DATA_PATH = "data/global_sku_demand_synthetic.csv"
OUTPUT_DIR = Path("output")

LOOKBACK = 45
HORIZON = 7
BATCH_SIZE = 32
VALIDATION_BATCH_SIZE = 128
LEARNING_RATE = 0.001
EMBEDDING_DIM = 8
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
EPOCHS = 50
PATIENCE = 8

MLFLOW_EXPERIMENT = "Demand-Forecast-LSTM-Global"


def run_training():
    """Train using chronological validation and save the best checkpoint."""
    set_seed(SEED)

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    data = load_global_data(
        DATA_PATH,
        lookback=LOOKBACK,
        horizon=HORIZON,
    )

    if len(data.train) == 0 or len(data.validation) == 0:
        raise RuntimeError("Training or validation dataset is empty.")

    train_loader = DataLoader(
        data.train,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )
    val_loader = DataLoader(
        data.validation,
        batch_size=VALIDATION_BATCH_SIZE,
        shuffle=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = OUTPUT_DIR / "global_best_model.pt"

    with mlflow.start_run(run_name="global-lstm-sku-embedding"):
        mlflow.log_params({
            "seed": SEED,
            "data_path": DATA_PATH,
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "batch_size": BATCH_SIZE,
            "validation_batch_size": VALIDATION_BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "embedding_dim": EMBEDDING_DIM,
            "hidden_size": HIDDEN_SIZE,
            "num_layers": NUM_LAYERS,
            "dropout": DROPOUT,
            "epochs_configured": EPOCHS,
            "early_stopping_patience": PATIENCE,
            "num_skus": data.num_skus,
            "num_categories": data.num_categories,
            "num_warehouses": data.num_warehouses,
            "num_train_windows": len(data.train),
            "num_validation_windows": len(data.validation),
            "device": str(device),
        })

        model = GlobalDemandLSTM(
            num_skus=data.num_skus,
            num_categories=data.num_categories,
            num_warehouses=data.num_warehouses,
            num_numeric_features=4,
            embedding_dim=EMBEDDING_DIM,
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

        def forward_batch(model, batch, device):
            """Move a batch to the selected device and make predictions."""
            x, sku, category, warehouse, y = batch

            prediction = model(
                x.to(device),
                sku.to(device),
                category.to(device),
                warehouse.to(device),
            )

            return prediction, y.to(device)

        def log_epoch_metrics(epoch, train_loss, val_loss):
            """Log per-epoch losses to MLflow."""
            mlflow.log_metrics(
                {
                    "train_mse": train_loss,
                    "validation_mse": val_loss,
                },
                step=epoch,
            )

        start = time.perf_counter()

        result = fit_with_early_stopping(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            optimizer=optimizer,
            loss_fn=loss_fn,
            device=device,
            epochs=EPOCHS,
            patience=PATIENCE,
            forward_batch=forward_batch,
            on_epoch_end=log_epoch_metrics,
        )

        elapsed = time.perf_counter() - start

        best_state = result["best_state"]
        best_val_loss = result["best_val_loss"]
        best_epoch = result["best_epoch"]
        epochs_completed = result["epochs_completed"]

        # The shared training function has restored the best weights.
        checkpoint = {
            "state_dict": best_state,
            "config": {
                "num_skus": int(data.num_skus),
                "num_categories": int(data.num_categories),
                "num_warehouses": int(data.num_warehouses),
                "num_numeric_features": 4,
                "embedding_dim": EMBEDDING_DIM,
                "hidden_size": HIDDEN_SIZE,
                "num_layers": NUM_LAYERS,
                "horizon": int(data.horizon),
                "dropout": DROPOUT,
            },
            "scaler_mean": data.scaler.mean_.tolist(),
            "scaler_scale": data.scaler.scale_.tolist(),
            "sku_mapping": {
                str(k): int(v) for k, v in data.sku_mapping.items()
            },
            "category_mapping": {
                str(k): int(v) for k, v in data.category_mapping.items()
            },
            "warehouse_mapping": {
                str(k): int(v) for k, v in data.warehouse_mapping.items()
            },
            "lookback": LOOKBACK,
            "seed": SEED,
            "best_epoch": int(best_epoch),
            "best_validation_mse": float(best_val_loss),
            "training_seconds": float(elapsed),
        }

        torch.save(checkpoint, checkpoint_path)

        mlflow.log_metrics({
            "best_validation_mse": float(best_val_loss),
            "best_epoch": float(best_epoch),
            "epochs_completed": float(epochs_completed),
            "training_seconds": float(elapsed),
        })

        mlflow.log_artifact(str(checkpoint_path))

        print("\nTRAINING COMPLETE")
        print("Best validation MSE:", round(best_val_loss, 6))
        print("Best epoch:", best_epoch)
        print("Epochs completed:", epochs_completed)
        print("Training time (seconds):", round(elapsed, 2))
        print("Checkpoint:", checkpoint_path)
        print("Scaler: stored inside checkpoint")
        print("MLflow run ID:", mlflow.active_run().info.run_id)


if __name__ == "__main__":
    run_training()
