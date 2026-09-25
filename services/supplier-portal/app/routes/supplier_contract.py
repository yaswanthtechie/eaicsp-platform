from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.core.auth import (
    require_roles,
    verify_token,
)

from app.schemas.supplier_contract import (
    ContractStatus,
    SupplierContractCreate,
    SupplierContractExpiryResponse,
    SupplierContractHistory,
    SupplierContractRenewalRequest,
    SupplierContractRenewalResponse,
    SupplierContractResponse,
    SupplierContractUpdate,
)

from app.services.supplier_contract_service import (
    activate_contract,
    create_contract,
    get_contract,
    get_contract_history,
    list_contracts,
    list_expiring_contracts,
    renew_contract,
    update_contract,
)


router = APIRouter(
    prefix="/supplier-contracts",
)


# ============================================================
# COMMON SUPPLIER IDENTITY VALIDATION
# ============================================================

def validate_supplier_identity(
    user: dict,
):
    """
    Supplier users must have a supplier_id.

    Internal users are not required to have supplier_id.
    """

    if user.get("role") != "supplier":
        return

    authenticated_supplier_id = user.get(
        "supplier_id"
    )

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier identity could not be resolved"
            ),
        )


# ============================================================
# COMMON SUPPLIER SCOPING
# ============================================================

def check_supplier_access(
    supplier_id: str,
    user: dict,
):
    """
    Supplier users can access only their own
    supplier contracts.

    Internal users are controlled by endpoint-level
    role authorization.
    """

    if user.get("role") != "supplier":
        return

    authenticated_supplier_id = user.get(
        "supplier_id"
    )

    if not authenticated_supplier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier identity could not be resolved"
            ),
        )

    if (
        authenticated_supplier_id
        != supplier_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier access is restricted "
                "to own data"
            ),
        )


# ============================================================
# COMMON ACTOR VALIDATION
# ============================================================

def get_actor_details(
    user: dict,
):
    """
    Get authenticated actor information from
    Platform authentication.
    """

    actor_id = user.get(
        "user_id"
    )
    actor_name = user.get(
        "full_name"
    )
    role = user.get(
        "role"
    )

    if actor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Authenticated user ID is required."
            ),
        )

    if not actor_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Authenticated user name is required."
            ),
        )

    return (
        str(actor_id),
        actor_name,
        role,
    )


# ============================================================
# 1. CREATE CONTRACT
# ============================================================

@router.post(
    "",
    response_model=SupplierContractResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_endpoint(
    contract_data: SupplierContractCreate,
    user=Depends(
        require_roles(
            "procurement_manager"
        )
    ),
):
    """
    Create a supplier contract.

    Only Procurement Managers can create contracts.
    """

    actor_id, actor_name, role = (
        get_actor_details(user)
    )

    try:
        return create_contract(
            contract_data=contract_data,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "supplier not found"
            in message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 2. LIST EXPIRING CONTRACTS
# ============================================================

@router.get(
    "/expiring",
    response_model=list[
        SupplierContractExpiryResponse
    ],
)
def list_expiring_contracts_endpoint(
    within_days: int | None = Query(
        default=None,
        ge=0,
        le=365,
    ),
    supplier_id: str | None = Query(
        default=None,
    ),
    user=Depends(verify_token),
):
    """
    Return active contracts approaching expiry.

    Supplier:
        - Can see only own expiring contracts.
        - If supplier_id is supplied, it must match
          the authenticated supplier.

    Internal users:
        - Can query all contracts.
        - Can optionally filter by supplier_id.
    """

    validate_supplier_identity(user)

    authenticated_supplier_id = user.get(
        "supplier_id"
    )

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        if (
            supplier_id is not None
            and supplier_id
            != authenticated_supplier_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Supplier access is restricted "
                    "to own data"
                ),
            )

        # Token-derived supplier_id is authoritative.
        supplier_id = (
            authenticated_supplier_id
        )

    try:
        return list_expiring_contracts(
            supplier_id=supplier_id,
            within_days=within_days,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ============================================================
# 3. LIST CONTRACTS
# ============================================================

@router.get(
    "",
    response_model=list[
        SupplierContractResponse
    ],
)
def list_contracts_endpoint(
    supplier_id: str | None = Query(
        default=None,
    ),
    contract_status: ContractStatus | None = Query(
        default=None,
        alias="status",
    ),
    user=Depends(verify_token),
):
    """
    List supplier contracts.

    Supplier:
        - Can see only own contracts.
        - Token supplier_id is always authoritative.

    Procurement Manager:
        - Can list all contracts.
        - Can optionally filter by supplier_id.
        - Can optionally filter by lifecycle status.
    """

    validate_supplier_identity(user)

    authenticated_supplier_id = user.get(
        "supplier_id"
    )

    # --------------------------------------------------------
    # SUPPLIER SCOPING
    # --------------------------------------------------------

    if user.get("role") == "supplier":

        if (
            supplier_id is not None
            and supplier_id
            != authenticated_supplier_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Supplier access is restricted "
                    "to own data"
                ),
            )

        # Never trust a supplier_id supplied by
        # the client.
        supplier_id = (
            authenticated_supplier_id
        )

    return list_contracts(
        supplier_id=supplier_id,
        status=contract_status,
    )


# ============================================================
# 4. GET CONTRACT DETAILS
# ============================================================

@router.get(
    "/{contract_id}",
    response_model=SupplierContractResponse,
)
def get_contract_endpoint(
    contract_id: str,
    user=Depends(verify_token),
):
    """
    Get a single contract.

    Supplier ownership is validated after retrieving the
    contract because the service needs the contract's
    supplier_id for the ownership comparison.
    """

    validate_supplier_identity(user)

    try:
        contract = get_contract(
            contract_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    check_supplier_access(
        contract["supplier_id"],
        user,
    )

    return contract


# ============================================================
# 5. UPDATE CONTRACT
# ============================================================

@router.put(
    "/{contract_id}",
    response_model=SupplierContractResponse,
)
def update_contract_endpoint(
    contract_id: str,
    contract_data: SupplierContractUpdate,
    user=Depends(
        require_roles(
            "procurement_manager"
        )
    ),
):
    """
    Update editable contract terms.

    Only Procurement Managers can modify contracts.

    The authenticated actor details are passed to the
    service so that every actual contract-term change
    is recorded in the audit history.
    """

    # --------------------------------------------------------
    # Get authenticated actor details
    # --------------------------------------------------------

    actor_id, actor_name, role = (
        get_actor_details(user)
    )

    try:
        return update_contract(
            contract_id=contract_id,
            contract_data=contract_data,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "contract not found"
            in message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 6. ACTIVATE CONTRACT
# ============================================================

@router.post(
    "/{contract_id}/activate",
    response_model=SupplierContractResponse,
    status_code=status.HTTP_201_CREATED,
)
def activate_contract_endpoint(
    contract_id: str,
    user=Depends(
        require_roles(
            "procurement_manager"
        )
    ),
):
    """
    Move a contract from DRAFT to ACTIVE.

    Only Procurement Managers can activate contracts.
    """

    actor_id, actor_name, role = (
        get_actor_details(user)
    )

    try:
        return activate_contract(
            contract_id=contract_id,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "contract not found"
            in message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 7. RENEW CONTRACT
# ============================================================

@router.post(
    "/{contract_id}/renew",
    response_model=SupplierContractRenewalResponse,
    status_code=status.HTTP_201_CREATED,
)
def renew_contract_endpoint(
    contract_id: str,
    renewal_data: SupplierContractRenewalRequest,
    user=Depends(
        require_roles(
            "procurement_manager"
        )
    ),
):
    """
    Renew a supplier contract.

    Only Procurement Managers can renew contracts.
    """

    actor_id, actor_name, role = (
        get_actor_details(user)
    )

    try:
        return renew_contract(
            contract_id=contract_id,
            renewal_data=renewal_data,
            actor_id=actor_id,
            actor_name=actor_name,
            role=role,
        )

    except ValueError as exc:
        message = str(exc)

        if (
            "contract not found"
            in message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )


# ============================================================
# 8. GET CONTRACT HISTORY
# ============================================================

@router.get(
    "/{contract_id}/history",
    response_model=list[
        SupplierContractHistory
    ],
)
def contract_history_endpoint(
    contract_id: str,
    user=Depends(verify_token),
):
    """
    Return contract lifecycle and audit history.

    Supplier users can access only their own
    contract history.
    """

    validate_supplier_identity(user)

    # --------------------------------------------------------
    # Resource lookup
    # --------------------------------------------------------

    try:
        contract = get_contract(
            contract_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # --------------------------------------------------------
    # Supplier ownership
    # --------------------------------------------------------

    check_supplier_access(
        contract["supplier_id"],
        user,
    )

    # --------------------------------------------------------
    # Return history
    # --------------------------------------------------------

    try:
        return get_contract_history(
            contract_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )