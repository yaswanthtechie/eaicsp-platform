from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from app.services.invoice_service import get_invoice_document


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


@router.get(
    "/invoices/{invoice_number}/document"
)
def download_invoice_document(
    invoice_number: str,
):
    try:
        filepath = get_invoice_document(
            invoice_number
        )


        return FileResponse(
             path=filepath,
             media_type="application/pdf",
             filename=f"{invoice_number}.pdf"
        )

    except ValueError as e:
        message = str(e)

        if message in [
            "Invoice not found.",
            "Document not found.",
            "File does not exist."
        ]:
            raise HTTPException(
                status_code=404,
                detail=message
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )