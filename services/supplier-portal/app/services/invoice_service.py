import os
import re

from fastapi import UploadFile

from app.schemas.invoice import InvoiceCreate
from app.services.purchase_order_service import purchase_orders
from app.core.config import UPLOAD_DIR

# In-memory storage
invoices = {}


def create_invoice(invoice: InvoiceCreate):
    """
    Create a new invoice.
    """

    # Allow only letters, numbers, underscore and hyphen
    if not re.fullmatch(r"[A-Za-z0-9_-]+", invoice.invoice_number):
        raise ValueError("Invalid invoice number.")

    if invoice.invoice_number in invoices:
        raise ValueError("Invoice already exists.")

    if invoice.po_number not in purchase_orders:
        raise ValueError("Purchase Order not found.")

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

    # Validate PDF signature
    if not contents.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF file.")

    # Validate invoice number
    if not re.fullmatch(r"[A-Za-z0-9_-]+", invoice_number):
        raise ValueError("Invalid invoice number.")

    # Create uploads directory
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Safe filename
    safe_invoice_number = os.path.basename(invoice_number)

    filename = f"{safe_invoice_number}.pdf"

    filepath = os.path.join(
        UPLOAD_DIR,
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