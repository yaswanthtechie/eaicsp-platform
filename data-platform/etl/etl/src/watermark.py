from datetime import date
from sqlalchemy import text
from database import get_engine


def get_watermark(pipeline_name="sales_etl"):
    query = text("""
        SELECT last_processed_date
        FROM etl_watermark
        WHERE pipeline_name = :pipeline_name;
    """)

    engine = get_engine()
    with engine.connect() as connection:
        result = connection.execute(query, {"pipeline_name": pipeline_name})
        row = result.fetchone()

        if row is None:
            return date(1900, 1, 1)

        return row[0]


def update_watermark(last_processed_date, pipeline_name="sales_etl"):
    query = text("""
        INSERT INTO etl_watermark (
            pipeline_name,
            last_processed_date
        )
        VALUES (
            :pipeline_name,
            :last_processed_date
        )
        ON CONFLICT (pipeline_name)
        DO UPDATE SET
            last_processed_date = EXCLUDED.last_processed_date,
            updated_at = NOW();
    """)

    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            query,
            {
                "pipeline_name": pipeline_name,
                "last_processed_date": last_processed_date
            }
        )
