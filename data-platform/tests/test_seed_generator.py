import hashlib
from pathlib import Path

import pandas as pd

from seed import catalog, ids
from seed.generate import (
    SAMPLES_DIR,
    build_frames,
    make_samples,
    write_all,
    write_csv,
)


def test_required_dataset_counts_and_canonical_ids():
    frames = build_frames(seed=42, days=3)

    assert len(frames["skus"]) == 500
    assert len(frames["warehouses"]) == 6
    assert len(frames["suppliers"]) == 60

    assert "SKU-000123" in set(frames["skus"]["sku_id"])
    assert "WH-BLR-01" in set(frames["warehouses"]["warehouse_id"])
    assert "SUP-00045" in set(frames["suppliers"]["supplier_id"])

    assert frames["skus"]["sku_id"].str.fullmatch(ids.SKU_RE).all()
    assert frames["warehouses"]["warehouse_id"].str.fullmatch(ids.WH_RE).all()
    assert frames["suppliers"]["supplier_id"].str.fullmatch(ids.SUP_RE).all()


def test_sales_and_opening_stock_row_counts():
    frames = build_frames(seed=42, days=3)

    assert len(frames["sales_daily"]) == 500 * 6 * 3
    assert len(frames["opening_stock"]) == 500 * 6


def test_sanctions_and_location_requirements():
    frames = build_frames(seed=42, days=3)
    suppliers = frames["suppliers"]

    assert int(suppliers["sanctions_flag"].sum()) == 3

    for name in ("warehouses", "suppliers"):
        locations = frames[name]
        assert locations[["city", "state", "lat", "lng"]].notna().all().all()
        assert locations["lat"].between(6.0, 37.5).all()
        assert locations["lng"].between(68.0, 98.0).all()

    assert suppliers["city"].nunique() >= 10


def test_sanctioned_suppliers_use_compliance_list_names():
    suppliers = build_frames(seed=42, days=3)["suppliers"].set_index("supplier_id")

    assert suppliers.loc["SUP-00007", "name"] == "ALPHA SANCTIONS CORP"
    assert suppliers.loc["SUP-00023", "name"] == "TEST EU ENTITY 01"
    assert suppliers.loc["SUP-00045", "name"] == "TEST UN ENTITY 01"

    clean = suppliers[~suppliers["sanctions_flag"]]
    assert not clean["name"].str.contains(
        "delta|alpha|beta|gamma", case=False
    ).any()


def test_same_seed_produces_identical_csv_files(tmp_path):
    frames1 = build_frames(seed=42, days=3)
    frames2 = build_frames(seed=42, days=3)

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"

    write_all(frames1, out1, ["csv"], {"seed": 42, "days": 3})
    write_all(frames2, out2, ["csv"], {"seed": 42, "days": 3})

    for name in (
        "warehouses.csv",
        "suppliers.csv",
        "skus.csv",
        "sales_daily.csv",
        "opening_stock.csv",
    ):
        hash1 = hashlib.sha256((out1 / name).read_bytes()).hexdigest()
        hash2 = hashlib.sha256((out2 / name).read_bytes()).hexdigest()
        assert hash1 == hash2, f"{name} differs between identical runs"


def test_samples_have_ten_rows_per_dataset():
    frames = build_frames(seed=42, days=3)
    samples = make_samples(frames, seed=42)

    assert set(samples) == {
        "warehouses", "suppliers", "skus", "sales_daily", "opening_stock"
    }

    for name, sample in samples.items():
        expected = 6 if name == "warehouses" else 10
        assert len(sample) == expected, name
        assert not sample.duplicated().any(), name

    assert int(samples["suppliers"]["sanctions_flag"].sum()) == 3

def test_parquet_generation_when_pyarrow_is_installed(tmp_path):
    import pytest

    pytest.importorskip("pyarrow")

    frames = build_frames(seed=42, days=3)
    manifest = write_all(
        frames, tmp_path, ["parquet"], {"seed": 42, "days": 3}
    )

    assert len(manifest["files"]) == 5
    for name in (
        "warehouses.parquet",
        "suppliers.parquet",
        "skus.parquet",
        "sales_daily.parquet",
        "opening_stock.parquet",
    ):
        assert (tmp_path / name).is_file()

def test_committed_samples_match_generator(tmp_path):
    samples = make_samples(build_frames())

    for name, df in samples.items():
        out = tmp_path / f"{name}.csv"
        write_csv(df, out)

        assert out.read_bytes() == (SAMPLES_DIR / f"{name}.csv").read_bytes(), (
            f"seed/samples/{name}.csv is stale: "
            "run python -m seed.generate --out out/ --write-samples"
        )

def test_same_seed_produces_identical_parquet_files(tmp_path):
    import pytest

    pytest.importorskip("pyarrow")

    frames1 = build_frames(seed=42, days=3)
    frames2 = build_frames(seed=42, days=3)

    metadata1 = write_all(
        frames1,
        tmp_path / "run1",
        ["parquet"],
        {"seed": 42, "days": 3},
    )
    metadata2 = write_all(
        frames2,
        tmp_path / "run2",
        ["parquet"],
        {"seed": 42, "days": 3},
    )

    assert len(metadata1["files"]) == 5

    for name, info in metadata1["files"].items():
        assert info["sha256"] == metadata2["files"][name]["sha256"], (
            f"{name} differs between identical runs"
        )
