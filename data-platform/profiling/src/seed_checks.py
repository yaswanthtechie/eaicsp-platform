"""
Flow-breaking checks on the R15 seed dataset (issue #200).

Run from data-platform/profiling:
    python -m src.seed_checks --seed-dir ../seed/out --out profile_report/SEED_FINDINGS.md
Exit code 1 if any check fails.
"""

import argparse
from pathlib import Path

import pandas as pd

PROFILING_DIR = Path(__file__).resolve().parent.parent

ID_PATTERNS = {
    "sku_id": r"^SKU-\d{6}$",
    "warehouse_id": r"^WH-[A-Z]{3}-\d{2}$",
    "supplier_id": r"^SUP-\d{5}$",
}


def load(seed_dir: Path) -> dict[str, pd.DataFrame]:
    names = ("skus", "suppliers", "warehouses", "sales_daily", "opening_stock", "current_stock")
    return {name: pd.read_csv(seed_dir / f"{name}.csv") for name in names}


def _result(name: str, bad: pd.DataFrame, note: str = "") -> dict:
    return {
        "check": name,
        "ok": bad.empty,
        "count": len(bad),
        "example": "" if bad.empty else bad.head(1).to_dict("records")[0],
        "note": note,
    }


def run_checks(data: dict[str, pd.DataFrame]) -> list[dict]:
    skus, suppliers, warehouses = data["skus"], data["suppliers"], data["warehouses"]
    sales = data["sales_daily"]
    results = []

    # 1. Duplicate IDs / keys
    for table, key in (
        ("skus", ["sku_id"]),
        ("suppliers", ["supplier_id"]),
        ("warehouses", ["warehouse_id"]),
        ("sales_daily", ["date", "sku_id", "warehouse_id"]),
        ("opening_stock", ["sku_id", "warehouse_id"]),
        ("current_stock", ["sku_id", "warehouse_id"]),
    ):
        df = data[table]
        results.append(_result(f"{table}: duplicate {'+'.join(key)}", df[df.duplicated(key, keep=False)]))

    # 2. Canonical ID formats (blueprint section 2)
    for table, df in data.items():
        for column, pattern in ID_PATTERNS.items():
            if column in df.columns:
                bad = df[~df[column].astype(str).str.fullmatch(pattern)]
                results.append(_result(f"{table}.{column}: canonical format", bad))

    # 3. Foreign keys across files
    known_skus, known_wh = set(skus.sku_id), set(warehouses.warehouse_id)
    for table in ("sales_daily", "opening_stock", "current_stock"):
        df = data[table]
        results.append(_result(f"{table}.sku_id exists in skus", df[~df.sku_id.isin(known_skus)]))
        results.append(_result(f"{table}.warehouse_id exists in warehouses", df[~df.warehouse_id.isin(known_wh)]))
    results.append(_result(
        "skus.supplier_id exists in suppliers",
        skus[~skus.supplier_id.isin(set(suppliers.supplier_id))],
    ))

    # 4. Impossible stock and sales
    for table in ("opening_stock", "current_stock"):
        df = data[table]
        results.append(_result(f"{table}: negative quantity_on_hand", df[df.quantity_on_hand < 0]))
    zero = data["current_stock"][data["current_stock"].quantity_on_hand == 0]
    results.append({
        "check": "current_stock: zero on hand (stockouts)",
        "ok": True,
        "count": len(zero),
        "example": "",
        "note": f"{len(zero) / len(data['current_stock']):.1%} of pairs; README expects ~2% by design",
    })
    results.append(_result("sales_daily: negative quantity_sold", sales[sales.quantity_sold < 0]))
    results.append(_result("sales_daily: unit_price <= 0", sales[sales.unit_price <= 0]))
    results.append(_result("skus: unit_cost > unit_price", skus[skus.unit_cost > skus.unit_price]))

    # 5. Date gaps: every SKU/warehouse pair has a row for every day
    dates = pd.to_datetime(sales.date)
    full_days = pd.date_range(dates.min(), dates.max(), freq="D")
    per_pair = sales.groupby(["sku_id", "warehouse_id"]).date.nunique()
    gaps = per_pair[per_pair < len(full_days)].rename("days_present").reset_index()
    results.append(_result(
        "sales_daily: date gaps per SKU/warehouse",
        gaps,
        f"range {full_days.min().date()} to {full_days.max().date()} ({len(full_days)} days)",
    ))
    missing_days = full_days.difference(pd.DatetimeIndex(dates.unique()))
    results.append(_result(
        "sales_daily: whole days missing",
        pd.DataFrame({"date": missing_days}),
    ))

    return results


def to_markdown(results: list[dict], seed_dir: Path, data: dict[str, pd.DataFrame]) -> str:
    lines = [
        "# R15 seed dataset findings (issue #200)",
        "",
        f"Source: `{seed_dir}`. Rows: "
        + ", ".join(f"{name} {len(df)}" for name, df in data.items()),
        "",
        "| Check | Result | Count | Example / note |",
        "|---|---|---|---|",
    ]
    for r in results:
        status = "OK" if r["ok"] else "**FAIL**"
        detail = r["note"] or (str(r["example"]) if r["example"] else "")
        lines.append(f"| {r['check']} | {status} | {r['count']} | {detail} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Flow-breaking checks on the seed dataset.")
    parser.add_argument("--seed-dir", type=Path, default=PROFILING_DIR.parent / "seed" / "out")
    parser.add_argument("--out", type=Path, default=PROFILING_DIR / "profile_report" / "SEED_FINDINGS.md")
    args = parser.parse_args()

    data = load(args.seed_dir)
    results = run_checks(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_markdown(results, args.seed_dir, data), encoding="utf-8")
    failed = [r for r in results if not r["ok"]]
    print(f"{len(results) - len(failed)} passed, {len(failed)} failed -> {args.out}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()