"""Leakage-aware dataset preparation for the global SKU LSTM."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import TensorDataset


REQUIRED_COLUMNS = {
    "date", "sku_id", "category", "warehouse_id",
    "sales", "promotion", "day_of_week",
}


@dataclass
class GlobalData:
    train: TensorDataset
    validation: TensorDataset
    test: TensorDataset
    num_skus: int
    num_categories: int
    num_warehouses: int
    scaler: StandardScaler
    sku_mapping: dict
    category_mapping: dict
    warehouse_mapping: dict
    lookback: int
    horizon: int
    split_dates: dict


def load_global_data(csv_path, lookback=45, horizon=7):
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df["sales"] = pd.to_numeric(df["sales"], errors="raise")
    df["promotion"] = pd.to_numeric(
        df["promotion"], errors="raise"
    )
    df["day_of_week"] = pd.to_numeric(
        df["day_of_week"], errors="raise"
    )

    if df[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Dataset contains missing required values.")

    if (df["sales"] < 0).any():
        raise ValueError("Sales must be non-negative.")

    df = df.sort_values(["sku_id", "date"]).reset_index(drop=True)

    if df.duplicated(["sku_id", "date"]).any():
        raise ValueError("Duplicate date/SKU rows found.")

    # Use the same chronological cutoffs for all SKUs.
    unique_dates = np.sort(df["date"].unique())
    if len(unique_dates) < lookback + horizon + 2:
        raise ValueError("Not enough unique dates for requested windows.")

    train_cut = unique_dates[int(len(unique_dates) * 0.70) - 1]
    val_cut = unique_dates[int(len(unique_dates) * 0.85) - 1]

    # Fit the scaler only on training-period sales.
    scaler = StandardScaler()
    train_sales = df.loc[df["date"] <= train_cut, ["sales"]]
    scaler.fit(train_sales)

    df["scaled_sales"] = scaler.transform(df[["sales"]]).ravel()

    # Calendar features are known without looking at future sales.
    dow = df["day_of_week"].astype(float)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

    sku_mapping = {
        value: idx for idx, value in enumerate(sorted(df["sku_id"].unique()))
    }
    category_mapping = {
        value: idx for idx, value in enumerate(sorted(df["category"].unique()))
    }
    warehouse_mapping = {
        value: idx
        for idx, value in enumerate(sorted(df["warehouse_id"].unique()))
    }

    df["sku_idx"] = df["sku_id"].map(sku_mapping)
    df["category_idx"] = df["category"].map(category_mapping)
    df["warehouse_idx"] = df["warehouse_id"].map(warehouse_mapping)

    # Three numeric inputs: scaled sales, promotion, and weekday cycle.
    feature_columns = ["scaled_sales", "promotion", "dow_sin"]
    # Keep both weekday cycle components.
    feature_columns = ["scaled_sales", "promotion", "dow_sin", "dow_cos"]

    buckets = {"train": [], "validation": [], "test": []}

    for _, group in df.groupby("sku_id", sort=False):
        group = group.sort_values("date").reset_index(drop=True)
        if len(group) < lookback + horizon:
            continue

        features = group[feature_columns].to_numpy(dtype=np.float32)
        sales = group["scaled_sales"].to_numpy(dtype=np.float32)
        dates = group["date"].to_numpy()

        sku_idx = int(group["sku_idx"].iloc[0])
        category_idx = int(group["category_idx"].iloc[0])
        warehouse_idx = int(group["warehouse_idx"].iloc[0])

        for end in range(lookback, len(group) - horizon + 1):
            target_end = end + horizon
            target_dates = dates[end:target_end]

            # Never assign a window across a split boundary.
            if target_dates[-1] <= train_cut:
                split = "train"
            elif target_dates[0] > train_cut and target_dates[-1] <= val_cut:
                split = "validation"
            elif target_dates[0] > val_cut:
                split = "test"
            else:
                continue

            x = features[end - lookback:end]
            y = sales[end:target_end]

            buckets[split].append(
                (x, y, sku_idx, category_idx, warehouse_idx)
            )

    def make_dataset(rows):
        if not rows:
            raise ValueError(
                "A dataset split is empty. Check date coverage and lookback."
            )

        x, y, sku, category, warehouse = zip(*rows)
        return TensorDataset(
            torch.tensor(np.asarray(x), dtype=torch.float32),
            torch.tensor(np.asarray(sku), dtype=torch.long),
            torch.tensor(np.asarray(category), dtype=torch.long),
            torch.tensor(np.asarray(warehouse), dtype=torch.long),
            torch.tensor(np.asarray(y), dtype=torch.float32),
        )

    return GlobalData(
        train=make_dataset(buckets["train"]),
        validation=make_dataset(buckets["validation"]),
        test=make_dataset(buckets["test"]),
        num_skus=len(sku_mapping),
        num_categories=len(category_mapping),
        num_warehouses=len(warehouse_mapping),
        scaler=scaler,
        sku_mapping=sku_mapping,
        category_mapping=category_mapping,
        warehouse_mapping=warehouse_mapping,
        lookback=lookback,
        horizon=horizon,
        split_dates={
            "train_end": str(pd.Timestamp(train_cut).date()),
            "validation_end": str(pd.Timestamp(val_cut).date()),
        },
    )
