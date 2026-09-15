"""R5 #4: Automated source-to-target reconciliation."""

import re

from sqlalchemy import text

from database import get_engine
from alert_service import write_alert
from logging_config import logger


DEFAULT_TOLERANCE = 0.01
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_configured_identifier(identifier, allowed):
    """Validate config-derived SQL identifiers against an explicit allow-list."""
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    if identifier not in allowed:
        raise ValueError(f"Identifier {identifier!r} is not allowed for this source")
    return identifier


def compute_stats(batches, numeric_column):
    """Return row count and numeric sum for batches at a pipeline stage."""
    rows = 0
    total = 0.0
    has_numeric = False
    for batch in batches or []:
        df = batch["data"]
        rows += len(df)
        if numeric_column in df.columns:
            has_numeric = True
            total += float(df[numeric_column].sum())
    return rows, (total if has_numeric else None)


def compute_expected(validated_batches, numeric_column):
    """Backward-compatible alias for the gate-approved stage."""
    rows, total = compute_stats(validated_batches, numeric_column)
    return rows, (0.0 if total is None else total)


def evaluate_reconciliation(raw_stats=None, approved_stats=None, transformed_stats=None, actual_stats=None,
                            tolerance=DEFAULT_TOLERANCE, *, expected_rows=None, expected_sum=None,
                            actual_rows=None, actual_sum=None):
    """Attribute differences across raw -> gate -> transform -> landed stages.

    Legacy callers may still pass expected_rows/expected_sum/actual_rows/actual_sum;
    those are treated as a gate-approved == transformed baseline.
    """
    if expected_rows is not None or expected_sum is not None:
        raw_stats = approved_stats = transformed_stats = (
            expected_rows or 0, expected_sum if expected_sum is not None else 0.0
        )
        actual_stats = (actual_rows or 0, actual_sum if actual_sum is not None else 0.0)

    if any(x is None for x in (raw_stats, approved_stats, transformed_stats, actual_stats)):
        raise TypeError("Provide stage statistics or the legacy expected/actual arguments")

    raw_rows, raw_sum = raw_stats
    approved_rows, approved_sum = approved_stats
    transformed_rows, transformed_sum = transformed_stats
    actual_rows, actual_sum = actual_stats

    def match(a, b):
        if a is None or b is None:
            return None
        return abs(a - b) <= tolerance

    raw_to_approved_rows = raw_rows - approved_rows
    raw_to_approved_sum = None if raw_sum is None or approved_sum is None else raw_sum - approved_sum
    gate_to_transform_rows = approved_rows - transformed_rows
    gate_to_transform_sum = None if approved_sum is None or transformed_sum is None else approved_sum - transformed_sum
    transform_to_landed_rows = transformed_rows - actual_rows
    transform_to_landed_sum = None if transformed_sum is None or actual_sum is None else transformed_sum - actual_sum

    gate_transform_ok = gate_to_transform_rows == 0 and (match(approved_sum, transformed_sum) is not False)
    load_ok = transform_to_landed_rows == 0 and (match(transformed_sum, actual_sum) is not False)
    raw_landed_match = raw_rows == actual_rows and (match(raw_sum, actual_sum) is not False)

    return {
        "matched": gate_transform_ok and load_ok,
        "raw_vs_landed_match": raw_landed_match,
        "raw_rows": raw_rows, "raw_sum": raw_sum,
        "approved_rows": approved_rows, "approved_sum": approved_sum,
        "transformed_rows": transformed_rows, "transformed_sum": transformed_sum,
        "actual_rows": actual_rows, "actual_sum": actual_sum,
        "raw_to_approved_rows_dropped": raw_to_approved_rows,
        "raw_to_approved_sum_delta": raw_to_approved_sum,
        "gate_to_transform_rows_dropped": gate_to_transform_rows,
        "gate_to_transform_sum_delta": gate_to_transform_sum,
        "transform_to_landed_rows_dropped": transform_to_landed_rows,
        "transform_to_landed_sum_delta": transform_to_landed_sum,
        "rows_match": transform_to_landed_rows == 0,
        "sum_match": match(transformed_sum, actual_sum) is not False,
    }


def reconcile_load(raw_batches, approved_batches, transformed_batches, source_config,
                   run_id, engine=None, tolerance=DEFAULT_TOLERANCE):
    """Reconcile raw source -> gate-approved -> transformed -> landed data.

    Raw source statistics are captured before schema/quality filtering. This
    makes legitimate upstream drops visible and attributable instead of
    hiding them by using only post-gate batches as the expected baseline.
    """
    engine = engine or get_engine()
    numeric_column = _validate_configured_identifier(
        source_config.quality_check_column,
        set(source_config.columns.keys()),
    )
    table = _validate_configured_identifier(source_config.table, {source_config.table})

    raw_stats = compute_stats(raw_batches, numeric_column)
    approved_stats = compute_stats(approved_batches, numeric_column)
    transformed_stats = compute_stats(transformed_batches, numeric_column)

    query = text(f"""
        SELECT COUNT(*) AS row_count,
               COALESCE(SUM({numeric_column}), 0) AS col_sum
        FROM {table}
        WHERE run_id = :run_id
    """)

    with engine.connect() as connection:
        row = connection.execute(query, {"run_id": run_id}).fetchone()

    actual_stats = (row.row_count, float(row.col_sum))
    result = evaluate_reconciliation(
        raw_stats, approved_stats, transformed_stats, actual_stats,
        tolerance=tolerance,
    )

    if not result["matched"]:
        message = (
            f"[{source_config.name}] Reconciliation mismatch for run_id={run_id}: "
            f"raw={result['raw_rows']} rows, gate-approved={result['approved_rows']}, "
            f"transformed={result['transformed_rows']}, landed={result['actual_rows']}. "
            f"Gate->transform dropped {result['gate_to_transform_rows_dropped']} rows; "
            f"transform->landed dropped {result['transform_to_landed_rows_dropped']} rows."
        )
        logger.error(f"[Reconciliation] {message}")
        write_alert(pipeline="sales_etl", severity="CRITICAL", message=message, run_id=run_id)
    else:
        logger.info(
            f"[Reconciliation] [{source_config.name}] run_id={run_id}: "
            f"raw={result['raw_rows']} -> approved={result['approved_rows']} -> "
            f"transformed={result['transformed_rows']} -> landed={result['actual_rows']}"
        )

    return result
