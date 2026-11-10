"""Load the generated current-stock seed into ClickHouse inventory snapshots."""
import argparse
import csv
import sys
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from .apply_ddl import _client, _database
except ImportError:
    from apply_ddl import _client, _database

COLUMNS = (
    "snapshot_date",
    "sku_id",
    "warehouse_id",
    "quantity_on_hand",
    "source",
    "version",
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "out"


def load_current_stock(client, database, data_dir):
    csv_path = Path(data_dir) / "current_stock.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Seed stock CSV not found: {csv_path}")

    version = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = []

    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"snapshot_date", "sku_id", "warehouse_id", "quantity_on_hand"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"{csv_path} is missing required columns: {sorted(missing)}"
            )

        for row in reader:
            rows.append((
                date.fromisoformat(row["snapshot_date"]),
                row["sku_id"],
                row["warehouse_id"],
                int(row["quantity_on_hand"]),
                "seed",
                version,
            ))

    if rows:
        client.insert(
            "inventory_snapshots",
            rows,
            column_names=list(COLUMNS),
            database=database,
        )

    print(f"Loaded {len(rows)} stock rows from {csv_path}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing current_stock.csv",
    )
    args = parser.parse_args()

    client = None
    try:
        database = _database()
        client = _client()
        load_current_stock(client, database, args.data_dir)
        return 0
    except Exception as exc:
        print(f"ERROR loading seed stock: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
