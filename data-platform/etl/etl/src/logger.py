from sqlalchemy import text
from database import get_engine


def create_run(pipeline_name="sales_etl", connection=None):

    query = text("""
        INSERT INTO etl_run_log
        (
            pipeline_name,
            started_at,
            status
        )
        VALUES
        (
            :pipeline_name,
            NOW(),
            'RUNNING'
        )
        RETURNING run_id;
    """)

    engine = get_engine()
    params = {"pipeline_name": pipeline_name}
    if connection is not None:
        return connection.execute(query, params).scalar()
    with engine.begin() as conn:
        return conn.execute(query, params).scalar()


def finish_run(
    run_id,
    end_time,
    status,
    batches_seen,
    rows_inserted,
    rows_updated,
    rows_rejected,
    error_message=None,
    connection=None
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

    params = {
        "run_id": run_id,
        "finished_at": end_time,
        "status": status,
        "batches_seen": batches_seen,
        "rows_inserted": rows_inserted,
        "rows_updated": rows_updated,
        "rows_rejected": rows_rejected,
        "error_message": error_message
    }
    engine = get_engine()
    if connection is not None:
        connection.execute(query, params)
    else:
        with engine.begin() as conn:
            conn.execute(query, params)


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

    engine = get_engine()
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

    engine = get_engine()
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


def record_run_batch(run_id, source_name, batch_file, connection=None):
    """Persist the source files associated with a pipeline run for safe replay."""
    query = text("""
        INSERT INTO etl_run_batches (run_id, source_name, batch_file)
        VALUES (:run_id, :source_name, :batch_file)
        ON CONFLICT (run_id, source_name, batch_file) DO NOTHING
    """)
    params = {"run_id": run_id, "source_name": source_name, "batch_file": batch_file}
    engine = get_engine()
    if connection is not None:
        connection.execute(query, params)
    else:
        with engine.begin() as conn:
            conn.execute(query, params)


def mark_run_status(run_id, status, error_message=None, connection=None):
    query = text("""
        UPDATE etl_run_log
        SET status = :status, error_message = COALESCE(:error_message, error_message)
        WHERE run_id = :run_id
    """)
    params = {"run_id": run_id, "status": status, "error_message": error_message}
    engine = get_engine()
    if connection is not None:
        connection.execute(query, params)
    else:
        with engine.begin() as conn:
            conn.execute(query, params)
