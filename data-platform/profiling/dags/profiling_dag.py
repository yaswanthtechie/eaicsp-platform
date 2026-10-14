import logging
import os
import sys
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.hooks.base import BaseHook
from sqlalchemy import create_engine, inspect, text

from src.audit_archive import AuditArchive
from src.postgres_profiler import PostgresPushdownProfiler

log = logging.getLogger(__name__)

# Local docker-compose database, used only when no Airflow connection exists.
# Override with the PROFILING_DB_URL environment variable.
LOCAL_FALLBACK_DB_URL = os.environ.get(
    "PROFILING_DB_URL",
    "postgresql://postgres:password@postgres-profiler:5432/profiling_db",
)


def setup_logging(log_level: str = "INFO") -> None:
    """Configures structured logging to stdout."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


# Tables profiled on every run. Each one must exist in schema 'public'.
#   benchmark_1m_sales : 1M-row sales table (Sandeep's pushdown benchmark data)
#   products           : product master data
TABLES_TO_PROFILE = [
    "benchmark_1m_sales",
    "products",
]


def _check_table_exists(db_url: str, table_name: str) -> None:
    """Logs which database the task uses and fails clearly if the table is missing.

    The password is never logged. A missing table fails immediately without
    retries, because retrying cannot make a missing table appear.
    """
    check_engine = create_engine(db_url)
    try:
        # Pass a plain string with the password already masked. Airflow's log
        # formatter calls str() on arguments, and str() of a URL shows the password.
        safe_url = check_engine.url.render_as_string(hide_password=True)
        log.info("Profiling database: %s", safe_url)

        with check_engine.connect() as conn:
            database_name = conn.execute(text("SELECT current_database()")).scalar()

        visible_tables = inspect(check_engine).get_table_names(schema="public")
        if table_name not in visible_tables:
            raise AirflowFailException(
                f"Table '{table_name}' not found in schema 'public' of database "
                f"'{database_name}'. Tables available: {visible_tables}"
            )
    finally:
        check_engine.dispose()


@dag(
    dag_id="scheduled_data_profiling",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["data_quality", "profiling", "monitoring"],
)
def profiling_dag():

    @task
    def profile_table(table_name: str):
        # 1. Resolve connection.
        # Tries Airflow's connection store first, falls back to the local Docker Compose
        # database for seamless dag.test() execution.
        try:
            conn = BaseHook.get_connection("postgres_profiler_db")
            db_url = conn.get_uri()
            log.info("Using Airflow connection: postgres_profiler_db")
        except Exception:
            db_url = LOCAL_FALLBACK_DB_URL
            log.info("Airflow connection not found. Using local docker-compose fallback.")

        # 2. Fail fast with a clear message if the table does not exist
        _check_table_exists(db_url, table_name)

        # 3. Execute SQL Pushdown Profiling
        log.info("Starting pushdown profiling for table: %s", table_name)
        profiler = PostgresPushdownProfiler(db_url)
        report = profiler.profile_table(table_name)

        # 4. Persist to existing Audit Archive
        archive = AuditArchive()
        audit_record = archive.save_run(report=report)

        log.info("Successfully archived run %s for %s.", audit_record["run_id"], table_name)
        return audit_record["run_id"]

    # Dynamically generate a parallel task for each table in the configuration list
    for table in TABLES_TO_PROFILE:
        profile_table.override(task_id=f"profile_table_{table}")(table)


# Register the DAG
dag_obj = profiling_dag()

if __name__ == "__main__":
    # Allows local execution without spinning up the Airflow scheduler or webserver.
    print("Running DAG locally via dag.test()...")
    dag_obj.test()
