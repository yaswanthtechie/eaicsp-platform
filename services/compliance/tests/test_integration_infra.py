import json
import os
import time
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.integration

PG_URL = os.environ.get("COMPLIANCE_PG_TEST_URL")
KAFKA = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


@pytest.fixture
def empty_postgres():
    if not PG_URL:
        pytest.skip("Set COMPLIANCE_PG_TEST_URL and start docker-compose.dev.yml")

    engine = create_engine(PG_URL)

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    yield engine

    engine.dispose()


def test_alembic_upgrade_head_on_empty_database(empty_postgres, monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", PG_URL)
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "head")

    tables = set(inspect(empty_postgres).get_table_names())

    assert {
        "compliance_audit", "compliance_case", "case_history",
        "compliance_override", "regulatory_rules", "alembic_version",
    } <= tables

    columns = {
        c["name"] for c in inspect(empty_postgres).get_columns("compliance_audit")
    }

    assert "decision" in columns

    command.downgrade(cfg, "base")

    assert inspect(empty_postgres).get_table_names() == ["alembic_version"]


def test_status_changed_event_reaches_real_kafka():
    from confluent_kafka import Consumer

    from app.services import kafka_producer

    supplier = f"IT-SUPPLIER-{uuid.uuid4()}"

    assert kafka_producer.publish_supplier_status_changed(
        supplier_name=supplier,
        country="India",
        old_status="CLEAR",
        new_status="BLOCK",
        matched_list=["OFAC"],
        reason="integration test",
        screening_run_id="it-run",
    ) is True

    consumer = Consumer({
        "bootstrap.servers": KAFKA,
        "group.id": f"it-{uuid.uuid4()}",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([kafka_producer.TOPIC])

    found = None
    found_topic = None
    deadline = time.time() + 20

    try:
        while found is None and time.time() < deadline:
            msg = consumer.poll(1.0)

            if msg is None or msg.error():
                continue

            event = json.loads(msg.value())
            payload = event.get("payload", {})
            if payload.get("supplier_name") == supplier:
                found, found_topic = event, msg.topic()
    finally:
        consumer.close()

    assert found is not None
    assert found_topic == found["event_type"] == "compliance.supplier.status_changed"