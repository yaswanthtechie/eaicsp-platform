from sqlalchemy import text
from database import get_engine
from alert_service import write_alert
from logging_config import logger
import time


PIPELINE_VERSION = "1.0.0"


def load_data(validated_data_frames, run_id):

    engine = get_engine()

    upsert_query = text("""
        INSERT INTO sales_fact (
            date,
            sku_id,
            warehouse_id,
            quantity_sold,
            unit_price,
            source_batch,
            run_id,
            pipeline_version
        )
        VALUES (
            :date,
            :sku_id,
            :warehouse_id,
            :quantity_sold,
            :unit_price,
            :source_batch,
            :run_id,
            :pipeline_version
        )
        ON CONFLICT (date, sku_id, warehouse_id)
        DO UPDATE SET
            quantity_sold = EXCLUDED.quantity_sold,
            unit_price = EXCLUDED.unit_price,
            source_batch = EXCLUDED.source_batch,
            run_id = EXCLUDED.run_id,
            pipeline_version = EXCLUDED.pipeline_version,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted;
    """)

    history_query = text("""
        INSERT INTO sales_fact_history
        (
            sales_fact_id,
            date,
            sku_id,
            warehouse_id,
            quantity_sold,
            unit_price,
            source_batch,
            run_id,
            pipeline_version,
            valid_from
        )
        SELECT
            id,
            date,
            sku_id,
            warehouse_id,
            quantity_sold,
            unit_price,
            source_batch,
            run_id,
            pipeline_version,
            updated_at
        FROM sales_fact
        WHERE
            date = :date
            AND sku_id = :sku_id
            AND warehouse_id = :warehouse_id
            AND (
                quantity_sold IS DISTINCT FROM :quantity_sold
                OR unit_price IS DISTINCT FROM :unit_price
            );
    """)

    rows_inserted = 0
    rows_updated = 0

    batch_size = 100

    try:

        with engine.begin() as connection:

            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": 4815162342},
            )

            for batch in validated_data_frames:

                df = batch["data"]

                source_batch = batch["file_path"].name

                records = df.to_dict(orient="records")

                i = 0

                while i < len(records):

                    batch_records = records[i:i + batch_size]

                    start = time.perf_counter()

                    for record in batch_records:

                        record["source_batch"] = source_batch
                        record["run_id"] = run_id
                        record["pipeline_version"] = PIPELINE_VERSION

                        connection.execute(
                            history_query,
                            record
                        )

                        result = connection.execute(
                            upsert_query,
                            record
                        )

                        row = result.fetchone()

                        if row.inserted:
                            rows_inserted += 1
                        else:
                            rows_updated += 1

                    i += len(batch_records)

                    elapsed = time.perf_counter() - start

                    logger.info(
                        f"Loaded {len(batch_records)} rows "
                        f"in {elapsed:.3f} sec "
                        f"(batch_size={batch_size})"
                    )

                    if elapsed < 0.2 and batch_size < 1000:

                        batch_size *= 2

                        logger.info(
                            f"Increasing batch size to {batch_size}"
                        )

                    elif elapsed > 1.0 and batch_size > 50:

                        batch_size //= 2

                        logger.info(
                            f"Reducing batch size to {batch_size}"
                        )

        print(
            f"Data loaded successfully! "
            f"Inserted: {rows_inserted}, Updated: {rows_updated}"
        )

        return rows_inserted, rows_updated

    except Exception as e:

        write_alert(
            pipeline="sales_etl",
            severity="CRITICAL",
            message=str(e)
        )

        raise