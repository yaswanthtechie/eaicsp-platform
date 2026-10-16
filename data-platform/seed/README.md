# Seed Dataset

This module generates a deterministic shared dataset for the EAICSP integration pipeline.

## Requirements

- Python 3.11+
- Dependencies pinned in seed/requirements.txt

Install from the data-platform directory:

```powershell
pip install -r seed/requirements.txt
```

PyArrow is required for Parquet output.

## Generate the dataset

Run from the `data-platform` directory:

```powershell
python -m seed.generate --out out/
```

The default output includes CSV and Parquet files for:

- Warehouses
- Suppliers
- SKUs
- Daily sales
- Opening stock
- Current stock snapshot (as of 2026-10-14)

Generated files include a manifest containing row counts, file sizes, SHA-256 hashes, and library versions. Keep generated output in a gitignored directory.

## Options

Generate a smaller dataset for testing:

```powershell
python -m seed.generate --out out/ --days 3 --formats csv
```

Use a different deterministic seed:

```powershell
python -m seed.generate --out out/ --seed 7
```

Refresh the ten-row sample CSV files using the default seed:

```powershell
python -m seed.generate --out out/ --write-samples
```

Supplier `city`, `state`, `lat`, and `lng` describe the supplier's Indian dispatch point; they do not necessarily represent the supplier's registered country.

## Canonical IDs

- SKU: `SKU-000123`
- Warehouse: `WH-BLR-01`
- Supplier: `SUP-00045`

The same seed and library versions are intended to produce byte-identical output.

## Tests

Run from the `data-platform` directory (not `seed/`):

```powershell
python -m pytest tests/test_seed_generator.py -q
```

## Sample files

The committed CSV samples contain 10 data rows per file, except
`warehouses.csv`, which contains all 6 warehouses (the full dataset only has six).

`current_stock.csv` contains the latest on-hand inventory snapshot, dated `2026-10-14`, with `snapshot_date`, `sku_id`, `warehouse_id`, and `quantity_on_hand` columns. Current stock is generated deterministically using approximately 10-45 days of cover, with approximately 2% of SKU-warehouse pairs stocked out.
