
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.core.auth import (
    enforce_not_suspended,
    verify_token,
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

from app.services.supplier_risk_client import (
    get_supplier_risk_score,
    SupplierRiskServiceError,
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
    user=Depends(verify_token),
):
    # 1. Validate authenticated supplier identity.
    validate_supplier_identity(user)

    # 2. Ensure supplier can access only own data.
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

    # 4. Fetch risk score from Supplier Risk Service.
    try:
        risk_data = get_supplier_risk_score(supplier_id)

    except SupplierRiskServiceError:
        # Risk is informational.
        # Risk Service failure must not block onboarding.
        return {
            "supplier_id": supplier_id,
            "risk_available": False,
            "score": None,
            "tier": None,
            "top_factors": [],
            "top_evidence_articles": [],
            "computed_at": None,
        }

    # 5. Return the available risk information.
    return {
        **risk_data,
        "risk_available": risk_data["score"] is not None,
    }
