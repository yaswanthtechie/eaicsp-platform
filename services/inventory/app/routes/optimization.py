import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import require_permission
from app.schemas.optimization import OptimizationRecommendationsResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/optimization",
    tags=["Optimization"],
)


@router.get(
    "/recommendations",
    response_model=OptimizationRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get reorder recommendations using demand forecast (Flow A)",
    description=(
        "Flow A: Computes replenishment recommendations by querying Forecast Service "
        "(GET /api/v1/demand/forecast/{sku_id}?horizon=30) and current inventory levels. "
        "Falls back to 28-day moving average if forecast is unavailable."
    ),
    dependencies=[
        Depends(require_permission("inventory:read")),
    ],
)
def get_optimization_recommendations():
    """
    Returns reorder recommendations for inventory optimization (Flow A).
    Returns 501 until Flow A calculation engine is wired.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Flow A optimization recommendation engine is under construction.",
    )
