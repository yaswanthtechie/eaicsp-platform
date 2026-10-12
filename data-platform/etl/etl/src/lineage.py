from sqlalchemy import text

from config_loader import load_pipeline_config
from database import get_engine


def _row_for_id(connection, table, row_id):
    return connection.execute(
        text(f"SELECT * FROM {table} WHERE id = :row_id"),
        {"row_id": row_id},
    ).mappings().first()


def _lineage_keys(source):
    if not source.lineage_keys:
        raise ValueError(f"Source '{source.name}' has no lineage_keys configured")
    return list(source.lineage_keys)


def _matching_upstream_rows(connection, upstream, event_date, key_values):
    upstream_keys = _lineage_keys(upstream)
    if len(upstream_keys) != len(key_values):
        raise ValueError(
            f"lineage_keys length mismatch for '{upstream.name}': "
            f"{upstream_keys} vs {len(key_values)} values"
        )

    where = [f"{upstream.date_column} = :event_date"]
    params = {"event_date": event_date}
    for i, (column, value) in enumerate(zip(upstream_keys, key_values)):
        where.append(f"{column} = :key_{i}")
        params[f"key_{i}"] = value

    sql = f"SELECT * FROM {upstream.table} WHERE {' AND '.join(where)} ORDER BY id"
    return connection.execute(text(sql), params).mappings().all()


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
            key_values = [current.get(col) for col in _lineage_keys(current_config)]

            if event_date is None or any(v is None for v in key_values):
                break

            upstream_rows = _matching_upstream_rows(
                connection, upstream, event_date, key_values
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
