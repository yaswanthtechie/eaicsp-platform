from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from confluent_kafka import Producer

from app.core.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_SUPPLIER_STATUS_TOPIC,
)


_producer: Producer | None = None


def get_kafka_producer() -> Producer:
    global _producer

    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "enable.idempotence": True,
            }
        )

    return _producer


def build_supplier_status_changed_event(
    *,
    entity_name: str,
    old_status: str,
    new_status: str,
    matched_list: list[str],
    reason: str,
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "compliance.supplier.status_changed",
        "source": "compliance-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "entity_name": entity_name,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": matched_list,
            "reason": reason,
        },
    }


def publish_supplier_status_changed(
    *,
    entity_name: str,
    old_status: str,
    new_status: str,
    matched_list: list[str],
    reason: str,
) -> dict:
    event = build_supplier_status_changed_event(
        entity_name=entity_name,
        old_status=old_status,
        new_status=new_status,
        matched_list=matched_list,
        reason=reason,
    )

    producer = get_kafka_producer()

    producer.produce(
        KAFKA_SUPPLIER_STATUS_TOPIC,
        key=entity_name,
        value=json.dumps(event),
    )

    producer.flush()

    return event