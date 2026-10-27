import re

from datetime import datetime, timezone

from fastapi import UploadFile

from app.services.purchase_order_service import purchase_orders
from app.schemas.purchase_order import PurchaseOrderStatus
from app.services.document_storage_service import (
    DocumentUploadError,
    DocumentStorageError,
    document_storage_service,
)

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceStatus,
    InvoiceAdjustment,
)
from app.services.po_p2p_state_machine import (
    P2PState,
    get_p2p_state,
    initialize_p2p_state,
    transition_p2p,
)
from app.services.canonical_po_service import (
    get_canonical_po,
    has_inventory_receipt,
)


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

def _get_invoice_po(
    po_number: str,
    supplier_id: str,
) -> dict | None:
    """
    Return the PO an invoice line refers to: a legacy in-memory PO
    first, then an approved Inventory PO from po_mirror.
    """
    purchase_order = purchase_orders.get(po_number)

    if purchase_order is not None:
        return purchase_order

    return get_canonical_po(po_number, supplier_id)


def _line_id(item: dict) -> str | None:
    """Inventory lines are identified by sku_id, legacy lines by item_code."""
    return item.get("sku_id") or item.get("item_code")

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
                and _line_id(item) == item_code
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

            if _line_id(item) == item_code:
                return item

    return None


def _validate_invoice_line_item(
    invoice_item: dict,
    supplier_id: str,
    exclude_invoice_number: str | None = None,
):
    """
    Validate one invoice line against its Purchase Order.

    Supports:
    - Legacy PO lines using item_code and unit_price
    - Inventory PO lines using sku_id and unit_cost
    """

    po_number = invoice_item["po_number"]
    item_code = _line_id(invoice_item)

    if not item_code:
        raise ValueError(
            "Invoice line must contain either sku_id or item_code."
        )

    invoice_quantity = invoice_item["quantity"]
    invoice_unit_price = invoice_item["unit_price"]

    # 1. Get legacy or canonical Inventory PO.
    purchase_order = _get_invoice_po(
        po_number,
        supplier_id,
    )

    if purchase_order is None:
        raise ValueError(
            f"Purchase Order '{po_number}' not found."
        )

    # 2. Validate supplier ownership.
    if purchase_order.get("supplier_id") != supplier_id:
        raise ValueError(
            f"Purchase Order '{po_number}' does not belong "
            f"to supplier '{supplier_id}'."
        )

    # 3. Validate PO status.
    status = purchase_order.get("status")

    status_value = (
        status.value
        if isinstance(status, PurchaseOrderStatus)
        else status
    )

    allowed_statuses = {
        PurchaseOrderStatus.acknowledged.value,
        PurchaseOrderStatus.fulfilled.value,
    }

    if status_value not in allowed_statuses:
        raise ValueError(
            f"Invoice cannot be created because "
            f"Purchase Order '{po_number}' is in "
            f"'{status_value}' status."
        )

    # 4. Validate invoice quantity.
    if invoice_quantity <= 0:
        raise ValueError(
            f"Invoice quantity for item '{item_code}' "
            "must be greater than zero."
        )

    # 5. Find matching PO line.
    po_item = _find_po_item(
        purchase_order,
        item_code,
    )

    if po_item is None:
        raise ValueError(
            f"Item '{item_code}' does not exist "
            f"in Purchase Order '{po_number}'."
        )

    # 6. Validate remaining quantity.
    ordered_quantity = po_item.get("quantity")

    if ordered_quantity is None:
        raise ValueError(
            f"Purchase Order line '{item_code}' "
            "does not contain a quantity."
        )

    already_invoiced_quantity = (
        _get_existing_invoiced_quantity(
            supplier_id=supplier_id,
            po_number=po_number,
            item_code=item_code,
            exclude_invoice_number=exclude_invoice_number,
        )
    )

    remaining_quantity = (
        ordered_quantity - already_invoiced_quantity
    )

    if invoice_quantity > remaining_quantity:
        raise ValueError(
            f"Invoice quantity for item '{item_code}' "
            "cannot exceed the remaining quantity. "
            f"Ordered: {ordered_quantity}, "
            f"Already invoiced: {already_invoiced_quantity}, "
            f"Remaining: {remaining_quantity}, "
            f"Requested: {invoice_quantity}."
        )

    # 7. Capture PO price for three-way matching.
    # Legacy PO: unit_price
    # Inventory PO: unit_cost
    po_price = po_item.get(
        "unit_price",
        po_item.get("unit_cost"),
    )

    if po_price is None:
        raise ValueError(
            f"Purchase Order line '{item_code}' "
            "does not contain unit_price or unit_cost."
        )

    po_unit_price = float(po_price)

    # Do not reject price differences here.
    # The three-way matching process must flag discrepancies.

    # 8. Return normalized validation details.
    return {
        "po_number": po_number,
        "item_code": item_code,
        "sku_id": po_item.get("sku_id"),
        "ordered_quantity": ordered_quantity,
        "already_invoiced_quantity": already_invoiced_quantity,
        "remaining_quantity": remaining_quantity,
        "invoice_quantity": invoice_quantity,
        "po_unit_price": po_unit_price,
        "invoice_unit_price": invoice_unit_price,
    }

def _get_unique_invoice_po_numbers(invoice: InvoiceCreate) -> list[str]:
    """
    Return unique Purchase Orders referenced by the invoice,
    preserving the original order.
    """
    return list(
        dict.fromkeys(
            item.po_number
            for item in invoice.items
        )
    )

def _validate_p2p_invoice_state(
    invoice: InvoiceCreate,
) -> list[str]:
    """
    Validate every PO before invoice creation.

    Inventory POs require an actual goods-received event.
    This function does not modify P2P states.
    """

    po_numbers = _get_unique_invoice_po_numbers(invoice)

    for po_number in po_numbers:
        purchase_order = _get_invoice_po(
            po_number,
            invoice.supplier_id,
        )

        if purchase_order is None:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        if purchase_order.get("supplier_id") != invoice.supplier_id:
            raise ValueError(
                f"Purchase Order '{po_number}' does not belong "
                f"to supplier '{invoice.supplier_id}'."
            )

        po_status = purchase_order.get("status")

        po_status_value = (
            po_status.value
            if isinstance(po_status, PurchaseOrderStatus)
            else po_status
        )

        allowed_statuses = {
            PurchaseOrderStatus.acknowledged.value,
            PurchaseOrderStatus.fulfilled.value,
        }

        if po_status_value not in allowed_statuses:
            raise ValueError(
                f"Purchase Order '{po_number}' has status "
                f"'{po_status_value}' and cannot be invoiced."
            )

        current_state = get_p2p_state(po_number)

        if purchase_order.get("is_inventory_po"):
            if current_state is None:
                if not has_inventory_receipt(
                    purchase_order["po_id"],
                    invoice.supplier_id,
                ):
                    raise ValueError(
                        f"Purchase Order '{po_number}' cannot be "
                        "invoiced before Inventory has received "
                        "the goods."
                    )

                # Do not initialize here.
                # Initialization happens after every validation passes.
                continue

        if current_state is None:
            raise ValueError(
                f"P2P workflow state is not initialized "
                f"for Purchase Order '{po_number}'."
            )

        if current_state != P2PState.received:
            raise ValueError(
                f"Purchase Order '{po_number}' cannot be invoiced "
                f"from P2P state '{current_state.value}'. "
                "Invoice creation requires P2P state 'received'."
            )

    return po_numbers

def create_invoice(invoice: InvoiceCreate):
    """
    Create and submit an invoice for legacy or Inventory POs.

    Every referenced PO must be in the received P2P state.
    Inventory POs require an actual goods-received event.
    """

    # 1. Validate invoice number.
    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice.invoice_number,
    ):
        raise ValueError("Invalid invoice number.")

    # 2. Build supplier-scoped invoice key.
    invoice_key = _get_invoice_key(
        supplier_id=invoice.supplier_id,
        invoice_number=invoice.invoice_number,
    )

    # 3. Prevent duplicate invoice.
    if invoice_key in invoices:
        raise ValueError(
            f"Invoice '{invoice.invoice_number}' already exists "
            f"for supplier '{invoice.supplier_id}'."
        )

    # 4. Require at least one invoice line.
    if not invoice.items:
        raise ValueError(
            "Invoice must contain at least one item."
        )

    # 5. Prevent duplicate PO/item lines.
    seen_items = set()

    for invoice_item in invoice.items:
        line_id = (
            invoice_item.sku_id
            or invoice_item.item_code
        )

        key = (
            invoice_item.po_number,
            line_id,
        )

        if key in seen_items:
            raise ValueError(
                f"Duplicate invoice line for Purchase Order "
                f"'{invoice_item.po_number}' and item '{line_id}'."
            )

        seen_items.add(key)

    # 6. Validate all POs and P2P states.
    # No state modifications happen in this function.
    po_numbers = _validate_p2p_invoice_state(invoice)

    # 7. Validate every invoice line.
    for invoice_item in invoice.items:
        po_number = invoice_item.po_number

        purchase_order = _get_invoice_po(
            po_number,
            invoice.supplier_id,
        )

        if purchase_order is None:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        if purchase_order.get("supplier_id") != invoice.supplier_id:
            raise ValueError(
                f"Invoice supplier '{invoice.supplier_id}' does not "
                f"match Purchase Order supplier "
                f"'{purchase_order.get('supplier_id')}'."
            )

        _validate_invoice_line_item(
            invoice_item.model_dump(),
            supplier_id=invoice.supplier_id,
        )

    # 8. Calculate invoice amount.
    calculated_amount = round(
        sum(
            item.quantity * item.unit_price
            for item in invoice.items
        ),
        2,
    )

    submitted_amount = round(invoice.amount, 2)

    if submitted_amount != calculated_amount:
        raise ValueError(
            f"Invoice amount does not match the line-item total. "
            f"Expected: {calculated_amount:.2f}, "
            f"Received: {submitted_amount:.2f}."
        )

    # 9. Prepare invoice data.
    invoice_data = invoice.model_dump()

    invoice_data["amount"] = submitted_amount
    invoice_data["document_url"] = None
    invoice_data["document_path"] = None
    invoice_data["status"] = InvoiceStatus.submitted
    invoice_data["dispute"] = None
    invoice_data["history"] = []

    # 10. Capture original P2P states.
    from app.services.po_p2p_state_machine import p2p_states

    original_states = {
        po_number: get_p2p_state(po_number)
        for po_number in po_numbers
    }

    # 11. Initialize missing Inventory P2P states and transition.
    try:
        for po_number in po_numbers:
            if get_p2p_state(po_number) is None:
                purchase_order = _get_invoice_po(
                    po_number,
                    invoice.supplier_id,
                )

                if (
                    purchase_order is None
                    or not purchase_order.get("is_inventory_po")
                ):
                    raise ValueError(
                        f"P2P workflow state is not initialized "
                        f"for Purchase Order '{po_number}'."
                    )

                initialize_p2p_state(
                    po_number,
                    P2PState.received,
                )

        # Store invoice only after all validations and initialization.
        invoices[invoice_key] = invoice_data

        for po_number in po_numbers:
            transition_p2p(
                po_number,
                P2PState.invoiced,
            )

    except Exception:
        # Roll back invoice creation.
        invoices.pop(invoice_key, None)

        # Restore the exact original P2P states.
        for po_number, original_state in original_states.items():
            if original_state is None:
                p2p_states.pop(po_number, None)
            else:
                p2p_states[po_number] = original_state

        raise

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
    actor_id: str,
    actor_name: str,
    role: str,
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
        approved / rejected

    Audit identity is taken from the authenticated
    Platform user and is NOT accepted from the request body.

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
    # 4. Validate authenticated audit identity
    # ========================================================

    if actor_id is None or not str(actor_id).strip():
        raise ValueError(
            "Authenticated user ID is required."
        )

    if not actor_name or not actor_name.strip():
        raise ValueError(
            "Authenticated user name is required."
        )

    if not role or not role.strip():
        raise ValueError(
            "Authenticated user role is required."
        )

    # ========================================================
    # 5. Build supplier-scoped invoice key
    # ========================================================

    invoice_key = _get_invoice_key(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    # ========================================================
    # 6. Check invoice exists for this supplier
    # ========================================================

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    invoice = invoices[invoice_key]

    # ========================================================
    # 7. Only disputed invoices can be adjusted
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
    # 8. Validate adjustment reason
    # ========================================================

    if (
        not adjustment.reason
        or not adjustment.reason.strip()
    ):
        raise ValueError(
            "Reason is required when adjusting an invoice."
        )

    # ========================================================
    # 9. Validate adjusted items
    # ========================================================

    if not adjustment.items:
        raise ValueError(
            "Adjusted invoice must contain at least one item."
        )

    # ========================================================
    # 10. Prevent duplicate PO/item lines
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
    # 11. Validate adjusted items
    #
    # Exclude current invoice from existing quantity
    # calculation because its old quantities are being replaced.
    # ========================================================

    adjusted_items = []

    for item in adjustment.items:

        item_data = item.model_dump()

        # ----------------------------------------------------
        # 11.1 Validate PO exists
        # ----------------------------------------------------

        po_number = item_data["po_number"]

        if po_number not in purchase_orders:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        purchase_order = purchase_orders[po_number]

        # ----------------------------------------------------
        # 11.2 Validate PO belongs to supplier
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
        # 11.3 Validate invoice line
        # ----------------------------------------------------

        _validate_invoice_line_item(
            item_data,
            supplier_id=supplier_id,
            exclude_invoice_number=invoice_number,
        )

        adjusted_items.append(item_data)

    # ========================================================
    # 12. Calculate new invoice amount
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
    # 13. Store old values for audit
    # ========================================================

    old_amount = invoice["amount"]

    old_items = [
        dict(item)
        for item in invoice["items"]
    ]

    # ========================================================
    # 14. Generate UTC timestamp
    # ========================================================

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # ========================================================
    # 15. Store adjustment audit information
    #
    # IMPORTANT:
    # actor information comes from the authenticated
    # Platform user, not from the request body.
    # ========================================================

    invoice["adjustment"] = {
        "actor_id": str(actor_id),
        "actor_name": actor_name,
        "role": role,
        "reason": adjustment.reason,
        "timestamp": timestamp,
        "old_amount": old_amount,
        "new_amount": calculated_amount,
        "old_items": old_items,
        "new_items": adjusted_items,
    }

    # ========================================================
    # 16. Update invoice data
    # ========================================================

    invoice["items"] = adjusted_items
    invoice["amount"] = calculated_amount

    # ========================================================
    # 17. Change status through invoice state machine
    #
    # disputed -> adjusted
    # ========================================================

    transition_invoice(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
        actor_id=str(actor_id),
        actor_name=actor_name,
        role=role,
        target_state=InvoiceStatus.adjusted,
        reason=adjustment.reason,
    )

    # ========================================================
    # 18. Include complete supplier-scoped history
    # ========================================================

    invoice["history"] = list(
        invoice_events.get(
            invoice_key,
            [],
        )
    )

    # ========================================================
    # 19. Save using supplier-scoped key
    # ========================================================

    invoices[invoice_key] = invoice

    # ========================================================
    # 20. Return updated invoice
    # ========================================================

    return invoice

 

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

    The PDF is stored in MinIO under a supplier-scoped object key.

    Example:
        suppliers/SUP-00001/invoices/INV1001_INV1001.pdf
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
    # 5. Validate invoice exists
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    invoice = invoices[invoice_key]

    # ---------------------------------------------------------
    # 6. Validate content type
    # ---------------------------------------------------------

    if file.content_type != "application/pdf":
        raise ValueError(
            "Only PDF files are allowed."
        )

    # ---------------------------------------------------------
    # 7. Validate declared size
    # ---------------------------------------------------------

    if getattr(file, "size", None) is not None:
        if file.size > MAX_FILE_SIZE:
            raise ValueError(
                "Maximum file size is 10 MB."
            )

    # ---------------------------------------------------------
    # 8. Read contents for validation
    # ---------------------------------------------------------

    contents = file.file.read()

    # ---------------------------------------------------------
    # 9. Validate actual size
    # ---------------------------------------------------------

    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(
            "Maximum file size is 10 MB."
        )

    # ---------------------------------------------------------
    # 10. Validate PDF signature
    # ---------------------------------------------------------

    if contents[:5] != b"%PDF-":
        raise ValueError(
            "Invalid PDF signature."
        )

    # Reset pointer because MinIO upload reads from the file.
    file.file.seek(0)

    # ---------------------------------------------------------
    # 11. Upload directly to MinIO
    # ---------------------------------------------------------

    try:
        object_key = (
            document_storage_service.upload_invoice_document(
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                file=file,
            )
        )

    except DocumentUploadError:
        # Preserve the storage-specific exception.
        # The API route maps this to HTTP 502 Bad Gateway.
        raise

    # ---------------------------------------------------------
    # 12. Store MinIO object key in invoice metadata
    # ---------------------------------------------------------

    invoice["document_path"] = object_key

    # This remains the stable API endpoint.
    # It is NOT a permanent MinIO URL.
    invoice["document_url"] = (
        f"/api/v1/invoices/"
        f"{supplier_id}/"
        f"{invoice_number}/document"
    )

    invoices[invoice_key] = invoice

    # ---------------------------------------------------------
    # 13. Return updated invoice
    # ---------------------------------------------------------

    return invoice

def get_invoice_document(
    supplier_id: str,
    invoice_number: str,
):
    """
    Return the MinIO object key for an invoice document.

    This function does not return a local filesystem path
    and does not expose a permanent storage URL.
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
    # 5. Validate invoice exists
    # ---------------------------------------------------------

    if invoice_key not in invoices:
        raise ValueError(
            f"Invoice '{invoice_number}' "
            f"not found for supplier "
            f"'{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 6. Get MinIO object key
    # ---------------------------------------------------------

    document_path = invoices[
        invoice_key
    ].get(
        "document_path"
    )

    if not document_path:
        raise ValueError(
            f"Document not found for invoice "
            f"'{invoice_number}' "
            f"and supplier '{supplier_id}'."
        )

    # ---------------------------------------------------------
    # 7. Return MinIO object key
    # ---------------------------------------------------------

    return document_path

def find_orphaned_invoice_files(
    older_than_days: int = 1,
):
    """
    Find invoice PDF objects in MinIO that are considered
    orphaned.

    Invoice documents are stored under:

        suppliers/{supplier_id}/invoices/{invoice_number}.pdf

    An object is considered orphaned when:

    1. It is an invoice PDF stored in MinIO.
    2. It is older than `older_than_days`.
    3. One of the following is true:

       a) The corresponding invoice does not exist.

       b) The invoice exists but has no registered document_path.

       c) The registered document_path does not match
          the MinIO object key.

       d) The invoice exists but is still in a non-terminal
          state and the document has remained there beyond
          the configured threshold.

    Terminal invoice states:

        approved
        rejected

    Non-terminal states:

        submitted
        disputed
        adjusted

    Recently uploaded objects are never returned as orphaned.
    """

    # =========================================================
    # 1. Validate threshold
    # =========================================================

    if older_than_days < 0:
        raise ValueError(
            "older_than_days must be greater than "
            "or equal to zero."
        )

    orphaned_files = []

    now = datetime.now(
        timezone.utc
    )

    threshold_seconds = (
        older_than_days
        * 24
        * 60
        * 60
    )

    # =========================================================
    # 2. List invoice objects from MinIO
    # =========================================================

    try:
        objects = (
            document_storage_service.list_objects(
                prefix="suppliers/"
            )
        )

    except DocumentStorageError:
        # Storage outage, not a bad request: the route maps it to 502.
        raise

    # =========================================================
    # 3. Inspect every MinIO object
    # =========================================================

    for obj in objects:

        object_key = obj.object_name

        # -----------------------------------------------------
        # Only inspect supplier invoice objects.
        #
        # Expected:
        #
        # suppliers/SUP-00001/invoices/INV1001.pdf
        # -----------------------------------------------------

        parts = object_key.split("/")

        if len(parts) != 4:
            continue

        if parts[0] != "suppliers":
            continue

        if parts[2] != "invoices":
            continue

        file_name = parts[3]

        # -----------------------------------------------------
        # Only PDF invoice documents
        # -----------------------------------------------------

        if not file_name.lower().endswith(
            ".pdf"
        ):
            continue

        supplier_id = parts[1]

        # -----------------------------------------------------
        # Extract invoice number
        #
        # INV1001.pdf -> INV1001
        # -----------------------------------------------------

        invoice_number = file_name[
            :-len(".pdf")
        ]

        if not invoice_number:
            continue

        # =====================================================
        # 4. Get MinIO object modification time
        # =====================================================

        last_modified = obj.last_modified

        if last_modified is None:
            continue

        if last_modified.tzinfo is None:
            last_modified = (
                last_modified.replace(
                    tzinfo=timezone.utc
                )
            )
        else:
            last_modified = (
                last_modified.astimezone(
                    timezone.utc
                )
            )

        file_age_seconds = (
            now - last_modified
        ).total_seconds()

        # -----------------------------------------------------
        # Protect recent files
        # -----------------------------------------------------

        if file_age_seconds < threshold_seconds:
            continue

        file_age_days = round(
            file_age_seconds
            / (24 * 60 * 60),
            2,
        )

        size_bytes = getattr(
            obj,
            "size",
            0,
        )

        # =====================================================
        # 5. Supplier-scoped invoice lookup
        # =====================================================

        invoice_key = (
            supplier_id,
            invoice_number,
        )

        invoice = invoices.get(
            invoice_key
        )

        base_data = {
            "invoice_number": invoice_number,
            "supplier_id": supplier_id,
            "file_path": object_key,
            "file_name": file_name,
            "size_bytes": size_bytes,
            "file_age_days": file_age_days,
        }

        # =====================================================
        # CASE A
        #
        # MinIO object exists but invoice does not.
        # =====================================================

        if invoice is None:

            orphaned_files.append(
                {
                    **base_data,
                    "invoice_status": None,
                    "reason": (
                        "No matching invoice record exists."
                    ),
                }
            )

            continue

        # =====================================================
        # 6. Normalize invoice status
        # =====================================================

        status = invoice.get(
            "status"
        )

        if isinstance(
            status,
            str,
        ):
            try:
                status = InvoiceStatus(
                    status
                )

            except ValueError:
                status = None

        # =====================================================
        # 7. Terminal invoices are protected
        #
        # Approved and rejected invoices are completed.
        # Their documents must NOT be orphaned.
        # =====================================================

        terminal_states = {
            InvoiceStatus.approved,
            InvoiceStatus.rejected,
        }

        if status in terminal_states:
            continue

        # =====================================================
        # 8. Get registered MinIO object key
        # =====================================================

        document_path = invoice.get(
            "document_path"
        )

        # =====================================================
        # CASE B
        #
        # Invoice exists but document is not registered.
        # =====================================================

        if not document_path:

            orphaned_files.append(
                {
                    **base_data,
                    "invoice_status": (
                        status.value
                        if status is not None
                        else None
                    ),
                    "reason": (
                        "Invoice is not in a terminal "
                        "state and the file is not "
                        "registered as its document."
                    ),
                }
            )

            continue

        # =====================================================
        # CASE C
        #
        # Object exists under a different key than the one
        # registered against the invoice.
        # =====================================================

        if document_path != object_key:

            orphaned_files.append(
                {
                    **base_data,
                    "invoice_status": (
                        status.value
                        if status is not None
                        else None
                    ),
                    "reason": (
                        "File object key does not match "
                        "the invoice document."
                    ),
                }
            )

            continue

        # =====================================================
        # CASE D
        #
        # Invoice exists and object is its registered document,
        # but invoice is still non-terminal beyond threshold.
        # =====================================================

        orphaned_files.append(
            {
                **base_data,
                "invoice_status": (
                    status.value
                    if status is not None
                    else None
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
    Delete invoice PDF objects identified as orphaned
    from MinIO.

    Only objects returned by
    find_orphaned_invoice_files() are considered.

    Recently uploaded objects are protected by the same
    age threshold.
    """

    # =========================================================
    # 1. Find orphaned MinIO objects
    # =========================================================

    orphaned_files = (
        find_orphaned_invoice_files(
            older_than_days=older_than_days,
        )
    )

    deleted_files = []

    # =========================================================
    # 2. Delete each orphan from MinIO
    # =========================================================

    for orphan in orphaned_files:

        object_key = orphan[
            "file_path"
        ]

        try:

            document_storage_service.delete_object(
                object_key=object_key,
            )

            deleted_files.append(
                orphan
            )

        except DocumentStorageError:
            # One object failing to delete must not prevent
            # the remaining orphaned objects from processing.
            continue

    # =========================================================
    # 3. Return purge result
    # =========================================================

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