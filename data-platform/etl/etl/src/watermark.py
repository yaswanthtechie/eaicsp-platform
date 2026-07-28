from datetime import date
from sqlalchemy import text
from database import get_engine

engine = get_engine()


def get_watermark():
    query = text("""
        SELECT last_processed_date
        FROM etl_watermark
        WHERE pipeline_name = 'sales_etl';
    """)

    with engine.connect() as connection:
        result = connection.execute(query)
        row = result.fetchone()

        if row is None:
            return date(1900, 1, 1)

        return row[0]


def update_watermark(last_processed_date):
    query = text("""
        INSERT INTO etl_watermark (
            pipeline_name,
            last_processed_date
        )
        VALUES (
            'sales_etl',
            :last_processed_date
        )
        ON CONFLICT (pipeline_name)
        DO UPDATE SET
            last_processed_date = EXCLUDED.last_processed_date,
            updated_at = NOW();
    """)

    with engine.begin() as connection:
        connection.execute(
            query,
            {
                "last_processed_date": last_processed_date
            }
        )