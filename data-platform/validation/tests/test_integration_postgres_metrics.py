"""
Integration tests against the REAL Postgres and Kafka from
docker-compose.dev.yml. They must FAIL (never pass) when the stack is down.

Run:
    cp .env.example .env            # fill in POSTGRES_* and DATABASE_URL
    docker compose -f docker-compose.dev.yml up -d
    set -a; source .env; set +a     # Git Bash: export the variables
    pytest -m integration --no-cov
"""

import json
import os
import time
import uuid

import pytest

from data_validator.postgres_client import fetch_run, persist_validation_result
from data_validator.validator import ValidationResult

pytestmark = pytest.mark.integration

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


# ------------------------------------------------------------------
# Postgres: a saved run can be read back with the same values
# ------------------------------------------------------------------

def test_run_is_saved_and_queryable_in_postgres():
    if not os.environ.get("DATABASE_URL"):
        pytest.fail("DATABASE_URL is not set; start the stack and load .env first")

    dataset = f"integration_{uuid.uuid4().hex[:8]}.csv"
    result = ValidationResult(
        config_version="dev-1.0.0",
        passed=False,
        batch_rejected=False,
        total_rows=500,
        total_rows_affected=12,
        sla_breached=False,
        evaluated_rules=["sku_format", "quantity_positive"],
    )

    run_id = persist_validation_result(dataset, result, duration_seconds=0.25)
    saved = fetch_run(run_id)

    assert saved is not None
    assert saved["dataset_name"] == dataset
    assert saved["mode"] == "batch"
    assert saved["rules_applied"] == ["sku_format", "quantity_positive"]
    assert saved["total_rows"] == 500
    assert saved["total_rows_affected"] == 12
    assert saved["passed"] is False


# ------------------------------------------------------------------
# Kafka: good -> .valid, bad -> .dlq, and a restart loses nothing
# ------------------------------------------------------------------

GOOD = {
    "transaction_id": 1, "date": "2024-03-10", "sku_id": "SKU-1000",
    "warehouse_id": "WH-01", "quantity_sold": 5, "unit_price": 20.0,
}
BAD = {
    "transaction_id": 2, "date": "2024-03-11", "sku_id": "BAD-SKU",
    "warehouse_id": "WH-02", "quantity_sold": -5, "unit_price": 10.0,
}


def _settings(prefix):
    return {
        "bootstrap_servers": BOOTSTRAP,
        "group_id": f"{prefix}-group",
        "input_topic": f"{prefix}.raw",
        "valid_topic": f"{prefix}.valid",
        "dlq_topic": f"{prefix}.dlq",
        "config_path": "configs/dev/sales_rules.yaml",
        "persist_every": 1000,  # don't need Postgres for the Kafka tests
        "metrics_port": 0,
    }


def _produce(topic, records):
    from confluent_kafka import Producer

    producer = Producer({"bootstrap.servers": BOOTSTRAP})
    for record in records:
        producer.produce(topic, json.dumps(record).encode("utf-8"))
    assert producer.flush(10) == 0, "test records were not delivered"


def _consumer(group_id):
    from confluent_kafka import Consumer

    return Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


def _streaming_validator(settings):
    from confluent_kafka import Producer

    from data_validator.streaming_validator import StreamingValidator
    from data_validator.validator import DataValidator

    consumer = _consumer(settings["group_id"])
    consumer.subscribe([settings["input_topic"]])
    producer = Producer({
        "bootstrap.servers": BOOTSTRAP,
        "enable.idempotence": True,
    })
    validator = DataValidator.from_config(settings["config_path"])
    return StreamingValidator(validator, consumer, producer, settings)


def _process(sv, count, timeout=60):
    """Handle exactly `count` input messages (or fail after timeout)."""
    handled = 0
    deadline = time.time() + timeout
    while handled < count:
        assert time.time() < deadline, f"only handled {handled}/{count} messages"
        msg = sv.consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        if sv.handle_message(msg):
            handled += 1


def _read_all(topic, timeout=30):
    consumer = _consumer(f"reader-{uuid.uuid4().hex[:8]}")
    consumer.subscribe([topic])
    values = []
    deadline = time.time() + timeout
    idle = 0
    while time.time() < deadline and idle < 5:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            idle += 1 if values else 0
            continue
        values.append(json.loads(msg.value()))
    consumer.close()
    return values


def test_good_goes_to_valid_and_bad_goes_to_dlq_with_reason():
    settings = _settings(f"it-{uuid.uuid4().hex[:8]}")
    _produce(settings["input_topic"], [GOOD, BAD])

    sv = _streaming_validator(settings)
    try:
        _process(sv, 2)
    finally:
        sv.consumer.close()

    valid = _read_all(settings["valid_topic"])
    dlq = _read_all(settings["dlq_topic"])

    assert [r["transaction_id"] for r in valid] == [1]
    assert len(dlq) == 1
    assert dlq[0]["original_record"]["transaction_id"] == 2
    assert dlq[0]["failed_rules"]
    assert all(dlq[0]["reasons"][rule] for rule in dlq[0]["failed_rules"])


def test_restart_mid_stream_loses_nothing_and_skips_committed_records():
    settings = _settings(f"it-{uuid.uuid4().hex[:8]}")
    records = [dict(GOOD, transaction_id=n) for n in range(1, 7)]
    _produce(settings["input_topic"], records)

    # First run: process 3 records, then "crash" (close without finishing).
    first = _streaming_validator(settings)
    _process(first, 3)
    first.consumer.close()

    # Restart with the same consumer group: it must resume at record 4.
    second = _streaming_validator(settings)
    try:
        _process(second, 3)
    finally:
        second.consumer.close()

    valid_ids = sorted(r["transaction_id"] for r in _read_all(settings["valid_topic"]))
    assert valid_ids == [1, 2, 3, 4, 5, 6]  # nothing lost, nothing repeated