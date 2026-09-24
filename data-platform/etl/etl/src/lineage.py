"""Cross-table, run-aware lineage traversal for the R9 ETL pipeline."""

from sqlalchemy import text

from config_loader import load_pipeline_config
from database import get_engine



def _row_for_id(connection, table, row_id):
    return connection.execute(
        text(f"SELECT * FROM {table} WHERE id = :row_id"),
        {"row_id": row_id},
    ).mappings().first()


def _matching_upstream_rows(connection, source, event_date, sku_id, warehouse_id):
    key_columns = source.lineage_keys

    sql = f"""
        SELECT *
        FROM {source.table}
        WHERE {source.date_column} = :event_date
          AND {key_columns[0]} = :sku_id
          AND {key_columns[1]} = :warehouse_id
        ORDER BY id
    """

    return connection.execute(
        text(sql),
        {
            "event_date": event_date,
            "sku_id": sku_id,
            "warehouse_id": warehouse_id,
        },
    ).mappings().all()


def trace_row_lineage(row_id, target_table, config=None, engine=None):
    """Trace a target row through every configured upstream table."""

    config = config or load_pipeline_config()
    engine = engine or get_engine()

    target_config = next(
        (s for s in config.sources if s.table == target_table),
        None,
    )

    if target_config is None:
        raise ValueError(f"Unknown configured target table '{target_table}'")

    with engine.connect() as connection:
        target = _row_for_id(connection, target_table, row_id)

        if target is None:
            return []

        lineage = [{
            "level": 0,
            "table": target_table,
            "row_id": target.get("id"),
            "run_id": target.get("run_id"),
            "source_batch": target.get("source_batch"),
            "role": "target",
        }]

        current = target
        current_config = target_config
        level = 1

        while current_config.depends_on:
            upstream = config.get_source(current_config.depends_on)
            event_date = current.get(current_config.date_column)

            key_columns = current_config.lineage_keys

            upstream_rows = _matching_upstream_rows(
                connection,
                upstream,
                event_date,
                current.get(key_columns[0]),
                current.get(key_columns[1]),
            )

            for row in upstream_rows:
                lineage.append({
                    "level": level,
                    "table": upstream.table,
                    "row_id": row.get("id"),
                    "run_id": row.get("run_id"),
                    "source_batch": row.get("source_batch"),
                    "role": "upstream",
                })

            if not upstream_rows:
                break

            current = upstream_rows[0]
            current_config = upstream
            level += 1

    return lineage
