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


def create_automatic_draft_po(
    db: Session,
    data: PurchaseOrderRequest,
):

    # --------------------------------------------------
    # 1. Find inventory
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 2. Calculate reorder point
    # --------------------------------------------------

    reorder_data = calculate_reorder_point(
        db=db,
        inventory=inventory,
    )

    reorder_point = reorder_data[
        "reorder_point"
    ]

    rolling_avg_demand = reorder_data[
        "rolling_avg_demand"
    ]

    # --------------------------------------------------
    # 3. Check whether reorder is required
    # --------------------------------------------------

    if (
        inventory.quantity_on_hand
        >= reorder_point
    ):
        raise ValueError(
            "Reorder is not required for this inventory"
        )

    # --------------------------------------------------
    # 4. Calculate suggested quantity
    # --------------------------------------------------

    suggested_quantity = max(
        int(
            reorder_point
            - inventory.quantity_on_hand
        ),
        1,
    )

    # --------------------------------------------------
    # 5. Select supplier automatically
    # --------------------------------------------------

    supplier = select_supplier(
        db=db,
        sku_id=data.sku_id,
    )

    # --------------------------------------------------
    # 6. Calculate expected cost
    # --------------------------------------------------

    expected_cost = (
        suggested_quantity
        * supplier.unit_cost
    )

    # --------------------------------------------------
    # 7. Create Draft PO
    # --------------------------------------------------

    purchase_order = PurchaseOrder(

        po_id=generate_po_id(),

        sku_id=data.sku_id,

        warehouse_id=data.warehouse_id,

        supplier_id=supplier.supplier_id,

        quantity=suggested_quantity,

        unit_cost=supplier.unit_cost,

        expected_cost=expected_cost,

        status="draft",
    )

    db.add(purchase_order)

    db.commit()

    db.refresh(purchase_order)

    return purchase_order