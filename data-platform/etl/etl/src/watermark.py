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
        UPDATE etl_watermark
        SET last_processed_date = :last_processed_date
        WHERE pipeline_name = 'sales_etl';
    """)

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "last_processed_date": last_processed_date
            }
        )