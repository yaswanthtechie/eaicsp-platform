from pathlib import Path
from datetime import datetime

from sqlalchemy import text

from config_loader import load_pipeline_config
from database import get_engine
from extract import extract_data
from data_contract import validate_schema_against, validate_no_unexpected_columns
from quality_gate import quality_gate_generic
from transform import transform_data_generic
from load import load_data_bulk_generic
from logger import create_run, finish_run, mark_run_status, record_run_batch


def _restore_run_state(connection, run_id, started_at):
    rows = connection.execute(text("""
        SELECT date, sku_id, warehouse_id FROM sales_fact WHERE run_id = :run_id
    """), {"run_id": run_id}).fetchall()
    restored = deleted = 0
    for row in rows:
        previous = connection.execute(text("""
            SELECT sales_fact_id, date, sku_id, warehouse_id, quantity_sold, unit_price,
                   source_batch, run_id, pipeline_version, valid_from
            FROM sales_fact_history
            WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh
              AND run_id <> :run_id AND valid_from <= :started_at
            ORDER BY valid_from DESC LIMIT 1
        """), {"date": row.date, "sku": row.sku_id, "wh": row.warehouse_id,
              "run_id": run_id, "started_at": started_at}).fetchone()
        if previous:
            connection.execute(text("""
                UPDATE sales_fact SET quantity_sold=:quantity_sold, unit_price=:unit_price,
                    source_batch=:source_batch, run_id=:prev_run_id, pipeline_version=:version,
                    updated_at=:valid_from
                WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh AND run_id=:run_id
            """), {"quantity_sold":previous.quantity_sold,"unit_price":previous.unit_price,
                 "source_batch":previous.source_batch,"prev_run_id":previous.run_id,
                 "version":previous.pipeline_version,"valid_from":previous.valid_from,
                 "date":row.date,"sku":row.sku_id,"wh":row.warehouse_id,"run_id":run_id})
            restored += 1
        else:
            connection.execute(text("""
                DELETE FROM sales_fact WHERE date=:date AND sku_id=:sku AND warehouse_id=:wh AND run_id=:run_id
            """), {"date":row.date,"sku":row.sku_id,"wh":row.warehouse_id,"run_id":run_id})
            deleted += 1
    return restored, deleted


def replay_run(run_id, source_name="sales", config_path=None):
    config = load_pipeline_config(config_path)
    source = config.get_source(source_name)
    engine = get_engine()
    with engine.begin() as conn:
        run = conn.execute(text("SELECT run_id, started_at, status FROM etl_run_log WHERE run_id=:run_id"), {"run_id":run_id}).fetchone()
        if not run:
            raise ValueError(f"Unknown run_id: {run_id}")
        if run.status == "RUNNING":
            raise ValueError("Cannot replay a running run")
        latest = conn.execute(text("""
            SELECT run_id FROM etl_run_log WHERE pipeline_name='sales_etl'
            ORDER BY run_id DESC LIMIT 1
        """)).scalar()
        if latest != run_id:
            raise ValueError("Safe replay only permits the latest run; later runs must not be overwritten")
        batch_names = [r.batch_file for r in conn.execute(text("""
            SELECT batch_file FROM etl_run_batches WHERE run_id=:run_id AND source_name=:source
        """), {"run_id":run_id,"source":source_name}).fetchall()]

    with engine.begin() as conn:
        restored, deleted = _restore_run_state(conn, run_id, run.started_at)

    new_run = create_run()
    try:
        extracted = extract_data(source_path=source.path, date_column=source.date_column)
        extracted = [b for b in extracted if b["file_path"].name in set(batch_names)]
        for b in extracted:
            validate_schema_against(b["data"], source.columns)
            validate_no_unexpected_columns(b["data"], source.columns)
            record_run_batch(new_run, source.name, b["file_path"].name)
        approved = quality_gate_generic(extracted, source)
        transformed = transform_data_generic([b["data"] for b in approved], source)
        for b, df in zip(approved, transformed):
            b["data"] = df
        inserted, updated = load_data_bulk_generic(approved, new_run, source) if approved else (0,0)
        finish_run(new_run, datetime.now(), "SUCCESS", len(extracted), inserted, updated, 0)
        mark_run_status(run_id, "REPLAYED", "Reverted and replayed as run_id=%s" % new_run)
        return {"original_run_id":run_id,"replay_run_id":new_run,"restored":restored,"deleted":deleted,"inserted":inserted,"updated":updated}
    except Exception as exc:
        finish_run(new_run, datetime.now(), "FAILED", 0, 0, 0, 0, error_message=str(exc))
        raise
