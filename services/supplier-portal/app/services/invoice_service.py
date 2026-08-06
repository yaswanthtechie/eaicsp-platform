import os
import re

from fastapi import UploadFile

from app.schemas.invoice import InvoiceCreate
from app.services.purchase_order_service import purchase_orders
from app.schemas.purchase_order import PurchaseOrderStatus
from app.core.config import UPLOAD_DIR

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

    minimum_amount = po_amount * 0.95

    maximum_amount = po_amount * 1.05

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
        raise ValueError("Only PDF files are allowed.")

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    # Check size before reading (if available)
    if getattr(file, "size", None) is not None:
        if file.size > MAX_FILE_SIZE:
            raise ValueError("Maximum file size is 10 MB.")

    # Read file in bytes.
    contents = file.file.read()

    # Fallback size validation
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError("Maximum file size is 10 MB.")

   # Validate PDF signature to prevent fake PDF uploads.
    signature = contents[:5]

    if signature != b"%PDF-":
        raise ValueError("Invalid PDF signature.")


    # Validate invoice number
    if not re.fullmatch(r"[A-Za-z0-9_-]+", invoice_number):
        raise ValueError("Invalid invoice number.")

    # Create uploads directory
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Safe filename
    supplier_id = invoices[invoice_number]["supplier_id"]

    supplier_directory = os.path.join(
    UPLOAD_DIR,
    supplier_id,
    )

    os.makedirs(
    supplier_directory,
    exist_ok=True,
    )

    safe_invoice_number = os.path.basename(
    invoice_number
   )

    filename = f"{safe_invoice_number}.pdf"

    filepath = os.path.join(
    supplier_directory,
    filename,
   )

    # Ensure the final path stays inside uploads directory
    upload_dir = os.path.abspath(UPLOAD_DIR)
    final_path = os.path.abspath(filepath)

    if not final_path.startswith(upload_dir):
        raise ValueError("Invalid file path.")

    # Save file
    with open(final_path, "wb") as f:
        f.write(contents)

    # Store document path
    invoices[invoice_number]["document_url"] = final_path

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