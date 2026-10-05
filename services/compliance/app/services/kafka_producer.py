from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from confluent_kafka import Producer
from app.core.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_FLUSH_TIMEOUT_SECONDS,
    SERVICE_NAME,
)
logger = logging.getLogger(__name__)
EVENT_TYPE = "compliance.supplier.status_changed"
EVENT_VERSION = 1
TOPIC = EVENT_TYPE
_producer: Producer | None = None

def get_kafka_producer() -> Producer:
    global _producer

    if _producer is None:
        _producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "enable.idempotence": True,
                "message.timeout.ms": 10000,
            }
        )

    return _producer


def build_supplier_status_changed_event(
    *,
    supplier_name: str,
    country: str | None,
    old_status: str,
    new_status: str,
    matched_list: list[str],
    reason: str,
    screening_run_id: str,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": EVENT_TYPE,
        "event_version": EVENT_VERSION,
        "occurred_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "producer": SERVICE_NAME,
        "payload": {
            "supplier_name": supplier_name,
            "country": country,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": matched_list,
            "reason": reason,
            "screening_run_id": screening_run_id,
        },
    }


def publish_supplier_status_changed(
    *,
    supplier_name: str,
    country: str | None,
    old_status: str,
    new_status: str,
    matched_list: list[str],
    reason: str,
    screening_run_id: str,
) -> bool:
    try:
        event = build_supplier_status_changed_event(
            supplier_name=supplier_name,
            country=country,
            old_status=old_status,
            new_status=new_status,
            matched_list=matched_list,
            reason=reason,
            screening_run_id=screening_run_id,
        )

        producer = get_kafka_producer()

        delivery_errors: list[str] = []

        def delivery_callback(
            err,
            msg,
        ) -> None:
            if err is not None:
                delivery_errors.append(
                    str(err)
                )

        producer.produce(
            TOPIC,
            key=supplier_name,
            value=json.dumps(event),
            callback=delivery_callback,
        )

        remaining = producer.flush(
            KAFKA_FLUSH_TIMEOUT_SECONDS
        )

        if delivery_errors or remaining:
            logger.error(
                "Kafka delivery failed for %s: %s",
                EVENT_TYPE,
                delivery_errors,
            )
            return False

        return True

    except Exception:
        logger.exception(
            "Kafka publish failed for %s",
            EVENT_TYPE,
        )
        return False

