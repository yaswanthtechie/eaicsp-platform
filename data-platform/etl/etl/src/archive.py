from datetime import date, timedelta

from sqlalchemy import text

from database import get_engine
from logging_config import logger
from alert_service import write_alert
from etl.src.config_loader import load_pipeline_config


def archive_old_sales(cutoff_days=730, run_id=None):
    engine = get_engine()
    config = load_pipeline_config()
    source = config.get_source("sales")
    live_table = source.table
    archive_table = source.archive_table
    cutoff_date = date.today() - timedelta(days=cutoff_days)

    archive_query = text(f"""
        INSERT INTO {archive_table} (
            id, date, sku_id, warehouse_id, quantity_sold, unit_price,
            source_batch, run_id, pipeline_version, loaded_at, updated_at
        )
        SELECT
            id, date, sku_id, warehouse_id, quantity_sold, unit_price,
            source_batch, run_id, pipeline_version, loaded_at, updated_at
        FROM {live_table}
        WHERE date < :cutoff_date
        ON CONFLICT (id) DO NOTHING;
    """)

    delete_query = text(f"""
        DELETE FROM {live_table}
        WHERE date < :cutoff_date;
    """)

    try:
        with engine.begin() as connection:
            archived_result = connection.execute(
                archive_query, {"cutoff_date": cutoff_date}
            )
            archived_count = archived_result.rowcount

            deleted_result = connection.execute(
                delete_query, {"cutoff_date": cutoff_date}
            )
            deleted_count = deleted_result.rowcount

        return archived_count, deleted_count

    except Exception as exc:
        logger.exception("Archive failed for run %s", run_id)
        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Archive failed for run {run_id}: {exc}",
            run_id=run_id,
        )
        raise
