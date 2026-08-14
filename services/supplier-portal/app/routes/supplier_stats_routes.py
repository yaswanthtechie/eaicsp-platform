from fastapi import APIRouter, HTTPException

from app.schemas.supplier_stats import (
    SupplierStatsResponse,
)

from app.services.supplier_stats_service import (
    get_supplier_stats,
)

router = APIRouter()


@router.get(
    "/suppliers/{supplier_id}/stats",
    response_model=SupplierStatsResponse,
)
def supplier_stats(
    supplier_id: str,
):
    try:
        return get_supplier_stats(
            supplier_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )