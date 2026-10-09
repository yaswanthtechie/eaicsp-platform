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


def build_event(
    supplier_name: str,
    new_status: str,
    old_status: str = "CLEAR",
    reason: str = "Compliance screening status update",
    country: str = "India",
) -> dict:
    """Same shape as build_supplier_status_changed_event() in services/compliance."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "compliance.supplier.status_changed",
        "event_version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": "compliance-service",
        "payload": {
            "supplier_name": supplier_name,
            "country": country,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": ["OFAC"] if new_status.upper() == "BLOCK" else [],
            "reason": reason,
            "screening_run_id": f"manual-{uuid.uuid4().hex[:8]}",
        },
    }


def publish_compliance_status_event(
    supplier_name: str,
    new_status: str,
    old_status: str = "CLEAR",
    reason: str = "Compliance screening status update",
    country: str = "India",
    topic: str | None = None,
    bootstrap_servers: str | None = None,
) -> str:
    topic = topic or settings.COMPLIANCE_STATUS_CHANGED_TOPIC
    envelope = build_event(
        supplier_name=supplier_name,
        new_status=new_status,
        old_status=old_status,
        reason=reason,
        country=country,
    )

    event_id = envelope["event_id"]
    serialized = json.dumps(envelope)
    publisher = KafkaEventPublisher(bootstrap_servers=bootstrap_servers)

    logger.info("Publishing event %s to topic %s for supplier '%s' (status: %s)", event_id, topic, supplier_name, new_status)
    publisher.publish(topic=topic, key=supplier_name, value=serialized)
    logger.info("Event %s successfully delivered to Kafka.", event_id)
    return event_id


def main():
    parser = argparse.ArgumentParser(description="Publish test compliance.supplier.status_changed events to Kafka")
    parser.add_argument("--supplier-name", default="ABC Supplies", help="Supplier name (e.g. 'ABC Supplies')")
    parser.add_argument("--new-status", default="BLOCK", choices=["CLEAR", "CLEARED", "BLOCK", "BLOCKED", "REVIEW", "needs review"], help="New compliance status")
    parser.add_argument("--old-status", default="CLEAR", help="Old compliance status")
    parser.add_argument("--reason", default="Entity matched sanctions list", help="Reason for status change")
    parser.add_argument("--country", default="India", help="Supplier country")
    parser.add_argument("--topic", default=None, help="Kafka topic name")
    parser.add_argument("--bootstrap-servers", default=None, help="Kafka bootstrap servers")

    args = parser.parse_args()

    try:
        publish_compliance_status_event(
            supplier_name=args.supplier_name,
            new_status=args.new_status,
            old_status=args.old_status,
            reason=args.reason,
            country=args.country,
            topic=args.topic,
            bootstrap_servers=args.bootstrap_servers,
        )
    except Exception as exc:
        logger.error("Failed to publish event: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
