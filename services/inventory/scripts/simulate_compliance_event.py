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
            "matched_list": ["OFAC"] if new_status.upper() in ("BLOCK", "BLOCKED") else [],
            "reason": reason,
            "screening_run_id": f"manual-{uuid.uuid4().hex[:8]}",
        },
    }


def simulate_event(
    supplier_name: str,
    new_status: str,
    old_status: str = "CLEAR",
    reason: str = "Compliance screening status update",
    country: str = "India",
):
    envelope = build_event(
        supplier_name=supplier_name,
        new_status=new_status,
        old_status=old_status,
        reason=reason,
        country=country,
    )

    db = SessionLocal()
    try:
        logger.info("Processing event %s for supplier '%s' (new_status=%s)...", envelope["event_id"], supplier_name, new_status)
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
    parser.add_argument("--supplier-name", default="ABC Supplies", help="Supplier name (e.g. 'ABC Supplies')")
    parser.add_argument(
        "--new-status",
        default="BLOCK",
        choices=["CLEAR", "CLEARED", "BLOCK", "BLOCKED", "REVIEW", "needs review"],
        help="New compliance status",
    )
    parser.add_argument("--old-status", default="CLEAR", help="Old compliance status")
    parser.add_argument("--reason", default="Entity matched sanctions list", help="Reason for status change")
    parser.add_argument("--country", default="India", help="Supplier country")

    args = parser.parse_args()

    try:
        simulate_event(
            supplier_name=args.supplier_name,
            new_status=args.new_status,
            old_status=args.old_status,
            reason=args.reason,
            country=args.country,
        )
    except Exception as exc:
        logger.error("Simulation failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
