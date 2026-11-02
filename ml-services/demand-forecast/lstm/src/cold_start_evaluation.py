
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

SEED = 42
LOOKBACK = 45
HORIZON = 7
BATCH_SIZE = 32
EPOCHS = 50
LEARNING_RATE = 1e-3
PATIENCE = 8

# These SKUs are never used for model training/validation.
COLD_SKUS = {
    "SKU010",
    "SKU011",
    "SKU012",
    "SKU013",
    "SKU014",
    "SKU015",
}

OUTPUT_DIR = Path("output")
DATA_PATH = Path("data/global_sku_demand_synthetic.csv")

EXPERIMENT_NAME = "Demand-Forecast-Cold-Start"


# ---------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------

def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def calculate_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict:
    actual = np.asarray(actual, dtype=np.float64).reshape(-1)
    predicted = np.asarray(predicted, dtype=np.float64).reshape(-1)

    if actual.size == 0:
        raise ValueError("Cannot calculate metrics: no test targets.")

    errors = actual - predicted

    nonzero = np.abs(actual) > 1e-8
    mape = (
        np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100
        if nonzero.any()
        else float("nan")
    )

    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "mape": float(mape),
    }


# ---------------------------------------------------------
# Data preparation
# ---------------------------------------------------------

def load_and_prepare_data() -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH.resolve()}"
        )

    df = pd.read_csv(DATA_PATH)

    required = {
        "date",
        "sku_id",
        "category",
        "warehouse_id",
        "sales",
        "promotion",
        "day_of_week",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df["promotion"] = pd.to_numeric(
        df["promotion"], errors="coerce"
    )
    df["day_of_week"] = pd.to_numeric(
        df["day_of_week"], errors="coerce"
    )

    df = df.dropna(
        subset=[
            "date",
            "sku_id",
            "category",
            "warehouse_id",
            "sales",
            "promotion",
            "day_of_week",
        ]
    ).copy()

    df["sku_id"] = df["sku_id"].astype(str)
    df = df.sort_values(["date", "sku_id"]).reset_index(drop=True)

    cold_skus = sorted(COLD_SKUS.intersection(set(df["sku_id"])))
    if not cold_skus:
        raise ValueError(
            f"None of the configured cold SKUs were found: {COLD_SKUS}"
        )

    known_df = df[~df["sku_id"].isin(COLD_SKUS)].copy()
    cold_df = df[df["sku_id"].isin(COLD_SKUS)].copy()

    # Split dates are determined chronologically.
    unique_dates = np.array(sorted(df["date"].unique()))
    if len(unique_dates) < 10:
        raise ValueError("Not enough unique dates for chronological splits.")

    train_end = pd.Timestamp(unique_dates[int(len(unique_dates) * 0.70) - 1])
    val_end = pd.Timestamp(unique_dates[int(len(unique_dates) * 0.85) - 1])

    # Fit scaler ONLY on known SKU sales within the training period.
    scaler = StandardScaler()
    scaler.fit(
        known_df.loc[known_df["date"] <= train_end, ["sales"]]
    )

    # Metadata vocabulary comes only from known SKUs.
    category_values = sorted(known_df["category"].astype(str).unique())
    warehouse_values = sorted(
        known_df["warehouse_id"].astype(str).unique()
    )
    known_sku_values = sorted(known_df["sku_id"].unique())

    # Index 0 is reserved for unknown values.
    category_mapping = {
        value: index + 1
        for index, value in enumerate(category_values)
    }
    warehouse_mapping = {
        value: index + 1
        for index, value in enumerate(warehouse_values)
    }
    sku_mapping = {
        value: index + 1
        for index, value in enumerate(known_sku_values)
    }

    def transform_frame(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()

        result["scaled_sales"] = scaler.transform(
            result[["sales"]]
        ).reshape(-1)

        dow = result["day_of_week"].astype(float)
        result["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
        result["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

        result["category_idx"] = (
            result["category"].astype(str)
            .map(category_mapping)
            .fillna(0)
            .astype("int64")
        )
        result["warehouse_idx"] = (
            result["warehouse_id"].astype(str)
            .map(warehouse_mapping)
            .fillna(0)
            .astype("int64")
        )
        result["sku_idx"] = (
            result["sku_id"].map(sku_mapping)
            .fillna(0)
            .astype("int64")
        )

        return result

    known_df = transform_frame(known_df)
    cold_df = transform_frame(cold_df)

    feature_columns = [
        "scaled_sales",
        "promotion",
        "dow_sin",
        "dow_cos",
    ]

    def make_samples(
        frame: pd.DataFrame,
        mode: str,
    ) -> list[dict]:
        samples = []

        for sku, group in frame.groupby("sku_id"):
            group = group.sort_values("date").reset_index(drop=True)

            if len(group) < LOOKBACK + HORIZON:
                continue

            features = group[feature_columns].to_numpy(
                dtype=np.float32
            )
            sales = group["scaled_sales"].to_numpy(dtype=np.float32)
            dates = group["date"].to_numpy()

            sku_idx = int(group["sku_idx"].iloc[0])
            category_idx = int(group["category_idx"].iloc[0])
            warehouse_idx = int(group["warehouse_idx"].iloc[0])

            for start in range(
                0,
                len(group) - LOOKBACK - HORIZON + 1,
            ):
                input_end = start + LOOKBACK
                target_end = input_end + HORIZON

                target_dates = dates[input_end:target_end]
                target_start_date = pd.Timestamp(target_dates[0])
                target_end_date = pd.Timestamp(target_dates[-1])

                if mode == "train":
                    # Both input and target remain in training period.
                    if target_end_date > train_end:
                        continue
                elif mode == "validation":
                    if (
                        target_start_date <= train_end
                        or target_end_date > val_end
                    ):
                        continue
                elif mode == "cold_test":
                    if target_start_date <= val_end:
                        continue

                samples.append(
                    {
                        "X": features[start:input_end],
                        "y": sales[input_end:target_end],
                        "sku_idx": sku_idx,
                        "category_idx": category_idx,
                        "warehouse_idx": warehouse_idx,
                        "sku": sku,
                    }
                )

        return samples

    train_samples = make_samples(known_df, "train")
    val_samples = make_samples(known_df, "validation")
    cold_samples = make_samples(cold_df, "cold_test")

    if not train_samples:
        raise ValueError("No training windows generated.")
    if not val_samples:
        raise ValueError(
            "No validation windows generated. Check dataset date ranges."
        )
    if not cold_samples:
        counts = cold_df.groupby("sku_id").size().to_dict()
        raise ValueError(
            "No cold test windows generated after the validation cutoff. "
            f"Cold SKU row counts: {counts}; train_end={train_end.date()}, "
            f"val_end={val_end.date()}. Check cold SKU date ranges."
        )

    return {
        "train_samples": train_samples,
        "val_samples": val_samples,
        "cold_samples": cold_samples,
        "scaler": scaler,
        "train_end": str(train_end.date()),
        "val_end": str(val_end.date()),
        "num_skus": len(sku_mapping) + 1,
        "num_categories": len(category_mapping) + 1,
        "num_warehouses": len(warehouse_mapping) + 1,
        "known_skus": known_sku_values,
        "cold_skus": cold_skus,
        "feature_count": len(feature_columns),
    }


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

class GlobalLSTM(nn.Module):
    """Global model without SKU/category/warehouse embeddings."""

    def __init__(
        self,
        input_size: int = 4,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = HORIZON,
        dropout: float = 0.2,
    ):
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
            nn.Linear(64, horizon),
        )

    def forward(
        self,
        x: torch.Tensor,
        sku_idx: torch.Tensor | None = None,
        category_idx: torch.Tensor | None = None,
        warehouse_idx: torch.Tensor | None = None,
    ) -> torch.Tensor:
        output, _ = self.lstm(x)
        return self.head(output[:, -1, :])


class GlobalLSTMWithEmbeddings(nn.Module):
    """Global model using SKU, category and warehouse embeddings."""

    def __init__(
        self,
        num_skus: int,
        num_categories: int,
        num_warehouses: int,
        input_size: int = 4,
        embedding_dim: int = 8,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizon: int = HORIZON,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.sku_embedding = nn.Embedding(num_skus, embedding_dim)
        self.category_embedding = nn.Embedding(
            num_categories, embedding_dim
        )
        self.warehouse_embedding = nn.Embedding(
            num_warehouses, embedding_dim
        )

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        combined_size = hidden_size + 3 * embedding_dim
        self.head = nn.Sequential(
            nn.Linear(combined_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, horizon),
        )

    def forward(
        self,
        x: torch.Tensor,
        sku_idx: torch.Tensor,
        category_idx: torch.Tensor,
        warehouse_idx: torch.Tensor,
    ) -> torch.Tensor:
        output, _ = self.lstm(x)
        sequence_features = output[:, -1, :]

        sku_emb = self.sku_embedding(sku_idx)
        category_emb = self.category_embedding(category_idx)
        warehouse_emb = self.warehouse_embedding(warehouse_idx)

        combined = torch.cat(
            [
                sequence_features,
                sku_emb,
                category_emb,
                warehouse_emb,
            ],
            dim=1,
        )

        return self.head(combined)


# ---------------------------------------------------------
# Tensor conversion and training
# ---------------------------------------------------------

def samples_to_tensors(
    samples: list[dict],
    device: torch.device,
) -> tuple[torch.Tensor, ...]:
    X = torch.tensor(
        np.stack([s["X"] for s in samples]),
        dtype=torch.float32,
        device=device,
    )
    y = torch.tensor(
        np.stack([s["y"] for s in samples]),
        dtype=torch.float32,
        device=device,
    )
    sku = torch.tensor(
        [s["sku_idx"] for s in samples],
        dtype=torch.long,
        device=device,
    )
    category = torch.tensor(
        [s["category_idx"] for s in samples],
        dtype=torch.long,
        device=device,
    )
    warehouse = torch.tensor(
        [s["warehouse_idx"] for s in samples],
        dtype=torch.long,
        device=device,
    )

    return X, y, sku, category, warehouse


def predict_model(
    model: nn.Module,
    samples: list[dict],
    device: torch.device,
    with_embeddings: bool,
) -> np.ndarray:
    model.eval()
    predictions = []

    X, _, sku, category, warehouse = samples_to_tensors(
        samples, device
    )

    with torch.no_grad():
        for start in range(0, len(samples), 128):
            end = start + 128
            if with_embeddings:
                output = model(
                    X[start:end],
                    sku[start:end],
                    category[start:end],
                    warehouse[start:end],
                )
            else:
                output = model(X[start:end])

            predictions.append(output.cpu().numpy())

    return np.concatenate(predictions, axis=0)


def train_model(
    model: nn.Module,
    train_samples: list[dict],
    val_samples: list[dict],
    device: torch.device,
    with_embeddings: bool,
    mask_unknown_metadata: bool = False,
) -> tuple[nn.Module, float]:
    X_train, y_train, sku_train, cat_train, wh_train = (
        samples_to_tensors(train_samples, device)
    )

    X_val, y_val, sku_val, cat_val, wh_val = (
        samples_to_tensors(val_samples, device)
    )

    train_loader = DataLoader(
        TensorDataset(
            X_train,
            y_train,
            sku_train,
            cat_train,
            wh_train,
        ),
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )
    loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0

    started = time.perf_counter()

    for epoch in range(EPOCHS):
        model.train()
        total_train_loss = 0.0
        total_count = 0

        for Xb, yb, sb, cb, wb in train_loader:
            # Simulate unknown SKU IDs during training so the
            # UNK SKU embedding learns a meaningful representation.
            if with_embeddings:
                sb = sb.clone()
                unknown_mask = (
                    torch.rand(sb.shape, device=device) < 0.20
                )
                sb[unknown_mask] = 0

                # Unknown category/warehouse indices also need
                # training examples; otherwise their embeddings
                # would remain untrained.
                if mask_unknown_metadata:
                    cb = cb.clone()
                    wb = wb.clone()

                    cat_mask = (
                        torch.rand(cb.shape, device=device) < 0.10
                    )
                    wh_mask = (
                        torch.rand(wb.shape, device=device) < 0.10
                    )
                    cb[cat_mask] = 0
                    wb[wh_mask] = 0

                prediction = model(Xb, sb, cb, wb)
            else:
                prediction = model(Xb)

            loss = loss_fn(prediction, yb)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), max_norm=1.0
            )
            optimizer.step()

            total_train_loss += loss.item() * len(Xb)
            total_count += len(Xb)

        model.eval()
        with torch.no_grad():
            if with_embeddings:
                val_prediction = model(
                    X_val, sku_val, cat_val, wh_val
                )
            else:
                val_prediction = model(X_val)

            val_loss = loss_fn(val_prediction, y_val).item()

        train_loss = total_train_loss / max(total_count, 1)

        print(
            f"Epoch {epoch + 1:02d}/{EPOCHS} | "
            f"train_loss={train_loss:.5f} | "
            f"val_loss={val_loss:.5f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= PATIENCE:
            print("Early stopping.")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    training_seconds = time.perf_counter() - started
    return model, training_seconds


# ---------------------------------------------------------
# Baseline
# ---------------------------------------------------------

def last_value_predictions(
    samples: list[dict],
) -> np.ndarray:
    predictions = []

    for sample in samples:
        # The last observed sales value in the input sequence.
        # scaled_sales is feature 0, so invert it using the scaler
        # outside this function; this function is replaced below.
        predictions.append(
            np.repeat(sample["last_sales"], HORIZON)
        )

    return np.stack(predictions)


# ---------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------

def main() -> None:
    set_seed()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load_and_prepare_data()

    train_samples = data["train_samples"]
    val_samples = data["val_samples"]
    cold_samples = data["cold_samples"]

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print(f"Device: {device}")
    print(f"Train windows: {len(train_samples)}")
    print(f"Validation windows: {len(val_samples)}")
    print(f"Cold test windows: {len(cold_samples)}")
    print(f"Known SKUs: {len(data['known_skus'])}")
    print(f"Cold SKUs: {data['cold_skus']}")
    print(f"Train cutoff: {data['train_end']}")
    print(f"Validation cutoff: {data['val_end']}")

    # Add the final observed sales value to each test sample.
    # Recover original sales from the standardized first feature.
    scaler = data["scaler"]
    for sample in cold_samples:
        last_scaled_sales = sample["X"][-1, 0]
        sample["last_sales"] = float(
            scaler.inverse_transform(
                np.array([[last_scaled_sales]])
            )[0, 0]
        )

    actual_scaled = np.stack([sample["y"] for sample in cold_samples])

    actual = scaler.inverse_transform(
        actual_scaled.reshape(-1, 1)
    ).reshape(actual_scaled.shape)

    # Same exact cold test windows for all three methods.
    mlflow.set_experiment(EXPERIMENT_NAME)

    results = {}
    model_configs = [
        ("global_lstm_no_embeddings", False, False),
        ("global_lstm_with_embeddings", True, True),
    ]

    for model_name, with_embeddings, mask_metadata in model_configs:
        set_seed()

        if with_embeddings:
            model = GlobalLSTMWithEmbeddings(
                num_skus=data["num_skus"],
                num_categories=data["num_categories"],
                num_warehouses=data["num_warehouses"],
            ).to(device)
        else:
            model = GlobalLSTM().to(device)

        with mlflow.start_run(run_name=model_name):
            mlflow.log_params(
                {
                    "model": model_name,
                    "lookback": LOOKBACK,
                    "horizon": HORIZON,
                    "epochs": EPOCHS,
                    "batch_size": BATCH_SIZE,
                    "cold_skus": ",".join(data["cold_skus"]),
                    "train_cutoff": data["train_end"],
                    "validation_cutoff": data["val_end"],
                    "embedding_dim": 8 if with_embeddings else 0,
                    "unknown_sku_dropout": 0.20 if with_embeddings else 0.0,
                    "unknown_metadata_dropout": (
                        0.10 if mask_metadata else 0.0
                    ),
                }
            )

            model, training_seconds = train_model(
                model,
                train_samples,
                val_samples,
                device,
                with_embeddings,
                mask_unknown_metadata=mask_metadata,
            )

            predictions_scaled = predict_model(
                model,
                cold_samples,
                device,
                with_embeddings,
            )

            # Models predict standardized sales, so convert back to
            # the original sales scale before evaluating.
            predictions = scaler.inverse_transform(
                predictions_scaled.reshape(-1, 1)
            ).reshape(predictions_scaled.shape)

            metrics = calculate_metrics(actual, predictions)
            metrics["training_seconds"] = float(training_seconds)
            results[model_name] = metrics

            mlflow.log_metrics(
                {
                    "test_mae": metrics["mae"],
                    "test_rmse": metrics["rmse"],
                    "test_mape": metrics["mape"],
                    "training_seconds": training_seconds,
                }
            )

            model_path = OUTPUT_DIR / f"{model_name}.pt"
            torch.save(model.state_dict(), model_path)
            mlflow.log_artifact(str(model_path))

            print(f"\n{model_name}")
            print(json.dumps(metrics, indent=2))

    # Last-value baseline: repeat the last observed sales value
    # for all seven forecast days.
    baseline_predictions = np.stack(
        [
            np.repeat(sample["last_sales"], HORIZON)
            for sample in cold_samples
        ]
    )
    baseline_metrics = calculate_metrics(actual, baseline_predictions)
    baseline_metrics["training_seconds"] = 0.0
    results["last_value_baseline"] = baseline_metrics

    with mlflow.start_run(run_name="last_value_baseline"):
        mlflow.log_params(
            {
                "model": "last_value_baseline",
                "lookback": LOOKBACK,
                "horizon": HORIZON,
                "cold_skus": ",".join(data["cold_skus"]),
            }
        )
        mlflow.log_metrics(
            {
                "test_mae": baseline_metrics["mae"],
                "test_rmse": baseline_metrics["rmse"],
                "test_mape": baseline_metrics["mape"],
                "training_seconds": 0.0,
            }
        )

    summary = {
        "experiment": EXPERIMENT_NAME,
        "evaluation": "cold-start SKUs excluded from training and validation",
        "train_cutoff": data["train_end"],
        "validation_cutoff": data["val_end"],
        "lookback": LOOKBACK,
        "horizon": HORIZON,
        "train_windows": len(train_samples),
        "validation_windows": len(val_samples),
        "cold_test_windows": len(cold_samples),
        "known_skus": data["known_skus"],
        "cold_skus": data["cold_skus"],
        "metrics": results,
    }

    summary_path = OUTPUT_DIR / "short_history_cold_start_summary.json"
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    rows = []
    for model_name, metrics in results.items():
        rows.append(
            {
                "model": model_name,
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "mape": metrics["mape"],
                "training_seconds": metrics["training_seconds"],
            }
        )

    results_path = OUTPUT_DIR / "short_history_cold_start_metrics.csv"
    pd.DataFrame(rows).sort_values("mae").to_csv(
        results_path, index=False
    )

    print("\nFinal results sorted by MAE:")
    print(
        pd.DataFrame(rows)
        .sort_values("mae")
        .to_string(index=False)
    )

    print(f"\nSaved summary: {summary_path}")
    print(f"Saved metrics: {results_path}")


if __name__ == "__main__":
    main()
