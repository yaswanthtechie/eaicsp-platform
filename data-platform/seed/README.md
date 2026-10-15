# Seed Dataset

This module generates a deterministic shared dataset for the EAICSP integration pipeline.

## Requirements

- Python 3.11+
- NumPy
- Pandas
- PyArrow (required for Parquet output)

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

## Canonical IDs

- SKU: `SKU-000123`
- Warehouse: `WH-BLR-01`
- Supplier: `SUP-00045`

The same seed and library versions are intended to produce byte-identical output.

## Tests

Run the seed generator tests from this directory:

```powershell
python -m pytest tests/test_seed_generator.py -q
```

## Sample files

The committed CSV samples contain exactly 10 data rows per file. Because the
complete warehouse dataset contains only six distinct warehouses, the warehouse
sample repeats records to reach 10 rows. This does not change the full dataset.
