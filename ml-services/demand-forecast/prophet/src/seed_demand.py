"""Load the R15 seed sales (canonical SKU/warehouse IDs) for forecasting."""

from pathlib import Path

import pandas as pd

from src.multi_horizon_config import SEED_SALES_PATH, SHARE_WINDOW_DAYS

SKU_PATTERN = r"SKU-\d{6}"
WAREHOUSE_PATTERN = r"WH-[A-Z]{3}-\d{2}"


def load_seed_sales(path: Path = SEED_SALES_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Seed sales not found: {path}. "
            "Run from the repo root: make seed"
        )

    df = pd.read_csv(path, usecols=["date", "sku_id", "warehouse_id", "quantity_sold"])
    df["date"] = pd.to_datetime(df["date"])

    bad = ~df["sku_id"].str.fullmatch(SKU_PATTERN) | ~df["warehouse_id"].str.fullmatch(WAREHOUSE_PATTERN)
    if bad.any():
        raise ValueError(f"Non-canonical IDs in seed sales, e.g. {df[bad].iloc[0].to_dict()}")
    if (df["quantity_sold"] < 0).any():
        raise ValueError("Negative quantity_sold in seed sales.")

    return df


def aggregate_daily(sales: pd.DataFrame) -> pd.DataFrame:
    """Total demand per day across all pairs: columns date, quantity_sold."""
    return (
        sales.groupby("date", as_index=False)["quantity_sold"].sum()
        .sort_values("date")
        .reset_index(drop=True)
    )


def pair_shares(sales: pd.DataFrame, end=None, window_days: int = SHARE_WINDOW_DAYS) -> dict[str, float]:
    """Each 'SKU|WH' pair's share of total demand over the window ending at `end`."""
    end = sales["date"].max() if end is None else end
    recent = sales[(sales["date"] > end - pd.Timedelta(days=window_days)) & (sales["date"] <= end)]
    by_pair = recent.groupby(["sku_id", "warehouse_id"])["quantity_sold"].sum()
    total = by_pair.sum()
    if total <= 0:
        raise ValueError("No demand in the share window.")
    return {f"{sku}|{wh}": float(qty / total) for (sku, wh), qty in by_pair.items()}