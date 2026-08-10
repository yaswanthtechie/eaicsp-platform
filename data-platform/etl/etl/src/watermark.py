from datetime import date
from sqlalchemy import text
from database import get_engine
from alert_service import write_alert

engine = get_engine()


def get_watermark():

    try:
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

    except Exception as e:

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Failed to get watermark: {e}"
        )

        raise


def update_watermark(last_processed_date):

    try:
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

    except Exception as e:

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Failed to update watermark: {e}"
        )

        raise