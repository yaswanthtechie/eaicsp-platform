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
    require_supplier_view_access,
    require_supplier_write_access,
)

from app.core.config import settings

from app.services.document_storage_service import (
    DocumentDownloadError,
    DocumentStorageError,
    document_storage_service,
)

from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceTransition,
    InvoiceAdjustment,
    InvoiceDocumentDownloadResponse,
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

from app.services.purchase_order_service import purchase_orders


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

    Round 14 compliance enforcement:

        View:
            CLEARED       -> allowed
            NEEDS_REVIEW  -> allowed
            SUSPENDED     -> denied

        Write:
            CLEARED       -> allowed
            NEEDS_REVIEW  -> denied
            SUSPENDED     -> denied
    """

    async def dependency(
        supplier_id: str,
        user=Depends(
            require_supplier_write_access
            if supplier_only
            else require_supplier_view_access
        ),
    ):
        # ----------------------------------------------------
        # 1. Supplier role check
        # ----------------------------------------------------

        if user.get("role") == "supplier":
            authenticated_supplier_id = user.get(
                "supplier_id"
            )

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
    user=Depends(require_supplier_view_access),
):
    """
    Get invoices.

    Supplier:
        Can see only invoices belonging to the authenticated
        supplier_id.

    Internal authenticated users:
        Can see all invoices.

    Round 14:
        SUSPENDED suppliers are denied.
        NEEDS_REVIEW suppliers can view invoices.
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
    user=Depends(
        verify_supplier_invoice_access()
    ),
):
    """
    Get a single invoice.

    Round 14:
        CLEARED      -> allowed
        NEEDS_REVIEW -> allowed
        SUSPENDED    -> denied
    """

    try:
        return get_invoice_by_number(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


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
    user=Depends(require_supplier_write_access),
):
    """
    Create / submit a new invoice.

    New invoices always start in:
        submitted

    Supplier users must submit an invoice using
    their own supplier_id and may only reference
    Purchase Orders belonging to them.

    Round 14:
        CLEARED      -> allowed
        NEEDS_REVIEW -> denied
        SUSPENDED    -> denied
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

        # ----------------------------------------------------
        # Check invoice supplier ownership
        # ----------------------------------------------------

        if (
            authenticated_supplier_id
            != invoice.supplier_id
        ):
            raise HTTPException(
                status_code=403,
                detail=(
                    "Forbidden: supplier does not own "
                    "this invoice"
                ),
            )

        # ----------------------------------------------------
        # Check PO ownership
        #
        # A supplier must not submit an invoice referencing
        # another supplier's Purchase Order.
        # ----------------------------------------------------

        for invoice_item in invoice.items:

            po_number = invoice_item.po_number

            # If PO does not exist, let create_invoice()
            # handle the normal 404 response.
            if po_number not in purchase_orders:
                continue

            purchase_order = purchase_orders[po_number]

            if (
                purchase_order["supplier_id"]
                != authenticated_supplier_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Forbidden: supplier does not own "
                        "this Purchase Order"
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
            ) from e

        # Purchase Order not found
        if (
            "purchase order" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from e

        # Other business validation errors
        raise HTTPException(
            status_code=400,
            detail=message,
        ) from e


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
        verify_supplier_invoice_access(
            supplier_only=True
        )
    ),
):
    """
    Change invoice status using the invoice state machine.

    Round 14:
        Only CLEARED suppliers may perform supplier-side
        invoice write operations.

    Audit information is taken from the authenticated
    Platform user and must never be supplied by the client.
    """

    # --------------------------------------------------------
    # Authenticated user information
    # --------------------------------------------------------

    actor_id = user.get("user_id")
    actor_name = user.get("full_name")
    role = user.get("role")

    if actor_id is None:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user ID is required.",
        )

    if not actor_name:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user name is required.",
        )

    if not role:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user role is required.",
        )

    try:
        return transition_invoice(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            actor_id=str(actor_id),
            actor_name=actor_name,
            role=role,
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
            ) from e

        # Other business validation errors
        raise HTTPException(
            status_code=400,
            detail=message,
        ) from e


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
        approved / rejected

    Audit information is taken from the authenticated
    Platform user and is never accepted from the request body.

    This is an internal compliance operation and therefore
    does not use supplier compliance access restrictions.
    """

    # ========================================================
    # Get authenticated user identity
    # ========================================================

    actor_id = user.get("user_id")
    actor_name = user.get("full_name")
    role = user.get("role")

    if actor_id is None:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user ID is required.",
        )

    if not actor_name:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user name is required.",
        )

    if not role:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user role is required.",
        )

    # ========================================================
    # Adjust invoice
    # ========================================================

    try:
        return adjust_invoice(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            adjustment=adjustment,
            actor_id=str(actor_id),
            actor_name=actor_name,
            role=role,
        )

    except ValueError as e:
        message = str(e)
        lower_message = message.lower()

        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            ) from e

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from e


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
        verify_supplier_invoice_access(
            supplier_only=True
        )
    ),
):
    """
    Upload a PDF document for an existing invoice.

    The actual PDF is stored in MinIO. The invoice record
    stores the supplier-scoped MinIO object key.

    Round 14:
        Only CLEARED suppliers may upload documents.
    """

    # DocumentStorageError covers DocumentUploadError AND
    # failures before the upload starts, such as
    # ensure_bucket() when MinIO is unreachable.
    try:
        return upload_invoice_document(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            file=file,
        )

    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        message = str(exc)
        lower_message = message.lower()

        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc


# ============================================================
# DOWNLOAD INVOICE DOCUMENT
# Supplier-facing endpoint
# ============================================================


@router.get(
    "/invoices/{supplier_id}/{invoice_number}/document",
    response_model=InvoiceDocumentDownloadResponse,
)
def download_invoice_document(
    supplier_id: str,
    invoice_number: str,
    user=Depends(
        verify_supplier_invoice_access()
    ),
):
    """
    Generate a short-lived presigned MinIO download URL.

    Access is supplier-scoped.

    Round 14:
        CLEARED      -> allowed
        NEEDS_REVIEW -> allowed
        SUSPENDED    -> denied

    No presigned URL is generated for a suspended supplier.
    """

    try:
        # ----------------------------------------------------
        # STEP 1: Get the invoice
        # ----------------------------------------------------

        invoice = get_invoice_by_number(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
        )

        # ----------------------------------------------------
        # STEP 2: Get registered MinIO object key
        # ----------------------------------------------------

        document_path = invoice.get("document_path")

        if not document_path:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        # ----------------------------------------------------
        # STEP 3: Verify that the registered object exists
        # ----------------------------------------------------

        if not document_storage_service.object_exists(
            object_key=document_path,
        ):
            raise HTTPException(
                status_code=404,
                detail="File does not exist.",
            )

        # ----------------------------------------------------
        # STEP 4: Generate presigned URL
        # ----------------------------------------------------

        download_url = (
            document_storage_service.generate_download_url(
                object_key=document_path,
            )
        )

        # ----------------------------------------------------
        # STEP 5: Return download contract
        # ----------------------------------------------------

        return {
            "invoice_number": invoice_number,
            "supplier_id": supplier_id,
            "file_name": f"{invoice_number}.pdf",
            "download_url": download_url,
            "expires_in_seconds": (
                settings.MINIO_PRESIGNED_EXPIRY_SECONDS
            ),
        }

    # --------------------------------------------------------
    # MinIO / document download failure
    # --------------------------------------------------------

    except DocumentDownloadError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Generic document storage failure
    # --------------------------------------------------------

    except DocumentStorageError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # --------------------------------------------------------
    # Preserve intentional HTTP errors
    # --------------------------------------------------------

    except HTTPException:
        raise

    # --------------------------------------------------------
    # Business validation / invoice lookup errors
    # --------------------------------------------------------

    except ValueError as exc:
        message = str(exc)
        lower_message = message.lower()

        if (
            "invoice" in lower_message
            and "not found" in lower_message
        ):
            raise HTTPException(
                status_code=404,
                detail="Invoice not found.",
            ) from exc

        if "document not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc


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

    except DocumentStorageError as exc:
        # MinIO/storage failure is a dependency failure,
        # not a client validation error.
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


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

    except DocumentStorageError as exc:
        # MinIO/storage failure is a dependency failure,
        # not a client validation error.
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
