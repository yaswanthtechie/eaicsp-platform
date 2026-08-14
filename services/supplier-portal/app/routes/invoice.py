from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceTransition,
    InvoiceAdjustment,
    OrphanedFileCleanupResponse,
    OrphanedFilePurgeResponse,
)

from app.services.invoice_service import (
    create_invoice,
    upload_invoice_document,
    get_invoice_document,
    get_all_invoices,
    get_invoice_by_number,
    transition_invoice,
    adjust_invoice,
    find_orphaned_invoice_files,
    purge_orphaned_invoice_files,
)

router = APIRouter()


# ============================================================
# GET ALL INVOICES
# ============================================================

@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
)
def get_invoices():
    """
    Get all invoices.

    Possible responses:
        200 - Invoices returned successfully
    """

    return get_all_invoices()


# ============================================================
# GET INVOICE BY NUMBER
# ============================================================

@router.get(
    "/invoices/{invoice_number}",
    response_model=InvoiceResponse,
)
def get_invoice(invoice_number: str):
    """
    Get a single invoice by invoice number.

    Possible responses:
        200 - Invoice found
        404 - Invoice not found
    """

    try:
        return get_invoice_by_number(
            invoice_number
        )

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )


# ============================================================
# CREATE / SUBMIT INVOICE
# ============================================================

@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=201,
)
def submit_invoice(
    invoice: InvoiceCreate,
):
    """
    Create / submit a new invoice.

    New invoices always start in:
        submitted

    Possible responses:
        201 - Invoice created
        400 - Business validation error
        404 - Purchase Order not found
        409 - Duplicate invoice
    """

    try:
        return create_invoice(invoice)

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # ----------------------------------------------------
        # Duplicate invoice
        # ----------------------------------------------------

        if "already exists" in lower_message:
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        # ----------------------------------------------------
        # Purchase Order not found
        # ----------------------------------------------------

        if (
            "purchase order" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Other business validation errors
        # ----------------------------------------------------

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# TRANSITION INVOICE
# ============================================================

@router.post(
    "/invoices/{invoice_number}/transition",
    response_model=InvoiceResponse,
)
def transition_invoice_status(
    invoice_number: str,
    transition: InvoiceTransition,
):
    """
    Change the invoice status using the invoice state machine.

    Allowed transitions:

        submitted -> approved
        submitted -> disputed
        submitted -> rejected

        disputed -> approved
        disputed -> adjusted
        disputed -> rejected

    Possible responses:
        200 - Transition successful
        400 - Illegal transition / validation error
        404 - Invoice not found
    """

    try:
        return transition_invoice(
            invoice_number=invoice_number,

            # NEW audit fields
            actor_id=transition.actor_id,
            actor_name=transition.actor_name,
            role=transition.role,

            target_state=transition.target_state,
            reason=transition.reason,
        )

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # ----------------------------------------------------
        # Invoice not found
        # ----------------------------------------------------

        if "invoice not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Illegal state transition
        # ----------------------------------------------------

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# ADJUST INVOICE
# ============================================================

@router.post(
    "/invoices/{invoice_number}/adjust",
    response_model=InvoiceResponse,
)
def adjust_invoice_endpoint(
    invoice_number: str,
    adjustment: InvoiceAdjustment,
):
    """
    Adjust a disputed invoice.

    This endpoint changes the invoice amount and moves
    the invoice from:

        disputed -> adjusted

    After that, the normal transition endpoint can be used:

        adjusted -> approved

    Possible responses:
        200 - Invoice adjusted successfully
        400 - Invoice cannot be adjusted
        404 - Invoice not found
    """

    try:

        return adjust_invoice(
            invoice_number=invoice_number,
            adjustment=adjustment,
        )

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # ----------------------------------------------------
        # Invoice not found
        # ----------------------------------------------------

        if "invoice not found" in lower_message:

            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Other adjustment errors
        # ----------------------------------------------------

        raise HTTPException(
            status_code=400,
            detail=message,
        )

# ============================================================
# UPLOAD INVOICE DOCUMENT
# ============================================================

@router.post(
    "/invoices/{invoice_number}/document",
    response_model=InvoiceResponse,
)
def upload_document(
    invoice_number: str,
    file: UploadFile = File(...),
):
    """
    Upload a PDF document for an existing invoice.

    Possible responses:
        200 - PDF uploaded successfully
        400 - Invalid file / PDF / size
        404 - Invoice not found
    """

    try:
        return upload_invoice_document(
            invoice_number,
            file,
        )

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # ----------------------------------------------------
        # Invoice does not exist
        # ----------------------------------------------------

        if "invoice not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Upload validation error
        # ----------------------------------------------------

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# DOWNLOAD INVOICE DOCUMENT
# ============================================================

@router.get(
    "/invoices/{invoice_number}/document",
)
def download_invoice_document(
    invoice_number: str,
):
    """
    Download the PDF document attached to an invoice.

    Possible responses:
        200 - PDF returned
        404 - Invoice/document/file not found
        400 - Other document error
    """

    try:

        filepath = get_invoice_document(
            invoice_number
        )

        return FileResponse(
            path=filepath,
            media_type="application/pdf",
            filename=f"{invoice_number}.pdf",
        )

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # ----------------------------------------------------
        # Invoice not found
        # ----------------------------------------------------

        if "invoice not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Document not found
        # ----------------------------------------------------

        if "document not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Physical file missing
        # ----------------------------------------------------

        if "file does not exist" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # ----------------------------------------------------
        # Other document errors
        # ----------------------------------------------------

        raise HTTPException(
            status_code=400,
            detail=message,
        )

# ============================================================
# FIND ORPHANED INVOICE FILES
# ============================================================

@router.get(
    "/maintenance/orphaned-invoice-files",
    response_model=OrphanedFileCleanupResponse,
)
def find_orphaned_files():

    orphaned_files = find_orphaned_invoice_files()

    return {
        "total": len(orphaned_files),
        "orphaned_files": orphaned_files,
    }


# ============================================================
# PURGE ORPHANED INVOICE FILES
# ============================================================

@router.delete(
    "/maintenance/orphaned-invoice-files",
    response_model=OrphanedFilePurgeResponse,
)
def purge_orphaned_files():

    return purge_orphaned_invoice_files()