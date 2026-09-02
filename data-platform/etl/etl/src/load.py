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




def source_file_priority(file_path):
    """Return a deterministic file precedence tuple from the filename.

    R5 rule: explicit version/timestamp metadata in the filename is the
    precedence signal; filesystem mtime is deliberately not used because it
    can change during copies, extraction, archival, or git checkout.

    Supported forms include __v2 / _v2 and YYYY-MM-DD_HHMMSS or YYYYMMDDHHMMSS.
    A correction marker is a documented tie-breaker for same-version files.
    """
    import re
    name = file_path.name
    version_match = re.search(r"(?:^|[_-])(?:v|version)[_-]?(\d+)(?:\D|$)", name, re.I)
    version = int(version_match.group(1)) if version_match else 0
    ts_match = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})(?:[T_-]?(\d{2})(?:[_:-]?(\d{2})(?:[_:-]?(\d{2}))?)?)?", name)
    timestamp = tuple(int(x or 0) for x in ts_match.groups()) if ts_match else (0, 0, 0, 0, 0, 0)
    correction = 1 if re.search(r"(?:^|[_-])(correction|corrected|fix)(?:[_-]|\.)", name, re.I) else 0
    return version, timestamp, correction, name

def _dedupe_records(records, conflict_keys, priority_key=None):
    """Dedupe a list of record dicts by conflict_keys.

    Without priority_key: keeps the *last* occurrence of each key - "last
    write wins" by list order, same semantics the row-by-row loader gets for
    free by executing one statement per row in order. This is the original
    behavior, preserved as the default so existing callers/tests are
    unaffected.

    With priority_key: explicit precedence rule (R5 #1). Keeps whichever
    record has the highest value at record[priority_key] - e.g. a source
    file's modification time, so "latest file wins" regardless of what
    order extract_data() happened to glob/process the files in. Ties (equal
    priority) fall back to last-occurrence, matching the no-priority case.
    """

    deduped = {}
    priorities = {}

    for record in records:
        key = tuple(record[k] for k in conflict_keys)

        if priority_key is None:
            deduped[key] = record
            continue

        priority = record.get(priority_key, float("-inf"))

        if key not in deduped or priority >= priorities[key]:
            deduped[key] = record
            priorities[key] = priority

    return list(deduped.values())


def bulk_upsert(
    engine,
    table_name,
    columns,
    conflict_keys,
    records,
    history_copy_fn=None,
    chunk_size=5000,
    priority_key=None,
):
    """Generic bulk UPSERT: builds one multi-row
    INSERT ... VALUES (...), (...), ... ON CONFLICT DO UPDATE
    statement per chunk instead of one round-trip per row.

    `columns` must be every column present in each record dict, including
    conflict_keys. `history_copy_fn(connection, chunk)`, if given, runs
    before each chunk's upsert (used to preserve sales_fact_history).
    `priority_key`, if given, is an extra (non-column) key each record may
    carry - see `_dedupe_records()` - used to resolve competing updates to
    the same conflict-key row within a chunk by an explicit rule (e.g.
    "latest file wins") instead of accidental processing order.
    Returns (rows_inserted, rows_updated), counted via RETURNING (xmax=0),
    same semantics as load_data()'s row-by-row loop.
    """

    if not records:
        return 0, 0

    update_columns = [c for c in columns if c not in conflict_keys]

    rows_inserted = 0
    rows_updated = 0

    # Dedupe across *all* records before chunking, not per-chunk: two
    # competing files could easily land in different chunks, and each chunk
    # is its own SQL statement executed in order - if dedup only looked
    # within a chunk, a cross-chunk conflict would still resolve by
    # accidental chunk order instead of the explicit priority_key rule.
    records = _dedupe_records(records, conflict_keys, priority_key=priority_key)

    with engine.begin() as connection:

        for i in range(0, len(records), chunk_size):

            chunk = records[i:i + chunk_size]

            # Postgres still rejects a multi-row INSERT...ON CONFLICT if the
            # same conflict-key combination appears twice in one statement -
            # the dedupe above already guarantees that can't happen, so this
            # chunk is safe to insert as one multi-row statement.

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
    single bulk_upsert() call (chunked internally).

    R5 #1 - conflict resolution: if two files in the same run both touch the
    same (conflict_keys) row with different values (e.g. an original file
    plus a same-day correction), the winner is decided by an explicit rule -
    latest file wins, by explicit filename version/timestamp - not by whichever
    file happened to be processed last. Each record carries its source
    file's mtime as "_conflict_priority", consumed by bulk_upsert()'s
    priority_key and never sent to the database (it isn't in `all_columns`).
    """

    engine = get_engine()

    business_columns = list(source_config.columns.keys())
    all_columns = business_columns + ["source_batch", "run_id", "pipeline_version"]

    records = []
    for batch in validated_batches:
        file_path = batch["file_path"]
        source_batch = file_path.name
        file_priority = source_file_priority(file_path)

        for record in batch["data"].to_dict(orient="records"):
            record["source_batch"] = source_batch
            record["run_id"] = run_id
            record["pipeline_version"] = PIPELINE_VERSION
            record["_conflict_priority"] = file_priority
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
        priority_key="_conflict_priority",
    )

    elapsed = time.perf_counter() - start

    logger.info(
        f"[{source_config.name}] Bulk-loaded {len(records)} rows "
        f"in {elapsed:.3f} sec "
        f"(inserted={rows_inserted}, updated={rows_updated})"
    )

    return rows_inserted, rows_updated