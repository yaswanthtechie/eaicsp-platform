"""Generate a deterministic 10M+ row sales history for the R14 benchmark.

--dirty-pct (default 0.5) appends extra rows so the cleaning rules matter:
exact duplicates, same-key collisions (different qty, appears later => wins),
and uncastable values (blank quantity / non-numeric price). Output rows exceed
--rows by roughly that percentage.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=10_000_000)
    p.add_argument("--output", default="data/backfill/sales_history.csv")
    p.add_argument("--dirty-pct", type=float, default=0.5)
    args = p.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)  # never append to a previous run
    rng = np.random.default_rng(1401)
    chunks = 250_000
    for start in range(0, args.rows, chunks):
        n = min(chunks, args.rows - start)
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", "2026-12-31", periods=n).strftime("%Y-%m-%d"),
            "sku_id": [f"SKU{v:05d}" for v in rng.integers(1, 10001, n)],
            "warehouse_id": [f"W{v:03d}" for v in rng.integers(1, 101, n)],
            "quantity_sold": rng.integers(1, 100, n).astype(str),
            "unit_price": np.round(rng.uniform(5, 500, n), 2).astype(str),
        })
        m = int(n * args.dirty_pct / 100 / 3)
        if m:
            dup = df.sample(m, random_state=start).copy()
            col = df.sample(m, random_state=start + 1).copy()
            col["quantity_sold"] = (col["quantity_sold"].astype(int) + 1).astype(str)
            bad = df.sample(m, random_state=start + 2).copy()
            bad.iloc[: m // 2, bad.columns.get_loc("quantity_sold")] = ""
            bad.iloc[m // 2:, bad.columns.get_loc("unit_price")] = "n/a"
            df = pd.concat([df, dup, col, bad], ignore_index=True)
        df.to_csv(out, mode="a", index=False, header=(start == 0))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
