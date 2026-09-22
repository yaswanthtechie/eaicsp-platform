
"""Automated R9 M5 disaster-recovery drill.

The drill is deliberately non-destructive:
- pg_dump creates a backup artifact;
- etl_run_batches supplies the exact source-file manifest;
- source files are verified;
- the existing replay mechanism can be invoked explicitly with --replay.

A real production exercise can restore the generated backup into a clean
PostgreSQL instance before using --replay.
"""

import argparse
import os
import subprocess
from pathlib import Path

from sqlalchemy import text

from etl.src.config_loader import load_pipeline_config
from etl.src.database import get_engine
from etl.src.dr_recovery import build_recovery_plan


def latest_successful_run(engine):
    with engine.connect() as conn:
        return conn.execute(text("""
            SELECT run_id
            FROM etl_run_log
            WHERE status = 'SUCCESS'
            ORDER BY finished_at DESC NULLS LAST, run_id DESC
            LIMIT 1
        """)).scalar()


def recorded_batches(engine, run_id):
    with engine.connect() as conn:
        return [
            row.batch_file
            for row in conn.execute(
                text("""
                    SELECT batch_file
                    FROM etl_run_batches
                    WHERE run_id = :run_id
                    ORDER BY source_name, batch_file
                """),
                {"run_id": run_id},
            ).fetchall()
        ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", default="docs/dr_drill_backup.dump")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument(
        "--replay",
        action="store_true",
        help="After the backup/manifest checks, replay the recorded run.",
    )
    args = parser.parse_args()

    engine = get_engine()
    run_id = args.run_id or latest_successful_run(engine)
    if run_id is None:
        raise SystemExit("No successful ETL run is available for the drill.")

    batch_names = recorded_batches(engine, run_id)
    config = load_pipeline_config()

    batch_paths = []
    for source in config.sources:
        for name in batch_names:
            candidate = Path(source.path) / name
            if candidate.exists():
                batch_paths.append(candidate)

    plan = build_recovery_plan(run_id, args.backup, batch_paths)

    backup_path = Path(args.backup)
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    # Uses the same connection settings as the ETL application.
    env = os.environ.copy()
    subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(backup_path),
         "--host", env.get("DB_HOST", "localhost"),
         "--port", env.get("DB_PORT", "5432"),
         "--username", env.get("DB_USER", "postgres"),
         "--dbname", env.get("DB_NAME", "etl_db")],
        check=True,
        env=env,
    )

    print(f"DR backup created: {backup_path}")
    print(f"Recovery manifest run_id={plan['run_id']}:")
    for item in plan["batch_files"]:
        print(f"  {item}")

    if args.replay:
        from etl.src.replay import replay_run
        result = replay_run(run_id)
        print(f"Replay completed: {result}")
    else:
        print("Next controlled step: restore the dump into a clean DB, then rerun with --replay.")


if __name__ == "__main__":
    main()
