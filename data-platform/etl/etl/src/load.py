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
            AND warehouse_id = :warehouse_id;
    """)

    rows_inserted = 0
    rows_updated = 0

    batch_size = 100

    try:

        with engine.begin() as connection:

            for batch in validated_data_frames:

                df = batch["data"]

                source_batch = batch["file_path"].name

                records = df.to_dict(orient="records")

                for i in range(0, len(records), batch_size):

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


# ---------------------------------------------------------------------------
# R4: generic bulk upsert.
#
# load_data() above does one INSERT + one history INSERT per row - fine for
# a handful of files a day, but doesn't scale (see
# scripts/benchmark_bulk_upsert.py for the measured before/after). This does
# the same upsert with a single multi-row INSERT ... ON CONFLICT statement
# per chunk, still returning per-row inserted/updated counts via the same
# (xmax = 0) trick, and still capturing history for sales_fact.
# ---------------------------------------------------------------------------

def _bulk_copy_sales_history(connection, chunk):
    """Bulk equivalent of load_data()'s per-row history_query: copy any
    existing sales_fact rows matching this chunk's keys into
    sales_fact_history before they get overwritten by the upsert below."""

    key_values_clauses = []
    params = {}

    for row_idx, record in enumerate(chunk):
        placeholders = []
        for col in ("date", "sku_id", "warehouse_id"):
            key = f"k_{col}_{row_idx}"
            placeholders.append(f":{key}")
            params[key] = record[col]
        key_values_clauses.append(f"({', '.join(placeholders)})")

    sql = f"""
        INSERT INTO sales_fact_history (
            sales_fact_id, date, sku_id, warehouse_id, quantity_sold,
            unit_price, source_batch, run_id, pipeline_version, valid_from
        )
        SELECT
            id, date, sku_id, warehouse_id, quantity_sold,
            unit_price, source_batch, run_id, pipeline_version, updated_at
        FROM sales_fact
        WHERE (date, sku_id, warehouse_id) IN ({", ".join(key_values_clauses)});
    """

    connection.execute(text(sql), params)


def _dedupe_records(records, conflict_keys):
    """Dedupe a list of record dicts by conflict_keys, keeping the *last*
    occurrence of each key - same "last write wins" semantics the row-by-row
    loader gets for free by executing one statement per row in order.
    Pure function, no DB dependency, so it's directly unit-testable."""

    deduped = {}
    for record in records:
        key = tuple(record[k] for k in conflict_keys)
        deduped[key] = record
    return list(deduped.values())


def bulk_upsert(
    engine,
    table_name,
    columns,
    conflict_keys,
    records,
    history_copy_fn=None,
    chunk_size=5000,
):
    """Generic bulk UPSERT: builds one multi-row
    INSERT ... VALUES (...), (...), ... ON CONFLICT DO UPDATE
    statement per chunk instead of one round-trip per row.

    `columns` must be every column present in each record dict, including
    conflict_keys. `history_copy_fn(connection, chunk)`, if given, runs
    before each chunk's upsert (used to preserve sales_fact_history).
    Returns (rows_inserted, rows_updated), counted via RETURNING (xmax=0),
    same semantics as load_data()'s row-by-row loop.
    """

    if not records:
        return 0, 0

    update_columns = [c for c in columns if c not in conflict_keys]

    rows_inserted = 0
    rows_updated = 0

    with engine.begin() as connection:

        for i in range(0, len(records), chunk_size):

            chunk = records[i:i + chunk_size]

            # Postgres rejects a multi-row INSERT...ON CONFLICT if the same
            # conflict-key combination appears twice in one statement. The
            # old row-by-row loader tolerated this naturally (each row is
            # its own statement, last write wins); preserve that semantics
            # here by deduping within the chunk, keeping the last occurrence.
            chunk = _dedupe_records(chunk, conflict_keys)

            if history_copy_fn:
                history_copy_fn(connection, chunk)

            values_clauses = []
            params = {}

            for row_idx, record in enumerate(chunk):
                placeholders = []
                for col in columns:
                    key = f"{col}_{row_idx}"
                    placeholders.append(f":{key}")
                    params[key] = record[col]
                values_clauses.append(f"({', '.join(placeholders)})")

            set_clause = ", ".join(
                f"{col} = EXCLUDED.{col}" for col in update_columns
            )
            set_clause += ", updated_at = NOW()"

            sql = f"""
                INSERT INTO {table_name} ({", ".join(columns)})
                VALUES {", ".join(values_clauses)}
                ON CONFLICT ({", ".join(conflict_keys)})
                DO UPDATE SET {set_clause}
                RETURNING (xmax = 0) AS inserted;
            """

            result = connection.execute(text(sql), params)

            for row in result:
                if row.inserted:
                    rows_inserted += 1
                else:
                    rows_updated += 1

    return rows_inserted, rows_updated


def load_data_bulk_generic(validated_batches, run_id, source_config):
    """Config-driven bulk loader used by the generic pipeline engine.
    Flattens all batches for this source into one record list and does a
    single bulk_upsert() call (chunked internally)."""

    engine = get_engine()

    business_columns = list(source_config.columns.keys())
    all_columns = business_columns + ["source_batch", "run_id", "pipeline_version"]

    records = []
    for batch in validated_batches:
        source_batch = batch["file_path"].name
        for record in batch["data"].to_dict(orient="records"):
            record["source_batch"] = source_batch
            record["run_id"] = run_id
            record["pipeline_version"] = PIPELINE_VERSION
            records.append(record)

    history_copy_fn = (
        _bulk_copy_sales_history if source_config.history_table else None
    )

    start = time.perf_counter()

    rows_inserted, rows_updated = bulk_upsert(
        engine=engine,
        table_name=source_config.table,
        columns=all_columns,
        conflict_keys=source_config.conflict_keys,
        records=records,
        history_copy_fn=history_copy_fn,
    )

    elapsed = time.perf_counter() - start

    logger.info(
        f"[{source_config.name}] Bulk-loaded {len(records)} rows "
        f"in {elapsed:.3f} sec "
        f"(inserted={rows_inserted}, updated={rows_updated})"
    )

    return rows_inserted, rows_updated