from sqlalchemy import text
from database import get_engine

engine = get_engine()


def create_run():

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            status
        )
        VALUES
        (
            'sales_etl',
            NOW(),
            'RUNNING'
        )
        RETURNING run_id;
    """)

    with engine.begin() as connection:

        run_id = connection.execute(query).scalar()

    return run_id


def finish_run(
    run_id,
    end_time,
    status,
    batches_seen,
    rows_inserted,
    rows_updated,
    rows_rejected,
    error_message=None
):

    query = text("""
        UPDATE etl_run_log
        SET
            finished_at = :finished_at,
            status = :status,
            batches_seen = :batches_seen,
            rows_inserted = :rows_inserted,
            rows_updated = :rows_updated,
            rows_rejected = :rows_rejected,
            error_message = :error_message
        WHERE run_id = :run_id;
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "run_id": run_id,
                "finished_at": end_time,
                "status": status,
                "batches_seen": batches_seen,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_rejected": rows_rejected,
                "error_message": error_message
            }
        )


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
    rows_rejected=0,
    status="FAILED"
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
            :status,
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
                "status": status,
                "batches_seen": batches_seen,
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "rows_rejected": rows_rejected,
                "error_message": str(error_message)
            }
        )