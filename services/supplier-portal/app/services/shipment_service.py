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
from app.models.po_mirror import POMirror
from app.models.shipment_outbox import ShipmentOutbox
from app.models.shipment import Shipment
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# ============================================================
# IN-MEMORY SHIPMENT STORAGE
# ============================================================

shipments: dict[str, dict] = {}

# Serialize shipment ID allocation within this process. Across
# processes the shipments primary key catches a clash and we retry.
_shipment_id_lock = Lock()

MAX_SHIPMENT_ID_ATTEMPTS = 5


def _next_shipment_id(db) -> str:
    """
    Return the next SHP-YYYY-NNNNNN ID from the database.

    The sequence is zero-padded, so the highest ID sorts last.
    Reading it from the database (not from memory) keeps IDs
    unique across restarts and across workers.
    """

    year = datetime.now(timezone.utc).year
    prefix = f"SHP-{year}-"

    latest = db.scalars(
        select(Shipment.shipment_id)
        .where(Shipment.shipment_id.like(f"{prefix}%"))
        .order_by(Shipment.shipment_id.desc())
        .limit(1)
    ).first()

    next_sequence = int(latest[len(prefix):]) + 1 if latest else 1

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
) -> dict:
    """
    Allocate the shipment ID, then persist the shipment and its
    dispatch event atomically. Sets shipment_data["shipment_id"]
    and returns the event.
    """

    with _shipment_id_lock:
        for attempt in range(1, MAX_SHIPMENT_ID_ATTEMPTS + 1):
            db = SessionLocal()

            try:
                shipment_data["shipment_id"] = _next_shipment_id(db)
                event = _build_shipment_dispatched_event(shipment_data)

                shipment_record = Shipment(
                    shipment_id=shipment_data["shipment_id"],
                    po_number=shipment_data["po_number"],
                    supplier_id=shipment_data["supplier_id"],
                    shipment_date=shipment_data["shipment_date"],
                    expected_delivery_date=shipment_data[
                        "expected_delivery_date"
                    ],
                    carrier=shipment_data["carrier"],
                    tracking_number=shipment_data["tracking_number"],
                    origin=shipment_data["origin"],
                    destination_warehouse=shipment_data[
                        "destination_warehouse"
                    ],
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

                return event

            except IntegrityError:
                db.rollback()

                # Another worker took this ID first: try the next one.
                if attempt == MAX_SHIPMENT_ID_ATTEMPTS:
                    raise

            except Exception:
                db.rollback()
                raise

            finally:
                db.close()


def _get_acknowledged_inventory_po(
    po_number: str,
    supplier_id: str,
) -> dict | None:
    """
    Return an Inventory PO from po_mirror that the supplier has
    acknowledged (#261), shaped like a legacy PO with sku_id lines.
    Returns None when po_mirror has no such PO.
    """

    db = SessionLocal()

    try:
        mirror = db.scalars(
            select(POMirror).where(
                (POMirror.po_id == po_number)
                | (POMirror.po_number == po_number)
            )
        ).first()

        if mirror is None:
            return None

        if mirror.supplier_id != supplier_id:
            raise ValueError(
                "Supplier does not own this Purchase Order."
            )

        if mirror.status != "acknowledged":
            raise ValueError(
                "Shipment can be created only for an "
                "acknowledged Purchase Order."
            )

        # The database is the record for Inventory POs, so this
        # check also holds after a restart.
        existing_shipment_id = db.scalars(
            select(Shipment.shipment_id)
            .where(Shipment.po_number == mirror.po_id)
            .limit(1)
        ).first()

        if existing_shipment_id is not None:
            raise ValueError(
                f"Purchase Order '{mirror.po_id}' has already been "
                f"dispatched in shipment '{existing_shipment_id}'."
            )

        return {
            "po_number": mirror.po_id,
            "supplier_id": mirror.supplier_id,
            "items": [
                {
                    "sku_id": line["sku_id"],
                    "quantity": line["quantity"],
                }
                for line in mirror.lines or []
            ],
        }

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

    Legacy POs: the shared P2P state machine controls the workflow
    transition acknowledged -> shipped.

    Inventory POs (po_mirror): the PO must be acknowledged in
    po_mirror and not already dispatched.
    """

    # --------------------------------------------------------
    # 1. GET PURCHASE ORDER
    # --------------------------------------------------------

    purchase_order = get_purchase_order_by_id(
        shipment.po_number
    )
    is_inventory_po = False

    if not purchase_order:
        purchase_order = _get_acknowledged_inventory_po(
            shipment.po_number,
            supplier_id,
        )
        is_inventory_po = purchase_order is not None

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

    if not is_inventory_po:

        # ----------------------------------------------------
        # 3. PO MUST BE ACKNOWLEDGED
        # ----------------------------------------------------

        if (
            purchase_order["status"]
            != PurchaseOrderStatus.acknowledged
        ):
            raise ValueError(
                "Shipment can be created only for an "
                "acknowledged Purchase Order."
            )

        # ----------------------------------------------------
        # 4. CHECK SHARED P2P STATE
        # ----------------------------------------------------

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
    #
    # Inventory PO lines are identified by sku_id,
    # legacy PO lines by item_code.
    # --------------------------------------------------------

    line_field = "sku_id" if is_inventory_po else "item_code"

    po_items = {
        item[line_field]: item["quantity"]
        for item in purchase_order["items"]
    }

    shipment_item_codes = set()

    for item in shipment.items:
        item_key = getattr(item, line_field)

        # Duplicate items are not allowed
        if item_key in shipment_item_codes:
            raise ValueError(
                f"Duplicate shipment item "
                f"'{item_key}'."
            )

        shipment_item_codes.add(item_key)

        # Item must exist in PO
        if item_key not in po_items:
            raise ValueError(
                f"Shipment item '{item.sku_id or item.item_code}' "
                "does not exist in the Purchase Order."
            )

        # Shipment quantity cannot exceed PO quantity
        if item.quantity > po_items[item_key]:
            raise ValueError(
                f"Shipment quantity for item "
                f"'{item_key}' exceeds the "
                "Purchase Order quantity."
            )

    # --------------------------------------------------------
    # 6. BUILD SHIPMENT
    #    The shipment ID is allocated from the database in step 7.
    # --------------------------------------------------------

    shipment_data = {
        "shipment_id": None,
        "po_number": purchase_order["po_number"],
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
            item.model_dump(exclude_none=True)
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

    # --------------------------------------------------------
    # 7. STORE SHIPMENT + DISPATCH EVENT THROUGH OUTBOX
    # --------------------------------------------------------

    _save_shipment_and_dispatch_event(shipment_data)

    shipment_id = shipment_data["shipment_id"]
    shipments[shipment_id] = shipment_data

    # --------------------------------------------------------
    # 8. ADVANCE SHARED P2P STATE (legacy POs only)
    #
    # Step 4 already confirmed the state is 'acknowledged',
    # so this transition is legal.
    # --------------------------------------------------------

    if not is_inventory_po:
        try:
            transition_p2p(
                shipment.po_number,
                P2PState.shipped,
            )

        except Exception:
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