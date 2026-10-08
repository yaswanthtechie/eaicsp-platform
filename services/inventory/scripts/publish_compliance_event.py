"""
Test producer script to publish compliance.supplier.status_changed events.
Allows testing the inventory compliance consumer in isolation without Geethika's service running.
"""
import argparse
from datetime import UTC, datetime
import json
import logging
import sys
import uuid

from app.core.config import settings
from app.services.kafka_producer import KafkaEventPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("compliance_test_producer")


def publish_compliance_status_event(
    supplier_id: str,
    new_status: str,
    old_status: str = "CLEAR",
    matched_list: list[str] | None = None,
    reason: str = "Compliance screening status update",
    topic: str | None = None,
    bootstrap_servers: str | None = None,
    event_id: str | None = None,
    occurred_at: str | None = None,
    event_version: str = "1.0",
) -> str:
    topic = topic or settings.COMPLIANCE_STATUS_CHANGED_TOPIC
    event_id = event_id or str(uuid.uuid4())
    occurred_at = occurred_at or datetime.now(UTC).isoformat()
    matched_list = matched_list if matched_list is not None else (["OFAC"] if new_status in ("BLOCK", "BLOCKED") else [])

    envelope = {
        "event_id": event_id,
        "event_type": "compliance.supplier.status_changed",
        "producer": "compliance-service",
        "occurred_at": occurred_at,
        "event_version": event_version,
        "trace_id": f"trace-{uuid.uuid4().hex[:8]}",
        "payload": {
            "supplier_id": supplier_id,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": matched_list,
            "reason": reason,
        },
    }

    serialized = json.dumps(envelope)
    publisher = KafkaEventPublisher(bootstrap_servers=bootstrap_servers)

    logger.info("Publishing event %s to topic %s for supplier %s (status: %s)", event_id, topic, supplier_id, new_status)
    publisher.publish(topic=topic, key=supplier_id, value=serialized)
    logger.info("Event %s successfully delivered to Kafka.", event_id)
    return event_id


def main():
    parser = argparse.ArgumentParser(description="Publish test compliance.supplier.status_changed events to Kafka")
    parser.add_argument("--supplier-id", default="SUP-TEST-001", help="Supplier identifier")
    parser.add_argument("--new-status", default="BLOCK", choices=["CLEAR", "CLEARED", "BLOCK", "BLOCKED", "REVIEW", "needs review"], help="New compliance status")
    parser.add_argument("--old-status", default="CLEAR", help="Old compliance status")
    parser.add_argument("--reason", default="Entity matched sanctions list", help="Reason for status change")
    parser.add_argument("--topic", default=None, help="Kafka topic name")
    parser.add_argument("--bootstrap-servers", default=None, help="Kafka bootstrap servers")
    parser.add_argument("--event-version", default="1.0", help="Envelope event version")

    args = parser.parse_args()

    try:
        publish_compliance_status_event(
            supplier_id=args.supplier_id,
            new_status=args.new_status,
            old_status=args.old_status,
            reason=args.reason,
            topic=args.topic,
            bootstrap_servers=args.bootstrap_servers,
            event_version=args.event_version,
        )
    except Exception as exc:
        logger.error("Failed to publish event: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

