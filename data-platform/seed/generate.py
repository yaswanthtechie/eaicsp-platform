"""Generate the shared seed dataset.

    python -m seed.generate --out out/                      # CSV + Parquet
    python -m seed.generate --out out/ --seed 7             # different (still deterministic) dataset
    python -m seed.generate --out out/ --write-samples      # also refresh seed/samples/ (default seed only)

Same seed + same library versions => byte-identical files. Nothing here reads
the clock, the environment, or unordered containers.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import DEFAULT_SEED, catalog, demand, ids

DEFAULT_END_DATE = "2026-10-14"  # fixed, never "today", or output would drift daily
DEFAULT_DAYS = 730               # two years of daily history
SAMPLE_ROWS = 10
SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

FILES = ["warehouses", "suppliers", "skus", "sales_daily", "opening_stock"]

_PARQUET_SCHEMAS = {  # built lazily so CSV-only runs don't need pyarrow
    "warehouses": [("warehouse_id", "string"), ("name", "string"), ("city", "string"), ("state", "string"),
                   ("lat", "float64"), ("lng", "float64"), ("capacity_units", "int64"), ("demand_weight", "float64")],
    "suppliers": [("supplier_id", "string"), ("name", "string"), ("country", "string"),
                  ("city", "string"), ("state", "string"), ("lat", "float64"), ("lng", "float64"),
                  ("sanctions_flag", "bool_"), ("sanctions_list", "string"), ("lead_time_days", "int32"),
                  ("payment_terms_days", "int32"), ("reliability_score", "float64")],
    "skus": [("sku_id", "string"), ("name", "string"), ("category", "string"), ("pack_size", "string"),
             ("unit_price", "float64"), ("unit_cost", "float64"), ("abc_class", "string"),
             ("supplier_id", "string")],
    "sales_daily": [("date", "date32"), ("sku_id", "string"), ("warehouse_id", "string"),
                    ("quantity_sold", "int32"), ("unit_price", "float64")],
    "opening_stock": [("snapshot_date", "date32"), ("sku_id", "string"), ("warehouse_id", "string"),
                      ("quantity_on_hand", "int32")],
}


def build_frames(seed: int = DEFAULT_SEED, days: int = DEFAULT_DAYS,
                 end_date: str = DEFAULT_END_DATE) -> dict[str, pd.DataFrame]:
    # Independent streams per concern: changing one model never shifts another's numbers.
    cat_rng, base_rng, sales_rng, stock_rng = (
        np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(4))

    wh = catalog.warehouses()
    sup = catalog.suppliers(cat_rng)
    sku = catalog.skus(cat_rng, sup["supplier_id"].tolist())
    dates = demand.date_index(end_date, days)
    base = demand.base_rate(sku, wh, base_rng)

    frames = {
        "warehouses": wh,
        "suppliers": sup,
        "skus": sku,
        "sales_daily": demand.sales(sku, wh, base, dates, sales_rng),
        "opening_stock": demand.opening_stock(sku, wh, base, dates[0], stock_rng),
    }
    validate(frames)
    return frames


def validate(f: dict[str, pd.DataFrame]) -> None:
    """Cheap invariants; raises AssertionError so a bad dataset never gets written."""
    assert len(f["skus"]) == catalog.N_SKUS
    assert len(f["warehouses"]) == 6
    assert len(f["suppliers"]) == catalog.N_SUPPLIERS
    assert int(f["suppliers"]["sanctions_flag"].sum()) == 3
    assert f["skus"]["sku_id"].str.match(ids.SKU_RE).all()
    assert f["warehouses"]["warehouse_id"].str.match(ids.WH_RE).all()
    assert f["suppliers"]["supplier_id"].str.match(ids.SUP_RE).all()
    for name in ("warehouses", "suppliers"):
        loc = f[name]
        assert loc[["city", "state", "lat", "lng"]].notna().all().all()
        assert loc["lat"].between(6.0, 37.5).all()
        assert loc["lng"].between(68.0, 98.0).all()
    assert f["suppliers"]["city"].nunique() >= 10
    for name in ("skus", "sales_daily", "opening_stock"):
        assert f[name]["sku_id"].isin(f["skus"]["sku_id"]).all(), name
    for name in ("sales_daily", "opening_stock"):
        assert f[name]["warehouse_id"].isin(f["warehouses"]["warehouse_id"]).all(), name
    assert f["skus"]["supplier_id"].isin(f["suppliers"]["supplier_id"]).all()
    assert (f["sales_daily"]["quantity_sold"] >= 0).all()
    assert (f["opening_stock"]["quantity_on_hand"] >= 0).all()


def make_samples(frames: dict[str, pd.DataFrame], seed: int = DEFAULT_SEED) -> dict[str, pd.DataFrame]:
    """10 rows per file, picked at random (not every Nth row) so SKUs and warehouses vary."""
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(5)[4])
    out = {}
    for name in FILES:
        df = frames[name]
        n = SAMPLE_ROWS
        pinned = np.flatnonzero(df["sanctions_flag"].to_numpy()) if name == "suppliers" else np.array([], dtype=int)
        rest = np.setdiff1d(np.arange(len(df)), pinned)  # sanctioned suppliers always appear in the sample
        # If a source has fewer than 10 rows (currently warehouses), sample with replacement.
        picked = rng.choice(rest, size=n - len(pinned), replace=len(rest) < n - len(pinned))
        out[name] = df.iloc[np.sort(np.concatenate([pinned, picked]))]
    return out


def write_csv(df: pd.DataFrame, path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        df.to_csv(fh, index=False, lineterminator="\n", float_format="%.2f")


def write_parquet(name: str, df: pd.DataFrame, path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema([(c, getattr(pa, t)()) for c, t in _PARQUET_SCHEMAS[name]])
    # Built from numpy arrays (not from_pandas): no pandas metadata, no dependence on pandas' string dtype.
    table = pa.table({c: pa.array(df[c].to_numpy()) for c in df.columns}).cast(schema)
    pq.write_table(table, path, compression="snappy", version="2.6", data_page_version="1.0")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_all(frames: dict[str, pd.DataFrame], out: Path, formats: list[str],
              params: dict) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in FILES:
        for fmt in formats:
            path = out / f"{name}.{fmt}"
            write_csv(frames[name], path) if fmt == "csv" else write_parquet(name, frames[name], path)
            files[path.name] = {"rows": len(frames[name]), "bytes": path.stat().st_size,
                                "sha256": sha256(path)}
    versions = {"numpy": np.__version__, "pandas": pd.__version__}
    if "parquet" in formats:
        import pyarrow
        versions["pyarrow"] = pyarrow.__version__
    manifest = {"params": params, "library_versions": versions, "files": files}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m seed.generate", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, type=Path, help="output directory (should be gitignored)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--end-date", default=DEFAULT_END_DATE, help="last sales date, YYYY-MM-DD")
    ap.add_argument("--formats", default="csv,parquet", help="comma list of: csv, parquet")
    ap.add_argument("--write-samples", action="store_true", help="refresh seed/samples/ (10 rows per file)")
    args = ap.parse_args(argv)

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    bad = set(formats) - {"csv", "parquet"}
    if bad:
        ap.error(f"unknown format(s): {sorted(bad)}")

    frames = build_frames(args.seed, args.days, args.end_date)
    params = {"seed": args.seed, "days": args.days, "end_date": args.end_date}
    manifest = write_all(frames, args.out, formats, params)

    if args.write_samples:
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        for name, df in make_samples(frames, args.seed).items():
            write_csv(df, SAMPLES_DIR / f"{name}.csv")

    for fname, info in manifest["files"].items():
        print(f"{fname:28s} {info['rows']:>10,} rows  {info['bytes']:>12,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
