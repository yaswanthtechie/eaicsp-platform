from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from database import get_engine
from config_loader import load_pipeline_config

app = FastAPI(title="EAICSP Pipeline Status", version="1.0")


def _identifier(value, allowed):
    if value not in allowed or not value.replace("_", "").isalnum():
        raise ValueError(f"Invalid configured identifier: {value}")
    return value


@app.get("/pipeline/status")
def pipeline_status():
    engine = get_engine()
    config = load_pipeline_config()
    tables = {s.table for s in config.sources}
    with engine.connect() as conn:
        last_runs = [dict(r._mapping) for r in conn.execute(text("""
            SELECT run_id, pipeline_name, started_at, finished_at, status,
                   batches_seen, rows_inserted, rows_updated, rows_rejected
            FROM etl_run_log
            ORDER BY finished_at DESC NULLS LAST LIMIT 50
        """))]

        watermarks = [dict(r._mapping) for r in conn.execute(text("""
            SELECT pipeline_name, last_processed_date, updated_at
            FROM etl_watermark ORDER BY pipeline_name
        """))]

        alerts = [dict(r._mapping) for r in conn.execute(text("""
            SELECT alert_id, pipeline, severity, message, batch_file, run_id, created_at
            FROM etl_alerts ORDER BY created_at DESC LIMIT 10
        """))]

        reconciliation = [dict(r._mapping) for r in conn.execute(text("""
            SELECT DISTINCT ON (source_name) source_name, run_id, status,
                   raw_rows, approved_rows, transformed_rows, landed_rows, created_at
            FROM etl_reconciliation_log
            ORDER BY source_name, created_at DESC
        """))]

        row_counts = {}
        for table in tables:
            safe_table = _identifier(table, tables)
            row_counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM {safe_table}")).scalar()

    last_per_pipeline = {}
    for run in last_runs:
        last_per_pipeline.setdefault(run["pipeline_name"], run)
    latest = last_runs[0] if last_runs else None
    healthy = bool(last_per_pipeline) and all(
        run.get("status") == "SUCCESS" for run in last_per_pipeline.values()
    ) and all(r["status"] == "PASS" for r in reconciliation)
    return {
        "healthy": healthy,
        "last_run_per_pipeline": last_per_pipeline,
        "last_run": latest,
        "recent_runs": last_runs,
        "row_counts": row_counts,
        "watermarks": watermarks,
        "recent_alerts": alerts,
        "reconciliation": reconciliation,
    }
