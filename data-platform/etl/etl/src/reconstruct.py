"""
R5 #3: Point-in-time reconstruction.

Given a run_id, answer "what did sales_fact look like right after that
specific run finished?" using loaded_at/updated_at (on sales_fact) and
valid_from (on sales_fact_history).

How the history mechanism works (see load.py's _bulk_copy_sales_history):
before every UPSERT that would overwrite a sales_fact row, the row's
*current* values are copied into sales_fact_history with
valid_from = that row's updated_at (i.e. "this version was valid starting
at valid_from"). So for any (date, sku_id, warehouse_id) key, its full
version history is:

    sales_fact_history rows (old versions, each tagged with when it BECAME
    valid)  +  the current sales_fact row itself (whose own updated_at is
    when it became valid).

To reconstruct the state "as of" a timestamp T: for each key, take whichever
version has the latest valid_from/updated_at that is still <= T. A key with
no version at all <= T simply didn't exist yet at T, and is correctly
excluded.

This module is read-only - it never writes to sales_fact or
sales_fact_history.
"""

from sqlalchemy import text

from database import get_engine


_AS_OF_QUERY = text("""
    WITH versions AS (
        SELECT
            sales_fact_id AS id, date, sku_id, warehouse_id,
            quantity_sold, unit_price, source_batch, run_id,
            pipeline_version, valid_from AS effective_at
        FROM sales_fact_history

        UNION ALL

        SELECT
            id, date, sku_id, warehouse_id,
            quantity_sold, unit_price, source_batch, run_id,
            pipeline_version, updated_at AS effective_at
        FROM sales_fact
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY date, sku_id, warehouse_id
                ORDER BY effective_at DESC
            ) AS rn
        FROM versions
        WHERE effective_at <= :as_of
    )
    SELECT id, date, sku_id, warehouse_id, quantity_sold, unit_price,
           source_batch, run_id, pipeline_version, effective_at
    FROM ranked
    WHERE rn = 1
    ORDER BY date, sku_id, warehouse_id;
""")


def get_run_finished_at(run_id, engine=None):
    """Looks up when a run finished, from etl_run_log. Returns None if the
    run doesn't exist or hasn't finished yet - reconstructing "as of" an
    unfinished run isn't well-defined."""

    engine = engine or get_engine()

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT finished_at FROM etl_run_log WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).fetchone()

    if row is None:
        return None

    return row.finished_at


def sales_fact_as_of_run(run_id, engine=None):
    """Read-only reconstruction of sales_fact as it looked immediately after
    `run_id` finished. Returns a list of row dicts (empty list if the table
    had no rows yet at that point, or the run isn't found/finished).

    This is a single point-in-time snapshot query, safe to run against a
    live table at any time - it never mutates sales_fact or
    sales_fact_history, and it only reads rows whose effective timestamp is
    <= the run's finished_at, so it's unaffected by anything loaded after
    that run.
    """

    engine = engine or get_engine()

    as_of = get_run_finished_at(run_id, engine=engine)

    if as_of is None:
        return []

    with engine.connect() as connection:
        result = connection.execute(_AS_OF_QUERY, {"as_of": as_of})
        rows = [dict(row._mapping) for row in result]

    return rows
