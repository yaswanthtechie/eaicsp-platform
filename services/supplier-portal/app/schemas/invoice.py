from pydantic import BaseModel, Field
from datetime import date


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(..., example="INV1001")
    po_number: str = Field(..., example="PO1001")
    supplier_id: str = Field(..., example="SUP001")
    amount: float
    invoice_date: date


class InvoiceResponse(BaseModel):
    invoice_number: str
    po_number: str
    supplier_id: str
    amount: float
    invoice_date: date


document_url: str | None = None