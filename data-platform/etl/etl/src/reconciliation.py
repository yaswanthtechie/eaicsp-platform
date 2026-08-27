"""
R5 #4: Automated reconciliation.

Compares row count and the sum of a source's numeric "quantity" column
between what the quality gate approved for load (the *validated* batches -
i.e. the raw source file's rows minus whatever the quality gate legitimately
and visibly dropped) and what's actually sitting in the target table for
this run_id afterwards.

This catches something schema/quality validation fundamentally can't: those
checks run BEFORE load and never look at the database again, so a bug in
the load step itself (a partial write, a silently-swallowed exception on
one chunk, a connection dropped mid-transaction) would sail straight past
them. Reconciliation is the one check that actually looks at what landed.

Split into a pure function (evaluate_reconciliation) and a thin DB wrapper
(reconcile_load), the same pattern as sla_monitor.py.
"""

from sqlalchemy import text

from database import get_engine
from alert_service import write_alert
from logging_config import logger


DEFAULT_TOLERANCE = 0.01


def compute_expected(validated_batches, numeric_column):
    """Pure: row count and sum(numeric_column) across the validated batches
    that were actually handed to the loader for this run. numeric_column
    should be the source's `quality_check_column` (quantity_sold for sales,
    quantity_on_hand for inventory) - already present in pipeline_config.yaml,
    no new config needed."""

    expected_rows = 0
    expected_sum = 0.0

    for batch in validated_batches:
        df = batch["data"]
        expected_rows += len(df)
        if numeric_column in df.columns:
            expected_sum += float(df[numeric_column].sum())

    return expected_rows, expected_sum


def evaluate_reconciliation(
    expected_rows,
    expected_sum,
    actual_rows,
    actual_sum,
    tolerance=DEFAULT_TOLERANCE,
):
    """Pure comparison, directly unit-testable without a database."""

    rows_match = expected_rows == actual_rows
    sum_match = abs(expected_sum - actual_sum) <= tolerance

    return {
        "matched": rows_match and sum_match,
        "rows_match": rows_match,
        "sum_match": sum_match,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "expected_sum": expected_sum,
        "actual_sum": actual_sum,
    }


def reconcile_load(
    validated_batches,
    source_config,
    run_id,
    engine=None,
    tolerance=DEFAULT_TOLERANCE,
):
    """DB-backed reconciliation for one source's load, for one run: computes
    what SHOULD be in the table (from the validated batches actually handed
    to the loader) and queries what IS in the table for this run_id, then
    compares. Writes a CRITICAL alert on mismatch - this is meant to catch
    something the quality gate structurally cannot, so any mismatch here is
    a load-time bug, not a data-quality issue.

    numeric_column defaults to source_config.quality_check_column, since
    that's already the "the one numeric column that matters for this
    source" field the quality gate itself uses - no new config required.
    """

    engine = engine or get_engine()
    numeric_column = source_config.quality_check_column

    expected_rows, expected_sum = compute_expected(validated_batches, numeric_column)

    query = text(f"""
        SELECT COUNT(*) AS row_count, COALESCE(SUM({numeric_column}), 0) AS col_sum
        FROM {source_config.table}
        WHERE run_id = :run_id
    """)

    with engine.connect() as connection:
        row = connection.execute(query, {"run_id": run_id}).fetchone()

    actual_rows = row.row_count
    actual_sum = float(row.col_sum)

    result = evaluate_reconciliation(
        expected_rows, expected_sum, actual_rows, actual_sum, tolerance=tolerance
    )

    if not result["matched"]:

        message = (
            f"[{source_config.name}] Reconciliation mismatch after load: "
            f"expected {result['expected_rows']} rows / "
            f"sum({numeric_column})={result['expected_sum']:.2f} "
            f"(from the batches the quality gate approved), but "
            f"{source_config.table} has {result['actual_rows']} rows / "
            f"sum({numeric_column})={result['actual_sum']:.2f} for run_id={run_id}. "
            f"This means rows the quality gate approved did not land correctly - "
            f"a load-time failure, not a data-quality issue."
        )

        logger.error(f"[Reconciliation] {message}")

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=message,
            run_id=run_id,
        )

    else:
        logger.info(
            f"[Reconciliation] [{source_config.name}] run_id={run_id} matched: "
            f"{result['actual_rows']} rows, sum({numeric_column})={result['actual_sum']:.2f}"
        )

    return result
