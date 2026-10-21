from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.po_ack_outbox import POAckOutbox
from app.models.po_mirror import POMirror


class POAcknowledgementError(Exception):
    """Raised when an approved PO cannot be acknowledged."""


def acknowledge_approved_po(
    db: Session,
    po_id: str,
    supplier_id: str,
) -> POMirror | None:
    """
    Acknowledge a mirrored PO and insert its event into the outbox
    in the same database transaction.

    Returns None when the PO does not belong to this supplier
    or does not exist.
    """
    try:
        po = (
            db.query(POMirror)
            .filter(
                POMirror.po_id == po_id,
                POMirror.supplier_id == supplier_id,
            )
            .with_for_update()
            .one_or_none()
        )

        if po is None:
            db.rollback()
            return None

        # Idempotent HTTP acknowledgement: do not create another event.
        if po.status == "acknowledged":
            db.commit()
            return po

        if po.status != "approved":
            raise POAcknowledgementError(
                f"PO cannot be acknowledged from status '{po.status}'"
            )

        acknowledged_at = datetime.now(timezone.utc)
        event_id = str(uuid4())

        event_payload = {
            "event_id": event_id,
            "event_type": "supplierportal.po.acknowledged",
            "event_version": 1,
            "occurred_at": acknowledged_at.isoformat(),
            "producer": "supplier-portal-service",
            "trace_id": None,
            "payload": {
                "po_id": po.po_id,
                "po_number": po.po_number,
                "supplier_id": po.supplier_id,
                "warehouse_id": po.warehouse_id,
                "acknowledged_at": acknowledged_at.isoformat(),
            },
        }

        po.status = "acknowledged"
        po.acknowledged_at = acknowledged_at

        db.add(
            POAckOutbox(
                event_id=event_id,
                topic=settings.PO_ACKNOWLEDGED_TOPIC,
                message_key=po.po_id,
                payload=event_payload,
                status="pending",
                attempts=0,
            )
        )

        # Both changes commit together, or both roll back.
        db.commit()
        db.refresh(po)
        return po

    except Exception:
        db.rollback()
        raise
