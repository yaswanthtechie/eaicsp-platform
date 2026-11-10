"""Stage the shared seed sales file for the ETL pipeline.

Usage from the repository root:
    python data-platform/etl/scripts/load_seed.py --data-dir data-platform/out
"""
import argparse
import shutil
import sys
from pathlib import Path

ETL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ETL_DIR.parent / "out"
SALES_BATCH_DIR = ETL_DIR / "data" / "batches" / "sales"


def stage_sales(data_dir, batch_dir=SALES_BATCH_DIR):
    source = Path(data_dir) / "sales_daily.csv"
    if not source.is_file():
        raise FileNotFoundError(f"{source} not found. Run `make seed` first.")

    batch_dir.mkdir(parents=True, exist_ok=True)
    target = batch_dir / source.name
    shutil.copyfile(source, target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stage seed sales for the ETL pipeline."
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args(argv)

    try:
        target = stage_sales(args.data_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Staged {target}. Trigger the sales_etl_pipeline DAG to load it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
