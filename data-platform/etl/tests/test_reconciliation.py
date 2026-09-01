"""
R5 #4: Automated reconciliation - tests for the pure functions
(compute_expected, evaluate_reconciliation).

reconcile_load() (the DB-backed wrapper) is proven against a real database
via scripts/reconciliation_check.py, including a deliberately-injected
mismatch, per spec.
"""

import pandas as pd

from etl.src.reconciliation import compute_expected, evaluate_reconciliation


def test_compute_expected_sums_across_batches():
    batches = [
        {"data": pd.DataFrame({"quantity_sold": [1, 2, 3]})},
        {"data": pd.DataFrame({"quantity_sold": [4, 5]})},
    ]

    rows, total = compute_expected(batches, "quantity_sold")

    assert rows == 5
    assert total == 15.0


def test_compute_expected_empty_batches():
    rows, total = compute_expected([], "quantity_sold")
    assert rows == 0
    assert total == 0.0


def test_compute_expected_missing_column_contributes_zero_sum():
    batches = [{"data": pd.DataFrame({"other_col": [1, 2]})}]
    rows, total = compute_expected(batches, "quantity_sold")
    # rows still counted, sum just doesn't include this batch
    assert rows == 2
    assert total == 0.0


def test_evaluate_reconciliation_exact_match():
    result = evaluate_reconciliation(
        expected_rows=100, expected_sum=5000.0,
        actual_rows=100, actual_sum=5000.0,
    )
    assert result["matched"] is True
    assert result["rows_match"] is True
    assert result["sum_match"] is True


def test_evaluate_reconciliation_row_count_mismatch_is_a_silent_partial_failure():
    # Exactly the scenario the spec calls out: some rows silently didn't land.
    result = evaluate_reconciliation(
        expected_rows=100, expected_sum=5000.0,
        actual_rows=97, actual_sum=4850.0,
    )
    assert result["matched"] is False
    assert result["rows_match"] is False


def test_evaluate_reconciliation_sum_mismatch_with_matching_row_count():
    # Same row count, but values got corrupted somewhere in the load path -
    # row-count-only reconciliation would have missed this entirely.
    result = evaluate_reconciliation(
        expected_rows=100, expected_sum=5000.0,
        actual_rows=100, actual_sum=4500.0,
    )
    assert result["matched"] is False
    assert result["rows_match"] is True
    assert result["sum_match"] is False


def test_evaluate_reconciliation_within_float_tolerance_matches():
    result = evaluate_reconciliation(
        expected_rows=10, expected_sum=100.004,
        actual_rows=10, actual_sum=100.006,
        tolerance=0.01,
    )
    assert result["matched"] is True


def test_stage_reconciliation_attributes_quality_gate_drop_without_calling_it_load_failure():
    result = evaluate_reconciliation(
        (100, 5000.0), (97, 4850.0), (97, 4850.0), (97, 4850.0)
    )
    assert result["matched"] is True
    assert result["raw_to_approved_rows_dropped"] == 3
    assert result["gate_to_transform_rows_dropped"] == 0
    assert result["transform_to_landed_rows_dropped"] == 0


def test_stage_reconciliation_catches_transform_drop():
    result = evaluate_reconciliation(
        (100, 5000.0), (100, 5000.0), (99, 4950.0), (99, 4950.0)
    )
    assert result["matched"] is False
    assert result["gate_to_transform_rows_dropped"] == 1


def test_stage_reconciliation_catches_load_drop():
    result = evaluate_reconciliation(
        (100, 5000.0), (100, 5000.0), (100, 5000.0), (99, 4950.0)
    )
    assert result["matched"] is False
    assert result["transform_to_landed_rows_dropped"] == 1
