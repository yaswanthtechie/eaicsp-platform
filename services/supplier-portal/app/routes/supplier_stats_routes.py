from fastapi import APIRouter, HTTPException

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
# SUPPLIER STATS
# ============================================================

@router.get(
    "/{supplier_id}/stats",
    response_model=SupplierStatsResponse,
)
def supplier_stats(
    supplier_id: str,
):
    try:
        return get_supplier_stats(supplier_id)

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )


# ============================================================
# SUPPLIER SCORECARD
# ============================================================

@router.get(
    "/{supplier_id}/scorecard",
    response_model=SupplierScorecard,
)
def get_supplier_scorecard(
    supplier_id: str,
):
    """
    Return the real-time supplier performance scorecard.
    """
    try:
        return calculate_supplier_scorecard(supplier_id)

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )