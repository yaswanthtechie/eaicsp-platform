from sqlalchemy import text
from database import get_engine


def write_alert(
    pipeline,
    severity,
    message,
    batch_file=None,
    run_id=None,
):
    engine = get_engine()

    query = text("""
        INSERT INTO etl_alerts
        (
            pipeline,
            severity,
            message,
            batch_file,
            run_id
        )
        VALUES
        (
            :pipeline,
            :severity,
            :message,
            :batch_file,
            :run_id
        )
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "pipeline": pipeline,
                "severity": severity,
                "message": message,
                "batch_file": batch_file,
                "run_id": run_id,
            },
        )