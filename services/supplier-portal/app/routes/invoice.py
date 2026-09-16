from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    Query,
    Depends,
)

from app.core.auth import (
    require_roles,
    verify_token,
)

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
# SUPPLIER INVOICE SCOPING
# ============================================================

def verify_supplier_invoice_access(
    supplier_only: bool = False,
):
    """
    Verify invoice access.

    supplier_only=False:
        Suppliers can access only their own invoices.
        Internal roles can read any invoice.

    supplier_only=True:
        Only the owning supplier can perform the action.
    """

    def dependency(
        supplier_id: str,
        user=Depends(verify_token),
    ):
        # ----------------------------------------------------
        # 1. Supplier role check
        # ----------------------------------------------------

        if user.get("role") == "supplier":
            authenticated_supplier_id = user.get("supplier_id")

            if not authenticated_supplier_id:
                raise HTTPException(
                    status_code=403,
                    detail="Supplier identity is missing",
                )

        # ----------------------------------------------------
        # 2. Supplier-only action
        # ----------------------------------------------------

        elif supplier_only:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier access required",
            )

        # ----------------------------------------------------
        # 3. Supplier scoping check
        # ----------------------------------------------------

        if (
            user.get("role") == "supplier"
            and user["supplier_id"] != supplier_id
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this invoice"
                ),
            )

        return user

    return dependency


# ============================================================
# GET ALL INVOICES
# ============================================================

@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
)
def get_invoices(
    user=Depends(verify_token),
):
    """
    Get invoices.

    Supplier:
        Can see only invoices belonging to the authenticated
        supplier_id.

    Internal authenticated users:
        Can see all invoices.
    """

    all_invoices = get_all_invoices()

    # --------------------------------------------------------
    # Supplier scoping
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        authenticated_supplier_id = user.get(
            "supplier_id"
        )

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        return [
            invoice
            for invoice in all_invoices
            if invoice.get("supplier_id")
            == authenticated_supplier_id
        ]

    # --------------------------------------------------------
    # Internal users
    # --------------------------------------------------------

    return all_invoices


# ============================================================
# GET INVOICE BY NUMBER
# Supplier-facing endpoint
# ============================================================

@router.get(
    "/invoices/{supplier_id}/{invoice_number}",
    response_model=InvoiceResponse,
)
def get_invoice(
    supplier_id: str,
    invoice_number: str,
    user=Depends(verify_supplier_invoice_access()),
):
    try:
        return get_invoice_by_number(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


# ============================================================
# CREATE / SUBMIT INVOICE
# Supplier-facing endpoint
# ============================================================

@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=201,
)
def submit_invoice(
    invoice: InvoiceCreate,
    user=Depends(verify_token),
):
    """
    Create / submit a new invoice.

    New invoices always start in:
        submitted

    Supplier users must submit an invoice using
    their own supplier_id.
    """

    # --------------------------------------------------------
    # Supplier scoping
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        authenticated_supplier_id = user.get(
            "supplier_id"
        )

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier identity is missing",
            )

        if authenticated_supplier_id != invoice.supplier_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this invoice"
                ),
            )

    try:
        return create_invoice(invoice)

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        # Duplicate invoice
        if "already exists" in lower_message:
            raise HTTPException(
                status_code=409,
                detail=message,
            )

        # Purchase Order not found
        if (
            "purchase order" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        # Other business validation errors
        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# TRANSITION INVOICE
# Supplier-facing endpoint
# ============================================================

@router.post(
    "/invoices/{supplier_id}/{invoice_number}/transition",
    response_model=InvoiceResponse,
)
def transition_invoice_status(
    supplier_id: str,
    invoice_number: str,
    transition: InvoiceTransition,
    user=Depends(
       verify_supplier_invoice_access(supplier_only=True)
    ),
):
    """
    Change invoice status using the invoice state machine.
    """

    try:
        return transition_invoice(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            actor_id=transition.actor_id,
            actor_name=transition.actor_name,
            role=transition.role,
            target_state=transition.target_state,
            reason=transition.reason,
        )

    except ValueError as e:
        message = str(e)
        lower_message = message.lower()

        # Invoice does not exist
        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )

        # Other business validation errors
        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# ADJUST INVOICE
# Requires: compliance_officer
# ============================================================

@router.post(
    "/invoices/{supplier_id}/{invoice_number}/adjust",
    response_model=InvoiceResponse,
)
def adjust_invoice_endpoint(
    supplier_id: str,
    invoice_number: str,
    adjustment: InvoiceAdjustment,
    user=Depends(
        require_roles("compliance_officer")
    ),
):
    """
    Adjust a disputed invoice.

    Requires:
        compliance_officer

    Flow:

        disputed
            ↓
        adjust
            ↓
        adjusted
            ↓
        transition
            ↓
        approved
    """

    try:
        return adjust_invoice(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            adjustment=adjustment,
        )

    except ValueError as e:

        message = str(e)
        lower_message = message.lower()

        if "invoice not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# UPLOAD INVOICE DOCUMENT
# Supplier-facing endpoint
# ============================================================

@router.post(
    "/invoices/{supplier_id}/{invoice_number}/document",
    response_model=InvoiceResponse,
)
def upload_document(
    supplier_id: str,
    invoice_number: str,
    file: UploadFile = File(...),
    user=Depends(
       verify_supplier_invoice_access(supplier_only=True)
    ),
):
    """
    Upload a PDF document for an existing invoice.
    """

    try:
        return upload_invoice_document(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            file=file,
        )

    except ValueError as e:
        message = str(e)
        lower_message = message.lower()

        # Invoice does not exist
        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )

        # Other validation/business errors
        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# DOWNLOAD INVOICE DOCUMENT
# Supplier-facing endpoint
# ============================================================

@router.get(
    "/invoices/{supplier_id}/{invoice_number}/document",
)
def download_invoice_document(
    supplier_id: str,
    invoice_number: str,
    user=Depends(verify_supplier_invoice_access()),
):
    """
    Download the PDF document attached to an invoice.
    """

    try:
        filepath = get_invoice_document(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
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
        # 1. Document is not associated with the invoice
        # ----------------------------------------------------
        if "document not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        # ----------------------------------------------------
        # 2. Physical document file was deleted/missing
        # ----------------------------------------------------
        if "document does not exist" in lower_message:
            raise HTTPException(
                status_code=404,
                detail="File does not exist.",
            )

        # ----------------------------------------------------
        # 3. Invoice itself does not exist
        # ----------------------------------------------------
        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            )

        # ----------------------------------------------------
        # 4. Other validation/business errors
        # ----------------------------------------------------
        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# FIND ORPHANED INVOICE FILES
# Requires: compliance_officer
# ============================================================

@router.get(
    "/maintenance/orphaned-invoice-files",
    response_model=OrphanedFileCleanupResponse,
)
def find_orphaned_files(
    older_than_days: int = Query(
        default=1,
        ge=0,
        description=(
            "Only files older than this number "
            "of days are considered orphaned."
        ),
    ),
    user=Depends(
        require_roles("compliance_officer")
    ),
):
    """
    Find orphaned invoice files.

    Requires:
        compliance_officer

    This is a global maintenance operation and therefore
    must never be available to suppliers.
    """

    try:
        orphaned_files = find_orphaned_invoice_files(
            older_than_days=older_than_days,
        )

        return {
            "total": len(orphaned_files),
            "orphaned_files": orphaned_files,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

# ============================================================
# PURGE ORPHANED INVOICE FILES
# Requires: compliance_officer
# ============================================================

@router.delete(
    "/maintenance/orphaned-invoice-files",
    response_model=OrphanedFilePurgeResponse,
)
def purge_orphaned_files(
    older_than_days: int = Query(
        default=1,
        ge=0,
        description=(
            "Only files older than this number "
            "of days can be deleted."
        ),
    ),
    user=Depends(
        require_roles("compliance_officer")
    ),
):
    """
    Permanently delete orphaned invoice files.

    Requires:
        compliance_officer

    Suppliers and other roles must not be allowed to
    perform this destructive maintenance operation.
    """

    try:
        return purge_orphaned_invoice_files(
            older_than_days=older_than_days,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )