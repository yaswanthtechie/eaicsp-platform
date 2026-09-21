from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier

from app.schemas.purchase_order import (
    PurchaseOrderRequest,
)

from app.services.reorder_service import (
    calculate_reorder_point,
)

from app.services.valuation_service import (
    add_cost_layer,
)


def generate_po_id():
    return f"PO-{uuid4().hex[:8].upper()}"


def select_supplier(
    db: Session,
    sku_id: str,
):
    suppliers = (
        db.query(Supplier)
        .filter(
            Supplier.sku_id == sku_id
        )
        .order_by(
            Supplier.unit_cost.asc()
        )
        .all()
    )

    if not suppliers:
        raise ValueError(
            f"No supplier found for SKU {sku_id}"
        )

    return suppliers[0]


def calculate_draft_po_details(
    db: Session,
    inventory: Inventory,
):
    """
    Calculate all information required to create
    a draft purchase order.

    This function does not create or commit a PO.
    """

    reorder_data = calculate_reorder_point(
        db=db,
        inventory=inventory,
    )

    reorder_point = reorder_data[
        "reorder_point"
    ]

    if (
        inventory.quantity_on_hand
        >= reorder_point
    ):
        return None

    suggested_quantity = max(
        int(
            reorder_point
            - inventory.quantity_on_hand
        ),
        1,
    )

    supplier = select_supplier(
        db=db,
        sku_id=inventory.sku_id,
    )

    expected_cost = (
        suggested_quantity
        * supplier.unit_cost
    )

    return {
        "quantity": suggested_quantity,
        "supplier_id": supplier.supplier_id,
        "unit_cost": supplier.unit_cost,
        "expected_cost": expected_cost,
    }


def find_existing_draft_po(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):
    """
    Find an existing draft PO for the same SKU
    and warehouse.

    This prevents duplicate draft POs.
    """

    return (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.sku_id == sku_id,
            PurchaseOrder.warehouse_id == warehouse_id,
            PurchaseOrder.status == "draft",
        )
        .order_by(
            PurchaseOrder.created_at.desc()
        )
        .first()
    )


def create_draft_po_for_inventory(
    db: Session,
    inventory: Inventory,
):
    """
    Automatically create a draft PO when inventory
    falls below its reorder point.

    If a draft PO already exists for the same
    SKU and warehouse, return the existing PO.

    Returns None when reorder is not required.
    """

    po_details = calculate_draft_po_details(
        db=db,
        inventory=inventory,
    )

    if po_details is None:
        return None

    existing_po = find_existing_draft_po(
        db=db,
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
    )

    if existing_po is not None:
        return existing_po

    purchase_order = PurchaseOrder(
        po_id=generate_po_id(),
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        supplier_id=po_details["supplier_id"],
        quantity=po_details["quantity"],
        unit_cost=po_details["unit_cost"],
        expected_cost=po_details["expected_cost"],
        status="draft",
    )

    db.add(purchase_order)

    try:
        db.commit()
        db.refresh(purchase_order)

    except Exception:
        db.rollback()
        raise

    return purchase_order


def create_automatic_draft_po(
    db: Session,
    data: PurchaseOrderRequest,
):
    """
    Existing request-driven PO endpoint.
    """

    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == data.sku_id,
            Inventory.warehouse_id
            == data.warehouse_id,
        )
        .first()
    )

    if inventory is None:
        raise ValueError(
            "Inventory record not found"
        )

    po_details = calculate_draft_po_details(
        db=db,
        inventory=inventory,
    )

    if po_details is None:
        raise ValueError(
            "Reorder is not required for this inventory"
        )

    purchase_order = PurchaseOrder(
        po_id=generate_po_id(),
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        supplier_id=po_details["supplier_id"],
        quantity=po_details["quantity"],
        unit_cost=po_details["unit_cost"],
        expected_cost=po_details["expected_cost"],
        status="draft",
    )

    db.add(purchase_order)

    try:
        db.commit()
        db.refresh(purchase_order)

    except Exception:
        db.rollback()
        raise

    return purchase_order


def receive_purchase_order(
    db: Session,
    po_id: str,
):
    """
    Receive a draft purchase order.

    Receiving a PO:
    1. Increases inventory quantity.
    2. Creates a new inventory cost layer.
    3. Uses the PO unit cost for the new layer.
    4. Increments inventory version.
    5. Changes PO status to received.
    """

    purchase_order = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.po_id == po_id
        )
        .with_for_update()
        .first()
    )

    if purchase_order is None:
        raise ValueError(
            "Purchase order not found"
        )

    if purchase_order.status != "draft":
        raise ValueError(
            "Only draft purchase orders can be received"
        )

    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id
            == purchase_order.sku_id,
            Inventory.warehouse_id
            == purchase_order.warehouse_id,
        )
        .with_for_update()
        .first()
    )

    if inventory is None:
        raise ValueError(
            "Inventory record not found for purchase order"
        )

    received_quantity = purchase_order.quantity

    if received_quantity <= 0:
        raise ValueError(
            "Purchase order quantity must be greater than zero"
        )

    inventory.quantity_on_hand += received_quantity

    inventory.version += 1

    add_cost_layer(
        db=db,
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        category=inventory.category,
        quantity=received_quantity,
        unit_cost=purchase_order.unit_cost,
    )

    purchase_order.status = "received"

    try:
        db.commit()
        db.refresh(purchase_order)

    except Exception:
        db.rollback()
        raise

    return purchase_order