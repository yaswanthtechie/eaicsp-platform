"""
CLI script to simulate compliance.supplier.status_changed event directly
against the local database without needing a running Kafka broker.
"""
import argparse
from datetime import UTC, datetime
import json
import logging
import sys
import uuid

from app.database import SessionLocal
from app.services.compliance_consumer import process_compliance_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulate_compliance_event")


def simulate_event(
    supplier_id: str,
    new_status: str,
    old_status: str = "CLEAR",
    reason: str = "Compliance screening status update",
    event_id: str | None = None,
    occurred_at: str | None = None,
    event_version: str = "1.0",
):
    event_id = event_id or f"evt-sim-{uuid.uuid4().hex[:8]}"
    occurred_at = occurred_at or datetime.now(UTC).isoformat()
    matched_list = ["OFAC"] if new_status.upper() in ("BLOCK", "BLOCKED") else []

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

    db = SessionLocal()
    try:
        logger.info("Processing event %s for supplier %s (new_status=%s)...", event_id, supplier_id, new_status)
        result = process_compliance_event(db=db, event_data=envelope)
        logger.info(
            "Result: %s | Affected POs: %s | Details: %s",
            result.status,
            result.affected_pos,
            result.details or "None",
        )
        return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Simulate compliance status changed event on local database")
    parser.add_argument("--supplier-id", default="SUP001", help="Supplier identifier (e.g. SUP001)")
    parser.add_argument(
        "--new-status",
        default="BLOCK",
        choices=["CLEAR", "CLEARED", "BLOCK", "BLOCKED", "REVIEW", "needs review"],
        help="New compliance status",
    )
    parser.add_argument("--old-status", default="CLEAR", help="Old compliance status")
    parser.add_argument("--reason", default="Entity matched sanctions list", help="Reason for status change")
    parser.add_argument("--event-id", default=None, help="Custom event_id for testing idempotency")
    parser.add_argument("--event-version", default="1.0", help="Envelope event version")

    args = parser.parse_args()

    try:
        simulate_event(
            supplier_id=args.supplier_id,
            new_status=args.new_status,
            old_status=args.old_status,
            reason=args.reason,
            event_id=args.event_id,
            event_version=args.event_version,
        )
    except Exception as exc:
        logger.error("Simulation failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

