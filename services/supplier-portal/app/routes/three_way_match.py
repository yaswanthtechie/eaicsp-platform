from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import require_roles, verify_token

from app.schemas.three_way_match import (
    ThreeWayMatchResponse,
    ThreeWayMatchResolution,
    PaymentApprovalResponse,
)

from app.services.three_way_match_service import (
    execute_three_way_match,
    get_three_way_match,
    resolve_three_way_discrepancy,
    approve_payment,
)

router = APIRouter()


# ============================================================
# SUPPLIER IDENTITY VALIDATION
# ============================================================

def validate_supplier_identity(user: dict) -> None:
    """
    Supplier users must have a supplier_id.

    Internal users do not require supplier_id.
    """
    if user.get("role") != "supplier":
        return

    if not user.get("supplier_id"):
        raise HTTPException(
            status_code=403,
            detail="Supplier ID is required.",
        )
    
# ============================================================
# SUPPLIER ACCESS VALIDATION
# ============================================================

def check_supplier_access(
    supplier_id: str,
    user: dict,
) -> None:
    """
    Validate supplier access.

    Supplier users can access only their own supplier_id.
    Internal users can access any supplier.
    """
    role = user.get("role")
    authenticated_supplier_id = user.get("supplier_id")

    if role == "supplier":

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Supplier ID is required.",
            )

        if authenticated_supplier_id != supplier_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: supplier does not own this resource.",
            )


# ============================================================
# AUTHENTICATED USER EMAIL
# ============================================================

def get_authenticated_email(
    user: dict,
) -> str:
    """
    Get authenticated user's email from Platform auth response.
    """
    email = user.get("email")

    if not email:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user email is required.",
        )

    return email


# ============================================================
# EXECUTE THREE-WAY MATCH
# Requires: procurement_manager
# ============================================================

@router.post(
    "/three-way-matches/{supplier_id}/{invoice_number}",
    response_model=ThreeWayMatchResponse,
)
def execute_match(
    supplier_id: str,
    invoice_number: str,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    """
    Execute three-way match.

    This is an internal procurement-side activity.

    Compares:

        Purchase Order
        Goods Receipt
        Invoice

    Successful match:

        P2P invoiced -> matched

    Discrepancy:

        P2P invoiced -> discrepancy

    Suppliers are not allowed to execute
    three-way matching.
    """
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    email = get_authenticated_email(user)

    try:
        return execute_three_way_match(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            created_by=email,
        )

    except ValueError as exc:

        message = str(exc)
        lower_message = message.lower()

        if "invoice not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        if "purchase order" in lower_message:

            if "not found" in lower_message:
                raise HTTPException(
                    status_code=404,
                    detail=message,
                )

            if "does not own" in lower_message:
                raise HTTPException(
                    status_code=403,
                    detail=message,
                )

        if (
            "must be fulfilled" in lower_message
            or "must be in p2p state" in lower_message
            or "cannot move" in lower_message
            or "invalid state" in lower_message
            or "already matched" in lower_message
        ):
            raise HTTPException(
                status_code=400,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# GET THREE-WAY MATCH
# ============================================================

@router.get(
    "/three-way-matches/{supplier_id}/{invoice_number}",
    response_model=ThreeWayMatchResponse,
)
def get_match(
    supplier_id: str,
    invoice_number: str,
    user=Depends(verify_token),
):
    """
    Get the stored three-way match result.

    Supplier:
        Can view only their own supplier resource.

    Internal users:
        Can view any supplier resource.

    Access rules:
        - Supplier without supplier_id -> 403
        - Unknown match -> 404
        - Other supplier's match -> 403
        - Own supplier's match -> 200
        - Internal users -> 200 when match exists
    """

    # 1. Supplier identity must be available first.
    #    This prevents a supplier without supplier_id from
    #    receiving a misleading 404.
    validate_supplier_identity(user)

    # 2. Check whether the requested match actually exists.
    #    Unknown resource must return 404 before ownership
    #    comparison is performed.
    match = get_three_way_match(
        supplier_id=supplier_id,
        invoice_number=invoice_number,
    )

    if not match:
        raise HTTPException(
            status_code=404,
            detail="Three-way match record not found.",
        )

    # 3. After confirming the resource exists, enforce
    #    supplier ownership.
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    # 4. Return the authorized match.
    return match



# ============================================================
# RESOLVE DISCREPANCY
# Requires: compliance_officer
# ============================================================

@router.post(
    "/three-way-matches/{supplier_id}/{invoice_number}/resolve",
    response_model=ThreeWayMatchResponse,
)
def resolve_match(
    supplier_id: str,
    invoice_number: str,
    resolution: ThreeWayMatchResolution,
    user=Depends(
        require_roles("compliance_officer")
    ),
):
    """
    Resolve a three-way-match discrepancy.

    Flow:

        discrepancy
             |
        human review
             |
          matched

    Only Compliance Officer can resolve discrepancies.
    """
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    email = get_authenticated_email(user)
    role = user.get("role")

    try:
        return resolve_three_way_discrepancy(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            reason=resolution.reason,
            resolved_by=email,
            resolved_role=role,
        )

    except ValueError as exc:

        message = str(exc)
        lower_message = message.lower()

        if "not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )


# ============================================================
# PAYMENT APPROVAL
# Requires: procurement_manager
# ============================================================

@router.post(
    "/three-way-matches/{supplier_id}/{invoice_number}/payment-approve",
    response_model=PaymentApprovalResponse,
)
def approve_payment_endpoint(
    supplier_id: str,
    invoice_number: str,
    user=Depends(
        require_roles("procurement_manager")
    ),
):
    """
    Approve payment only after successful three-way matching.

    Flow:

        matched
           |
        payment_approved

    Payment cannot be approved while the P2P workflow
    is in invoiced or discrepancy state.
    """
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    email = get_authenticated_email(user)
    role = user.get("role")

    try:
        return approve_payment(
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            approved_by=email,
            approved_role=role,
        )

    except ValueError as exc:

        message = str(exc)
        lower_message = message.lower()

        if "not found" in lower_message:
            raise HTTPException(
                status_code=404,
                detail=message,
            )

        raise HTTPException(
            status_code=400,
            detail=message,
        )

