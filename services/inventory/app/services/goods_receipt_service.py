from datetime import UTC, datetime
import logging
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.purchase_order import PurchaseOrder
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.cache_service import invalidate_inventory_cache
from app.services.outbox_service import record_event
from app.services.valuation_service import add_cost_layer

logger = logging.getLogger(__name__)


def generate_goods_receipt_id(db: Session) -> str:
    """Canonical Goods Receipt ID per blueprint Section 2: GR-<year>-<6 digits>, e.g. GR-2026-000077."""
    # Serialise GR numbering until commit (Postgres). SQLite tests run single-threaded.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('inventory.goods_receipt_id'))"))

    prefix = f"GR-{datetime.now(UTC).year}-"
    last = (
        db.query(GoodsReceipt.receipt_id)
        .filter(GoodsReceipt.receipt_id.like(f"{prefix}%"))
        .order_by(GoodsReceipt.receipt_id.desc())
        .first()
    )
    next_number = int(last[0].removeprefix(prefix)) + 1 if last else 1
    return f"{prefix}{next_number:06d}"


def record_goods_receipt(
    db: Session,
    data: GoodsReceiptCreate,
    received_by: str,
) -> GoodsReceipt:
    """
    Record physical receipt of goods against an approved purchase order (Flow B).

    Important Transaction Boundary Guarantees:
    - This function does NOT commit the transaction.
    - Locks the PO with `with_for_update()`.
    - Validates PO approval status and ensures PO is not on hold.
    - Validates that received SKUs match the purchase order.
    - Updates stock in inventory_ledger, appends cost layers, and invalidates cache.
    - Inserts GoodsReceipt and GoodsReceiptItem records.
    - Writes the 'inventory.goods.received' outbox event atomically.
    - Updates the PO status to 'received' (if full) or 'partially_received' (if short).
    - The caller commits once so stock, receipt entity, and outbox event all succeed or fail together.
    """
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.po_id == data.po_id)
        .with_for_update()
        .first()
    )

    if po is None:
        raise LookupError(f"Purchase order {data.po_id} not found")

    if po.status == "on_hold" or po.hold_reason is not None:
        raise ValueError(
            f"Cannot receive purchase order: PO is on hold ({po.hold_reason or 'compliance review'})"
        )

    if po.approval_status != "approved":
        raise ValueError("Purchase order is not approved")

    if po.status == "received":
        raise ValueError(f"Purchase order {data.po_id} is already received")

    if data.warehouse_id != po.warehouse_id:
        raise ValueError(
            f"Warehouse ID '{data.warehouse_id}' does not match purchase order warehouse '{po.warehouse_id}'"
        )

    # 1. Validate all SKUs belong to PO before applying any modifications
    for item in data.items:
        if item.sku_id != po.sku_id:
            raise ValueError(
                f"SKU {item.sku_id} does not belong to purchase order {po.po_id}"
            )
        if item.quantity_received <= 0:
            raise ValueError("Quantity received must be greater than zero")

    # 1b. Never receive more than is still outstanding on the PO
    prior_received_qty = (
        db.query(func.coalesce(func.sum(GoodsReceiptItem.quantity_received), 0))
        .join(GoodsReceipt, GoodsReceipt.receipt_id == GoodsReceiptItem.receipt_id)
        .filter(GoodsReceipt.po_id == po.po_id, GoodsReceiptItem.sku_id == po.sku_id)
        .scalar()
    ) or 0
    current_batch_qty = sum(item.quantity_received for item in data.items)
    outstanding = po.quantity - prior_received_qty
    if current_batch_qty > outstanding:
        raise ValueError(
            f"Receiving {current_batch_qty} units exceeds the {outstanding} "
            f"still outstanding on purchase order {po.po_id}"
        )

    # 2. Update stock & cost layers for each item
    for item in data.items:
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.sku_id == item.sku_id,
                Inventory.warehouse_id == data.warehouse_id,
            )
            .with_for_update()
            .first()
        )

        if inventory is None:
            raise ValueError(
                f"Inventory record not found for SKU {item.sku_id} at warehouse {data.warehouse_id}"
            )

        unit_cost = item.unit_cost if item.unit_cost is not None else po.unit_cost

        inventory.quantity_on_hand += item.quantity_received
        inventory.version += 1

        add_cost_layer(
            db=db,
            sku_id=inventory.sku_id,
            warehouse_id=inventory.warehouse_id,
            category=inventory.category,
            quantity=item.quantity_received,
            unit_cost=unit_cost,
        )

    # 3. Insert goods receipt and receipt line items
    receipt_id = generate_goods_receipt_id(db)
    received_at = datetime.now(UTC)

    receipt = GoodsReceipt(
        receipt_id=receipt_id,
        po_id=po.po_id,
        supplier_id=po.supplier_id,
        warehouse_id=data.warehouse_id,
        received_by=received_by,
        received_at=received_at,
        status="received",
        notes=data.notes,
    )
    db.add(receipt)

    for item in data.items:
        unit_cost = item.unit_cost if item.unit_cost is not None else po.unit_cost
        gr_item = GoodsReceiptItem(
            receipt_id=receipt_id,
            sku_id=item.sku_id,
            quantity_received=item.quantity_received,
            unit_cost=unit_cost,
        )
        db.add(gr_item)

    # 4. Check whether PO is fully received or partially received
    total_received = prior_received_qty + current_batch_qty

    if total_received >= po.quantity:
        po.status = "received"
    else:
        po.status = "partially_received"

    # 5. Emit 'inventory.goods.received' via transactional outbox
    iso_received_at = (
        received_at.isoformat().replace("+00:00", "Z")
        if received_at.tzinfo
        else received_at.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    )

    event_items = []
    for item in data.items:
        item_dict = {
            "sku_id": item.sku_id,
            "quantity_received": item.quantity_received,
        }
        cost = item.unit_cost if item.unit_cost is not None else po.unit_cost
        if cost is not None:
            item_dict["unit_cost"] = float(cost)
        event_items.append(item_dict)

    payload = {
        "receipt_id": receipt.receipt_id,
        "po_id": po.po_id,
        "supplier_id": po.supplier_id,
        "warehouse_id": receipt.warehouse_id,
        "received_by": receipt.received_by,
        "received_at": iso_received_at,
        "status": "received",
        "items": event_items,
    }
    if receipt.notes:
        payload["notes"] = receipt.notes

    record_event(
        db=db,
        event_type="inventory.goods.received",
        aggregate_type="goods_receipt",
        aggregate_id=receipt.receipt_id,
        payload=payload,
    )

    logger.info(
        "Recorded goods receipt %s for PO %s (status=%s, total_received=%d/%d)",
        receipt_id,
        po.po_id,
        po.status,
        total_received,
        po.quantity,
    )

    return receipt


def invalidate_receipt_cache(db: Session, receipt: GoodsReceipt) -> None:
    """Call AFTER commit, so readers never re-cache pre-receipt stock."""
    for item in receipt.items:
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.sku_id == item.sku_id,
                Inventory.warehouse_id == receipt.warehouse_id,
            )
            .first()
        )
        if inventory is not None:
            invalidate_inventory_cache(
                inventory.sku_id,
                inventory.warehouse_id,
                version=inventory.version,
            )


