"""
R5 #2: SLA monitoring proof against a real database.

Seeds etl_run_log with a handful of "normal" historical runs (~120s each),
then inserts one run that finished successfully but took 45 minutes -
exactly the spec's example (usually 2 min, today 45 min). Calls
check_run_duration_sla() and shows it fires a CRITICAL alert into
etl_alerts even though the run's own status was SUCCESS.

Runs against real etl_run_log/etl_alerts rows (all tagged with a dedicated
pipeline_name so they're easy to find and clean up; nothing else in those
tables is touched).

Usage:
    cd etl/src && python3 ../../scripts/sla_monitoring_check.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl" / "src"))
os.chdir(REPO_ROOT)

from sqlalchemy import text

from database import get_engine
from sla_monitor import check_run_duration_sla


PIPELINE_NAME = "sla_check_demo"


def seed_run(engine, started_at, finished_at, status="SUCCESS"):
    with engine.begin() as conn:
        return conn.execute(
            text("""
                INSERT INTO etl_run_log
                    (pipeline_name, started_at, finished_at, status,
                     batches_seen, rows_inserted, rows_updated, rows_rejected)
                VALUES
                    (:pipeline_name, :started_at, :finished_at, :status, 1, 10, 0, 0)
                RETURNING run_id;
            """),
            {
                "pipeline_name": PIPELINE_NAME,
                "started_at": started_at,
                "finished_at": finished_at,
                "status": status,
            },
        ).scalar()


def cleanup(engine):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM etl_alerts WHERE pipeline = :p"),
            {"p": PIPELINE_NAME},
        )
        conn.execute(
            text("DELETE FROM etl_run_log WHERE pipeline_name = :p"),
            {"p": PIPELINE_NAME},
        )


def main():
    engine = get_engine()

    cleanup(engine)  # in case a previous run of this script didn't clean up

    now = datetime.now()

    print(f"Seeding 5 historical runs for '{PIPELINE_NAME}', each ~120s...")
    for i, duration in enumerate([118, 122, 119, 121, 120]):
        started = now - timedelta(days=5 - i, seconds=duration)
        finished = started + timedelta(seconds=duration)
        seed_run(engine, started, finished)

    print("Inserting today's run: 45 minutes, but SUCCESS.")
    slow_started = now - timedelta(minutes=45)
    slow_run_id = seed_run(engine, slow_started, now, status="SUCCESS")

    print(f"\nChecking SLA for run_id={slow_run_id}...\n")
    result = check_run_duration_sla(slow_run_id, pipeline_name=PIPELINE_NAME, engine=engine)

    print("=" * 60)
    print("SLA MONITORING CHECK")
    print("=" * 60)
    print(f"Run status in etl_run_log : SUCCESS")
    print(f"Run duration              : {result['current_duration_seconds']:.1f}s")
    print(f"Historical average        : {result['historical_avg_seconds']:.1f}s "
          f"(over {result['historical_run_count']} runs)")
    print(f"Threshold (3x average)    : {result['threshold_seconds']:.1f}s")
    print(f"SLA breached              : {result['breached']}")

    with engine.connect() as conn:
        alert = conn.execute(
            text("""
                SELECT severity, message FROM etl_alerts
                WHERE pipeline = :p AND run_id = :r
                ORDER BY created_at DESC LIMIT 1
            """),
            {"p": PIPELINE_NAME, "r": slow_run_id},
        ).fetchone()

    if result["breached"] and alert is not None and alert.severity == "CRITICAL":
        print(f"\nAlert written to etl_alerts: [{alert.severity}] {alert.message}")
        print("\nPASS: a run that succeeded was still flagged for its anomalous duration.")
    else:
        print("\nFAIL: expected a CRITICAL alert for this run, found none.")
        cleanup(engine)
        sys.exit(1)

    cleanup(engine)
    print("(demo rows cleaned up)")


if __name__ == "__main__":
    main()
