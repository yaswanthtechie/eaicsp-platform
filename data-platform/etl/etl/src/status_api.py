from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from database import get_engine
from config_loader import load_pipeline_config

app = FastAPI(title="EAICSP Pipeline Status", version="1.1")


def _identifier(value, allowed):
    if value not in allowed or not value.replace("_", "").isalnum():
        raise ValueError(f"Invalid configured identifier: {value}")
    return value


@app.get("/pipeline/status")
def pipeline_status():
    try:
        engine = get_engine()
        config = load_pipeline_config()
        tables = {s.table for s in config.sources}
        pipeline_names = {"sales_etl", "sales_etl_replay"}
        with engine.connect() as conn:
            last_runs = [dict(r._mapping) for r in conn.execute(text("""
                SELECT DISTINCT ON (pipeline_name) run_id, pipeline_name, started_at, finished_at, status,
                       batches_seen, rows_inserted, rows_updated, rows_rejected
                FROM etl_run_log
                WHERE pipeline_name IN ('sales_etl', 'sales_etl_replay')
                ORDER BY pipeline_name, finished_at DESC NULLS LAST, run_id DESC
            """))]

            recent_runs = [dict(r._mapping) for r in conn.execute(text("""
                SELECT run_id, pipeline_name, started_at, finished_at, status,
                       batches_seen, rows_inserted, rows_updated, rows_rejected
                FROM etl_run_log
                ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC LIMIT 50
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
                ORDER BY source_name, created_at DESC, run_id DESC
            """))]

            row_counts = {}
            for table in tables:
                safe_table = _identifier(table, tables)
                row_counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM {safe_table}")).scalar()

        normal_runs = [r for r in last_runs if r["pipeline_name"] == "sales_etl"]
        critical_cutoff = datetime.now() - timedelta(hours=24)
        recent_critical = [
            a for a in alerts
            if str(a.get("severity", "")).upper() == "CRITICAL"
            and a.get("created_at") and a["created_at"] >= critical_cutoff
        ]
        watermark_by_name = {w["pipeline_name"]: w for w in watermarks}
        stale_watermarks = []
        for name in config.source_names():
            wm = watermark_by_name.get(name) or watermark_by_name.get("sales_etl")
            if not wm or not wm.get("last_processed_date"):
                stale_watermarks.append(name)

        last_normal_success = bool(normal_runs and normal_runs[0].get("status") == "SUCCESS")
        recon_by_source = {r["source_name"]: r for r in reconciliation}
        recon_healthy = all(
            recon_by_source.get(name, {}).get("status") == "PASS"
            for name in config.source_names()
        )
        healthy = last_normal_success and recon_healthy and not recent_critical and not stale_watermarks

        last_per_pipeline = {r["pipeline_name"]: r for r in last_runs if r["pipeline_name"] in pipeline_names}
        return {
            "healthy": healthy,
            "health_reasons": {
                "last_normal_run_success": last_normal_success,
                "recent_critical_alert": bool(recent_critical),
                "stale_or_missing_watermark": stale_watermarks,
                "reconciliation_all_pass": recon_healthy,
            },
            "last_run_per_pipeline": last_per_pipeline,
            "last_run": last_runs[0] if last_runs else None,
            "recent_runs": recent_runs,
            "row_counts": row_counts,
            "watermarks": watermarks,
            "recent_alerts": alerts,
            "reconciliation": reconciliation,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pipeline status unavailable: {exc}") from exc
