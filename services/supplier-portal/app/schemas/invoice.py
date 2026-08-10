from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class InvoiceCreate(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invoice_number": "INV1001",
                "po_number": "PO1001",
                "supplier_id": "SUP001",
                "amount": 1000,
                "invoice_date": "2026-08-06"
            }
        }
    )

    invoice_number: str = Field(
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    po_number: str

    supplier_id: str = Field(
        pattern=r"^[A-Za-z0-9_-]+$"
    )

    amount: float

    invoice_date: date


class InvoiceResponse(BaseModel):
    invoice_number: str
    po_number: str
    supplier_id: str
    amount: float
    invoice_date: date
    document_url: str | None = None