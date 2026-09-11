from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.core.auth import (
    require_roles,
    verify_token,
)

from app.schemas.supplier_onboarding import (
    SupplierApprovalRequest,
    SupplierApprovalResponse,
    SupplierDocumentResponse,
    SupplierOnboardingHistory,
    SupplierOnboardingResponse,
    SupplierRegistration,
    SupplierStatusResponse,
    SupplierActivationResponse,
    SupplierVerificationResponse,
)

from app.services.supplier_onboarding_service import (
    activate_supplier,
    approve_supplier,
    get_supplier,
    get_supplier_history,
    get_supplier_status,
    list_supplier_documents,
    list_suppliers,
    register_supplier,
    upload_supplier_document,
    verify_supplier,
)


router = APIRouter(
    prefix="/suppliers",
)


# ============================================================
# COMMON SUPPLIER IDENTITY VALIDATION
# ============================================================

def validate_supplier_identity(user: dict):
    """
    Supplier users must have a supplier_id.

    Internal users are not required to have supplier_id.
    """

    if user.get("role") != "supplier":
        return

    authenticated_supplier_id = user.get("supplier_id")

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier identity could not be resolved",
        )


# ============================================================
# COMMON SUPPLIER SCOPING
# ============================================================

def check_supplier_access(
    supplier_id: str,
    user: dict,
):
    """
    Supplier users can access only their own supplier data.

    Internal users are allowed according to their
    endpoint-level role authorization.
    """

    if user.get("role") != "supplier":
        return

    authenticated_supplier_id = user.get("supplier_id")

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier identity could not be resolved",
        )

    if authenticated_supplier_id != supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier access is restricted to own data",
        )


# ============================================================
# COMMON ACTOR VALIDATION
# ============================================================

def get_actor_details(user: dict):
    """
    Get authenticated actor information from Platform auth.
    """

    actor_id = user.get("user_id")
    actor_name = user.get("full_name")
    role = user.get("role")

    if actor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user ID is required.",
        )

    if not actor_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user name is required.",
        )

    return str(actor_id), actor_name, role


# ============================================================
# 1. REGISTER SUPPLIER
# ============================================================

@router.post(
    "/register",
    response_model=SupplierOnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_supplier_endpoint(
    registration: SupplierRegistration,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    actor_id, actor_name, role = get_actor_details(user)

    try:
        return register_supplier(
            registration=registration,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# 2. GET SUPPLIER DETAILS
# ============================================================

@router.get(
    "/{supplier_id}",
    response_model=SupplierOnboardingResponse,
)
def get_supplier_endpoint(
    supplier_id: str,
    user=Depends(verify_token),
):
    # Missing supplier identity must always be rejected first.
    validate_supplier_identity(user)

    # Check whether the requested supplier exists.
    try:
        supplier = get_supplier(
            supplier_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Existing supplier belonging to another supplier user
    # must return 403.
    check_supplier_access(
        supplier_id,
        user,
    )

    return supplier


# ============================================================
# 3. UPLOAD SUPPLIER DOCUMENT
# ============================================================

@router.post(
    "/{supplier_id}/documents",
    response_model=SupplierDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_endpoint(
    supplier_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    # Only supplier users can upload documents.
    if user.get("role") != "supplier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only suppliers can upload onboarding documents.",
        )

    # Missing supplier_id must return 403.
    validate_supplier_identity(user)

    # Supplier can upload only for own supplier_id.
    check_supplier_access(
        supplier_id,
        user,
    )

    actor_id, actor_name, _ = get_actor_details(user)

    try:
        return upload_supplier_document(
            supplier_id=supplier_id,
            document_type=document_type,
            file=file,
            actor_id=actor_id,
            actor_name=actor_name,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 4. LIST SUPPLIER DOCUMENTS
# ============================================================

@router.get(
    "/{supplier_id}/documents",
    response_model=list[SupplierDocumentResponse],
)
def list_documents_endpoint(
    supplier_id: str,
    user=Depends(verify_token),
):
    # Missing supplier identity must return 403.
    validate_supplier_identity(user)

    # First determine whether the requested supplier exists.
    try:
        documents = list_supplier_documents(
            supplier_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Existing other supplier -> 403.
    check_supplier_access(
        supplier_id,
        user,
    )

    return documents


# ============================================================
# 5. MOCK VERIFICATION
# ============================================================

@router.post(
    "/{supplier_id}/verify",
    response_model=SupplierVerificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def verify_supplier_endpoint(
    supplier_id: str,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    actor_id, actor_name, role = get_actor_details(user)

    try:
        return verify_supplier(
            supplier_id=supplier_id,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 6. APPROVE SUPPLIER
# ============================================================

@router.post(
    "/{supplier_id}/approve",
    response_model=SupplierApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_supplier_endpoint(
    supplier_id: str,
    approval: SupplierApprovalRequest,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    actor_id, actor_name, role = get_actor_details(user)

    try:
        return approve_supplier(
            supplier_id=supplier_id,
            approval=approval,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 7. ACTIVATE SUPPLIER
# ============================================================

@router.post(
    "/{supplier_id}/activate",
    response_model=SupplierActivationResponse,
    status_code=status.HTTP_201_CREATED,
)
def activate_supplier_endpoint(
    supplier_id: str,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    actor_id, actor_name, role = get_actor_details(user)

    try:
        return activate_supplier(
            supplier_id=supplier_id,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if "not found" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 8. LIST ALL SUPPLIERS
# ============================================================

@router.get(
    "",
    response_model=list[SupplierOnboardingResponse],
)
def list_suppliers_endpoint(
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    return list_suppliers()


# ============================================================
# 9. GET SUPPLIER ONBOARDING STATUS
# ============================================================

@router.get(
    "/{supplier_id}/status",
    response_model=SupplierStatusResponse,
)
def supplier_status_endpoint(
    supplier_id: str,
    user=Depends(verify_token),
):
    # Missing supplier identity must return 403.
    validate_supplier_identity(user)

    # Check resource existence first.
    try:
        result = get_supplier_status(
            supplier_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Existing other supplier -> 403.
    check_supplier_access(
        supplier_id,
        user,
    )

    return result


# ============================================================
# 10. GET SUPPLIER ONBOARDING HISTORY
# ============================================================

@router.get(
    "/{supplier_id}/history",
    response_model=list[SupplierOnboardingHistory],
)
def supplier_history_endpoint(
    supplier_id: str,
    user=Depends(verify_token),
):
    # Missing supplier identity must return 403.
    validate_supplier_identity(user)

    # Check resource existence first.
    try:
        history = get_supplier_history(
            supplier_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Existing other supplier -> 403.
    check_supplier_access(
        supplier_id,
        user,
    )

    return history

