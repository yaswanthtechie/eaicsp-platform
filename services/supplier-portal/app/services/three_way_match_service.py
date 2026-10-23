from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.invoice import InvoiceStatus
from app.schemas.purchase_order import PurchaseOrderStatus
from app.schemas.three_way_match import (
    DiscrepancyType,
    ThreeWayMatchStatus,
)

from app.services.invoice_service import (
    get_invoice_by_number,
)
from app.services.purchase_order_service import (
    get_purchase_order_by_id,
)
from app.services.goods_receipt_service import (
    get_goods_receipts_by_po,
)
from app.services.po_p2p_state_machine import (
    P2PState,
    get_p2p_state,
    transition_p2p,
    p2p_states,
)
from app.core.config import PRICE_TOLERANCE_PERCENT
from sqlalchemy import select

from app.database import SessionLocal
from app.models.inventory_goods_receipt_event import (
    InventoryGoodsReceiptEvent,
)
from app.models.po_mirror import POMirror
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

# ============================================================
# STORAGE
# ============================================================

three_way_matches: dict[tuple[str, str], dict] = {}


# ============================================================
# HELPERS
# ============================================================

def _value(value):
    """
    Return the string value when value is an Enum.
    Otherwise return the value unchanged.
    """
    if hasattr(value, "value"):
        return value.value

    return value


def _find_item(items, item_code):
    """
    Find an item by item_code.
    """
    for item in items:
        if item.get("item_code") == item_code:
            return item

    return None


def _get_purchase_order(
    po_number: str,
    supplier_id: str,
) -> dict | None:
    """Get a legacy PO first, then fall back to the canonical PO mirror."""

    # 1. Check the legacy in-memory purchase orders first.
    purchase_order = get_purchase_order_by_id(po_number)

    if purchase_order is not None:
        if purchase_order.get("supplier_id") != supplier_id:
            raise ValueError(
                "Supplier does not own this Purchase Order."
            )
        return purchase_order

    # 2. Fall back to the canonical Inventory PO mirror.
    db = SessionLocal()

    try:
        statement = select(POMirror).where(
            POMirror.supplier_id == supplier_id,
            (
                (POMirror.po_id == po_number)
                | (POMirror.po_number == po_number)
            ),
        )

        mirror = db.scalars(statement).first()

        if mirror is None:
            return None

        # Only approved Inventory POs can be matched.
        if mirror.approval_status != "approved":
            raise ValueError(
                f"Purchase Order '{po_number}' is not approved."
            )

        return {
            "po_number": mirror.po_number or mirror.po_id,
            "po_id": mirror.po_id,
            "supplier_id": mirror.supplier_id,
            "status": PurchaseOrderStatus.fulfilled.value,
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


def _get_received_quantity(
    po_number: str,
    item_identifier: str,
    supplier_id: str | None = None,
) -> float:
    """Get received quantity from Inventory events or legacy receipts."""
    purchase_order = (
        _get_purchase_order(po_number, supplier_id)
        if supplier_id
        else get_purchase_order_by_id(po_number)
    )

    if not purchase_order:
        return 0.0

    is_inventory_po = purchase_order.get("is_inventory_po") or any(
        item.get("sku_id")
        for item in purchase_order.get("items", [])
    )

    if not is_inventory_po:
        total = 0.0
        for receipt in get_goods_receipts_by_po(po_number):
            for item in receipt.get("items", []):
                if item.get("item_code") == item_identifier:
                    total += float(item.get("quantity", 0))
        return total

    db = SessionLocal()
    try:
        statement = select(InventoryGoodsReceiptEvent).where(
            InventoryGoodsReceiptEvent.po_id
            == purchase_order.get("po_id", po_number),
            InventoryGoodsReceiptEvent.supplier_id
            == purchase_order.get("supplier_id"),
        )
        events = db.scalars(statement).all()

        total = 0.0
        for record in events:
            payload = record.payload.get("payload", {})

            if payload.get("status") != "received":
                continue

            for item in payload.get("items", []):
                if item.get("sku_id") == item_identifier:
                    total += float(item.get("quantity_received", 0))

        return total
    finally:
        db.close()



def _get_invoice_quantity(
    invoice: dict,
    po_number: str,
    item_identifier: str,
    supplier_id: str | None = None,
    identifier_field: str = "item_code",
) -> float:
    """Calculate total invoiced quantity for a PO item."""
    total_invoiced = 0.0

    for item in invoice.get("items", []):
        if (
            item.get("po_number") == po_number
            and item.get(identifier_field) == item_identifier
        ):
            total_invoiced += float(item.get("quantity", 0))

    return total_invoiced

def _get_invoice_unit_price(
    invoice: dict,
    po_number: str,
    item_identifier: str,
    identifier_field: str = "item_code",
):
    """Get invoice unit price for a matching PO item."""
    for item in invoice.get("items", []):
        if (
            item.get("po_number") == po_number
            and item.get(identifier_field) == item_identifier
        ):
            return float(item.get("unit_price", 0))

    return None


def _price_difference_percentage(
    po_price: float,
    invoice_price: float,
) -> float:
    """
    Calculate absolute percentage difference between
    PO unit price and invoice unit price.
    """
    if po_price == 0:
        if invoice_price == 0:
            return 0.0

        return 100.0

    difference = abs(
        invoice_price - po_price
    )

    return round(
        (difference / po_price) * 100,
        2,
    )


def _get_invoice_po_numbers(
    invoice: dict,
) -> list[str]:
    """
    Return unique PO numbers referenced by the invoice.
    """
    if not invoice:
        return []

    return list(
        dict.fromkeys(
            item.get("po_number")
            for item in invoice.get("items", [])
            if item.get("po_number")
        )
    )


def _rollback_p2p_states(
    po_numbers: list[str],
    state: P2PState,
) -> None:
    """
    Restore P2P states after a failed multi-PO transition.
    """
    for po_number in po_numbers:
        p2p_states[po_number] = state


# ============================================================
# GET MATCH
# ============================================================

def get_three_way_match(
    supplier_id: str,
    invoice_number: str,
):
    """
    Return stored three-way match result.
    """
    match_key = (
        supplier_id,
        invoice_number,
    )

    return three_way_matches.get(match_key)


# ============================================================
# EXECUTE THREE-WAY MATCH
# ============================================================

def execute_three_way_match(
    supplier_id: str,
    invoice_number: str,
    created_by: str,
):
    """
    Compare Purchase Order, Goods Receipt, and Invoice.

    Matching result:
        Within configured price tolerance and equal quantities -> matched
        Quantity or price mismatch -> discrepancy
    """

    # 1. Find invoice
    invoice = get_invoice_by_number(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not invoice:
        raise ValueError("Invoice not found.")

    # 2. Invoice must be submitted
    invoice_status = _value(invoice.get("status"))

    if invoice_status != InvoiceStatus.submitted.value:
        raise ValueError(
            "Three-way match can only be performed "
            "for submitted invoices."
        )

    # 3. Prevent repeated matching
    existing_match = get_three_way_match(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if existing_match:
        raise ValueError(
            "Three-way match has already been performed "
            "for this invoice."
        )

    # 4. Find referenced Purchase Orders
    po_numbers = _get_invoice_po_numbers(invoice)

    if not po_numbers:
        raise ValueError(
            "Invoice does not reference any Purchase Orders."
        )

    match_lines = []
    discrepancy_types = set()

    # 5. Validate and compare each Purchase Order
    for po_number in po_numbers:
        purchase_order = _get_purchase_order(
            po_number=po_number,
            supplier_id=supplier_id,
       )

        if not purchase_order:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        # Supplier ownership
        if purchase_order.get("supplier_id") != supplier_id:
            raise ValueError(
                "Supplier does not own this Purchase Order."
            )

        # Preserve the existing lifecycle requirement
        po_status = _value(purchase_order.get("status"))

        if po_status != PurchaseOrderStatus.fulfilled.value:
            raise ValueError(
                f"Purchase Order '{po_number}' must be fulfilled "
                "before three-way matching."
            )

        # Preserve the existing P2P lifecycle requirement
        current_p2p_state = get_p2p_state(po_number)

        if current_p2p_state != P2PState.invoiced:
            raise ValueError(
                f"Purchase Order '{po_number}' must be in P2P "
                "state 'invoiced' before three-way matching."
            )

        # Compare every PO line
        for po_item in purchase_order.get("items", []):
            sku_id = po_item.get("sku_id")
            item_code = po_item.get("item_code")

            # Support both canonical Inventory lines and legacy lines.
            if sku_id:
                item_identifier = sku_id
                identifier_field = "sku_id"
            elif item_code:
                item_identifier = item_code
                identifier_field = "item_code"
            else:
                raise ValueError(
                    f"Purchase Order '{po_number}' contains an item "
                    "without sku_id or item_code."
                )

            po_quantity = float(po_item.get("quantity", 0))

            # Inventory PO contracts use unit_cost; legacy POs use unit_price.
            po_unit_price = float(
                po_item.get("unit_cost", po_item.get("unit_price", 0))
            )

            # Goods receipt quantity
            received_quantity = _get_received_quantity(
                po_number=po_number,
                item_identifier=item_identifier,
                supplier_id=supplier_id,
            )

            # Invoice quantity
            invoiced_quantity = _get_invoice_quantity(
                invoice=invoice,
                po_number=po_number,
                item_identifier=item_identifier,
                supplier_id=supplier_id,
                identifier_field=identifier_field,
            )

            # Invoice unit price
            invoice_unit_price = _get_invoice_unit_price(
                invoice=invoice,
                po_number=po_number,
                item_identifier=item_identifier,
                identifier_field=identifier_field,
            )

            if invoice_unit_price is None:
                invoice_unit_price = 0.0

            # Compare quantities across all three records
            quantity_matched = (
                po_quantity == received_quantity
                and received_quantity == invoiced_quantity
            )

            # Compare unit prices using configured tolerance
            price_difference = _price_difference_percentage(
                po_price=po_unit_price,
                invoice_price=invoice_unit_price,
            )

            price_matched = (
                price_difference <= PRICE_TOLERANCE_PERCENT
            )

            line_discrepancies = []

            if not quantity_matched:
                line_discrepancies.append(
                    DiscrepancyType.quantity_mismatch
                )
                discrepancy_types.add(
                    DiscrepancyType.quantity_mismatch
                )

            if not price_matched:
                line_discrepancies.append(
                    DiscrepancyType.price_mismatch
                )
                discrepancy_types.add(
                    DiscrepancyType.price_mismatch
                )

            # Preserve item_code in legacy response records.
            # Canonical Inventory records expose sku_id instead.
            match_line = {
                "po_number": po_number,
                "po_quantity": po_quantity,
                "received_quantity": received_quantity,
                "invoiced_quantity": invoiced_quantity,
                "po_unit_price": po_unit_price,
                "invoice_unit_price": invoice_unit_price,
                "price_difference_percentage": price_difference,
                "quantity_matched": quantity_matched,
                "price_matched": price_matched,
                "discrepancies": line_discrepancies,
            }

            if sku_id:
                match_line["sku_id"] = sku_id
            else:
                match_line["item_code"] = item_code

            match_lines.append(match_line)

    # 6. Determine overall result
    if discrepancy_types:
        match_status = ThreeWayMatchStatus.discrepancy
    else:
        match_status = ThreeWayMatchStatus.matched

    # 7. Transition all referenced P2P states
    target_state = (
        P2PState.matched
        if match_status == ThreeWayMatchStatus.matched
        else P2PState.discrepancy
    )

    transitioned = []

    try:
        for po_number in po_numbers:
            transition_p2p(
                po_number=po_number,
                target_state=target_state,
            )
            transitioned.append(po_number)

    except Exception as exc:
        _rollback_p2p_states(
            transitioned,
            P2PState.invoiced,
        )

        raise ValueError(
            f"Unable to complete three-way match: {exc}"
        ) from exc

    # 8. Create and store match record
    match_id = f"3WM-{uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    match_record = {
        "match_id": match_id,
        "supplier_id": supplier_id,
        "invoice_number": invoice_number,
        "status": match_status.value,
        "lines": match_lines,
        "discrepancies": [
            discrepancy.value
            for discrepancy in discrepancy_types
        ],
        "created_at": now,
        "created_by": created_by,
        "resolution": None,
        "resolved_at": None,
        "resolved_by": None,
        "payment_approved": False,
        "payment_approved_at": None,
        "payment_approved_by": None,
        "payment_approved_role": None,
    }

    three_way_matches[(supplier_id, invoice_number)] = match_record

    return match_record



# ============================================================
# RESOLVE DISCREPANCY
# ============================================================

def resolve_three_way_discrepancy(
    supplier_id: str,
    invoice_number: str,
    reason: str,
    resolved_by: str,
    resolved_role: str,
):
    """
    Resolve a discrepancy after human review.

    P2P:
        discrepancy -> matched
    """

    match = get_three_way_match(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not match:
        raise ValueError(
            "Three-way match record not found."
        )

    if (
        match.get("status")
        != ThreeWayMatchStatus.discrepancy.value
    ):
        raise ValueError(
            "Only a three-way match with discrepancy "
            "status can be resolved."
        )

    if not reason or not reason.strip():
        raise ValueError(
            "Resolution reason is required."
        )

    invoice = get_invoice_by_number(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not invoice:
        raise ValueError(
            "Invoice not found."
        )

    po_numbers = _get_invoice_po_numbers(
        invoice
    )

    if not po_numbers:
        raise ValueError(
            "Invoice does not reference any Purchase Orders."
        )

    transitioned = []

    try:

        for po_number in po_numbers:

            current_state = get_p2p_state(
                po_number
            )

            if current_state != P2PState.discrepancy:
                raise ValueError(
                    f"Purchase Order '{po_number}' "
                    "is not in P2P state 'discrepancy'."
                )

            transition_p2p(
                po_number=po_number,
                target_state=P2PState.matched,
            )

            transitioned.append(
                po_number
            )

    except Exception as exc:

        _rollback_p2p_states(
            transitioned,
            P2PState.discrepancy,
        )

        raise ValueError(
            f"Unable to resolve discrepancy: {exc}"
        )

    now = datetime.now(
        timezone.utc
    )

    match["status"] = (
        ThreeWayMatchStatus.matched.value
    )

    match["resolution"] = {
        "reason": reason,
        "resolved_at": now,
        "resolved_by": resolved_by,
        "resolved_role": resolved_role,
    }

    match["resolved_at"] = now
    match["resolved_by"] = resolved_by

    return match


# ============================================================
# PAYMENT APPROVAL
# ============================================================

def approve_payment(
    supplier_id: str,
    invoice_number: str,
    approved_by: str,
    approved_role: str,
):
    """
    Approve payment only after successful matching.

    P2P state transition:
        matched -> payment_approved
    """

    match = get_three_way_match(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not match:
        raise ValueError(
            "Three-way match record not found."
        )

    if (
        match.get("status")
        != ThreeWayMatchStatus.matched.value
    ):
        raise ValueError(
            "Payment can only be approved "
            "after the three-way match is matched."
        )

    if match.get("payment_approved"):
        raise ValueError(
            "Payment has already been approved."
        )

    invoice = get_invoice_by_number(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not invoice:
        raise ValueError(
            "Invoice not found."
        )

    po_numbers = _get_invoice_po_numbers(
        invoice
    )

    if not po_numbers:
        raise ValueError(
            "Invoice does not reference any Purchase Orders."
        )

    transitioned = []

    try:

        for po_number in po_numbers:

            current_state = get_p2p_state(
                po_number
            )

            if current_state != P2PState.matched:
                raise ValueError(
                    f"Purchase Order '{po_number}' "
                    "must be in P2P state 'matched' "
                    "before payment approval."
                )

            transition_p2p(
                po_number=po_number,
                target_state=P2PState.payment_approved,
            )

            transitioned.append(
                po_number
            )

    except Exception as exc:

        _rollback_p2p_states(
            transitioned,
            P2PState.matched,
        )

        raise ValueError(
            f"Unable to approve payment: {exc}"
        )

    now = datetime.now(
        timezone.utc
    )

    match["payment_approved"] = True
    match["payment_approved_at"] = now
    match["payment_approved_by"] = approved_by
    match["payment_approved_role"] = approved_role

    return {
        "supplier_id": supplier_id,
        "invoice_number": invoice_number,
        "payment_status": (
            P2PState.payment_approved.value
        ),
        "approved_at": now,
        "approved_by": approved_by,
        "approved_role": approved_role,
    }

