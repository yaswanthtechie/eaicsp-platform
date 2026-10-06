"""Integration tests: need real containers. Run with `pytest -m integration`.

Each test skips itself (instead of failing) when its service is unreachable, so
`pytest` on a clean machine stays green. Set DB_*, KAFKA_BOOTSTRAP_SERVERS,
CLICKHOUSE_HOST/PORT to point at your local containers.
"""
import os
import socket
import uuid

import pytest

pytestmark = pytest.mark.integration


def _reachable(host, port):
    try:
        socket.create_connection((host, int(port)), timeout=2).close()
        return True
    except OSError:
        return False


def _kafka_addr():
    # Tests run on the HOST, so use Kafka's EXTERNAL listener.
    first = os.getenv("KAFKA_HOST_BOOTSTRAP", "localhost:9094").split(",")[0]
    host, _, port = first.partition(":")
    return host, port or "9094"


@pytest.fixture
def real_postgres():
    host, port = os.getenv("DB_HOST", "127.0.0.1"), os.getenv("DB_PORT", "5432")
    if not (os.getenv("DB_PASSWORD") is not None and _reachable(host, port)):
        pytest.skip("PostgreSQL not reachable / DB_* not set")
    import kafka_events as ke
    from sqlalchemy import text
    ke.ensure_outbox()
    yield ke
    with ke.get_engine().begin() as c:
        c.execute(text("DELETE FROM etl_event_outbox WHERE payload->>'it_marker' = 'r12-13-it'"))


def test_outbox_on_real_postgres_survives_kafka_being_down(real_postgres, monkeypatch):
    ke = real_postgres
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:1")   # nothing listens here
    monkeypatch.setenv("KAFKA_PUBLISH_TIMEOUT_S", "2")

    res = ke.queue_and_publish("data.pipeline.completed", 1, {"it_marker": "r12-13-it"})

    assert res["published"] is False and res["persisted"] is True
    from sqlalchemy import text
    with ke.get_engine().connect() as c:
        row = c.execute(text("SELECT status, attempts, payload FROM etl_event_outbox WHERE event_id=:i"),
                        {"i": res["event_id"]}).one()
    assert row.status == "PENDING" and row.attempts == 1
    assert row.payload["it_marker"] == "r12-13-it"          # JSONB round-trips as a dict


def test_real_kafka_publish_and_consume_roundtrip(real_postgres, monkeypatch):
    host, port = _kafka_addr()
    if not _reachable(host, port):
        pytest.skip("Kafka not reachable")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", f"{host}:{port}")
    from kafka import KafkaConsumer
    ke = real_postgres
    marker = str(uuid.uuid4())
    consumer = KafkaConsumer("data.pipeline.completed", bootstrap_servers=f"{host}:{port}",
                             auto_offset_reset="latest", consumer_timeout_ms=15000,
                             group_id=f"it-{marker}", api_version=(3,9))
    consumer.poll(timeout_ms=3000)                      # join group / get assignment
    res = ke.queue_and_publish("data.pipeline.completed", 1, {"it_marker": "r12-13-it", "m": marker})
    assert res["published"] is True
    import json
    got = [json.loads(m.value) for m in consumer]
    consumer.close()
    match = [e for e in got if e["event_id"] == res["event_id"]]
    assert match and match[0]["event_version"] == 1 and match[0]["producer"] == "etl"


def test_real_clickhouse_sink_is_idempotent_and_view_hides_duplicates():
    host, port = os.getenv("CLICKHOUSE_HOST", "localhost"), os.getenv("CLICKHOUSE_PORT", "8123")
    if not _reachable(host, port):
        pytest.skip("ClickHouse not reachable")
    from datetime import date, datetime, timezone
    import clickhouse_connect
    import clickhouse_sink as cs
    client = clickhouse_connect.get_client(host=host, port=int(port), username=os.getenv("CLICKHOUSE_USER", "default"), password=os.getenv("CLICKHOUSE_PASSWORD", ""))
    os.environ["CLICKHOUSE_DATABASE"] = "analytics_it"
    client.command("DROP DATABASE IF EXISTS analytics_it")
    cs.ensure_schema(client)
    mart = "mart_inventory_position"
    for month, qty in [(1, 5), (2, 9)]:      # same key, different months -> must collapse to latest
        client.insert(f"analytics_it.ch_{mart}",
                      [[date(2024, month, 1), "SKU1", "WH1", qty, datetime.now(timezone.utc)]],
                      column_names=cs.MARTS[mart]["columns"] + ["version"])
    rows = client.query(f"SELECT quantity_on_hand FROM analytics_it.{mart}").result_rows
    client.command("DROP DATABASE analytics_it")
    assert rows == [(9,)]



