
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.core.auth import (
    enforce_not_suspended,
    require_roles,
)

from app.schemas.supplier_risk import (
    SupplierRiskScoreResponse,
)

from app.routes.supplier_onboarding import (
    validate_supplier_identity,
    check_supplier_access,
)

from app.services.supplier_onboarding_service import (
    get_supplier,
)

from app.services.supplier_risk_service import (
    get_supplier_risk_score_response,
)


router = APIRouter(
    prefix="/suppliers",
    tags=["Supplier Risk"],
    dependencies=[Depends(enforce_not_suspended)],
)


# ============================================================
# GET SUPPLIER RISK SCORE
# ============================================================

@router.get(
    "/{supplier_id}/risk-score",
    response_model=SupplierRiskScoreResponse,
)
def get_supplier_risk_score_endpoint(
    supplier_id: str,
    user=Depends(
        require_roles(
            "supplier",
            "procurement_manager",
            "compliance_officer",
        )
    ),
):
    # 1. Validate authenticated supplier identity.
    validate_supplier_identity(user)

    # 2. Restrict supplier users to their own supplier data.
    check_supplier_access(
        supplier_id,
        user,
    )

    # 3. Verify supplier exists in Supplier Portal.
    try:
        get_supplier(supplier_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # 4. Retrieve risk information and build the response.
    try:
        return get_supplier_risk_score_response(supplier_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
