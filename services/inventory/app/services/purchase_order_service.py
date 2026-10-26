from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.compliance_event import SupplierComplianceState
from app.models.inventory import Inventory
from app.models.product import Product
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

from app.services.compliance_client import (
    ComplianceBlockedError,
    check_supplier_compliance,
)
from app.services.compliance_consumer import classify_compliance_status
from app.services.outbox_service import record_event
from app.services.cache_service import invalidate_inventory_cache


def generate_po_id(db: Session) -> str:
    """Canonical PO ID per blueprint section 2: PO-<year>-<6 digits>, e.g. PO-2026-000123."""
    prefix = f"PO-{datetime.now(UTC).year}-"
    last = (
        db.query(PurchaseOrder.po_id)
        .filter(PurchaseOrder.po_id.like(f"{prefix}%"))
        .order_by(PurchaseOrder.po_id.desc())
        .first()
    )
    next_number = int(last[0].removeprefix(prefix)) + 1 if last else 1
    return f"{prefix}{next_number:06d}"


@dataclass(frozen=True)
class SupplierChoice:
    supplier_id: str
    supplier_name: str
    unit_cost: float
    lead_time_days: int


def select_supplier(
    db: Session,
    sku_id: str,
):
    # Seeded catalog: each product names its supplier and unit cost (skus.csv).
    product = db.query(Product).filter(Product.sku_id == sku_id).first()
    if product is not None and product.supplier_id:
        supplier = (
            db.query(Supplier)
            .filter(Supplier.supplier_id == product.supplier_id)
            .first()
        )
        if supplier is not None:
            return SupplierChoice(
                supplier_id=supplier.supplier_id,
                supplier_name=supplier.supplier_name,
                unit_cost=product.unit_cost,
                lead_time_days=supplier.lead_time_days,
            )

    # No catalog entry: fall back to per-SKU supplier rows, cheapest first.
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


def determine_approval_status(
    expected_cost: float,
) -> str:
    """
    Determine whether a purchase order can be
    automatically approved or requires VP Operations approval.
    """

    if (
        expected_cost
        <= settings.PO_AUTO_APPROVAL_THRESHOLD
    ):
        return "approved"

    return "pending_vp_approval"


def check_supplier_before_po(
    supplier_id: str,
    supplier_name: str,
):
    """
    Check the selected supplier with Compliance Service
    before creating an automatic purchase order.

    Raises ComplianceBlockedError for BLOCK / REVIEW, and
    ComplianceServiceError when no usable decision came back.
    """

    compliance_result = check_supplier_compliance(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        country=settings.DEFAULT_SUPPLIER_COUNTRY,
    )

    if compliance_result["decision"] != "CLEAR":
        raise ComplianceBlockedError(
            supplier_id=supplier_id,
            decision=compliance_result["decision"],
            reason=(
                compliance_result.get("reason")
                or "No reason given"
            ),
        )

    return compliance_result


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
        "supplier_name": supplier.supplier_name,
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


def _initial_po_status(db: Session, supplier_id: str) -> tuple[str, str | None, str | None]:
    """Draft POs for a blocked / under-review supplier start on hold."""
    db.query(Supplier).filter(Supplier.supplier_id == supplier_id).with_for_update().first()
    state = (
        db.query(SupplierComplianceState)
        .filter(SupplierComplianceState.supplier_id == supplier_id)
        .first()
    )
    if state is not None and classify_compliance_status(state.last_status) in ("BLOCKED", "NEEDS_REVIEW"):
        return "on_hold", state.last_reason or f"Supplier compliance status: {state.last_status}", "compliance"
    return "draft", None, None


def create_draft_po_for_inventory(
    db: Session,
    inventory: Inventory,
):
    """
    Automatically create a draft PO when inventory
    falls below its reorder point.
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

    check_supplier_before_po(
        supplier_id=po_details["supplier_id"],
        supplier_name=po_details["supplier_name"],
    )

    approval_status = determine_approval_status(
        expected_cost=po_details["expected_cost"],
    )

    po_status, hold_reason, hold_source = _initial_po_status(db, po_details["supplier_id"])

    purchase_order = PurchaseOrder(
        po_id=generate_po_id(db),
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        supplier_id=po_details["supplier_id"],
        quantity=po_details["quantity"],
        unit_cost=po_details["unit_cost"],
        expected_cost=po_details["expected_cost"],
        status=po_status,
        approval_status=approval_status,
        hold_reason=hold_reason,
        hold_source=hold_source,
    )

    db.add(purchase_order)

    # Transactional Outbox: Write inventory.po.drafted in the same transaction
    record_event(
        db=db,
        event_type="inventory.po.drafted",
        aggregate_type="purchase_order",
        aggregate_id=purchase_order.po_id,
        payload={
            "po_id": purchase_order.po_id,
            "sku_id": purchase_order.sku_id,
            "warehouse_id": purchase_order.warehouse_id,
            "supplier_id": purchase_order.supplier_id,
            "quantity": purchase_order.quantity,
            "unit_cost": purchase_order.unit_cost,
            "expected_cost": purchase_order.expected_cost,
            "status": purchase_order.status,
            "approval_status": purchase_order.approval_status,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

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

    Compliance must clear the selected supplier
    before the draft PO is created.
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

    check_supplier_before_po(
        supplier_id=po_details["supplier_id"],
        supplier_name=po_details["supplier_name"],
    )

    approval_status = determine_approval_status(
        expected_cost=po_details["expected_cost"],
    )

    po_status, hold_reason, hold_source = _initial_po_status(db, po_details["supplier_id"])

    purchase_order = PurchaseOrder(
        po_id=generate_po_id(db),
        sku_id=inventory.sku_id,
        warehouse_id=inventory.warehouse_id,
        supplier_id=po_details["supplier_id"],
        quantity=po_details["quantity"],
        unit_cost=po_details["unit_cost"],
        expected_cost=po_details["expected_cost"],
        status=po_status,
        approval_status=approval_status,
        hold_reason=hold_reason,
        hold_source=hold_source,
    )

    db.add(purchase_order)

    # Transactional Outbox: Write inventory.po.drafted in the same transaction
    record_event(
        db=db,
        event_type="inventory.po.drafted",
        aggregate_type="purchase_order",
        aggregate_id=purchase_order.po_id,
        payload={
            "po_id": purchase_order.po_id,
            "sku_id": purchase_order.sku_id,
            "warehouse_id": purchase_order.warehouse_id,
            "supplier_id": purchase_order.supplier_id,
            "quantity": purchase_order.quantity,
            "unit_cost": purchase_order.unit_cost,
            "expected_cost": purchase_order.expected_cost,
            "status": purchase_order.status,
            "approval_status": purchase_order.approval_status,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    try:
        db.commit()
        db.refresh(purchase_order)

    except Exception:
        db.rollback()
        raise

    return purchase_order


def approve_purchase_order(
    db: Session,
    po_id: str,
):
    """
    Approve a purchase order that requires
    VP Operations approval.
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
        raise LookupError(
            "Purchase order not found"
        )

    if purchase_order.status == "on_hold":
        raise ValueError(
            f"Cannot approve purchase order: PO is on hold ({purchase_order.hold_reason or 'compliance review'})"
        )

    if purchase_order.status != "draft":
        raise ValueError(
            "Only draft purchase orders can be approved"
        )

    if (
        purchase_order.approval_status
        != "pending_vp_approval"
    ):
        raise ValueError(
            "Purchase order does not require VP Operations approval"
        )

    purchase_order.approval_status = "approved"

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
    received_by: str,
):
    """
    Receive a purchase order (legacy).
    Delegates to record_goods_receipt with the PO's full quantity.
    """
    purchase_order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.po_id == po_id)
        .with_for_update()
        .first()
    )

    if purchase_order is None:
        raise LookupError("Purchase order not found")

    if purchase_order.status == "on_hold":
        raise ValueError(
            f"Cannot receive purchase order: PO is on hold ({purchase_order.hold_reason or 'compliance review'})"
        )

    if purchase_order.status not in ("draft", "acknowledged"):
        raise ValueError(
            "Only draft or acknowledged purchase orders can be received"
        )

    if purchase_order.approval_status != "approved":
        raise ValueError(
            "Purchase order requires VP Operations approval"
        )

    if purchase_order.quantity <= 0:
        raise ValueError(
            "Purchase order quantity must be greater than zero"
        )

    from app.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
    from app.services.goods_receipt_service import (
        invalidate_receipt_cache,
        record_goods_receipt,
    )

    receipt_data = GoodsReceiptCreate(
        po_id=purchase_order.po_id,
        warehouse_id=purchase_order.warehouse_id,
        items=[
            GoodsReceiptItemCreate(
                sku_id=purchase_order.sku_id,
                quantity_received=purchase_order.quantity,
                unit_cost=purchase_order.unit_cost,
            )
        ],
        notes="Legacy PO receive endpoint",
    )

    receipt = record_goods_receipt(
        db=db,
        data=receipt_data,
        received_by=received_by,
    )

    try:
        db.commit()
        db.refresh(purchase_order)
        invalidate_receipt_cache(db, receipt)
    except Exception:
        db.rollback()
        raise

    return purchase_order


def get_purchase_order(
    db: Session,
    po_id: str,
) -> PurchaseOrder:
    """Retrieve a purchase order by ID."""
    purchase_order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.po_id == po_id)
        .first()
    )
    if purchase_order is None:
        raise LookupError("Purchase order not found")
    return purchase_order


def list_purchase_orders(
    db: Session,
    po_id: str | None = None,
    supplier_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[PurchaseOrder]:
    """List purchase orders with optional PO ID, supplier, and status filters."""
    query = db.query(PurchaseOrder)
    if po_id:
        query = query.filter(PurchaseOrder.po_id.startswith(po_id))
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    return query.order_by(PurchaseOrder.created_at.desc()).limit(limit).all()