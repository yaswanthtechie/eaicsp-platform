"""
Persist every validation run (batch or stream) to PostgreSQL.

Fails loudly: if a run cannot be saved, PersistenceError is raised. The
caller decides what to do (the batch CLI exits non-zero; the streaming
consumer logs it, counts it in Prometheus and keeps consuming). Silently
"mocking" persistence would make the run history look complete when it
is not.
"""

import logging
import os
from typing import Optional, Sequence

from data_validator.validator import ValidationResult

logger = logging.getLogger(__name__)

VALID_MODES = ("batch", "stream")

_INSERT_RUN = """
    INSERT INTO validation_runs
        (mode, dataset_name, config_version, rules_applied, passed,
         batch_rejected, total_rows, total_rows_affected,
         duration_seconds, sla_breached)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING run_id
"""

_SELECT_RUN = """
    SELECT run_id, mode, dataset_name, config_version, rules_applied,
           passed, batch_rejected, total_rows, total_rows_affected,
           duration_seconds, sla_breached, created_at
    FROM validation_runs
    WHERE run_id = %s
"""


class PersistenceError(RuntimeError):
    """A validation run could not be written to (or read from) Postgres."""


def _connect():
    """Open a connection using DATABASE_URL, or raise PersistenceError."""
    try:
        import psycopg2
    except (ImportError, OSError) as exc:
        # OSError: the native driver DLL is blocked by OS policy. That is an
        # environment problem to fix, not a reason to pretend we saved data.
        raise PersistenceError(
            f"psycopg2 cannot be loaded ({type(exc).__name__}: {exc}). "
            "Install psycopg2-binary or fix the local policy; runs are NOT saved."
        ) from exc

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise PersistenceError(
            "DATABASE_URL is not set. Copy .env.example to .env and set it."
        )

    try:
        return psycopg2.connect(dsn)
    except Exception as exc:
        # Never log the DSN: it contains the password.
        raise PersistenceError(
            f"Could not connect to Postgres: {type(exc).__name__}: {exc}"
        ) from exc


def persist_validation_result(
    dataset_name: str,
    result: ValidationResult,
    duration_seconds: float,
    mode: str = "batch",
    rules_applied: Optional[Sequence[str]] = None,
) -> int:
    """
    Save one validation run and return its run_id.

    rules_applied defaults to result.evaluated_rules (every rule the
    validator ran). Raises PersistenceError if the run was not saved.
    """
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    if not dataset_name:
        raise ValueError("dataset_name must not be empty")
    if duration_seconds < 0:
        raise ValueError("duration_seconds must not be negative")

    rules = list(rules_applied if rules_applied is not None else result.evaluated_rules)

    conn = _connect()
    try:
        with conn:  # commits on success, rolls back on any error
            with conn.cursor() as cur:
                cur.execute(
                    _INSERT_RUN,
                    (
                        mode,
                        dataset_name,
                        result.config_version,
                        rules,
                        result.passed,
                        result.batch_rejected,
                        result.total_rows,
                        result.total_rows_affected,
                        duration_seconds,
                        result.sla_breached,
                    ),
                )
                run_id = cur.fetchone()[0]
    except Exception as exc:
        raise PersistenceError(
            f"Could not save validation run for '{dataset_name}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    finally:
        conn.close()

    logger.info(
        "Saved validation run %s (%s, dataset=%s, passed=%s)",
        run_id, mode, dataset_name, result.passed,
    )
    return run_id


def fetch_run(run_id: int) -> Optional[dict]:
    """Read one saved run back (used to prove persistence really happened)."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_SELECT_RUN, (run_id,))
            row = cur.fetchone()
            if row is None:
                return None
            columns = [col[0] for col in cur.description]
            return dict(zip(columns, row))
    except Exception as exc:
        raise PersistenceError(
            f"Could not read validation run {run_id}: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        conn.close()