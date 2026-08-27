"""
R5 #1: Explicit conflict resolution for competing updates.

If two source files in the same run both claim to update the same
(date, sku_id, warehouse_id) row with different values (e.g. an original
file plus a same-day correction), the winner must be decided by an explicit
rule - not by whichever file happened to be processed last by accident.

_dedupe_records() implements that rule: pass priority_key and the record
with the higher priority value wins, regardless of list order.
"""

from etl.src.load import _dedupe_records


def test_no_priority_key_keeps_last_occurrence_unchanged():
    """Default behavior (no priority_key) is untouched - existing callers
    and tests relying on 'last occurrence wins' still get exactly that."""

    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5},
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 99},
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"])

    assert len(result) == 1
    assert result[0]["quantity_sold"] == 99


def test_priority_key_beats_processing_order():
    """The whole point of R5 #1: an explicit priority rule must win even
    when it contradicts plain list/processing order.

    Here the record that appears FIRST in the list has the HIGHER priority
    (e.g. it came from a file with a later mtime, but extract_data() happened
    to glob/sort it earlier). Naive 'last occurrence wins' would pick the
    second record (quantity_sold=5, the stale original); the explicit rule
    must pick the first one instead (quantity_sold=250, the correction).
    """

    records = [
        {
            "date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1",
            "quantity_sold": 250, "_conflict_priority": 2000.0,  # newer file, processed first
        },
        {
            "date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1",
            "quantity_sold": 5, "_conflict_priority": 1000.0,  # older/original file, processed last
        },
    ]

    result = _dedupe_records(
        records,
        ["date", "sku_id", "warehouse_id"],
        priority_key="_conflict_priority",
    )

    assert len(result) == 1
    assert result[0]["quantity_sold"] == 250


def test_priority_key_tie_falls_back_to_last_occurrence():
    """Equal priority (e.g. two rows for the same key within one file) still
    resolves deterministically, matching the no-priority default."""

    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5, "_p": 100.0},
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 99, "_p": 100.0},
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"], priority_key="_p")

    assert len(result) == 1
    assert result[0]["quantity_sold"] == 99


def test_priority_key_preserves_distinct_records():
    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5, "_p": 1.0},
        {"date": "2024-01-01", "sku_id": "SKU2", "warehouse_id": "WH1", "quantity_sold": 10, "_p": 2.0},
        {"date": "2024-01-02", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 15, "_p": 3.0},
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"], priority_key="_p")

    assert len(result) == 3


def test_priority_key_missing_defaults_to_zero():
    """A record with no priority value at all (e.g. file.stat() failed) is
    treated as lowest priority, not as an error."""

    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5, "_p": -10.0},
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 99},  # no "_p" key
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"], priority_key="_p")

    assert len(result) == 1
    # missing priority defaults to 0, which beats -10.0
    assert result[0]["quantity_sold"] == 99
