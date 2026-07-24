from sqlalchemy import text
from database import get_engine



engine = get_engine()


def log_success(start_time, end_time, rows_loaded):

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            finished_at,
            status,
            rows_inserted,
            rows_updated,
            rows_rejected,
            error_message
        )
        VALUES
        (
            'sales_etl',
            :started_at,
            :finished_at,
            'SUCCESS',
            :rows_inserted,
            0,
            0,
            NULL
        );
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "started_at": start_time,
                "finished_at": end_time,
                "rows_inserted": rows_loaded
            }
        )

def log_failure(start_time, end_time, error_message):

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            finished_at,
            status,
            rows_inserted,
            rows_updated,
            rows_rejected,
            error_message
        )
        VALUES
        (
            'sales_etl',
            :started_at,
            :finished_at,
            'FAILED',
            0,
            0,
            0,
            :error_message
        );
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "started_at": start_time,
                "finished_at": end_time,
                "error_message": str(error_message)
            }
        )