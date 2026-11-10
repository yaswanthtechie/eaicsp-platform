import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.inventory_goods_receipt_event import (
    InventoryGoodsReceiptEvent,
)
from app.models.po_mirror import POMirror
from app.schemas.purchase_order import PurchaseOrderStatus

logger = logging.getLogger(__name__)


def get_canonical_po(
    po_number: str,
    supplier_id: str,
) -> dict | None:
    """
    Return an approved Inventory PO from po_mirror as a PO dict.

    Used by invoicing and three-way matching, so both read the same
    PO. Lines keep the Inventory contract fields: sku_id, quantity,
    unit_cost. Returns None when the supplier has no such PO.
    """
    db = SessionLocal()

    try:
        mirror = db.scalars(
            select(POMirror).where(
                POMirror.supplier_id == supplier_id,
                (
                    (POMirror.po_id == po_number)
                    | (POMirror.po_number == po_number)
                ),
            )
        ).first()

        if mirror is None:
            return None

        # Only approved Inventory POs can be invoiced or matched.
        if mirror.approval_status != "approved":
            raise ValueError(
                f"Purchase Order '{po_number}' is not approved."
            )

        return {
            "po_number": mirror.po_number or mirror.po_id,
            "po_id": mirror.po_id,
            "supplier_id": mirror.supplier_id,
            "status": PurchaseOrderStatus.fulfilled,
            "items": mirror.lines or [],
            "is_inventory_po": True,
        }

    except SQLAlchemyError:
        # Compatibility with test databases where the mirror table
        # has not been created. Do not hide this error in production.
        logger.exception(
            "Failed to query PO mirror for PO %s",
            po_number,
        )
        return None

    finally:
        db.close()


def has_inventory_receipt(
    po_id: str,
    supplier_id: str,
) -> bool:
    """Return True once Inventory has reported goods received for the PO."""
    db = SessionLocal()

    try:
        event_id = db.scalars(
            select(InventoryGoodsReceiptEvent.event_id)
            .where(
                InventoryGoodsReceiptEvent.po_id == po_id,
                InventoryGoodsReceiptEvent.supplier_id == supplier_id,
            )
            .limit(1)
        ).first()

        return event_id is not None

    finally:
        db.close()