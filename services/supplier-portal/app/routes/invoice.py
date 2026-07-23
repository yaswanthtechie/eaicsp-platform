from fastapi import APIRouter, HTTPException, UploadFile, File

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
)

from app.services.invoice_service import (
    create_invoice,
    upload_invoice_document,
)

router = APIRouter()

@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=201
)
def submit_invoice(invoice: InvoiceCreate):
    try:
        return create_invoice(invoice)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    



@router.post(
    "/invoices/{invoice_number}/document",
    response_model=InvoiceResponse,
)
def upload_document(
    invoice_number: str,
    file: UploadFile = File(...),
):
    try:
        return upload_invoice_document(
            invoice_number,
            file,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )