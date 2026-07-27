from sqlalchemy import text
from database import get_engine

engine = get_engine()


def log_success(
    start_time,
    end_time,
    batches_seen,
    rows_inserted,
    rows_updated,
    rows_rejected
):

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            finished_at,
            status,
            batches_seen,
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
            :batches_seen,
            :rows_inserted,
            :rows_updated,
            :rows_rejected,
            NULL
        );
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "started_at": start_time,
                "finished_at": end_time,
                "batches_seen": batches_seen,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_rejected": rows_rejected
            }
        )


def log_failure(
    start_time,
    end_time,
    error_message,
    batches_seen=0,
    rows_inserted=0,
    rows_updated=0,
    rows_rejected=0
):

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            finished_at,
            status,
            batches_seen,
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
            :batches_seen,
            :rows_inserted,
            :rows_updated,
            :rows_rejected,
            :error_message
        );
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "started_at": start_time,
                "finished_at": end_time,
                "batches_seen": batches_seen,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_rejected": rows_rejected,
                "error_message": str(error_message)
            }
        )