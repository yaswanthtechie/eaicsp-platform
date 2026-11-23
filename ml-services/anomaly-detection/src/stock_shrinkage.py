"""
Stock shrinkage check (R15-K7): flag stock that disappears without a sale.

For each product and warehouse, between two inventory snapshots:

    received  = quantity of purchase orders received after the start snapshot,
                up to and including the end snapshot day
    sold      = units sold on the same days
    expected  = start on-hand + received - sold
    gap       = expected - actual on-hand     (the unexplained drop)

A pair is flagged when the gap is at least SHRINK_MIN_UNITS units AND at least
SHRINK_MIN_PCT of the expected on-hand (both in src/config.py). Severity
(high, medium, low) is set by the same two numbers; the rule is in the README.

Input: the three client-format files (inventory_snapshot.csv with at least two
snapshot dates, sales_history.csv, purchase_order_history.csv). Missing or
invalid data is never guessed: the pair is skipped and the skip is counted.

Each run is logged to MLflow the same way as the sales anomaly runs (see
src/sales_anomaly_tracking.py); without MLFLOW_TRACKING_URI nothing is logged.

Run from ml-services/anomaly-detection:

    python -m src.stock_shrinkage --inventory inventory.csv \
        --sales sales_history.csv --purchase-orders purchase_order_history.csv
"""

import argparse
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .sales_anomaly_tracking import safe_log_run

log = logging.getLogger("stock_shrinkage")

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = SERVICE_ROOT / "output" / "stock_shrinkage_flags.csv"

SHRINK_NAMES = (
    "SHRINK_MIN_UNITS",
    "SHRINK_MIN_PCT",
    "SHRINK_MEDIUM_UNITS",
    "SHRINK_MEDIUM_PCT",
    "SHRINK_HIGH_UNITS",
    "SHRINK_HIGH_PCT",
)

# Why a pair was skipped. A pair is counted once, under the first reason that
# applies (this order).
SKIP_REASONS = (
    "missing_start_snapshot",
    "missing_end_snapshot",
    "duplicate_snapshot",
    "invalid_on_hand",
    "bad_sales_row",
    "bad_po_row",
    "no_sales_in_window",
    "negative_expected",
)

KEY = ["product_code", "warehouse_code"]

FLAG_COLUMNS = [
    "product_code",
    "warehouse_code",
    "start_date",
    "end_date",
    "start_on_hand",
    "received",
    "sold",
    "expected",
    "actual",
    "gap",
    "gap_pct",
    "severity",
]

REQUIRED = {
    "inventory": (
        "snapshot_date",
        "product_code",
        "warehouse_code",
        "quantity_on_hand",
    ),
    "sales": ("sale_date", "product_code", "warehouse_code", "quantity_sold"),
    "purchase orders": (
        "product_code",
        "warehouse_code",
        "received_date",
        "quantity_ordered",
        "po_status",
    ),
}


@dataclass
class Result:
    """What one check found."""

    start: pd.Timestamp
    end: pd.Timestamp
    flags: pd.DataFrame
    checked: int = 0
    above_expected: int = 0
    unattributable_rows: int = 0
    undated_rows: int = 0
    skipped: Counter = field(default_factory=Counter)

    @property
    def skipped_total(self):
        return sum(self.skipped.values())

    def severity_counts(self):
        counts = self.flags["severity"].value_counts()

        return {s: int(counts.get(s, 0)) for s in ("high", "medium", "low")}


def shrink_settings():
    """The thresholds in force, from src/config.py."""

    return {name.lower(): getattr(config, name) for name in SHRINK_NAMES}


def severity(gap, gap_pct):
    """high, medium or low. A level needs both its units and its share."""

    if gap >= config.SHRINK_HIGH_UNITS and gap_pct >= config.SHRINK_HIGH_PCT:
        return "high"

    if gap >= config.SHRINK_MEDIUM_UNITS and gap_pct >= config.SHRINK_MEDIUM_PCT:
        return "medium"

    return "low"


def is_flagged(gap, gap_pct):
    return gap >= config.SHRINK_MIN_UNITS and gap_pct >= config.SHRINK_MIN_PCT


def _prepare(df, name, date_col, qty_col):
    """Text columns to clean codes, a date (NaT if invalid) and a quantity (NaN if invalid)."""

    missing = [c for c in REQUIRED[name] if c not in df.columns]

    if missing:
        raise ValueError(f"The {name} file has no column {', '.join(missing)}")

    out = pd.DataFrame(index=df.index)

    for column in KEY:
        out[column] = df[column].fillna("").astype(str).str.strip()

    out["has_codes"] = (out[KEY[0]] != "") & (out[KEY[1]] != "")
    out["day"] = pd.to_datetime(
        df[date_col].fillna("").astype(str).str.strip(),
        format="%Y-%m-%d",
        errors="coerce",
    )

    number = pd.to_numeric(
        df[qty_col].fillna("").astype(str).str.strip(), errors="coerce"
    )
    valid = (
        number.notna()
        & np.isfinite(number)
        & (number >= 0)
        & (number == number.round())
    )
    out["qty"] = number.where(valid)

    return out


def _window_totals(rows, start, end):
    """
    Sum the quantity per product and warehouse over (start, end].

    Returns (totals, bad_keys, unattributable, undated): bad_keys are pairs with
    a row in the window whose quantity is invalid; unattributable counts rows in
    the window with no product or warehouse; undated counts rows with no valid
    date, which cannot be placed in any window.
    """

    undated = int(rows["day"].isna().sum())
    relevant = rows[(rows["day"] > start) & (rows["day"] <= end)]
    unattributable = int((~relevant["has_codes"]).sum())
    relevant = relevant[relevant["has_codes"]]

    bad = relevant[relevant["qty"].isna()]
    bad_keys = set(zip(bad[KEY[0]], bad[KEY[1]], strict=True))

    good = relevant[relevant["qty"].notna()]
    totals = good.groupby(KEY)["qty"].sum()

    return totals, bad_keys, unattributable, undated


def check(inventory, sales, orders, start, end):
    """
    Check every product and warehouse between the snapshots dated start and end.

    inventory, sales and orders are DataFrames read as text (dtype=str).
    """

    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()

    if not start < end:
        raise ValueError(
            "The start snapshot date must be before the end snapshot date."
        )

    snap = _prepare(inventory, "inventory", "snapshot_date", "quantity_on_hand")

    # A window date with no snapshot at all is a wrong date, not a clean run.
    snapshot_days = set(snap.loc[snap["has_codes"], "day"].dropna())
    no_snapshot = [d.date().isoformat() for d in (start, end) if d not in snapshot_days]

    if no_snapshot:
        raise ValueError(
            f"The inventory file has no snapshot on {', '.join(no_snapshot)}."
        )

    sold_rows = _prepare(sales, "sales", "sale_date", "quantity_sold")
    po_rows = _prepare(orders, "purchase orders", "received_date", "quantity_ordered")

    # Only received orders move stock. Open and cancelled ones are ignored,
    # whatever their dates.
    status = orders["po_status"].fillna("").astype(str).str.strip().str.lower()
    po_rows = po_rows[status == "received"]

    result = Result(start=start, end=end, flags=pd.DataFrame(columns=FLAG_COLUMNS))

    sold, bad_sales, lost, undated = _window_totals(sold_rows, start, end)
    result.unattributable_rows += lost
    result.undated_rows += undated
    received, bad_pos, lost, undated = _window_totals(po_rows, start, end)
    result.unattributable_rows += lost
    result.undated_rows += undated

    result.unattributable_rows += int(
        (~snap["has_codes"] & snap["day"].isin([start, end])).sum()
    )
    snap = snap[snap["has_codes"] & snap["day"].isin([start, end])]
    sides = {}

    for label, day in (("start", start), ("end", end)):
        rows = snap[snap["day"] == day]
        sides[label] = {
            "count": rows.groupby(KEY).size().to_dict(),
            "qty": rows.drop_duplicates(KEY, keep=False)
            .set_index(KEY)["qty"]
            .to_dict(),
        }

    keys = sorted(set(sides["start"]["count"]) | set(sides["end"]["count"]))
    flagged = []

    for key in keys:
        in_start = sides["start"]["count"].get(key, 0)
        in_end = sides["end"]["count"].get(key, 0)

        if in_start == 0:
            reason = "missing_start_snapshot"
        elif in_end == 0:
            reason = "missing_end_snapshot"
        elif in_start > 1 or in_end > 1:
            reason = "duplicate_snapshot"
        elif pd.isna(sides["start"]["qty"][key]) or pd.isna(sides["end"]["qty"][key]):
            reason = "invalid_on_hand"
        elif key in bad_sales:
            reason = "bad_sales_row"
        elif key in bad_pos:
            reason = "bad_po_row"
        elif key not in sold.index:
            reason = "no_sales_in_window"
        else:
            reason = None

        if reason is not None:
            result.skipped[reason] += 1
            continue

        start_on_hand = int(sides["start"]["qty"][key])
        actual = int(sides["end"]["qty"][key])
        units_received = int(received.get(key, 0))
        units_sold = int(sold[key])
        expected = start_on_hand + units_received - units_sold

        if expected < 0:
            # More was sold than was ever there: a data problem.
            result.skipped["negative_expected"] += 1
            continue

        gap = expected - actual
        gap_pct = gap / expected if expected > 0 else 0.0

        result.checked += 1

        if gap < 0:
            result.above_expected += 1

        if is_flagged(gap, gap_pct):
            flagged.append(
                {
                    "product_code": key[0],
                    "warehouse_code": key[1],
                    "start_date": start.date().isoformat(),
                    "end_date": end.date().isoformat(),
                    "start_on_hand": start_on_hand,
                    "received": units_received,
                    "sold": units_sold,
                    "expected": expected,
                    "actual": actual,
                    "gap": gap,
                    "gap_pct": round(gap_pct, 4),
                    "severity": severity(gap, gap_pct),
                }
            )

    if flagged:
        result.flags = (
            pd.DataFrame(flagged, columns=FLAG_COLUMNS)
            .sort_values(
                ["gap", "product_code", "warehouse_code"], ascending=[False, True, True]
            )
            .reset_index(drop=True)
        )

    if result.unattributable_rows:
        log.warning(
            "%d inventory, sales or purchase order rows in the window have no "
            "product or warehouse code and could not be matched to a pair.",
            result.unattributable_rows,
        )

    if result.undated_rows:
        log.warning(
            "%d sales or purchase order rows have no valid date and were not "
            "counted in any window.",
            result.undated_rows,
        )

    for reason in SKIP_REASONS:
        if result.skipped[reason]:
            log.warning("Skipped %d pairs: %s.", result.skipped[reason], reason)

    return result


def latest_snapshot_dates(inventory):
    """The two most recent snapshot dates in the file, (start, end)."""

    if "snapshot_date" not in inventory.columns:
        raise ValueError("The inventory file has no column snapshot_date")

    days = pd.to_datetime(
        inventory["snapshot_date"].fillna("").astype(str).str.strip(),
        format="%Y-%m-%d",
        errors="coerce",
    ).dropna()
    days = sorted(days.unique())

    if len(days) < 2:
        raise ValueError(
            "The inventory file needs at least two snapshot dates; "
            f"it has {len(days)}. Pass --start and --end if the dates are in "
            "different files."
        )

    return pd.Timestamp(days[-2]), pd.Timestamp(days[-1])


def summary_line(result):
    counts = result.severity_counts()
    skipped = ", ".join(f"{k} {v}" for k, v in result.skipped.items()) or "none"

    return (
        f"window: {result.start.date()} to {result.end.date()}  "
        f"checked: {result.checked}  "
        f"flagged: {len(result.flags)} "
        f"(high {counts['high']}, medium {counts['medium']}, low {counts['low']})  "
        f"above expected: {result.above_expected}  "
        f"skipped: {result.skipped_total} ({skipped})  "
        f"unmatched rows: {result.unattributable_rows}  "
        f"undated rows: {result.undated_rows}"
    )


def log_to_mlflow(result, files):
    """Log this run to MLflow. Never raises."""

    metrics = {
        "pairs_checked": result.checked,
        "pairs_skipped": result.skipped_total,
        "above_expected": result.above_expected,
        "unmatched_rows": result.unattributable_rows,
        "undated_rows": result.undated_rows,
        "units_unexplained": int(result.flags["gap"].sum()) if len(result.flags) else 0,
    }

    for reason in SKIP_REASONS:
        metrics[f"skipped_{reason}"] = result.skipped.get(reason, 0)

    return safe_log_run(
        "stock-shrinkage",
        params={**shrink_settings(), **files},
        data_start=result.start.date().isoformat(),
        data_end=result.end.date().isoformat(),
        severities=result.severity_counts(),
        metrics=metrics,
        texts={"flags.csv": result.flags.to_csv(index=False)},
        tags={"run_kind": "shrinkage"},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inventory", required=True, help="inventory_snapshot.csv")
    parser.add_argument("--sales", required=True, help="sales_history.csv")
    parser.add_argument(
        "--purchase-orders", required=True, help="purchase_order_history.csv"
    )
    parser.add_argument(
        "--start", help="start snapshot date (default: second latest in the file)"
    )
    parser.add_argument("--end", help="end snapshot date (default: latest in the file)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="flags CSV to write")
    args = parser.parse_args(argv)

    if bool(args.start) != bool(args.end):
        parser.error("--start and --end go together: pass both or neither.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        inventory = pd.read_csv(args.inventory, dtype=str)
        sales = pd.read_csv(args.sales, dtype=str)
        orders = pd.read_csv(args.purchase_orders, dtype=str)

        if args.start and args.end:
            start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
        else:
            start, end = latest_snapshot_dates(inventory)

        result = check(inventory, sales, orders, start, end)

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.flags.to_csv(out, index=False)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)

        return 2

    log_to_mlflow(
        result,
        {
            "inventory": Path(args.inventory).name,
            "sales": Path(args.sales).name,
            "purchase_orders": Path(args.purchase_orders).name,
        },
    )

    print(summary_line(result))
    print(f"flags written to {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
