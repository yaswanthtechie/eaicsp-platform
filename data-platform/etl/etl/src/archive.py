"""
R4 #4: archival.

Rows in the live sales table older than a configurable cutoff move to the
archive table instead of the live table growing forever. Both table names
come from the `archive:` block of the active environment's config
(sales_fact / staging_sales_fact / prod_sales_fact and their _archive twins).

Idempotency: within one transaction we (1) copy old rows into the archive
table with ON CONFLICT (id) DO NOTHING, then (2) delete those same rows from
the live table. After a successful run there is nothing left in the live
table older than the cutoff, so running archive_old_sales() again simply
finds zero matching rows and does nothing - it does not re-archive or
duplicate anything. The ON CONFLICT guard only matters if a previous run
crashed between steps 1 and 2 (archived but not yet deleted); the run after
that will insert 0 new archive rows (conflict) and pick up the leftover
deletes.
"""

from datetime import date, timedelta

from sqlalchemy import text

from database import get_engine
from logging_config import logger
from alert_service import write_alert
from config_loader import load_pipeline_config


def archive_old_sales(cutoff_days=730, run_id=None, config=None):
    engine = get_engine()
    config = config or load_pipeline_config()

    live_table = config.archive.table
    archive_table = config.archive.archive_table
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

        logger.info(
            f"Archive: env={config.environment} "
            f"{live_table} -> {archive_table} cutoff={cutoff_date} "
            f"archived={archived_count} deleted_from_live={deleted_count}"
        )

        return {
            "cutoff_date": cutoff_date,
            "live_table": live_table,
            "archive_table": archive_table,
            "archived_count": archived_count,
            "deleted_count": deleted_count,
        }

    except Exception as exc:
        logger.exception("Archive failed for run %s", run_id)
        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=f"Archive failed for run {run_id} "
                    f"({live_table} -> {archive_table}): {exc}",
            run_id=run_id,
        )
        raise
