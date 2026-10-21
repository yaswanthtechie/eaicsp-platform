import json

import pandas as pd
import pytest

from seed import ids
from seed.generate import build_frames, sha256, validate, write_all


def test_canonical_id_formats():
    assert ids.sku_id(123) == "SKU-000123"
    assert ids.supplier_id(45) == "SUP-00045"
    assert ids.warehouse_id("BLR", 1) == "WH-BLR-01"

    assert ids.SKU_RE.fullmatch(ids.sku_id(123))
    assert ids.SUP_RE.fullmatch(ids.supplier_id(45))
    assert ids.WH_RE.fullmatch(ids.warehouse_id("BLR", 1))

    assert not ids.SKU_RE.fullmatch("SKU123")
    assert not ids.SUP_RE.fullmatch("SUP-45")
    assert not ids.WH_RE.fullmatch("WH-blr-01")


def test_small_dataset_has_expected_row_counts():
    frames = build_frames(seed=42, days=3)

    assert len(frames["warehouses"]) == 6
    assert len(frames["suppliers"]) == 60
    assert len(frames["skus"]) == 500
    assert len(frames["sales_daily"]) == 3 * 500 * 6
    assert len(frames["opening_stock"]) == 500 * 6

    assert frames["sales_daily"]["date"].nunique() == 3
    assert frames["opening_stock"]["snapshot_date"].nunique() == 1


def test_same_seed_produces_identical_frames():
    first = build_frames(seed=42, days=3)
    second = build_frames(seed=42, days=3)

    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])


def test_validation_rejects_negative_sales():
    frames = build_frames(seed=42, days=3)
    frames["sales_daily"].loc[
        frames["sales_daily"].index[0], "quantity_sold"
    ] = -1

    with pytest.raises(AssertionError):
        validate(frames)


def test_csv_output_manifest_and_checksums(tmp_path):
    frames = build_frames(seed=42, days=3)
    params = {"seed": 42, "days": 3, "end_date": "2026-10-14"}

    manifest = write_all(frames, tmp_path, ["csv"], params)

    manifest_path = tmp_path / "manifest.json"
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert saved_manifest["params"] == params

    for name, frame in frames.items():
        filename = f"{name}.csv"
        output_path = tmp_path / filename

        assert output_path.exists()
        assert manifest["files"][filename]["rows"] == len(frame)
        assert saved_manifest["files"][filename]["sha256"] == sha256(
            output_path
        )
        assert saved_manifest["files"][filename]["bytes"] == output_path.stat().st_size
