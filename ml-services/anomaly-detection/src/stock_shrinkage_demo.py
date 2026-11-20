"""
Make a synthetic pair of inventory snapshots to try the stock shrinkage check.

The client sample has only one snapshot date. This script treats it as the END
snapshot and builds an earlier START snapshot from the sales and the received
purchase orders, so every pair balances exactly, except a few pairs where it
plants a loss (stock gone without a sale): one high, one medium, one low.

Synthetic data only. Writes inventory_two_snapshots.csv (both dates).

    python -m src.stock_shrinkage_demo --samples <client_format folder> --out output/demo
"""

import argparse
from pathlib import Path

import pandas as pd

from .stock_shrinkage import _prepare, _window_totals

# Share of the expected on-hand planted as a loss: high, medium, low.
PLANTED_SHARES = (0.25, 0.12, 0.06)


def build(inventory, sales, orders, days=14):
    """Return the inventory with a synthetic start snapshot added, and the planted pairs."""

    snap = _prepare(inventory, "inventory", "snapshot_date", "quantity_on_hand")
    end = snap["day"].max()
    start = end - pd.offsets.Day(days)

    sold, bad_sales, _ = _window_totals(
        _prepare(sales, "sales", "sale_date", "quantity_sold"), start, end
    )

    po_rows = _prepare(orders, "purchase orders", "received_date", "quantity_ordered")
    status = orders["po_status"].fillna("").astype(str).str.strip().str.lower()
    received, bad_pos, _ = _window_totals(po_rows[status == "received"], start, end)

    rows = inventory[snap["day"] == end].copy()
    out = []
    planted = []

    for row in rows.itertuples(index=False):
        key = (str(row.product_code).strip(), str(row.warehouse_code).strip())
        actual = pd.to_numeric(row.quantity_on_hand, errors="coerce")

        if (
            key not in sold.index
            or key in bad_sales
            or key in bad_pos
            or pd.isna(actual)
            or actual < 0
        ):
            continue

        loss = 0

        if len(planted) < len(PLANTED_SHARES) and actual >= 100:
            share = PLANTED_SHARES[len(planted)]
            loss = round(actual * share / (1 - share))
            planted.append((key, loss))

        before = int(actual + sold[key] - received.get(key, 0) + loss)

        if before < 0:
            continue

        earlier = row._asdict()
        earlier["snapshot_date"] = start.date().isoformat()
        earlier["quantity_on_hand"] = str(before)
        out.append(earlier)

    both = pd.concat([pd.DataFrame(out), inventory], ignore_index=True)

    return both, planted, start, end


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--samples", required=True, help="folder with the client format CSVs"
    )
    parser.add_argument(
        "--out", required=True, help="folder to write the new inventory file to"
    )
    parser.add_argument(
        "--days", type=int, default=14, help="days between the two snapshots"
    )
    args = parser.parse_args(argv)

    samples = Path(args.samples)
    inventory = pd.read_csv(samples / "inventory_snapshot.csv", dtype=str)
    sales = pd.read_csv(samples / "sales_history.csv", dtype=str)
    orders = pd.read_csv(samples / "purchase_order_history.csv", dtype=str)

    both, planted, start, end = build(inventory, sales, orders, args.days)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "inventory_two_snapshots.csv"
    both.to_csv(path, index=False)

    print(f"snapshots: {start.date()} (synthetic) and {end.date()}")

    for (product, warehouse), loss in planted:
        print(f"planted loss: {product} / {warehouse}: {loss} units")

    print(f"written to {path}")


if __name__ == "__main__":
    main()