"""
Profile every seed file and write one HTML report per file.

Run from data-platform/profiling:
    python -m src.profiling_report --seed-dir ../seed/out --out-dir profile_report
"""

import argparse
from pathlib import Path

import pandas as pd

from src.profiler import Profiler

PROFILING_DIR = Path(__file__).resolve().parent.parent
SEED_FILES = (
    "skus",
    "suppliers",
    "warehouses",
    "sales_daily",
    "opening_stock",
    "current_stock",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the R15 seed dataset.")
    parser.add_argument("--seed-dir", type=Path, default=PROFILING_DIR.parent / "seed" / "out")
    parser.add_argument("--out-dir", type=Path, default=PROFILING_DIR / "profile_report")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    profiler = Profiler()

    for name in SEED_FILES:
        source = args.seed_dir / f"{name}.csv"
        if not source.exists():
            raise SystemExit(f"Missing seed file: {source}")
        df = pd.read_csv(source)
        target = args.out_dir / f"{name}_report.html"
        profiler.profile(df).save_html(str(target))
        print(f"\n{name}: {len(df)} rows -> {target}")


if __name__ == "__main__":
    main()