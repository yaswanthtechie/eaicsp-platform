from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import verify_token

from app.schemas.supplier_stats import (
    SupplierStatsResponse,
    SupplierScorecard,
)

from app.services.supplier_stats_service import (
    get_supplier_stats,
    calculate_supplier_scorecard,
)


router = APIRouter()


# ============================================================
# SUPPLIER ACCESS / SCOPING
# ============================================================

def check_supplier_access(
    supplier_id: str,
    user: dict,
):
    """
    Enforce supplier-level data isolation.

    Supplier users can access only their own supplier data.

    Internal authorized roles are allowed to access supplier
    statistics for any supplier.
    """

    user_role = user.get("role")

    # Supplier users must be restricted to their own supplier_id.
    if user_role == "supplier":

        authenticated_supplier_id = user.get("supplier_id")

        if not authenticated_supplier_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supplier identity is missing",
            )

        if authenticated_supplier_id != supplier_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to access this supplier",
            )

    return user


# ============================================================
# SUPPLIER STATS
# ============================================================

@router.get(
    "/{supplier_id}/stats",
    response_model=SupplierStatsResponse,
)
def supplier_stats(
    supplier_id: str,
    user: dict = Depends(verify_token),
):
    """
    Return supplier performance statistics.

    Supplier users can access only their own statistics.
    Internal authenticated users can access supplier statistics
    according to their role permissions.
    """

    # First verify that the supplier exists.
    # This allows a genuinely unknown supplier to return 404
    # instead of being incorrectly treated as an authorization failure.
    try:
        result = get_supplier_stats(supplier_id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Supplier-level authorization is checked only after
    # confirming that the supplier exists.
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    return result


# ============================================================
# SUPPLIER SCORECARD
# ============================================================

@router.get(
    "/{supplier_id}/scorecard",
    response_model=SupplierScorecard,
)
def get_supplier_scorecard(
    supplier_id: str,
    user: dict = Depends(verify_token),
):
    """
    Return the real-time supplier performance scorecard.

    Supplier users can access only their own scorecard.
    Internal authenticated users can access supplier scorecards
    according to their role permissions.
    """

    # First verify that the supplier exists.
    try:
        result = calculate_supplier_scorecard(supplier_id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Then enforce supplier-level authorization.
    check_supplier_access(
        supplier_id=supplier_id,
        user=user,
    )

    return result

