# src/make_messy_data.py
import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# 1. Centralized Configuration
@dataclass
class MessyDataConfig:
    n_base: int = 5_000_000
    chunk_size: int = 500_000
    seed: int = 42
    start_date: str = "2024-01-01"
    end_date: str = "2024-04-02"
    date_freq: str = "D"
    warehouses: List[str] = field(default_factory=lambda: ["WH-01", "WH-02", "WH-03", "WH-04"])

    sku_start_range: int = 1000
    # sku_end_range: int = 1050
    sku_end_range: int = 200100
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
    frac_missing_warehouse_id: float = 0.01
    frac_missing_date: float = 0.012
    frac_exact_duplicates: float = 0.031
    frac_missing_price: float = 0.02
    frac_unparseable_date: float = 0.01


def _inject_anomaly(df: pd.DataFrame, column: str, fraction: float, replacement: Any) -> pd.Index:
    count = int(len(df) * fraction)
    idx = df.sample(n=count, replace=False).index
    df.loc[idx, column] = replacement
    return idx


def generate_messy_data(filepath: Path | str, config: Optional[MessyDataConfig] = None) -> None:
    cfg = config or MessyDataConfig()

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    np.random.seed(cfg.seed)

    # Pre-generate valid domains to sample from
    date_range = pd.date_range(start=cfg.start_date, end=cfg.end_date, freq=cfg.date_freq)
    valid_skus = [f"SKU-{str(i).zfill(4)}" for i in range(cfg.sku_start_range, cfg.sku_end_range)]

    total_generated = 0
    first_chunk = True

    logger.info(f"Generating {cfg.n_base:,} rows in chunks of {cfg.chunk_size:,} to {filepath}...")

    # --- Streaming Generator Loop ---
    while total_generated < cfg.n_base:
        current_chunk_size = min(cfg.chunk_size, cfg.n_base - total_generated)

        # 1. Generate Base Data for current chunk (Suppressed static type warnings for numpy)
        dates: List[Any] = np.random.choice(date_range, size=current_chunk_size).tolist()  # type: ignore
        sku_col: List[str] = np.random.choice(valid_skus, size=current_chunk_size).tolist()  # type: ignore
        warehouse_col = np.random.choice(cfg.warehouses, size=current_chunk_size).tolist()  # type: ignore
        quantities: List[float] = np.random.randint(cfg.qty_min, cfg.qty_max, size=current_chunk_size).astype(
            float).tolist()  # type: ignore
        prices = np.random.uniform(cfg.price_min, cfg.price_max, size=current_chunk_size).round(
            2).tolist()  # type: ignore

        df = pd.DataFrame({
            "transaction_id": range(total_generated + 1, total_generated + current_chunk_size + 1),
            "date": dates,
            "sku_id": sku_col,
            "warehouse_id": warehouse_col,
            "quantity_sold": quantities,
            "unit_price": prices
        })

        # 2. Introduce Data Corruption for current chunk
        missing_idx = _inject_anomaly(df, "quantity_sold", cfg.frac_missing_qty, np.nan)

        valid_idx = df.index.difference(missing_idx)
        neg_count = int(len(df) * cfg.frac_negative_qty)
        neg_idx = df.loc[valid_idx].sample(n=neg_count, replace=False).index

        target_series = df.loc[neg_idx, "quantity_sold"]
        df.loc[neg_idx, "quantity_sold"] = target_series.astype(float) * -1.0

        _inject_anomaly(df, "sku_id", cfg.frac_bad_sku_format, cfg.bad_sku_string)
        _inject_anomaly(df, "sku_id", cfg.frac_missing_sku, np.nan)
        _inject_anomaly(df, "warehouse_id", cfg.frac_missing_warehouse_id, np.nan)
        _inject_anomaly(df, "unit_price", cfg.frac_missing_price, np.nan)

        random_formats: List[str] = np.random.choice(cfg.date_formats, size=current_chunk_size).tolist()  # type: ignore
        df["date"] = [
            d.strftime(fmt) if pd.notna(d) else d
            for d, fmt in zip(pd.to_datetime(df["date"]), random_formats)
        ]

        _inject_anomaly(df, "date", cfg.frac_missing_date, np.nan)
        _inject_anomaly(df, "date", cfg.frac_unparseable_date, "NOT_A_DATE")

        # 3. Duplicates & Shuffling for current chunk
        dup_count = int(len(df) * cfg.frac_exact_duplicates)
        duplicates = df.sample(n=dup_count, replace=True, random_state=cfg.seed)
        df = pd.concat([df, duplicates], ignore_index=True)

        df = df.sample(frac=1, random_state=cfg.seed).reset_index(drop=True)

        # 4. Write chunk to disk (Using strict Literals for pandas)
        mode: Literal['w', 'a'] = 'w' if first_chunk else 'a'
        df.to_csv(str(filepath), mode=mode, header=first_chunk, index=False)

        total_generated += current_chunk_size
        first_chunk = False

        logger.info(f"Progress: {total_generated:,} / {cfg.n_base:,} rows written.")

    logger.info(f"Messy data successfully generated at: {filepath}")


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="Generate messy data in chunks to prevent OOM errors.")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "messy_sales.csv",
                        help="Path to save the generated CSV.")
    parser.add_argument("--n-base", type=int, default=500_000,
                        help="Total number of rows to generate.")
    parser.add_argument("--chunk-size", type=int, default=100_000,
                        help="Number of rows per chunk.")

    args = parser.parse_args()

    cfg = MessyDataConfig(n_base=args.n_base, chunk_size=args.chunk_size)
    generate_messy_data(filepath=args.output, config=cfg)


if __name__ == "__main__":
    main()