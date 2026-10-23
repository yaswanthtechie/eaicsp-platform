"""Creates the tables the profiling DAG expects. Safe to re-run (replaces the tables)."""
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from src.db_config import get_db_url

PRODUCT_ROWS = 500


def make_products(rng) -> pd.DataFrame:
    return pd.DataFrame({
        "product_id": np.arange(1, PRODUCT_ROWS + 1),
        "sku_id": [f"SKU{i:03d}" for i in range(1, PRODUCT_ROWS + 1)],
        "category": rng.choice(["Electronics", "Grocery", "Apparel", "Hardware"], size=PRODUCT_ROWS),
        "unit_cost": rng.uniform(5.0, 400.0, size=PRODUCT_ROWS).round(2),
        "created_at": pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 270, size=PRODUCT_ROWS), unit="D"),
    })


def main():
    engine = create_engine(get_db_url())
    products = make_products(np.random.default_rng(42))
    products.to_sql("products", engine, if_exists="replace", index=False)
    print(f"Loaded 'products' with {len(products)} rows.")
    print("For 'benchmark_1m_sales', run: python benchmark_pushdown.py")


if __name__ == "__main__":
    main()