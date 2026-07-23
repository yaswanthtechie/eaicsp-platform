import os

from fastapi import UploadFile

from app.schemas.invoice import InvoiceCreate
from app.services.purchase_order_service import purchase_orders

# In-memory storage
invoices = {}

UPLOAD_DIR = "uploads"


def create_invoice(invoice: InvoiceCreate):

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

    if file.content_type != "application/pdf":
        raise ValueError("Only PDF files are allowed.")

    contents = file.file.read()

    if len(contents) > 10 * 1024 * 1024:
        raise ValueError("Maximum file size is 10 MB.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = f"{invoice_number}.pdf"

    filepath = os.path.join(
        UPLOAD_DIR,
        filename,
    )

    with open(filepath, "wb") as f:
        f.write(contents)

    invoices[invoice_number]["document_url"] = filepath

    return invoices[invoice_number]