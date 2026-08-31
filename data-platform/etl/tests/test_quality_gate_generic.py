from pathlib import Path

import pandas as pd
import pytest

from etl.src.quality_gate import check_batch_generic, quality_gate_generic
from etl.src.config_loader import load_pipeline_config
import etl.src.dead_letter as dead_letter
import etl.src.quality_gate as quality_gate_module


CONFIG = load_pipeline_config()
INVENTORY_CONFIG = CONFIG.get_source("inventory")


@pytest.fixture(autouse=True)
def _mock_write_alert(monkeypatch):
    # quality_gate_generic writes alerts (real DB write) on rejection - mock
    # it out so these tests stay DB-free, matching the existing test suite.
    monkeypatch.setattr(
        quality_gate_module,
        "write_alert",
        lambda **kwargs: None,
    )


def _make_inventory_df(n, quantity_values=None):
    if quantity_values is None:
        quantity_values = [10] * n

    return pd.DataFrame({
        "snapshot_date": pd.to_datetime(["2024-01-01"] * n),
        "sku_id": [f"SKU{i}" for i in range(n)],
        "warehouse_id": ["WH1"] * n,
        "quantity_on_hand": quantity_values,
    })


def test_healthy_batch_passes():
    df = _make_inventory_df(10)

    passed, report = check_batch_generic(
        df,
        "batch.csv",
        INVENTORY_CONFIG,
    )

    assert passed is True
    assert report["reason"] == ""


def test_all_null_column_rejected():
    df = _make_inventory_df(
        10,
        quantity_values=[None] * 10,
    )

    passed, report = check_batch_generic(
        df,
        "batch.csv",
        INVENTORY_CONFIG,
    )

    assert passed is False
    assert report["reason"] == "too many nulls"


def test_mostly_negative_column_rejected():
    df = _make_inventory_df(
        10,
        quantity_values=[-1] * 10,
    )

    passed, report = check_batch_generic(
        df,
        "batch.csv",
        INVENTORY_CONFIG,
    )

    assert passed is False
    assert "negative" in report["reason"]


def test_huge_batch_over_max_rows_rejected():
    # inventory's configured max_rows is 5000
    df = _make_inventory_df(6000)

    passed, report = check_batch_generic(
        df,
        "batch.csv",
        INVENTORY_CONFIG,
    )

    assert passed is False
    assert report["reason"] == "invalid row count"


def test_empty_batch_list_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        dead_letter,
        "COUNTS_FILE",
        tmp_path / "counts.json",
    )

    dead_letter.COUNTS_FILE.write_text("{}")

    result = quality_gate_generic(
        [],
        INVENTORY_CONFIG,
    )

    assert result == []


def test_dead_letter_moves_after_three_consecutive_failures(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        dead_letter,
        "COUNTS_FILE",
        tmp_path / "counts.json",
    )

    # Start this test with a clean failure counter.
    dead_letter.COUNTS_FILE.write_text("{}")

    monkeypatch.chdir(tmp_path)

    bad_df = _make_inventory_df(
        10,
        quantity_values=[None] * 10,
    )

    # quality_gate.py now anchors these folders to the project root
    # instead of using the current working directory.
    project_root = Path(__file__).resolve().parents[1]

    rejected_dir = project_root / "data" / "rejected"
    manual_review_dir = (
        project_root / "data" / "needs_manual_review"
    )

    rejected_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manual_review_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_name = "recurring_bad.csv"

    # Clean up any stale file from a previous failed test run.
    rejected_file = rejected_dir / file_name
    manual_review_file = manual_review_dir / file_name

    if rejected_file.exists():
        rejected_file.unlink()

    if manual_review_file.exists():
        manual_review_file.unlink()

    for i in range(1, 4):
        batch_file = (
            tmp_path
            / "data"
            / "batches"
            / file_name
        )

        batch_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        batch_file.write_text("placeholder")

        batches = [
            {
                "file_path": batch_file,
                "data": bad_df.copy(),
            }
        ]

        result = quality_gate_generic(
            batches,
            INVENTORY_CONFIG,
        )

        assert result == []

        if i < 3:
            assert rejected_file.exists()

            # Remove the rejected file so the next iteration can
            # recreate the same filename.
            rejected_file.unlink()

        else:
            assert manual_review_file.exists()

            manual_review_file.unlink()


def test_successful_batch_clears_failure_count(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        dead_letter,
        "COUNTS_FILE",
        tmp_path / "counts.json",
    )

    dead_letter.COUNTS_FILE.write_text("{}")

    dead_letter.record_failure("some_file.csv")
    dead_letter.record_failure("some_file.csv")

    assert dead_letter._load_counts()["some_file.csv"] == 2

    dead_letter.clear_failures("some_file.csv")

    assert "some_file.csv" not in dead_letter._load_counts()