from datetime import datetime
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


# ============================================================
# IN-MEMORY SHIPMENT STORAGE
# ============================================================

shipments: dict[str, dict] = {}


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

    shipment_id = (
        f"SHIP-{uuid4().hex[:12].upper()}"
    )

    # --------------------------------------------------------
    # 7. STORE SHIPMENT
    # --------------------------------------------------------

    shipment_data = {
        "shipment_id": shipment_id,
        "po_number": shipment.po_number,
        "supplier_id": supplier_id,
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
        "created_at": datetime.utcnow(),
        "created_by": created_by,
    }

    shipments[shipment_id] = shipment_data

    # --------------------------------------------------------
    # 8. ADVANCE SHARED P2P STATE
    # --------------------------------------------------------

    try:

        transition_p2p(
            shipment.po_number,
            P2PState.shipped,
        )

    except ValueError:

        # Roll back shipment creation if the workflow
        # transition fails.
        del shipments[shipment_id]

        raise

    return shipment_data


# ============================================================
# GET SHIPMENT
# ============================================================

def get_shipment_by_id(
    shipment_id: str,
):
    return shipments.get(
        shipment_id
    )


# ============================================================
# GET SHIPMENTS FOR A PO
# ============================================================

def get_shipments_by_po(
    po_number: str,
):
    return [
        shipment
        for shipment in shipments.values()
        if shipment["po_number"] == po_number
    ]


# ============================================================
# GET ALL SHIPMENTS
# ============================================================

def get_all_shipments():
    return list(
        shipments.values()
    )