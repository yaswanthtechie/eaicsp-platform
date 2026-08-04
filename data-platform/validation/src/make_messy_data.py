from random import randint

import pandas as pd
import numpy as np
import uuid
from pathlib import Path
from typing import Any, List, Optional
from dataclasses import dataclass, field


# 1. Centralized Configuration (No Magic Numbers/Strings)
@dataclass
class MessyDataConfig:
    n_base: int = 970
    seed: int = 42
    start_date: str = "2024-01-01"
    end_date: str = "2024-04-10"
    date_freq: str = "D"

    products: List[str] = field(default_factory=lambda: [
        "iPhone 15", "IPHONE-15", "iphone 15 ", "Galaxy S24", "GALAXY-s24", " galaxy s24"
    ])

    sku_start_range: int = 1000
    sku_end_range: int = 1050
    qty_min: int = 1
    qty_max: int = 15
    price_min: float = 10.0
    price_max: float = 1200.0


    date_formats: List[str] = field(default_factory=lambda: ["%Y-%m-%d", "%d/%m/%Y", "%b %d %Y"])
    bad_sku_string: str = "BAD-9999"

    # Corruption Percentages
    frac_missing_qty: float = 0.05
    frac_negative_qty: float = 0.006
    frac_bad_sku_format: float = 0.015
    frac_missing_sku: float = 0.01
    frac_missing_txn: float = 0.01
    frac_missing_date: float = 0.012
    frac_exact_duplicates: float = 0.031
    frac_missing_price: float = 0.02


def _inject_anomaly(df: pd.DataFrame, column: str, fraction: float, replacement: Any) -> pd.Index:
    count = int(len(df) * fraction)
    idx = df.sample(n=count, replace=False).index
    df.loc[idx, column] = replacement
    return idx


def generate_messy_data(filepath: Path | str, config: Optional[MessyDataConfig] = None) -> pd.DataFrame:
    cfg = config or MessyDataConfig()

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    np.random.seed(cfg.seed)

    # --- 1. Generate Base Data (Vectorized) ---
    date_range = pd.date_range(start=cfg.start_date, end=cfg.end_date, freq=cfg.date_freq)
    product_col = np.random.choice(cfg.products, size=cfg.n_base)
    dates: List[Any] = np.random.choice(date_range, size=cfg.n_base).tolist()  # type: ignore

    valid_skus = [f"SKU-{str(i).zfill(4)}" for i in range(cfg.sku_start_range, cfg.sku_end_range)]
    sku_col: List[str] = np.random.choice(valid_skus, size=cfg.n_base).tolist()  # type: ignore

    quantities: List[float] = np.random.randint(cfg.qty_min, cfg.qty_max, size=cfg.n_base).astype(
        float).tolist()  # type: ignore
    txn_col: List[str] = [f"TXN-{uuid.uuid4().hex[:8].upper()}" for _ in range(cfg.n_base)]

    # price = np.random.randint(100, 100000, size=cfg.n_base).astype((float)).tolist()
    prices = np.random.uniform(cfg.price_min, cfg.price_max, size=cfg.n_base).round(2).tolist()

    df = pd.DataFrame({
        "order_date": dates,
        "sku_id": sku_col,
        "product_name": product_col,
        "quantity_sold": quantities,
        "transaction_id": txn_col,
        "unit_price": prices
    })

    # --- 2. Introduce Data Corruption ---
    missing_idx = _inject_anomaly(df, "quantity_sold", cfg.frac_missing_qty, np.nan)

    valid_idx = df.index.difference(missing_idx)
    neg_count = int(len(df) * cfg.frac_negative_qty)
    neg_idx = df.loc[valid_idx].sample(n=neg_count, replace=False).index

    target_series = df.loc[neg_idx, "quantity_sold"]
    df.loc[neg_idx, "quantity_sold"] = target_series.astype(float) * -1.0

    _inject_anomaly(df, "sku_id", cfg.frac_bad_sku_format, cfg.bad_sku_string)
    _inject_anomaly(df, "sku_id", cfg.frac_missing_sku, np.nan)
    _inject_anomaly(df, "transaction_id", cfg.frac_missing_txn, np.nan)
    _inject_anomaly(df, "unit_price", cfg.frac_missing_price, np.nan)

    random_formats: List[str] = np.random.choice(cfg.date_formats, size=cfg.n_base).tolist()  # type: ignore
    df["order_date"] = [
        d.strftime(fmt) if pd.notna(d) else d
        for d, fmt in zip(pd.to_datetime(df["order_date"]), random_formats)
    ]

    _inject_anomaly(df, "order_date", cfg.frac_missing_date, np.nan)

    # --- 3. Duplicates & Shuffling ---
    dup_count = int(len(df) * cfg.frac_exact_duplicates)
    duplicates = df.sample(n=dup_count, replace=True, random_state=cfg.seed)
    df = pd.concat([df, duplicates], ignore_index=True)

    df = df.sample(frac=1, random_state=cfg.seed).reset_index(drop=True)
    df.to_csv(filepath, index=False)

    print(f"Messy data successfully generated at: {filepath}")
    return df


if __name__ == "__main__":
    # Provides a default path strictly for standalone testing purposes
    generate_messy_data(Path(__file__).resolve().parent.parent / "data" / "messy_sales.csv")