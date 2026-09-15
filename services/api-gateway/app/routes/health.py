"""
Health check routes for the API Gateway.
"""

from fastapi import APIRouter, Request

from app.schemas.responses import HealthResponse
from app.services.health import get_system_health

# --------------------------------------------------
# Router
# --------------------------------------------------

router = APIRouter(
    tags=["Health"],
)


# --------------------------------------------------
# Health Endpoint
# --------------------------------------------------

@router.get(
    "",
    response_model=HealthResponse,
    summary="Gateway Health Check",
)
async def health_check(
    request: Request,
):
    """
    Check the health status of all configured
    downstream microservices.

    Returns:
        Dict[str, str]:
            {
                "inventory": "UP",
                "auth": "UP",
                "supplier-risk": "DOWN"
            }
    """

    return await get_system_health(request)