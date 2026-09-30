
"""Disaster-recovery drill helpers for the ETL pipeline."""

from pathlib import Path


def build_recovery_plan(run_id, backup_path, batch_files):
    if not run_id:
        raise ValueError("A completed run_id is required for a DR drill")
    missing = [str(p) for p in batch_files if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(
            "Recorded source batches required for recovery are missing: "
            + ", ".join(missing)
        )
    return {
        "run_id": run_id,
        "backup_path": str(backup_path),
        "batch_files": [str(p) for p in batch_files],
        "steps": [
            "restore database backup",
            "verify restored ETL run log and batch manifest",
            "replay the recorded run from its batch manifest",
            "reconcile restored target tables",
            "record drill result",
        ],
    }
