"""
Streaming validation must give the same answer as in-memory validation on the same file.

The older parity test in test_validator.py only uses ISO dates and no missing values,
which is exactly where the two paths agreed. This test uses the real generator output:
mixed date formats (normalised by a transform) and missing key columns.
"""
from pathlib import Path

import pandas as pd
import pytest

from src.make_messy_data import MessyDataConfig, generate_messy_data
from src.validator import DataValidator

CONFIG = Path(__file__).resolve().parent.parent / "configs" / "sales_rules.yaml"


def _counts(report):
    return {(e["rule"], e["field"]): e["count"] for e in report.errors + report.warnings}


@pytest.mark.parametrize("chunksize", [700, 5000])
def test_stream_matches_in_memory_on_messy_data(tmp_path, chunksize):
    csv_path = tmp_path / "messy.csv"
    generate_messy_data(csv_path, MessyDataConfig(n_base=3000))

    validator = DataValidator.from_config(str(CONFIG))

    validator.rules = [
        r for r in validator.rules
        if not getattr(r, 'requires_full_dataset', False)
    ]

    in_memory = validator.validate(pd.read_csv(csv_path))
    streamed = validator.validate_stream(str(csv_path), chunksize=chunksize)

    # Guard: the file really contains the cases that used to diverge
    raw = pd.read_csv(csv_path)
    assert raw[["date", "sku_id", "warehouse_id"]].isna().any(axis=1).sum() > 0
    assert (~raw["date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$") & raw["date"].notna()).sum() > 0

    assert _counts(streamed) == _counts(in_memory)
    assert streamed.total_rows == in_memory.total_rows
    assert streamed.batch_rejected == in_memory.batch_rejected


@pytest.mark.parametrize("profile", ["default", "strict", "bulk"])
def test_shipped_profiles_are_streamable(tmp_path, profile):
    """
        This is the guard against an aggregate rule being added to a profile that
        others inherit, which would silently take the whole streaming path offline.
    """
    csv_path = tmp_path / "messy.csv"
    generate_messy_data(csv_path, MessyDataConfig(n_base=500))

    validator = DataValidator.from_config(str(CONFIG), profile_name=profile)
    report = validator.validate_stream(str(csv_path), chunksize=100)

    assert report.total_rows > 0


def test_streaming_refuses_aggregate_rules(tmp_path):
    """
        An IQR is computed over the whole dataset, so a per-chunk answer would be
        wrong. Streaming must abort loudly rather than report a different number.
    """
    csv_path = tmp_path / "messy.csv"
    generate_messy_data(csv_path, MessyDataConfig(n_base=500))
    validator = DataValidator.from_config(str(CONFIG), profile_name="deep")

    with pytest.raises(RuntimeError, match="detect_quantity_outliers"):
        validator.validate_stream(str(csv_path), chunksize=100)


def test_deep_profile_still_works_in_memory(tmp_path):
    """Aborting on stream must not affect the in-memory path."""
    csv_path = tmp_path / "messy.csv"
    generate_messy_data(csv_path, MessyDataConfig(n_base=500))
    df = pd.read_csv(csv_path)
    validator = DataValidator.from_config(str(CONFIG), profile_name="deep")
    report = validator.validate(df)

    assert report.total_rows == len(df)
    assert any(w["rule"] == "detect_quantity_outliers" for w in report.warnings)
