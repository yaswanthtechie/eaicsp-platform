import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.database import get_db
from app.schemas.optimization import OptimizationRecommendationsResponse
from app.services.optimization_service import generate_recommendations

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
    responses={
        401: {"description": "Missing or invalid token"},
        403: {"description": "Insufficient permissions"},
    },
    dependencies=[
        Depends(require_permission("inventory:read")),
    ],
)
def get_optimization_recommendations(
    db: Session = Depends(get_db),
) -> OptimizationRecommendationsResponse:
    """
    Returns reorder recommendations for inventory optimization (Flow A).
    Queries model forecast or falls back to 28-day moving average.
    """
    return generate_recommendations(db=db)
