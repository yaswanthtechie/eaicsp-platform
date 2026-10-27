from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentStatus,
)

from app.services.po_p2p_state_machine import (
    P2PState,
    get_p2p_state,
    transition_p2p,
)

from app.services.purchase_order_service import (
    get_purchase_order_by_id,
)
import re
from threading import Lock
from app.core.config import settings
from app.database import SessionLocal
from app.models.shipment_outbox import ShipmentOutbox
from app.models.shipment import Shipment
from sqlalchemy import select

# ============================================================
# IN-MEMORY SHIPMENT STORAGE
# ============================================================

shipments: dict[str, dict] = {}

# Protect shipment ID generation during concurrent requests.
_shipment_id_lock = Lock()


def _generate_shipment_id() -> str:
    """Generate a unique SHP-YYYY-NNNNNN shipment ID."""

    year = datetime.now(timezone.utc).year
    prefix = f"SHP-{year}-"

    with _shipment_id_lock:
        existing_sequences = [
            int(shipment_id[len(prefix):])
            for shipment_id in shipments
            if shipment_id.startswith(prefix)
            and re.fullmatch(
                rf"SHP-{year}-[0-9]{{6}}",
                shipment_id,
            )
        ]

        next_sequence = max(existing_sequences, default=0) + 1

        if next_sequence > 999999:
            raise ValueError(
                "Shipment ID sequence exhausted for this year."
            )

        return f"{prefix}{next_sequence:06d}"

def _build_shipment_dispatched_event(
    shipment_data: dict,
) -> dict:
    """Build an event that follows the shipment-dispatched v1 contract."""

    po_number = shipment_data["po_number"]

    if not re.fullmatch(r"PO-[0-9]{4}-[0-9]{6}", po_number):
        raise ValueError(
            "Purchase Order number must follow "
            "PO-YYYY-NNNNNN format to publish a dispatch event."
        )

    return {
        "event_id": str(uuid4()),
        "event_type": "supplierportal.shipment.dispatched",
        "event_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": "supplier-portal",
        "payload": {
            "shipment_id": shipment_data["shipment_id"],
            "po_number": po_number,
            "supplier_id": shipment_data["supplier_id"],
            "origin": shipment_data["origin"],
            "destination_warehouse": shipment_data[
                "destination_warehouse"
            ],
            "carrier": shipment_data["carrier"],
            "dispatched_at": shipment_data[
                "dispatched_at"
            ].isoformat(),
        },
    }

def _save_shipment_and_dispatch_event(
    shipment_data: dict,
    event: dict,
) -> None:
    """Persist the shipment and its dispatch event atomically."""

    db = SessionLocal()

    try:
        shipment_record = Shipment(
            shipment_id=shipment_data["shipment_id"],
            po_number=shipment_data["po_number"],
            supplier_id=shipment_data["supplier_id"],
            shipment_date=shipment_data["shipment_date"],
            expected_delivery_date=shipment_data["expected_delivery_date"],
            carrier=shipment_data["carrier"],
            tracking_number=shipment_data["tracking_number"],
            origin=shipment_data["origin"],
            destination_warehouse=shipment_data["destination_warehouse"],
            items=shipment_data["items"],
            status=shipment_data["status"].value,
            created_by=shipment_data["created_by"],
            dispatched_at=shipment_data["dispatched_at"],
            eta_days=None,
            confidence_low=None,
            confidence_high=None,
            model_version=None,
            predicted_at=None,
        )

        outbox_event = ShipmentOutbox(
            event_id=event["event_id"],
            topic=settings.SHIPMENT_DISPATCHED_TOPIC,
            message_key=event["payload"]["shipment_id"],
            payload=event,
            status="pending",
        )

        db.add(shipment_record)
        db.add(outbox_event)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

# ============================================================
# CREATE SHIPMENT NOTICE
# ============================================================

def create_shipment(
    shipment: ShipmentCreate,
    supplier_id: str,
    created_by: str,
):
    """
    Create a Shipment Notice for an acknowledged Purchase Order.

    The shared P2P state machine controls the workflow transition:

        acknowledged -> shipped
    """

    # --------------------------------------------------------
    # 1. GET PURCHASE ORDER
    # --------------------------------------------------------

    purchase_order = get_purchase_order_by_id(
        shipment.po_number
    )

    if not purchase_order:
        raise ValueError(
            "Purchase Order not found."
        )

    # --------------------------------------------------------
    # 2. VERIFY SUPPLIER OWNERSHIP
    # --------------------------------------------------------

    if purchase_order["supplier_id"] != supplier_id:
        raise ValueError(
            "Supplier does not own this Purchase Order."
        )

    # --------------------------------------------------------
    # 3. PO MUST BE ACKNOWLEDGED
    # --------------------------------------------------------

    if (
        purchase_order["status"]
        != PurchaseOrderStatus.acknowledged
    ):
        raise ValueError(
            "Shipment can be created only for an "
            "acknowledged Purchase Order."
        )

    # --------------------------------------------------------
    # 4. CHECK SHARED P2P STATE
    # --------------------------------------------------------

    current_p2p_state = get_p2p_state(
        shipment.po_number
    )

    if current_p2p_state != P2PState.acknowledged:
        raise ValueError(
            "Purchase Order is not in the acknowledged "
            "P2P state."
        )

    # --------------------------------------------------------
    # 5. VALIDATE SHIPMENT ITEMS AGAINST PO
    # --------------------------------------------------------

    po_items = {
        item["item_code"]: item["quantity"]
        for item in purchase_order["items"]
    }

    shipment_item_codes = set()

    for item in shipment.items:

        # Duplicate item codes are not allowed
        if item.item_code in shipment_item_codes:
            raise ValueError(
                f"Duplicate shipment item "
                f"'{item.item_code}'."
            )

        shipment_item_codes.add(
            item.item_code
        )

        # Item must exist in PO
        if item.item_code not in po_items:
            raise ValueError(
                f"Shipment item '{item.item_code}' "
                "does not exist in the Purchase Order."
            )

        # Shipment quantity cannot exceed PO quantity
        if item.quantity > po_items[item.item_code]:
            raise ValueError(
                f"Shipment quantity for item "
                f"'{item.item_code}' exceeds the "
                "Purchase Order quantity."
            )

    # --------------------------------------------------------
    # 6. GENERATE SHIPMENT ID
    # --------------------------------------------------------

    shipment_id = _generate_shipment_id()

    # --------------------------------------------------------
    # 7. STORE SHIPMENT
    # --------------------------------------------------------

    shipment_data = {
        "shipment_id": shipment_id,
        "po_number": shipment.po_number,
        "supplier_id": supplier_id,
        "origin": shipment.origin,
        "destination_warehouse": shipment.destination_warehouse,
        "dispatched_at": datetime.now(timezone.utc),
        "shipment_date": shipment.shipment_date,
        "expected_delivery_date": (
            shipment.expected_delivery_date
        ),
        "carrier": shipment.carrier,
        "tracking_number": shipment.tracking_number,
        "items": [
            item.model_dump()
            for item in shipment.items
        ],
        "status": ShipmentStatus.created,
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
        # ETA prediction fields are populated
        # when eta.shipment.predicted is consumed.
        "eta_days": None,
        "confidence_low": None,
        "confidence_high": None,
        "model_version": None,
        "predicted_at": None,
    }

    shipments[shipment_id] = shipment_data

        # --------------------------------------------------------
    # 8. PUBLISH SHIPMENT DISPATCH EVENT THROUGH OUTBOX
    # --------------------------------------------------------

    try:
        dispatch_event = _build_shipment_dispatched_event(
            shipment_data
        )

        _save_shipment_and_dispatch_event(
            shipment_data,
            dispatch_event
        )

        # ----------------------------------------------------
        # 9. ADVANCE SHARED P2P STATE
        # ----------------------------------------------------

        transition_p2p(
            shipment.po_number,
            P2PState.shipped,
        )

    except Exception:
        # Roll back in-memory shipment if event persistence
        # or workflow transition fails.
        shipments.pop(shipment_id, None)
        raise

    return shipment_data

def get_shipment_by_id(shipment_id: str):
    db = SessionLocal()

    try:
        return db.get(Shipment, shipment_id)
    finally:
        db.close()


def get_shipments_by_po(po_number: str):
    db = SessionLocal()

    try:
        statement = (
            select(Shipment)
            .where(Shipment.po_number == po_number)
            .order_by(Shipment.created_at.desc())
        )

        return list(db.scalars(statement).all())
    finally:
        db.close()


def get_all_shipments():
    db = SessionLocal()

    try:
        statement = select(Shipment).order_by(
            Shipment.created_at.desc()
        )

        return list(db.scalars(statement).all())
    finally:
        db.close()