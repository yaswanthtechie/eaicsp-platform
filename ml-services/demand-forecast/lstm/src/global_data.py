
"""Leakage-aware dataset preparation for the global SKU LSTM."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import TensorDataset


REQUIRED_COLUMNS = {
    "date",
    "sku_id",
    "category",
    "warehouse_id",
    "sales",
    "promotion",
    "day_of_week",
}

UNK = 0


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

    train_target_dates: list
    validation_target_dates: list
    test_target_dates: list

    skus_with_train_windows: list
    skus_mapped_to_unk: list
    too_short_skipped: list


def load_global_data(
    csv_path,
    lookback=45,
    horizon=7,
    train_end=None,
    validation_end=None,
    test_end=None,
):
    """Load data, fit the scaler on training rows, and build chronological windows."""

    if lookback < 1:
        raise ValueError("lookback must be at least 1.")

    if horizon < 1:
        raise ValueError("horizon must be at least 1.")

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

    df["sku_id"] = df["sku_id"].astype(str)
    df = df.sort_values(["sku_id", "date"]).reset_index(drop=True)

    if df.duplicated(["sku_id", "date"]).any():
        raise ValueError("Duplicate date/SKU rows found.")

    # Validate daily date continuity for each SKU.
    for sku, group in df.groupby("sku_id", sort=False):
        group = group.sort_values("date")

        full_dates = pd.date_range(
            start=group["date"].min(),
            end=group["date"].max(),
            freq="D",
        )

        if len(full_dates) != len(group):
            missing_days = len(full_dates) - len(group)
            raise ValueError(
                f"{sku}: {missing_days} missing days; "
                "reindex/impute before windowing"
            )

    unique_dates = np.sort(df["date"].unique())

    if len(unique_dates) < lookback + horizon + 2:
        raise ValueError(
            "Not enough unique dates for requested windows."
        )

    train_cut = unique_dates[
        int(len(unique_dates) * 0.70) - 1
    ]
    val_cut = unique_dates[
        int(len(unique_dates) * 0.85) - 1
    ]

    # Fit scaler only on rows within the training period.
    scaler = StandardScaler()
    train_sales = df.loc[
        df["date"] <= train_cut, ["sales"]
    ]
    scaler.fit(train_sales)

    df["scaled_sales"] = scaler.transform(
        df[["sales"]]
    ).ravel()

    dow = df["day_of_week"].astype(float)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7.0)

    feature_columns = [
        "scaled_sales",
        "promotion",
        "dow_sin",
        "dow_cos",
    ]

    buckets = {
        "train": [],
        "validation": [],
        "test": [],
    }

    # Record the dates being forecast in each window.
    target_date_buckets = {
        "train": [],
        "validation": [],
        "test": [],
    }

    sku_window_counts = {
        sku: {
            "train": 0,
            "validation": 0,
            "test": 0,
        }
        for sku in sorted(df["sku_id"].unique())
    }

    category_mapping = {
        value: idx + 1
        for idx, value in enumerate(
            sorted(df["category"].astype(str).unique())
        )
    }

    warehouse_mapping = {
        value: idx + 1
        for idx, value in enumerate(
            sorted(df["warehouse_id"].astype(str).unique())
        )
    }

    df["category_idx"] = (
        df["category"]
        .astype(str)
        .map(category_mapping)
        .astype("int64")
    )

    df["warehouse_idx"] = (
        df["warehouse_id"]
        .astype(str)
        .map(warehouse_mapping)
        .astype("int64")
    )

    too_short = sorted(
        sku
        for sku, group in df.groupby("sku_id")
        if len(group) < lookback + horizon
    )

    for sku, group in df.groupby("sku_id", sort=False):
        group = (
            group.sort_values("date")
            .reset_index(drop=True)
        )

        if len(group) < lookback + horizon:
            continue

        features = group[feature_columns].to_numpy(
            dtype=np.float32
        )
        sales = group["scaled_sales"].to_numpy(
            dtype=np.float32
        )
        dates = group["date"].to_numpy()

        category_idx = int(
            group["category_idx"].iloc[0]
        )
        warehouse_idx = int(
            group["warehouse_idx"].iloc[0]
        )

        for end in range(
            lookback,
            len(group) - horizon + 1,
        ):
            target_dates = dates[end:end + horizon]

            # Assign a window only if all target dates belong
            # to one split. Windows straddling a boundary are skipped.
            if target_dates[-1] <= train_cut:
                split = "train"

            elif (
                target_dates[0] > train_cut
                and target_dates[-1] <= val_cut
            ):
                split = "validation"

            elif target_dates[0] > val_cut:
                split = "test"

            else:
                continue

            x = features[end - lookback:end]
            y = sales[end:end + horizon]

            buckets[split].append(
                (
                    x,
                    y,
                    str(sku),
                    category_idx,
                    warehouse_idx,
                )
            )

            target_date_buckets[split].append(
                pd.to_datetime(target_dates).tolist()
            )

            sku_window_counts[str(sku)][split] += 1

    trained = sorted(
        sku
        for sku, counts in sku_window_counts.items()
        if counts["train"] > 0
    )

    all_skus = set(df["sku_id"].unique())

    # SKUs too short for any complete window are skipped.
    # Other SKUs without training windows map to UNK.
    untrained = sorted(
        all_skus - set(trained) - set(too_short)
    )

    # Index 0 is reserved for unknown/untrained SKUs.
    sku_mapping = {
        sku: idx + 1
        for idx, sku in enumerate(trained)
    }

    print(
        f"SKUs with train windows: {len(trained)}; "
        f"without (mapped to UNK): {untrained}; "
        f"too short, skipped: {too_short}"
    )

    def make_dataset(rows):
        if not rows:
            raise ValueError(
                "A dataset split is empty. "
                "Check date coverage and lookback."
            )

        x, y, sku, category, warehouse = zip(*rows)

        sku_indices = [
            sku_mapping.get(str(value), UNK)
            for value in sku
        ]

        return TensorDataset(
            torch.tensor(
                np.asarray(x), dtype=torch.float32
            ),
            torch.tensor(
                np.asarray(sku_indices), dtype=torch.long
            ),
            torch.tensor(
                np.asarray(category), dtype=torch.long
            ),
            torch.tensor(
                np.asarray(warehouse), dtype=torch.long
            ),
            torch.tensor(
                np.asarray(y), dtype=torch.float32
            ),
        )

    return GlobalData(
        train=make_dataset(buckets["train"]),
        validation=make_dataset(buckets["validation"]),
        test=make_dataset(buckets["test"]),

        num_skus=len(sku_mapping) + 1,
        num_categories=len(category_mapping) + 1,
        num_warehouses=len(warehouse_mapping) + 1,

        scaler=scaler,
        sku_mapping=sku_mapping,
        category_mapping=category_mapping,
        warehouse_mapping=warehouse_mapping,

        lookback=lookback,
        horizon=horizon,

        split_dates={
            "train_end": str(
                pd.Timestamp(train_cut).date()
            ),
            "validation_end": str(
                pd.Timestamp(val_cut).date()
            ),
        },

        train_target_dates=target_date_buckets["train"],
        validation_target_dates=target_date_buckets["validation"],
        test_target_dates=target_date_buckets["test"],

        skus_with_train_windows=trained,
        skus_mapped_to_unk=untrained,
        too_short_skipped=too_short,
    )
