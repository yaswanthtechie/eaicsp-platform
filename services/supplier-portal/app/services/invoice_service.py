import os
import re
from pathlib import Path
from datetime import datetime, timezone

from fastapi import UploadFile

from app.services.purchase_order_service import purchase_orders
from app.schemas.purchase_order import PurchaseOrderStatus
from app.core.config import UPLOAD_DIR

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceStatus,
    InvoiceAdjustment,
)


TOLERANCE = 0.05
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# In-memory storage
invoices = {}
# In-memory invoice status history
invoice_events = {}



def get_all_invoices():
    """
    Return all invoices.
    """
    return list(invoices.values())



def get_invoice_by_number(
    supplier_id: str,
    invoice_number: str,
):
    """
    Return an invoice using the supplier-scoped invoice key.

    The invoice is identified by:
        supplier_id + invoice_number
    """

    # ---------------------------------------------------------
    # 1. Validate supplier ID
    # ---------------------------------------------------------

    if not supplier_id or not supplier_id.strip():
        raise ValueError(
            "Supplier ID is required."
        )

    # ---------------------------------------------------------
    # 2. Validate invoice number
    # ---------------------------------------------------------

    if not invoice_number or not invoice_number.strip():
        raise ValueError(
            "Invoice number is required."
        )

    # ---------------------------------------------------------
    # 3. Validate invoice number format
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 4. Build supplier-scoped key
    # ---------------------------------------------------------

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ---------------------------------------------------------
    # 5. Check invoice exists
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        # IMPORTANT:
        # Keep this exact message because your tests expect it.
        raise ValueError(
            "Invoice not found."
        )

    # ---------------------------------------------------------
    # 6. Return invoice
    # ---------------------------------------------------------

    return invoices[invoice_key]

def _get_invoice_key(
    supplier_id: str,
    invoice_number: str,
):
    """
    Build the supplier-scoped invoice storage key.
    """

    return (
        supplier_id,
        invoice_number,
    )


def _get_existing_invoiced_quantity(
    supplier_id: str,
    po_number: str,
    item_code: str,
    exclude_invoice_number: str | None = None,
) -> int:
    """
    Calculate the quantity already invoiced for a PO line.

    Rejected invoices do NOT consume PO quantity because
    their quantities are released and can be invoiced again.

    Active invoice states:
        submitted
        disputed
        adjusted
        approved

    Rejected:
        ignored
    """

    total_quantity = 0

    for invoice_key, existing_invoice in invoices.items():

        existing_supplier_id, existing_invoice_number = (
            invoice_key
        )

        # -----------------------------------------------------
        # 1. Only count invoices belonging to this supplier
        # -----------------------------------------------------

        if existing_supplier_id != supplier_id:
            continue

        # -----------------------------------------------------
        # 2. Don't count the current invoice during adjustment
        # -----------------------------------------------------

        if (
            exclude_invoice_number is not None
            and existing_invoice_number
            == exclude_invoice_number
        ):
            continue

        # -----------------------------------------------------
        # 3. Get invoice status
        # -----------------------------------------------------

        status = existing_invoice.get("status")

        if isinstance(status, str):
            status = InvoiceStatus(status)

        # -----------------------------------------------------
        # 4. Rejected invoices do not consume PO quantity
        # -----------------------------------------------------

        if status == InvoiceStatus.rejected:
            continue

        # -----------------------------------------------------
        # 5. Count matching PO/item quantities
        # -----------------------------------------------------

        for item in existing_invoice.get("items", []):

            if (
                item["po_number"] == po_number
                and item["item_code"] == item_code
            ):
                total_quantity += item["quantity"]

    return total_quantity


def _find_po_item(
    purchase_order: dict,
    item_code: str,
):
    """
    Find a Purchase Order line item by item code.
    """

    for item in purchase_order.get("items", []):

        if isinstance(item, dict):

            if item.get("item_code") == item_code:
                return item

    return None


def _validate_invoice_line_item(
    invoice_item: dict,
    supplier_id: str,
    exclude_invoice_number: str | None = None,
):
    """
    Validate one invoice line against its Purchase Order.

    Validation includes:

    - PO exists
    - PO belongs to the supplier
    - PO status is valid
    - item exists in the PO
    - quantity is positive
    - quantity does not exceed remaining PO quantity
    - unit price is within the configured tolerance
    """

    po_number = invoice_item["po_number"]
    item_code = invoice_item["item_code"]
    invoice_quantity = invoice_item["quantity"]
    invoice_unit_price = invoice_item["unit_price"]

    # ---------------------------------------------------------
    # 1. Validate Purchase Order exists
    # ---------------------------------------------------------

    if po_number not in purchase_orders:
        raise ValueError(
            f"Purchase Order '{po_number}' not found."
        )

    purchase_order = purchase_orders[po_number]

    # ---------------------------------------------------------
    # 2. Validate Purchase Order belongs to supplier
    # ---------------------------------------------------------

    if purchase_order["supplier_id"] != supplier_id:
        raise ValueError(
            f"Purchase Order '{po_number}' does not belong "
            f"to supplier '{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 3. Validate Purchase Order status
    # ---------------------------------------------------------

    status = purchase_order["status"]

    if status not in [
        PurchaseOrderStatus.acknowledged,
        PurchaseOrderStatus.fulfilled,
    ]:
        raise ValueError(
            f"Invoice cannot be created because "
            f"Purchase Order '{po_number}' is in "
            f"'{status.value}' status."
        )

    # ---------------------------------------------------------
    # 4. Validate invoice quantity
    # ---------------------------------------------------------

    if invoice_quantity <= 0:
        raise ValueError(
            f"Invoice quantity for item '{item_code}' "
            f"must be greater than zero."
        )

    # ---------------------------------------------------------
    # 5. Find matching PO line item
    # ---------------------------------------------------------

    po_item = _find_po_item(
        purchase_order,
        item_code,
    )

    if po_item is None:
        raise ValueError(
            f"Item '{item_code}' does not exist "
            f"in Purchase Order '{po_number}'."
        )

    # ---------------------------------------------------------
    # 6. Check remaining quantity
    # ---------------------------------------------------------

    ordered_quantity = po_item["quantity"]

    already_invoiced_quantity = (
        _get_existing_invoiced_quantity(
            supplier_id=supplier_id,
            po_number=po_number,
            item_code=item_code,
            exclude_invoice_number=exclude_invoice_number,
        )
    )

    remaining_quantity = (
        ordered_quantity
        - already_invoiced_quantity
    )

    if invoice_quantity > remaining_quantity:
        raise ValueError(
            f"Invoice quantity for item '{item_code}' "
            f"cannot exceed the remaining quantity. "
            f"Ordered: {ordered_quantity}, "
            f"Already invoiced: "
            f"{already_invoiced_quantity}, "
            f"Remaining: {remaining_quantity}, "
            f"Requested: {invoice_quantity}."
        )

    # ---------------------------------------------------------
    # 7. Validate unit price tolerance
    # ---------------------------------------------------------

    po_unit_price = float(
        po_item["unit_price"]
    )

    minimum_unit_price = (
        po_unit_price * (1 - TOLERANCE)
    )

    maximum_unit_price = (
        po_unit_price * (1 + TOLERANCE)
    )

    if not (
        minimum_unit_price
        <= invoice_unit_price
        <= maximum_unit_price
    ):
        raise ValueError(
            f"Invoice unit price for item "
            f"'{item_code}' must be between "
            f"{minimum_unit_price:.2f} and "
            f"{maximum_unit_price:.2f}."
        )

    # ---------------------------------------------------------
    # 8. Return validation details
    # ---------------------------------------------------------

    return {
        "po_number": po_number,
        "item_code": item_code,
        "ordered_quantity": ordered_quantity,
        "already_invoiced_quantity": (
            already_invoiced_quantity
        ),
        "remaining_quantity": remaining_quantity,
        "invoice_quantity": invoice_quantity,
        "po_unit_price": po_unit_price,
        "invoice_unit_price": invoice_unit_price,
    }

def create_invoice(invoice: InvoiceCreate):
    """
    Create an invoice with line-item-level reconciliation.

    Supports:

    - Multiple Purchase Orders in one invoice
    - Partial invoicing
    - Multiple items from the same PO
    - Quantity validation
    - Unit-price tolerance validation
    - Duplicate invoice protection
    """

    # ---------------------------------------------------------
    # 1. Validate invoice number
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice.invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 2. Build supplier-scoped invoice key
    # ---------------------------------------------------------

    invoice_key = _get_invoice_key(
        supplier_id=invoice.supplier_id,
        invoice_number=invoice.invoice_number,
    )

    # ---------------------------------------------------------
    # 3. Prevent duplicate invoice
    # ---------------------------------------------------------

    if invoice_key in invoices:
        raise ValueError(
            f"Invoice '{invoice.invoice_number}' "
            f"already exists for supplier "
            f"'{invoice.supplier_id}'."
        )

    # ---------------------------------------------------------
    # 4. Validate invoice contains at least one item
    # ---------------------------------------------------------

    if not invoice.items:
        raise ValueError(
            "Invoice must contain at least one item."
        )

    # ---------------------------------------------------------
    # 5. Prevent duplicate PO/item lines
    #    inside the same invoice
    # ---------------------------------------------------------

    seen_items = set()

    for invoice_item in invoice.items:

        key = (
            invoice_item.po_number,
            invoice_item.item_code,
        )

        if key in seen_items:
            raise ValueError(
                f"Duplicate invoice line for "
                f"Purchase Order "
                f"'{invoice_item.po_number}' "
                f"and item "
                f"'{invoice_item.item_code}'."
            )

        seen_items.add(key)

    # ---------------------------------------------------------
    # 6. Validate every invoice line
    # ---------------------------------------------------------

    for invoice_item in invoice.items:

        po_number = invoice_item.po_number

        # -----------------------------------------------------
        # 6.1 Validate PO exists
        # -----------------------------------------------------

        if po_number not in purchase_orders:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        purchase_order = purchase_orders[po_number]

        # -----------------------------------------------------
        # 6.2 Validate invoice supplier matches PO supplier
        # -----------------------------------------------------

        if (
            invoice.supplier_id
            != purchase_order["supplier_id"]
        ):
            raise ValueError(
                f"Invoice supplier "
                f"'{invoice.supplier_id}' "
                f"does not match Purchase Order "
                f"supplier "
                f"'{purchase_order['supplier_id']}'."
            )

        # -----------------------------------------------------
        # 6.3 Validate line item against PO
        # -----------------------------------------------------

        item_data = invoice_item.model_dump()

        _validate_invoice_line_item(
            item_data,
            supplier_id=invoice.supplier_id,
        )

    # ---------------------------------------------------------
    # 7. Calculate expected invoice amount
    # ---------------------------------------------------------

    calculated_amount = 0.0

    for invoice_item in invoice.items:

        calculated_amount += (
            invoice_item.quantity
            * invoice_item.unit_price
        )

    calculated_amount = round(
        calculated_amount,
        2,
    )

    # ---------------------------------------------------------
    # 8. Normalize submitted amount
    # ---------------------------------------------------------

    submitted_amount = round(
        invoice.amount,
        2,
    )

    # ---------------------------------------------------------
    # 9. Validate invoice amount
    # ---------------------------------------------------------

    if submitted_amount != calculated_amount:
        raise ValueError(
            f"Invoice amount does not match "
            f"the line-item total. "
            f"Expected: {calculated_amount:.2f}, "
            f"Received: {submitted_amount:.2f}."
        )

    # ---------------------------------------------------------
    # 10. Prepare invoice data
    # ---------------------------------------------------------

    invoice_data = invoice.model_dump()

    invoice_data["amount"] = submitted_amount

    invoice_data["document_url"] = None
    invoice_data["document_path"] = None

    invoice_data["status"] = (
        InvoiceStatus.submitted
    )

    invoice_data["dispute"] = None

    invoice_data["history"] = []

    # ---------------------------------------------------------
    # 11. Store invoice using supplier-scoped key
    # ---------------------------------------------------------

    invoices[invoice_key] = invoice_data

    # ---------------------------------------------------------
    # 12. Return created invoice
    # ---------------------------------------------------------

    return invoices[invoice_key]



# ---------------------------------------------------------
# Transition validation and state machine
# ---------------------------------------------------------

VALID_INVOICE_TRANSITIONS = {
    # Submitted invoice can be:
    # - approved directly
    # - disputed for review
    # - rejected
    InvoiceStatus.submitted: [
        InvoiceStatus.approved,
        InvoiceStatus.disputed,
        InvoiceStatus.rejected,
    ],

    # A disputed invoice can be resolved by:
    # - approving it
    # - adjusting it
    # - rejecting it
    InvoiceStatus.disputed: [
        InvoiceStatus.approved,
        InvoiceStatus.adjusted,
        InvoiceStatus.rejected,
    ],

    # An adjusted invoice can still be:
    # - approved
    # - rejected if the adjustment is found to be incorrect
    InvoiceStatus.adjusted: [
        InvoiceStatus.approved,
        InvoiceStatus.rejected,
    ],

    # Terminal states
    InvoiceStatus.approved: [],
    InvoiceStatus.rejected: [],
}


def add_invoice_history(
    supplier_id: str,
    invoice_number: str,
    from_status: InvoiceStatus | None,
    to_status: InvoiceStatus,
    actor_id: str,
    actor_name: str,
    role: str,
    reason: str | None = None,
):
    """
    Add an invoice status-change event to history.
    """

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    event = {
        "from_status": (
            from_status.value
            if from_status is not None
            else None
        ),
        "to_status": to_status.value,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "role": role,
        "reason": reason,
        "timestamp": timestamp,
    }

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    invoice_events.setdefault(
        invoice_key,
        [],
    ).append(event)

    return event


def transition_invoice(
    supplier_id: str,
    invoice_number: str,
    actor_id: str,
    actor_name: str,
    role: str,
    target_state: InvoiceStatus,
    reason: str | None = None,
):
    """
    Change invoice status using the invoice state machine.

    The invoice is identified using BOTH:
        supplier_id
        invoice_number

    Legal transitions:

        submitted -> approved
        submitted -> disputed
        submitted -> rejected

        disputed -> approved
        disputed -> adjusted
        disputed -> rejected

        adjusted -> approved
        adjusted -> rejected
    """

    # ---------------------------------------------------------
    # 1. Validate supplier ID
    # ---------------------------------------------------------

    if not supplier_id or not supplier_id.strip():
        raise ValueError(
            "Supplier ID is required."
        )

    # ---------------------------------------------------------
    # 2. Validate invoice number
    # ---------------------------------------------------------

    if not invoice_number or not invoice_number.strip():
        raise ValueError(
            "Invoice number is required."
        )

    # ---------------------------------------------------------
    # 3. Validate invoice number format
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 4. Build supplier-scoped invoice key
    # ---------------------------------------------------------

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ---------------------------------------------------------
    # 5. Check invoice exists for this supplier
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    invoice = invoices[invoice_key]

    # ---------------------------------------------------------
    # 6. Get current status
    # ---------------------------------------------------------

    current_state = invoice["status"]

    if isinstance(current_state, str):
        current_state = InvoiceStatus(
            current_state
        )

    # ---------------------------------------------------------
    # 7. Get allowed transitions
    # ---------------------------------------------------------

    allowed_states = VALID_INVOICE_TRANSITIONS.get(
        current_state,
        [],
    )

    # ---------------------------------------------------------
    # 8. Validate transition
    # ---------------------------------------------------------

    if target_state not in allowed_states:

        allowed = ", ".join(
            state.value
            for state in allowed_states
        )

        if not allowed:
            allowed = "none"

        raise ValueError(
            f"Cannot go from "
            f"{current_state.value} "
            f"to {target_state.value}. "
            f"Allowed: {allowed}."
        )

    # ---------------------------------------------------------
    # 9. Generate UTC timestamp
    # ---------------------------------------------------------

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # ---------------------------------------------------------
    # 10. Handle new dispute
    # ---------------------------------------------------------

    if target_state == InvoiceStatus.disputed:

        if not reason or not reason.strip():
            raise ValueError(
                "Reason is required when "
                "an invoice is disputed."
            )

        invoice["dispute"] = {
            "reason": reason,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "role": role,
            "timestamp": timestamp,
            "resolution": None,
            "resolved_by": None,
            "resolved_at": None,
        }

    # ---------------------------------------------------------
    # 11. Resolve existing dispute
    # ---------------------------------------------------------

    if (
        current_state == InvoiceStatus.disputed
        and target_state in [
            InvoiceStatus.approved,
            InvoiceStatus.adjusted,
            InvoiceStatus.rejected,
        ]
    ):

        if invoice.get("dispute"):

            invoice["dispute"]["resolution"] = (
                target_state.value
            )

            invoice["dispute"]["resolved_by"] = (
                actor_id
            )

            invoice["dispute"]["resolved_at"] = (
                timestamp
            )

    # ---------------------------------------------------------
    # 12. Handle adjusted -> rejected
    # ---------------------------------------------------------

    if (
        current_state == InvoiceStatus.adjusted
        and target_state == InvoiceStatus.rejected
    ):

        invoice["adjustment_rejection"] = {
            "actor_id": actor_id,
            "actor_name": actor_name,
            "role": role,
            "reason": reason,
            "timestamp": timestamp,
        }

    # ---------------------------------------------------------
    # 13. Change invoice status
    # ---------------------------------------------------------

    invoice["status"] = target_state

    # ---------------------------------------------------------
    # 14. Create history event
    # ---------------------------------------------------------

    add_invoice_history(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        from_status=current_state,
        to_status=target_state,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason=reason,
    )

    # ---------------------------------------------------------
    # 15. Attach complete supplier-scoped history
    # ---------------------------------------------------------

    invoice["history"] = list(
        invoice_events.get(
            invoice_key,
            [],
        )
    )

    # ---------------------------------------------------------
    # 16. Save using supplier-scoped key
    # ---------------------------------------------------------

    invoices[invoice_key] = invoice

    # ---------------------------------------------------------
    # 17. Return updated invoice
    # ---------------------------------------------------------

    return invoice


def adjust_invoice(
    supplier_id: str,
    invoice_number: str,
    adjustment: InvoiceAdjustment,
):
    """
    Adjust a disputed invoice.

    The invoice is identified using BOTH:
        supplier_id
        invoice_number

    Flow:

        disputed
            ↓
        adjust endpoint
            ↓
        adjusted
            ↓
        transition endpoint
            ↓
        approved

    This endpoint changes the actual invoice data.
    """

    # ========================================================
    # 1. Validate supplier ID
    # ========================================================

    if not supplier_id or not supplier_id.strip():
        raise ValueError(
            "Supplier ID is required."
        )

    # ========================================================
    # 2. Validate invoice number
    # ========================================================

    if not invoice_number or not invoice_number.strip():
        raise ValueError(
            "Invoice number is required."
        )

    # ========================================================
    # 3. Validate invoice number format
    # ========================================================

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ========================================================
    # 4. Build supplier-scoped invoice key
    # ========================================================

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ========================================================
    # 5. Check invoice exists for this supplier
    # ========================================================

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    invoice = invoices[invoice_key]

    # ========================================================
    # 6. Only disputed invoices can be adjusted
    # ========================================================

    current_status = invoice["status"]

    if isinstance(current_status, str):
        current_status = InvoiceStatus(
            current_status
        )

    if current_status != InvoiceStatus.disputed:
        raise ValueError(
            "Only disputed invoices can be adjusted."
        )

    # ========================================================
    # 7. Validate adjustment reason
    # ========================================================

    if (
        not adjustment.reason
        or not adjustment.reason.strip()
    ):
        raise ValueError(
            "Reason is required when adjusting an invoice."
        )

    # ========================================================
    # 8. Validate adjusted items
    # ========================================================

    if not adjustment.items:
        raise ValueError(
            "Adjusted invoice must contain at least one item."
        )

    # ========================================================
    # 9. Prevent duplicate PO/item lines
    # ========================================================

    seen_items = set()

    for item in adjustment.items:

        key = (
            item.po_number,
            item.item_code,
        )

        if key in seen_items:
            raise ValueError(
                f"Duplicate invoice line for "
                f"Purchase Order '{item.po_number}' "
                f"and item '{item.item_code}'."
            )

        seen_items.add(key)

    # ========================================================
    # 10. Validate adjusted items
    #
    # Exclude current invoice from existing quantity
    # calculation because its old quantities are being replaced.
    # ========================================================

    adjusted_items = []

    for item in adjustment.items:

        item_data = item.model_dump()

        # ----------------------------------------------------
        # 10.1 Validate PO exists
        # ----------------------------------------------------

        po_number = item_data["po_number"]

        if po_number not in purchase_orders:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        purchase_order = purchase_orders[po_number]

        # ----------------------------------------------------
        # 10.2 Validate PO belongs to supplier
        # ----------------------------------------------------

        if (
            purchase_order["supplier_id"]
            != supplier_id
        ):
            raise ValueError(
                f"Purchase Order '{po_number}' "
                f"does not belong to supplier "
                f"'{supplier_id}'."
            )

        # ----------------------------------------------------
        # 10.3 Validate invoice line
        # ----------------------------------------------------

        _validate_invoice_line_item(
            item_data,
            supplier_id=supplier_id,
            exclude_invoice_number=invoice_number,
        )

        adjusted_items.append(item_data)

    # ========================================================
    # 11. Calculate new invoice amount
    # ========================================================

    calculated_amount = 0.0

    for item in adjustment.items:

        calculated_amount += (
            item.quantity
            * item.unit_price
        )

    calculated_amount = round(
        calculated_amount,
        2,
    )

    # ========================================================
    # 12. Store old values for audit
    # ========================================================

    old_amount = invoice["amount"]

    old_items = [
        dict(item)
        for item in invoice["items"]
    ]

    # ========================================================
    # 13. Generate UTC timestamp
    # ========================================================

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # ========================================================
    # 14. Store adjustment audit information
    # ========================================================

    invoice["adjustment"] = {
        "actor_id": adjustment.actor_id,
        "actor_name": adjustment.actor_name,
        "role": adjustment.role,
        "reason": adjustment.reason,
        "timestamp": timestamp,
        "old_amount": old_amount,
        "new_amount": calculated_amount,
        "old_items": old_items,
        "new_items": adjusted_items,
    }

    # ========================================================
    # 15. Update invoice data
    # ========================================================

    invoice["items"] = adjusted_items
    invoice["amount"] = calculated_amount

    # ========================================================
    # 16. Change status through state machine
    #
    # disputed -> adjusted
    # ========================================================

    transition_invoice(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        actor_id=adjustment.actor_id,
        actor_name=adjustment.actor_name,
        role=adjustment.role,
        target_state=InvoiceStatus.adjusted,
        reason=adjustment.reason,
    )

    # ========================================================
    # 17. Include complete supplier-scoped history
    # ========================================================

    invoice["history"] = list(
        invoice_events.get(
            invoice_key,
            [],
        )
    )

    # ========================================================
    # 18. Save using supplier-scoped key
    # ========================================================

    invoices[invoice_key] = invoice

    # ========================================================
    # 19. Return updated invoice
    # ========================================================

    return invoice

 # ========================================================
    # Resolve stored invoice document path
# ========================================================

def resolve_document_path(
    document_path: str,
) -> Path:
    """
    Resolve a stored invoice document path safely
    relative to UPLOAD_DIR.
    """

    if not document_path:
        raise ValueError(
            "Document path is required."
        )

    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    relative_path = Path(
        document_path
    )

    # Stored paths must be relative to UPLOAD_DIR.
    if relative_path.is_absolute():
        raise ValueError(
            "Invalid document path."
        )

    full_path = (
        upload_root / relative_path
    ).resolve()

    # Protect against path traversal.
    if not full_path.is_relative_to(
        upload_root
    ):
        raise ValueError(
            "Invalid document path."
        )

    return full_path

# ---------------------------------------------------------
# upload_invoice_document
# ---------------------------------------------------------

def upload_invoice_document(
    supplier_id: str,
    invoice_number: str,
    file: UploadFile,
):
    """
    Upload a PDF document for an existing supplier-scoped invoice.

    The invoice is identified using BOTH:
        supplier_id
        invoice_number

    The document is stored inside the supplier-specific
    upload directory.
    """

    # ---------------------------------------------------------
    # 1. Validate supplier ID
    # ---------------------------------------------------------

    if not supplier_id or not supplier_id.strip():
        raise ValueError(
            "Supplier ID is required."
        )

    # ---------------------------------------------------------
    # 2. Validate invoice number
    # ---------------------------------------------------------

    if not invoice_number or not invoice_number.strip():
        raise ValueError(
            "Invoice number is required."
        )

    # ---------------------------------------------------------
    # 3. Validate invoice number format
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 4. Build supplier-scoped invoice key
    # ---------------------------------------------------------

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ---------------------------------------------------------
    # 5. Validate invoice exists for this supplier
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    # Get the actual stored invoice
    invoice = invoices[invoice_key]

    # ---------------------------------------------------------
    # 6. Validate Content-Type
    # ---------------------------------------------------------

    if file.content_type != "application/pdf":
        raise ValueError(
            "Only PDF files are allowed."
        )

    # ---------------------------------------------------------
    # 7. Check size before reading, if available
    # ---------------------------------------------------------

    if getattr(file, "size", None) is not None:

        if file.size > MAX_FILE_SIZE:
            raise ValueError(
                "Maximum file size is 10 MB."
            )

    # ---------------------------------------------------------
    # 8. Read file contents
    # ---------------------------------------------------------

    contents = file.file.read()

    # ---------------------------------------------------------
    # 9. Validate actual file size
    # ---------------------------------------------------------

    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(
            "Maximum file size is 10 MB."
        )

    # ---------------------------------------------------------
    # 10. Validate actual PDF signature
    # ---------------------------------------------------------

    signature = contents[:5]

    if signature != b"%PDF-":
        raise ValueError(
            "Invalid PDF signature."
        )

    # ---------------------------------------------------------
    # 11. Resolve upload root
    # ---------------------------------------------------------

    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    # ---------------------------------------------------------
    # 12. Build safe invoice filename
    # ---------------------------------------------------------

    safe_invoice_number = os.path.basename(
        invoice_number
    )

    filename = (
        f"{safe_invoice_number}.pdf"
    )

    # ---------------------------------------------------------
    # 13. Build supplier directory
    # ---------------------------------------------------------

    supplier_directory = (
        upload_root / supplier_id
    )

    # ---------------------------------------------------------
    # 14. Build and resolve final path
    # ---------------------------------------------------------

    final_path = (
        supplier_directory / filename
    ).resolve()

    # ---------------------------------------------------------
    # 15. Protect against path traversal
    # ---------------------------------------------------------

    if not final_path.is_relative_to(
        upload_root
    ):
        raise ValueError(
            "Invalid file path."
        )

    # ---------------------------------------------------------
    # 16. Create directory only after path validation
    # ---------------------------------------------------------

    supplier_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # 17. Save PDF
    # ---------------------------------------------------------

    with open(
        final_path,
        "wb",
    ) as f:
        f.write(contents)

    # ---------------------------------------------------------
    # 18. Store relative document path and public URL
    # ---------------------------------------------------------

    relative_path = (
        Path(supplier_id) / filename
    )

    invoice["document_path"] = str(
        relative_path
    ).replace("\\", "/")

    invoice["document_url"] = (
        f"/api/v1/invoices/"
        f"{supplier_id}/"
        f"{invoice_number}/document"
    )

    invoices[invoice_key] = invoice

    # ---------------------------------------------------------
    # 19. Return updated invoice
    # ---------------------------------------------------------

    return invoice

def get_invoice_document(
    supplier_id: str,
    invoice_number: str,
):
    """
    Return the stored invoice document path.

    The invoice is identified using BOTH:
        supplier_id
        invoice_number
    """

    # ---------------------------------------------------------
    # 1. Validate supplier ID
    # ---------------------------------------------------------

    if not supplier_id or not supplier_id.strip():
        raise ValueError(
            "Supplier ID is required."
        )

    # ---------------------------------------------------------
    # 2. Validate invoice number
    # ---------------------------------------------------------

    if not invoice_number or not invoice_number.strip():
        raise ValueError(
            "Invoice number is required."
        )

    # ---------------------------------------------------------
    # 3. Validate invoice number format
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 4. Build supplier-scoped invoice key
    # ---------------------------------------------------------

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ---------------------------------------------------------
    # 5. Validate invoice exists for this supplier
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 6. Get stored document path
    # ---------------------------------------------------------

    document_path = invoices[
        invoice_key
    ].get(
        "document_path"
    )

    # ---------------------------------------------------------
    # 7. Validate document is associated
    # ---------------------------------------------------------

    if not document_path:
        raise ValueError(
            f"Document not found for invoice "
            f"'{invoice_number}' "
            f"and supplier '{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 8. Resolve stored relative path safely
    # ---------------------------------------------------------

    filepath = resolve_document_path(
        document_path
    )

    # ---------------------------------------------------------
    # 9. Validate file still exists
    # ---------------------------------------------------------

    if not os.path.exists(filepath):
        raise ValueError(
            f"Invoice document does not exist for "
            f"invoice '{invoice_number}' "
            f"and supplier '{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 10. Return document path
    # ---------------------------------------------------------

    return str(filepath)


def find_orphaned_invoice_files(
    older_than_days: int = 1,
):
    """
    Find invoice PDF files that are considered orphaned.

    A file is considered orphaned when:

    1. It is a PDF inside the invoice upload directory.
    2. The file is older than `older_than_days`.
    3. One of the following is true:

       a) The corresponding invoice does not exist.

       b) The corresponding invoice exists but is NOT in
          a terminal state.

    Terminal invoice states are:

        approved
        rejected

    Non-terminal states are:

        submitted
        disputed
        adjusted

    This prevents recently uploaded files from being
    incorrectly identified as orphaned.
    """

    # ---------------------------------------------------------
    # 1. Validate threshold
    # ---------------------------------------------------------

    if older_than_days < 0:
        raise ValueError(
            "older_than_days must be greater than or equal to zero."
        )

    orphaned_files = []

    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    # ---------------------------------------------------------
    # 2. Upload directory does not exist
    # ---------------------------------------------------------

    if not upload_root.exists():
        return orphaned_files

    # ---------------------------------------------------------
    # 3. Calculate age threshold
    # ---------------------------------------------------------

    now = datetime.now(timezone.utc)

    threshold_seconds = (
        older_than_days * 24 * 60 * 60
    )

    # ---------------------------------------------------------
    # 4. Search supplier directories
    # ---------------------------------------------------------

    for supplier_directory in upload_root.iterdir():

        if not supplier_directory.is_dir():
            continue

        supplier_id = supplier_directory.name

        # -----------------------------------------------------
        # 5. Search files
        # -----------------------------------------------------

        for file_path in supplier_directory.iterdir():

            if not file_path.is_file():
                continue

            # We only manage PDF invoice files
            if file_path.suffix.lower() != ".pdf":
                continue

            # -------------------------------------------------
            # 6. Get file modification time
            #
            # This represents when the file was last uploaded/
            # modified in our local filesystem.
            # -------------------------------------------------

            try:
                file_modified_timestamp = (
                    file_path.stat().st_mtime
                )

            except OSError:
                # File may have disappeared while scanning.
                continue

            file_modified_time = datetime.fromtimestamp(
                file_modified_timestamp,
                tz=timezone.utc,
            )

            file_age_seconds = (
                now - file_modified_time
            ).total_seconds()

            # -------------------------------------------------
            # 7. Ignore recent files
            # -------------------------------------------------

            if file_age_seconds < threshold_seconds:
                continue

            # -------------------------------------------------
            # 8. Extract invoice number
            # -------------------------------------------------

            invoice_number = file_path.stem

            # -------------------------------------------------
            # 9. Build supplier-scoped invoice key
            # -------------------------------------------------

            invoice_key = (
                supplier_id,
                invoice_number,
            )

            # -------------------------------------------------
            # 10. Check whether invoice exists
            # -------------------------------------------------

            invoice = invoices.get(
                invoice_key
            )

            # -------------------------------------------------
            # Build safe relative file path
            # -------------------------------------------------

            relative_file_path = str(
                file_path.relative_to(
                    upload_root
                )
            ).replace("\\", "/")

            # -------------------------------------------------
            # CASE A:
            # No corresponding invoice exists.
            #
            # The file is orphaned.
            # -------------------------------------------------

            if invoice is None:

                orphaned_files.append(
                    {
                        "invoice_number": invoice_number,
                        "supplier_id": supplier_id,
                        "file_path": relative_file_path,
                        "file_name": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "invoice_status": None,
                        "file_age_days": round(
                            file_age_seconds / (
                                24 * 60 * 60
                            ),
                            2,
                        ),
                        "reason": (
                            "No matching invoice record exists."
                        ),
                    }
                )

                continue

            # -------------------------------------------------
            # 11. Get invoice status
            # -------------------------------------------------

            status = invoice.get(
                "status"
            )

            if isinstance(status, str):
                try:
                    status = InvoiceStatus(status)

                except ValueError:
                    status = None

            # -------------------------------------------------
            # 12. Terminal states
            #
            # Approved and rejected invoices are completed.
            # Their files must NOT be considered orphaned.
            # -------------------------------------------------

            terminal_states = {
                InvoiceStatus.approved,
                InvoiceStatus.rejected,
            }

            if status in terminal_states:
                continue

            # -------------------------------------------------
            # 13. Verify document association
            # -------------------------------------------------

            document_path = invoice.get(
                "document_path"
            )

            # -------------------------------------------------
            # Case B:
            # Invoice exists, but document_path is missing.
            #
            # The physical file has no registered association
            # with the invoice.
            # -------------------------------------------------

            if not document_path:

                orphaned_files.append(
                    {
                        "invoice_number": invoice_number,
                        "supplier_id": supplier_id,
                        "file_path": relative_file_path,
                        "file_name": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "invoice_status": (
                            status.value
                            if status is not None
                            else None
                        ),
                        "file_age_days": round(
                            file_age_seconds / (
                                24 * 60 * 60
                            ),
                            2,
                        ),
                        "reason": (
                            "Invoice is not in a terminal "
                            "state and the file is not "
                            "registered as its document."
                        ),
                    }
                )

                continue

            # -------------------------------------------------
            # 14. Verify stored document path
            # -------------------------------------------------

            try:

                stored_path = (
                    resolve_document_path(
                        document_path
                    )
                )

                current_path = (
                    file_path.resolve()
                )

            except (OSError, ValueError):

                orphaned_files.append(
                    {
                        "invoice_number": invoice_number,
                        "supplier_id": supplier_id,
                        "file_path": relative_file_path,
                        "file_name": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "invoice_status": (
                            status.value
                            if status is not None
                            else None
                        ),
                        "file_age_days": round(
                            file_age_seconds / (
                                24 * 60 * 60
                            ),
                            2,
                        ),
                        "reason": (
                            "Invoice document path "
                            "could not be resolved."
                        ),
                    }
                )

                continue

            # -------------------------------------------------
            # 15. File path does not match invoice document
            # -------------------------------------------------

            if stored_path != current_path:

                orphaned_files.append(
                    {
                        "invoice_number": invoice_number,
                        "supplier_id": supplier_id,
                        "file_path": relative_file_path,
                        "file_name": file_path.name,
                        "size_bytes": file_path.stat().st_size,
                        "invoice_status": (
                            status.value
                            if status is not None
                            else None
                        ),
                        "file_age_days": round(
                            file_age_seconds / (
                                24 * 60 * 60
                            ),
                            2,
                        ),
                        "reason": (
                            "File path does not match "
                            "the invoice document."
                        ),
                    }
                )

                continue

            # -------------------------------------------------
            # 16. Important:
            #
            # The invoice exists, is non-terminal and the
            # file belongs to it.
            #
            # According to the requirement, the invoice was
            # never completed, so this old file is orphaned.
            # -------------------------------------------------

            orphaned_files.append(
                {
                    "invoice_number": invoice_number,
                    "supplier_id": supplier_id,
                    "file_path": relative_file_path,
                    "file_name": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "invoice_status": (
                        status.value
                        if status is not None
                        else None
                    ),
                    "file_age_days": round(
                        file_age_seconds / (
                            24 * 60 * 60
                        ),
                        2,
                    ),
                    "reason": (
                        "Invoice is not in a terminal "
                        "state and has remained incomplete "
                        "beyond the configured age threshold."
                    ),
                }
            )

    return orphaned_files

def purge_orphaned_invoice_files(
    older_than_days: int = 1,
):
    """
    Delete invoice PDF files identified as orphaned.

    The same `older_than_days` threshold used by
    find_orphaned_invoice_files() is applied here.

    This protects recently uploaded files from accidental
    deletion.
    """

    # ---------------------------------------------------------
    # 1. Find only files older than the requested threshold
    # ---------------------------------------------------------

    orphaned_files = find_orphaned_invoice_files(
        older_than_days=older_than_days,
    )

    deleted_files = []

    # ---------------------------------------------------------
    # 2. Delete orphaned files
    # ---------------------------------------------------------

    for orphan in orphaned_files:

        file_path = resolve_document_path(
            orphan["file_path"]
        )

        try:

            if file_path.exists():

                file_path.unlink()

                deleted_files.append(
                    orphan
                )

        except OSError:
            # If one file cannot be deleted,
            # continue processing the remaining files.
            continue

    # ---------------------------------------------------------
    # 3. Return purge result
    # ---------------------------------------------------------

    return {
        "total": len(
            orphaned_files
        ),
        "deleted": len(
            deleted_files
        ),
        "files": deleted_files,
        "older_than_days": older_than_days,
    }