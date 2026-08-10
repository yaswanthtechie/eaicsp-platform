import os
import re
from pathlib import Path

from fastapi import UploadFile

from app.schemas.invoice import InvoiceCreate
from app.services.purchase_order_service import purchase_orders
from app.schemas.purchase_order import PurchaseOrderStatus
from app.core.config import UPLOAD_DIR

TOLERANCE = 0.05

# In-memory storage
invoices = {}


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


def create_invoice(invoice: InvoiceCreate):

    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice.invoice_number
    ):
        raise ValueError(
            "Invalid invoice number."
        )

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

    if invoice.po_number not in purchase_orders:
        raise ValueError(
            "Purchase Order not found."
        )

    purchase_order = purchase_orders[
        invoice.po_number
    ]

    status = purchase_order["status"]

    if status not in [
        PurchaseOrderStatus.acknowledged,
        PurchaseOrderStatus.fulfilled,
    ]:
        raise ValueError(
            f"Invoice cannot be created because "
            f"the Purchase Order is in "
            f"'{status.value}' status."
        )

    po_amount = purchase_order["total_amount"]

    minimum_amount = po_amount * (1 - TOLERANCE)
    maximum_amount = po_amount * (1 + TOLERANCE)

    if not (
        minimum_amount
        <= invoice.amount
        <= maximum_amount
    ):
        raise ValueError(
            f"Invoice amount must be between "
            f"{minimum_amount:.2f} and "
            f"{maximum_amount:.2f}."
        )

    invoice_data = invoice.model_dump()

    invoice_data["document_url"] = None

    invoices[invoice.invoice_number] = invoice_data

    return invoices[invoice.invoice_number]


def upload_invoice_document(
    invoice_number: str,
    file: UploadFile,
):

    if invoice_number not in invoices:
        raise ValueError("Invoice not found.")

    # Validate Content-Type
    if file.content_type != "application/pdf":
        raise ValueError(
            "Only PDF files are allowed."
        )

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    # Check size before reading, if available
    if getattr(file, "size", None) is not None:
        if file.size > MAX_FILE_SIZE:
            raise ValueError(
                "Maximum file size is 10 MB."
            )

    # Read file contents
    contents = file.file.read()

    # Validate actual file size
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(
            "Maximum file size is 10 MB."
        )

    # Validate PDF signature
    signature = contents[:5]

    if signature != b"%PDF-":
        raise ValueError(
            "Invalid PDF signature."
        )

    # Validate invoice number
    if not re.fullmatch(
        r"[A-Za-z0-9_-]+",
        invoice_number
    ):
        raise ValueError(
            "Invalid invoice number."
        )

    # Get supplier ID from the stored invoice
    supplier_id = invoices[
        invoice_number
    ]["supplier_id"]

    # Resolve the upload root to an absolute path
    upload_root = Path(
        UPLOAD_DIR
    ).resolve()

    # Safe invoice filename
    safe_invoice_number = os.path.basename(
        invoice_number
    )

    filename = f"{safe_invoice_number}.pdf"

    # Build supplier directory
    supplier_directory = (
        upload_root / supplier_id
    )

    # Build and resolve the final file path
    final_path = (
        supplier_directory / filename
    ).resolve()

    # Make sure the final path is actually
    # inside the uploads directory.
    #
    # is_relative_to() checks actual path
    # structure instead of comparing strings.
    if not final_path.is_relative_to(
        upload_root
    ):
        raise ValueError(
            "Invalid file path."
        )

    # Create the directory only AFTER
    # confirming the path is safe.
    supplier_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    # Save the PDF
    with open(
        final_path,
        "wb"
    ) as f:
        f.write(contents)

    # Store document path
    invoices[
        invoice_number
    ]["document_url"] = str(
        final_path
    )

    return invoices[invoice_number]


def get_invoice_document(
    invoice_number: str,
):

    if invoice_number not in invoices:
        raise ValueError(
            "Invoice not found."
        )

    filepath = invoices[
        invoice_number
    ].get(
        "document_url"
    )

    if not filepath:
        raise ValueError(
            "Document not found."
        )

    if not os.path.exists(filepath):
        raise ValueError(
            "File does not exist."
        )

    return filepath