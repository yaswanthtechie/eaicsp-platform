"""
Generates synthetic sales + inventory batch files for local/dev testing.

Two things this deliberately gets right:

1. Anchored to PROJECT_ROOT via __file__, not CWD - so `python etl/src/make_batches.py`
   produces the same output whether you run it from the repo root, from etl/src/,
   or from inside a container with a different working directory.

2. Fixed random seed - batches are reproducible between runs, which matters for
   proving backfill idempotency later (same input data -> same expected output
   every time you regenerate).

Writes into the *per-source* subfolders that pipeline_config.yaml actually points
at (data/batches/sales/, data/batches/inventory/), not a flat data/batches/ -
extract_data() globs non-recursively, so a flat layout is invisible to the pipeline.
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_ROOT = PROJECT_ROOT / "data" / "batches"

SALES_FOLDER = BATCH_ROOT / "sales"
INVENTORY_FOLDER = BATCH_ROOT / "inventory"

SALES_FOLDER.mkdir(parents=True, exist_ok=True)
INVENTORY_FOLDER.mkdir(parents=True, exist_ok=True)

START_DATE = date(2024, 1, 1)
NUM_DAYS = 5

SALES_ROWS_PER_DAY = 400
INVENTORY_ROWS_PER_DAY = 1000

# A handful of intentionally-bad inventory rows per day, so the quality gate
# has something real to catch (negative quantity_on_hand). Small enough to
# stay under negative_rate_threshold at the batch level - this demonstrates
# the gate working, not a defect in the generator.
BAD_INVENTORY_ROWS_PER_DAY = 2


def _sku():
    return f"SKU{random.randint(100, 999)}"


def _warehouse():
    return f"WH{random.randint(1, 5)}"


for day_offset in range(NUM_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)

    # --- Sales -----------------------------------------------------------
    sales_rows = [
        {
            "date": current_date.isoformat(),
            "sku_id": _sku(),
            "warehouse_id": _warehouse(),
            "quantity_sold": random.randint(1, 20),
            "unit_price": random.randint(100, 1000),
        }
        for _ in range(SALES_ROWS_PER_DAY)
    ]

    sales_df = pd.DataFrame(sales_rows)
    sales_df.to_csv(SALES_FOLDER / f"sales_{current_date}.csv", index=False)

    # --- Inventory ---------------------------------------------------------
    inventory_rows = [
        {
            "snapshot_date": current_date.isoformat(),
            "sku_id": _sku(),
            "warehouse_id": _warehouse(),
            "quantity_on_hand": random.randint(1, 500),
        }
        for _ in range(INVENTORY_ROWS_PER_DAY - BAD_INVENTORY_ROWS_PER_DAY)
    ]

    # Intentionally invalid rows: negative quantity_on_hand.
    inventory_rows += [
        {
            "snapshot_date": current_date.isoformat(),
            "sku_id": _sku(),
            "warehouse_id": _warehouse(),
            "quantity_on_hand": -random.randint(1, 10),
        }
        for _ in range(BAD_INVENTORY_ROWS_PER_DAY)
    ]

    random.shuffle(inventory_rows)

    inventory_df = pd.DataFrame(inventory_rows)
    inventory_df.to_csv(
        INVENTORY_FOLDER / f"inventory_{current_date}.csv", index=False
    )

print(
    f"Wrote {NUM_DAYS} sales batches to {SALES_FOLDER} "
    f"({NUM_DAYS * SALES_ROWS_PER_DAY} rows)"
)
print(
    f"Wrote {NUM_DAYS} inventory batches to {INVENTORY_FOLDER} "
    f"({NUM_DAYS * INVENTORY_ROWS_PER_DAY} rows, "
    f"{NUM_DAYS * BAD_INVENTORY_ROWS_PER_DAY} intentionally invalid)"
)
