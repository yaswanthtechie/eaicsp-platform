from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from config_loader import load_pipeline_config
from database import get_engine
from extract import extract_data
from data_contract import validate_schema_against, validate_no_unexpected_columns
from quality_gate import quality_gate_generic
from transform import transform_data_generic
from load import load_data_bulk_generic
from logger import create_run, finish_run, mark_run_status, record_run_batch


def _restore_run_state(connection, run_id, started_at, table_name, history_table):
    rows = connection.execute(text(f"""
        SELECT date, sku_id, warehouse_id FROM {table_name} WHERE run_id = :run_id
    """), {"run_id": run_id}).fetchall()
    restored = deleted = 0
    for row in rows:
        previous = connection.execute(text(f"""
            SELECT sales_fact_id, date, sku_id, warehouse_id, quantity_sold, unit_price,
                   source_batch, run_id, pipeline_version, valid_from
            FROM {history_table}
            WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh
              AND run_id <> :run_id AND valid_from <= :started_at
            ORDER BY valid_from DESC LIMIT 1
        """), {"date": row.date, "sku": row.sku_id, "wh": row.warehouse_id,
              "run_id": run_id, "started_at": started_at}).fetchone()
        if previous:
            connection.execute(text(f"""
                UPDATE {table_name} SET quantity_sold=:quantity_sold, unit_price=:unit_price,
                    source_batch=:source_batch, run_id=:prev_run_id, pipeline_version=:version,
                    updated_at=:valid_from
                WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh AND run_id=:run_id
            """), {"quantity_sold": previous.quantity_sold, "unit_price": previous.unit_price,
                 "source_batch": previous.source_batch, "prev_run_id": previous.run_id,
                 "version": previous.pipeline_version, "valid_from": previous.valid_from,
                 "date": row.date, "sku": row.sku_id, "wh": row.warehouse_id, "run_id": run_id})
            restored += 1
        else:
            connection.execute(text(f"""
                DELETE FROM {table_name}
                WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh AND run_id=:run_id
            """), {"date": row.date, "sku": row.sku_id, "wh": row.warehouse_id, "run_id": run_id})
            deleted += 1
    return restored, deleted


def replay_run(run_id, source_name="sales", config_path=None):
    """Safely replay a recorded sales run.

    All source files are verified and the replacement data is validated before
    the database is touched. Revert + reload + run bookkeeping happen in one
    database transaction, so a reload failure rolls the revert back. Replay
    runs use a separate pipeline_name and therefore do not block retrying the
    original run. Non-sales sources are rejected until restore logic is
    generalized for their schemas/history tables.
    """
    config = load_pipeline_config(config_path)
    source = config.get_source(source_name)

    if not source.history_table:
        raise ValueError(
            f"Replay is only supported for sources with a history_table "
            f"(currently: sales). '{source.name}' has none."
        )
    engine = get_engine()

    # Read metadata and verify every recorded file before touching the DB.
    with engine.connect() as conn:
        run = conn.execute(text(
            "SELECT run_id, started_at, status FROM etl_run_log WHERE run_id=:run_id"
        ), {"run_id": run_id}).fetchone()
        if not run:
            raise ValueError(f"Unknown run_id: {run_id}")
        if run.status == "RUNNING":
            raise ValueError("Cannot replay a running run")
        latest = conn.execute(text("""
            SELECT run_id FROM etl_run_log
            WHERE pipeline_name='sales_etl'
            ORDER BY run_id DESC LIMIT 1
        """)).scalar()
        if latest != run_id:
            raise ValueError(
                "Safe replay only permits the latest normal run; "
                "later normal runs must not be overwritten"
            )
        batch_names = [r.batch_file for r in conn.execute(text("""
            SELECT batch_file FROM etl_run_batches
            WHERE run_id=:run_id AND source_name=:source
            ORDER BY batch_file
        """), {"run_id": run_id, "source": source_name}).fetchall()]

    if not batch_names:
        raise ValueError(f"No recorded source batches found for run_id={run_id}")

    source_path = Path(source.path)
    available = {p.name: p for p in source_path.glob("*.csv")}
    missing = [name for name in batch_names if name not in available]
    if missing:
        raise FileNotFoundError(
            "Replay aborted before database changes; recorded batch file(s) are missing: "
            + ", ".join(missing)
        )

    extracted = extract_data(source_path=source.path, date_column=source.date_column)
    by_name = {b["file_path"].name: b for b in extracted}
    selected = [by_name[name] for name in batch_names]
    for batch in selected:
        validate_schema_against(batch["data"], source.columns)
        validate_no_unexpected_columns(batch["data"], source.columns)

    approved = quality_gate_generic(selected, source)
    if len(approved) != len(selected):
        raise ValueError(
            f"Replay aborted before database changes: quality gate approved "
            f"{len(approved)}/{len(selected)} recorded batches"
        )

    transformed = transform_data_generic([b["data"] for b in approved], source)
    for batch, df in zip(approved, transformed):
        batch["data"] = df

    new_run = None
    try:
        # One transaction: create replay run, revert, reload, and mark original.
        with engine.begin() as conn:
            new_run = create_run(pipeline_name="sales_etl_replay", connection=conn)
            for batch in approved:
                record_run_batch(new_run, source.name, batch["file_path"].name, connection=conn)

            restored, deleted = _restore_run_state(conn, run_id, run.started_at, source.table, source.history_table)
            inserted, updated = load_data_bulk_generic(
                approved, new_run, source, connection=conn
            )
            finish_run(
                new_run, datetime.now(), "SUCCESS", len(approved),
                inserted, updated, 0, connection=conn
            )
            mark_run_status(
                run_id, "REPLAYED",
                f"Reverted and replayed as run_id={new_run}",
                connection=conn,
            )

        return {
            "original_run_id": run_id,
            "replay_run_id": new_run,
            "restored": restored,
            "deleted": deleted,
            "inserted": inserted,
            "updated": updated,
        }
    except Exception as exc:
        # The transaction above rolls back the revert and replacement load.
        # Keep a separate failure record without changing the original run.
        try:
            failed_run = create_run(pipeline_name="sales_etl_replay")
            finish_run(failed_run, datetime.now(), "FAILED", 0, 0, 0, 0, error_message=str(exc))
        except Exception:
            pass
        raise
