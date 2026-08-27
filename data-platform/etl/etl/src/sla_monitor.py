"""
R5 #2: Pipeline SLA monitoring.

A run that eventually succeeds but took 20x its normal duration hides a
real problem just as much as an outright failure does (a slow query, a
resource contention issue, a silently-growing batch). This compares each
run's duration against its own pipeline's recent history and raises a
CRITICAL alert when a run is a meaningful outlier - independent of whether
the run's rows/quality-gate status looked fine.

Split into a pure function (evaluate_sla) and a thin DB wrapper
(check_run_duration_sla), the same pattern as reconciliation.py - the pure
function is what's unit-tested; the wrapper is proven against a real
database via scripts/sla_monitoring_check.py.
"""

from sqlalchemy import text

from database import get_engine
from alert_service import write_alert
from logging_config import logger


DEFAULT_THRESHOLD_MULTIPLIER = 3.0
DEFAULT_MIN_HISTORICAL_RUNS = 3
DEFAULT_LOOKBACK_RUNS = 10


def evaluate_sla(
    current_duration_seconds,
    historical_durations_seconds,
    threshold_multiplier=DEFAULT_THRESHOLD_MULTIPLIER,
    min_historical_runs=DEFAULT_MIN_HISTORICAL_RUNS,
):
    """Pure comparison: is current_duration_seconds a meaningful outlier
    against historical_durations_seconds (a list of past successful runs'
    durations, most-recent-first or in any order - only the values matter)?

    Without enough history to trust an average against, this deliberately
    refuses to judge (evaluable=False) rather than alerting on noise from a
    single prior data point, or never alerting on the very first few runs.

    Returns a dict with everything needed to log/alert/test against:
        {
            "evaluable": bool,
            "breached": bool,
            "current_duration_seconds": float,
            "historical_avg_seconds": float | None,
            "threshold_seconds": float | None,
            "historical_run_count": int,
        }
    """

    historical_run_count = len(historical_durations_seconds)

    if historical_run_count < min_historical_runs:
        return {
            "evaluable": False,
            "breached": False,
            "current_duration_seconds": current_duration_seconds,
            "historical_avg_seconds": None,
            "threshold_seconds": None,
            "historical_run_count": historical_run_count,
        }

    historical_avg_seconds = sum(historical_durations_seconds) / historical_run_count
    threshold_seconds = historical_avg_seconds * threshold_multiplier

    breached = current_duration_seconds > threshold_seconds

    return {
        "evaluable": True,
        "breached": breached,
        "current_duration_seconds": current_duration_seconds,
        "historical_avg_seconds": historical_avg_seconds,
        "threshold_seconds": threshold_seconds,
        "historical_run_count": historical_run_count,
    }


def check_run_duration_sla(
    run_id,
    pipeline_name="sales_etl",
    threshold_multiplier=DEFAULT_THRESHOLD_MULTIPLIER,
    min_historical_runs=DEFAULT_MIN_HISTORICAL_RUNS,
    lookback_runs=DEFAULT_LOOKBACK_RUNS,
    engine=None,
):
    """DB-backed SLA check for one finished run: pulls this run's duration
    and its pipeline's last `lookback_runs` prior SUCCESSFUL runs' durations
    from etl_run_log, evaluates via evaluate_sla(), and writes a CRITICAL
    alert if the run breached the SLA. Meant to be called once a run has
    finished (see log_run_task in the DAG).

    Returns evaluate_sla()'s result dict, or None if the run itself can't be
    found or hasn't finished yet.
    """

    engine = engine or get_engine()

    with engine.connect() as connection:

        current_run = connection.execute(
            text("""
                SELECT started_at, finished_at
                FROM etl_run_log
                WHERE run_id = :run_id
            """),
            {"run_id": run_id},
        ).fetchone()

        if current_run is None or current_run.finished_at is None:
            return None

        current_duration = (
            current_run.finished_at - current_run.started_at
        ).total_seconds()

        historical_rows = connection.execute(
            text("""
                SELECT started_at, finished_at
                FROM etl_run_log
                WHERE pipeline_name = :pipeline_name
                  AND status = 'SUCCESS'
                  AND run_id != :run_id
                  AND finished_at IS NOT NULL
                ORDER BY finished_at DESC
                LIMIT :lookback_runs
            """),
            {
                "pipeline_name": pipeline_name,
                "run_id": run_id,
                "lookback_runs": lookback_runs,
            },
        ).fetchall()

    historical_durations = [
        (row.finished_at - row.started_at).total_seconds()
        for row in historical_rows
    ]

    result = evaluate_sla(
        current_duration,
        historical_durations,
        threshold_multiplier=threshold_multiplier,
        min_historical_runs=min_historical_runs,
    )

    if result["breached"]:

        message = (
            f"Run {run_id} took {result['current_duration_seconds']:.1f}s, "
            f"more than {threshold_multiplier:.1f}x its "
            f"{result['historical_run_count']}-run historical average of "
            f"{result['historical_avg_seconds']:.1f}s "
            f"(threshold {result['threshold_seconds']:.1f}s). "
            f"The run succeeded but this duration is a real anomaly worth "
            f"investigating - a slow-but-successful run hides a problem "
            f"just as much as a failed one."
        )

        logger.warning(f"[SLA] {message}")

        write_alert(
            pipeline=pipeline_name,
            severity="CRITICAL",
            message=message,
            run_id=run_id,
        )

    elif result["evaluable"]:

        logger.info(
            f"[SLA] Run {run_id} took {result['current_duration_seconds']:.1f}s, "
            f"within SLA (avg={result['historical_avg_seconds']:.1f}s over "
            f"{result['historical_run_count']} runs, "
            f"threshold={result['threshold_seconds']:.1f}s)."
        )

    else:
        logger.info(
            f"[SLA] Run {run_id}: not enough historical runs "
            f"({result['historical_run_count']} < {min_historical_runs}) "
            f"to evaluate SLA yet."
        )

    return result
