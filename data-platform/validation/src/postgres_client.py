import os
import logging
from typing import Optional
from src.validator import ValidationResult

logger = logging.getLogger(__name__)

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except (ImportError, OSError) as e:
    PSYCOPG2_AVAILABLE = False
    logger.warning(f"psycopg2 unavailable or blocked by system policy: {e}. PostgreSQL persistence will be mocked/skipped.")

def persist_validation_result(dataset_name: str, result: ValidationResult, duration_seconds: float):
    """Saves the ValidationResult payload to PostgreSQL with graceful fallback if blocked."""
    if not PSYCOPG2_AVAILABLE:
        logger.info(f"[Mock DB] Would persist run for '{dataset_name}' (Passed: {result.passed})")
        return

    conn_str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/validation_db")
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO validation_runs 
            (dataset_name, config_version, passed, batch_rejected, total_rows, total_rows_affected, duration_seconds, sla_breached)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                dataset_name,
                result.config_version,
                result.passed,
                result.batch_rejected,
                result.total_rows,
                result.total_rows_affected,
                duration_seconds,
                result.sla_breached
            )
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to persist validation run to Postgres: {e}")