from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_clickhouse_sink_is_incremental_and_watermark_driven():
    source = (PROJECT_ROOT / "etl/src/clickhouse_sink.py").read_text()
    assert "get_watermark" in source
    assert "update_watermark" in source
    assert "ReplacingMergeTree" in source
    assert "FINAL" in source
    assert "clickhouse_" in source


def test_clickhouse_benchmark_refuses_fewer_than_one_million_rows():
    import subprocess, sys
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts/benchmark_postgres_clickhouse.py"), "--rows", "1000"],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "1,000,000" in (proc.stdout + proc.stderr)


def test_kafka_event_contract_and_outbox():
    source = (PROJECT_ROOT / "etl/src/kafka_events.py").read_text()
    assert '"event_id"' in source
    assert '"event_type"' in source
    assert '"event_version"' in source
    assert '"occurred_at"' in source
    assert '"producer"' in source
    assert '"payload"' in source
    assert "etl_event_outbox" in source
    assert "PENDING" in source
    assert "PUBLISHED" in source


def test_kafka_retry_dag_exists():
    dag = (PROJECT_ROOT / "dags/kafka_event_retry_dag.py").read_text()
    assert 'dag_id="etl_event_outbox_retry"' in dag
    assert "*/5 * * * *" in dag
    assert "retry_pending_events" in dag


def test_compose_contains_local_clickhouse_and_kafka():
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text()
    assert "clickhouse/clickhouse-server" in compose
    assert "apache/kafka" in compose
    assert "CLICKHOUSE_HOST" in compose
    assert "KAFKA_BOOTSTRAP_SERVERS" in compose
