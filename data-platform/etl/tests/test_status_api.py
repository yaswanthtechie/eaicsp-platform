from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_pipeline_status_returns_health_payload(monkeypatch):
    import etl.src.status_api as status_api

    class Result:
        def __init__(self, rows=()): self._rows = list(rows)
        def __iter__(self): return iter(self._rows)
        def fetchall(self): return self._rows
        def fetchone(self): return self._rows[0] if self._rows else None
        def scalar(self): return self._rows[0][0] if self._rows else None

    class Row:
        def __init__(self, **values): self._mapping = values

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, query, params=None):
            sql = str(query)
            if "DISTINCT ON (pipeline_name)" in sql:
                return Result([Row(run_id=1, pipeline_name="sales_etl", started_at=None, finished_at=None, status="SUCCESS", batches_seen=1, rows_inserted=2, rows_updated=0, rows_rejected=0)])
            if "LIMIT 50" in sql and "etl_run_log" in sql:
                return Result([])
            if "etl_watermark" in sql:
                return Result([Row(pipeline_name="sales_etl", last_processed_date="2026-09-15", updated_at=None)])
            if "etl_alerts" in sql:
                return Result([])
            if "etl_reconciliation_log" in sql:
                return Result([
                    Row(source_name="sales", run_id=1, status="PASS", raw_rows=2, approved_rows=2, transformed_rows=2, landed_rows=2, created_at=None),
                    Row(source_name="inventory", run_id=1, status="PASS", raw_rows=2, approved_rows=2, transformed_rows=2, landed_rows=2, created_at=None),
                    Row(source_name="shipments", run_id=1, status="PASS", raw_rows=2, approved_rows=2, transformed_rows=2, landed_rows=2, created_at=None),
                ])
            if "SELECT COUNT(*)" in sql:
                return Result([(2,)])
            raise AssertionError(sql)

    class Engine:
        def connect(self): return Conn()

    config = SimpleNamespace(
        sources=[SimpleNamespace(name="sales", table="sales_fact"), SimpleNamespace(name="inventory", table="inventory_snapshot"), SimpleNamespace(name="shipments", table="shipments_fact")],
        source_names=lambda: ["sales", "inventory", "shipments"],
    )
    engine = Engine()
    monkeypatch.setattr(status_api, "get_engine", lambda: engine)
    monkeypatch.setattr(status_api, "load_pipeline_config", lambda: config)

    response = TestClient(status_api.app).get("/pipeline/status")
    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["last_run_per_pipeline"]["sales_etl"]["status"] == "SUCCESS"
    assert set(body["row_counts"]) == {"sales_fact", "inventory_snapshot", "shipments_fact"}


def test_pipeline_status_returns_503_on_database_error(monkeypatch):
    import etl.src.status_api as status_api
    monkeypatch.setattr(status_api, "get_engine", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    response = TestClient(status_api.app).get("/pipeline/status")
    assert response.status_code == 503
    assert "Pipeline status unavailable" in response.json()["detail"]
