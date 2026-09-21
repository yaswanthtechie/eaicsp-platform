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