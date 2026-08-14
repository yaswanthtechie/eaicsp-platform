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
    InvoiceDispute,
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



def get_invoice_by_number(invoice_number: str):
    """
    Return invoice by invoice number.
    """

    if invoice_number not in invoices:
        raise ValueError("Invoice not found.")

    return invoices[invoice_number]


def _get_existing_invoiced_quantity(
    po_number: str,
    item_code: str,
    exclude_invoice_number: str | None = None,
) -> int:
    """
    Return total quantity already invoiced for a PO item.

    The current invoice can optionally be excluded.
    This is important when adjusting an existing invoice.
    """

    total_quantity = 0

    for invoice_number, existing_invoice in invoices.items():

        if (
            exclude_invoice_number is not None
            and invoice_number == exclude_invoice_number
        ):
            continue

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
    # 2. Validate Purchase Order status
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
    # 3. Validate invoice quantity
    # ---------------------------------------------------------

    if invoice_quantity <= 0:
        raise ValueError(
            f"Invoice quantity for item '{item_code}' "
            f"must be greater than zero."
        )

    # ---------------------------------------------------------
    # 4. Find the matching PO line item
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
    # 5. Check remaining quantity
    # ---------------------------------------------------------

    ordered_quantity = po_item["quantity"]

    already_invoiced_quantity = (
        _get_existing_invoiced_quantity(
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
    # 6. Validate unit price tolerance
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
    # 2. Prevent duplicate invoice
    # ---------------------------------------------------------

    for existing_invoice in invoices.values():

        if (
            existing_invoice["invoice_number"]
            == invoice.invoice_number
            and
            existing_invoice["supplier_id"]
            == invoice.supplier_id
        ):
            raise ValueError(
                f"Invoice '{invoice.invoice_number}' "
                f"already exists for supplier "
                f"'{invoice.supplier_id}'."
            )

    # ---------------------------------------------------------
    # 3. Validate invoice contains at least one item
    # ---------------------------------------------------------

    if not invoice.items:
        raise ValueError(
            "Invoice must contain at least one item."
        )

    # ---------------------------------------------------------
    # 4. Prevent duplicate PO/item lines inside
    #    the same invoice
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
    # 5. Validate every invoice line
    # ---------------------------------------------------------

    validated_items = []

    for invoice_item in invoice.items:

        po_number = invoice_item.po_number

        if po_number not in purchase_orders:
            raise ValueError(
                f"Purchase Order '{po_number}' not found."
            )

        purchase_order = purchase_orders[po_number]

        if invoice.supplier_id != purchase_order["supplier_id"]:
            raise ValueError(
                f"Invoice supplier '{invoice.supplier_id}' "
                f"does not match Purchase Order supplier "
                f"'{purchase_order['supplier_id']}'."
            )

        item_data = invoice_item.model_dump()

        validated_item = _validate_invoice_line_item(
            item_data,
            supplier_id=invoice.supplier_id,
        )

        validated_items.append(validated_item)

    # ---------------------------------------------------------
    # 6. Calculate expected invoice amount
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

    submitted_amount = round(
        invoice.amount,
        2,
    )

    # ---------------------------------------------------------
    # 7. Make sure invoice.amount matches
    # ---------------------------------------------------------

    if submitted_amount != calculated_amount:
        raise ValueError(
            f"Invoice amount does not match "
            f"the line-item total. "
            f"Expected: {calculated_amount:.2f}, "
            f"Received: {submitted_amount:.2f}."
        )

    # ---------------------------------------------------------
    # 8. Store invoice
    # ---------------------------------------------------------

    invoice_data = invoice.model_dump()

    invoice_data["amount"] = submitted_amount
    invoice_data["document_url"] = None
    invoice_data["status"] = InvoiceStatus.submitted
    invoice_data["dispute"] = None

    invoices[
        invoice.invoice_number
    ] = invoice_data

    return invoices[
        invoice.invoice_number
    ]
  # ---------------------------------------------------------
    #  Transition validation and state machine
  # ---------------------------------------------------------

VALID_INVOICE_TRANSITIONS = {
    InvoiceStatus.submitted: [
        InvoiceStatus.approved,
        InvoiceStatus.disputed,
        InvoiceStatus.rejected,
    ],

    InvoiceStatus.disputed: [
        InvoiceStatus.approved,
        InvoiceStatus.rejected,
    ],

    InvoiceStatus.adjusted: [
        InvoiceStatus.approved,
    ],

    InvoiceStatus.approved: [],
    InvoiceStatus.rejected: [],
}

def add_invoice_history(
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

    invoice_events.setdefault(
        invoice_number,
        [],
    ).append(event)

    return event
def transition_invoice(
    invoice_number: str,
    actor_id: str,
    actor_name: str,
    role: str,
    target_state: InvoiceStatus,
    reason: str | None = None,
):
    """
    Change invoice status using the invoice state machine.
    """

    # ---------------------------------------------------------
    # 1. Check invoice exists
    # ---------------------------------------------------------

    if invoice_number not in invoices:
        raise ValueError("Invoice not found.")

    invoice = invoices[invoice_number]

    # ---------------------------------------------------------
    # 2. Get current status
    # ---------------------------------------------------------

    current_state = invoice["status"]

    # Convert stored string to enum if necessary
    if isinstance(current_state, str):
        current_state = InvoiceStatus(current_state)

    # ---------------------------------------------------------
    # 3. Get allowed transitions
    # ---------------------------------------------------------

    allowed_states = VALID_INVOICE_TRANSITIONS.get(
        current_state,
        [],
    )

    # ---------------------------------------------------------
    # 4. Validate transition
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
    # 5. Generate timestamp
    # ---------------------------------------------------------

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # ---------------------------------------------------------
    # 6. Handle dispute
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
    # 7. Resolve dispute
    # ---------------------------------------------------------

    if (
        current_state == InvoiceStatus.disputed
        and target_state in [
            InvoiceStatus.approved,
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
    # 8. Change invoice status
    # ---------------------------------------------------------

    invoice["status"] = target_state

    # ---------------------------------------------------------
    # 9. Create history event
    # ---------------------------------------------------------

    add_invoice_history(
        invoice_number=invoice_number,
        from_status=current_state,
        to_status=target_state,
        actor_id=actor_id,
        actor_name=actor_name,
        role=role,
        reason=reason,
    )

    # ---------------------------------------------------------
    # 10. Attach complete history
    # ---------------------------------------------------------

    invoice["history"] = list(
        invoice_events.get(
            invoice_number,
            [],
        )
    )

    # ---------------------------------------------------------
    # 11. Save invoice
    # ---------------------------------------------------------

    invoices[invoice_number] = invoice

    return invoice

def adjust_invoice(
    invoice_number: str,
    adjustment: InvoiceAdjustment,
):
    """
    Adjust a disputed invoice.

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
    # 1. Check invoice exists
    # ========================================================

    if invoice_number not in invoices:
        raise ValueError(
            "Invoice not found."
        )

    invoice = invoices[invoice_number]

    # ========================================================
    # 2. Only disputed invoices can be adjusted
    # ========================================================

    if invoice["status"] != InvoiceStatus.disputed:
        raise ValueError(
            "Only disputed invoices can be adjusted."
        )

    # ========================================================
    # 3. Validate adjustment reason
    # ========================================================

    if not adjustment.reason.strip():
        raise ValueError(
            "Reason is required when adjusting an invoice."
        )

    # ========================================================
    # 4. Validate adjusted items
    # ========================================================

    if not adjustment.items:
        raise ValueError(
            "Adjusted invoice must contain at least one item."
        )

    # ========================================================
    # 5. Prevent duplicate PO/item lines
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
    # 6. Validate adjusted items
    #
    # IMPORTANT:
    # Exclude the current invoice from existing quantity
    # calculation.
    # ========================================================

    adjusted_items = []

    for item in adjustment.items:

        item_data = item.model_dump()

        _validate_invoice_line_item(
            item_data,
            supplier_id=invoice["supplier_id"],
            exclude_invoice_number=invoice_number,
        )

        adjusted_items.append(item_data)

    # ========================================================
    # 7. Calculate new invoice amount
    # ========================================================

    calculated_amount = 0.0

    for item in adjustment.items:

        calculated_amount += (
            item.quantity * item.unit_price
        )

    calculated_amount = round(
        calculated_amount,
        2,
    )

    # ========================================================
    # 8. Store old values for audit
    # ========================================================

    old_amount = invoice["amount"]

    old_items = invoice["items"]

    # ========================================================
    # 9. Generate UTC timestamp
    # ========================================================

    timestamp = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    # ========================================================
    # 10. Update invoice data
    # ========================================================

    invoice["items"] = adjusted_items

    invoice["amount"] = calculated_amount

    # ========================================================
    # 11. Change status
    #
    # disputed -> adjusted
    # ========================================================

    invoice["status"] = InvoiceStatus.adjusted

    # ========================================================
    # 12. Add status history
    # ========================================================

    add_invoice_history(
        invoice_number=invoice_number,
        from_status=InvoiceStatus.disputed,
        to_status=InvoiceStatus.adjusted,
        actor_id=adjustment.actor_id,
        actor_name=adjustment.actor_name,
        role=adjustment.role,
        reason=adjustment.reason,
    )

    # ========================================================
    # 13. Update dispute resolution information
    # ========================================================

    if invoice.get("dispute"):

        invoice["dispute"]["resolution"] = "adjusted"

        invoice["dispute"]["resolved_by"] = (
            adjustment.actor_id
        )

        invoice["dispute"]["resolved_at"] = (
            timestamp
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
    # 15. Include history in response
    # ========================================================

    invoice["history"] = invoice_events.get(
        invoice_number,
        [],
    )

    # ========================================================
    # 16. Save
    # ========================================================

    invoices[invoice_number] = invoice

    return invoice


    # ---------------------------------------------------------
    #  upload_invoice_document
    # ---------------------------------------------------------

def upload_invoice_document(
    invoice_number: str,
    file: UploadFile,
):
    """
    Upload a PDF document for an existing invoice.
    """

    # ---------------------------------------------------------
    # 1. Validate invoice exists
    # ---------------------------------------------------------

    if invoice_number not in invoices:
        raise ValueError(
            "Invoice not found."
        )

    # ---------------------------------------------------------
    # 2. Validate Content-Type
    # ---------------------------------------------------------

    if file.content_type != "application/pdf":
        raise ValueError(
            "Only PDF files are allowed."
        )

    # ---------------------------------------------------------
    # 3. Check size before reading, if available
    # ---------------------------------------------------------

    if getattr(file, "size", None) is not None:

        if file.size > MAX_FILE_SIZE:
            raise ValueError(
                "Maximum file size is 10 MB."
            )

    # ---------------------------------------------------------
    # 4. Read file contents
    # ---------------------------------------------------------

    contents = file.file.read()

    # ---------------------------------------------------------
    # 5. Validate actual file size
    # ---------------------------------------------------------

    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(
            "Maximum file size is 10 MB."
        )

    # ---------------------------------------------------------
    # 6. Validate actual PDF signature
    # ---------------------------------------------------------

    signature = contents[:5]

    if signature != b"%PDF-":
        raise ValueError(
            "Invalid PDF signature."
        )

    # ---------------------------------------------------------
    # 7. Validate invoice number
    # ---------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number,
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # ---------------------------------------------------------
    # 8. Get supplier ID from stored invoice
    # ---------------------------------------------------------

    supplier_id = invoices[
        invoice_number
    ]["supplier_id"]

    # ---------------------------------------------------------
    # 9. Resolve upload root
    # ---------------------------------------------------------

    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    # ---------------------------------------------------------
    # 10. Safe invoice filename
    # ---------------------------------------------------------

    safe_invoice_number = os.path.basename(
        invoice_number
    )

    filename = (
        f"{safe_invoice_number}.pdf"
    )

    # ---------------------------------------------------------
    # 11. Build supplier directory
    # ---------------------------------------------------------

    supplier_directory = (
        upload_root / supplier_id
    )

    # ---------------------------------------------------------
    # 12. Build and resolve final path
    # ---------------------------------------------------------

    final_path = (
        supplier_directory / filename
    ).resolve()

    # ---------------------------------------------------------
    # 13. Protect against path traversal
    # ---------------------------------------------------------

    if not final_path.is_relative_to(
        upload_root
    ):
        raise ValueError(
            "Invalid file path."
        )

    # ---------------------------------------------------------
    # 14. Create directory only after
    #     path validation
    # ---------------------------------------------------------

    supplier_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # 15. Save PDF
    # ---------------------------------------------------------

    with open(
        final_path,
        "wb",
    ) as f:
        f.write(contents)

    # ---------------------------------------------------------
    # 16. Store document path
    # ---------------------------------------------------------

    invoices[
        invoice_number
    ]["document_url"] = str(
        final_path
    )

    return invoices[
        invoice_number
    ]


def get_invoice_document(
    invoice_number: str,
):
    """
    Return the stored invoice document path.
    """

    # ---------------------------------------------------------
    # 1. Validate invoice exists
    # ---------------------------------------------------------

    if invoice_number not in invoices:
        raise ValueError(
            "Invoice not found."
        )

    # ---------------------------------------------------------
    # 2. Get document path
    # ---------------------------------------------------------

    filepath = invoices[
        invoice_number
    ].get(
        "document_url"
    )

    if not filepath:
        raise ValueError(
            "Document not found."
        )

    # ---------------------------------------------------------
    # 3. Validate file still exists
    # ---------------------------------------------------------

    if not os.path.exists(filepath):
        raise ValueError(
            "File does not exist."
        )

    return filepath


def find_orphaned_invoice_files():
    """
    Find PDF files in the upload directory that do not
    have a corresponding invoice in the in-memory invoice store.

    An orphaned file is a PDF where:

        uploads/<supplier_id>/<invoice_number>.pdf

    exists, but invoice_number does not exist in invoices.
    """

    orphaned_files = []

    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    # Upload directory does not exist
    if not upload_root.exists():
        return orphaned_files

    # Search supplier directories
    for supplier_directory in upload_root.iterdir():

        if not supplier_directory.is_dir():
            continue

        supplier_id = supplier_directory.name

        # Search files inside supplier directory
        for file_path in supplier_directory.iterdir():

            if not file_path.is_file():
                continue

            # We only manage PDF invoice files
            if file_path.suffix.lower() != ".pdf":
                continue

            invoice_number = file_path.stem

            # ------------------------------------------------
            # Invoice exists → file is NOT orphaned
            # ------------------------------------------------

            if invoice_number in invoices:

                invoice = invoices[
                    invoice_number
                ]

                # File belongs to the invoice
                document_url = invoice.get(
                    "document_url"
                )

                if document_url:

                    try:
                        stored_path = Path(
                            document_url
                        ).resolve()

                        current_path = (
                            file_path.resolve()
                        )

                        if stored_path == current_path:
                            continue

                    except OSError:
                        pass

            # ------------------------------------------------
            # Invoice does not exist or file is not the
            # invoice's registered document
            # ------------------------------------------------

            orphaned_files.append(
                {
                    "invoice_number": invoice_number,
                    "supplier_id": supplier_id,
                    "file_path": str(
                        file_path
                    ),
                    "file_name": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                }
            )

    return orphaned_files


def purge_orphaned_invoice_files():
    """
    Delete all orphaned invoice PDF files.

    Returns:
        total  -> number of orphaned files found
        deleted -> number of files successfully deleted
        files -> information about successfully deleted files
    """

    orphaned_files = find_orphaned_invoice_files()

    deleted_files = []

    for orphan in orphaned_files:

        file_path = Path(
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

    return {
        "total": len(orphaned_files),
        "deleted": len(deleted_files),
        "files": deleted_files,
    }