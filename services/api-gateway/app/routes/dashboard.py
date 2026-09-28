"""
Aggregated Health Dashboard route for the API Gateway.
"""

from fastapi import APIRouter, Request

from app.core.config import settings
from app.services.health import get_system_health
from app.services.metrics import metrics_collector

router = APIRouter(
    prefix="",
    tags=["Dashboard"],
)


@router.get(
    "/status",
    summary="Gateway Operational Status",
)
async def get_gateway_status():
    """
    Return gateway operational status metadata without exposing any sensitive
    configuration, credentials, or secret keys.
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "app_name": settings.APP_NAME,
    }


@router.get(
    "/dashboard",
    summary="Aggregated Health & Metrics Dashboard",
)
async def get_gateway_dashboard(request: Request):
    """
    Return aggregated real-time gateway metrics for downstream microservices.
    Includes circuit breaker state, cache hit rate, request volume, p50 and p95 latency,
    plus the health of the Inventory -> Compliance and Supplier-Portal -> Compliance chains.
    """
    # Snapshot metrics first, then run the live health pings (up to 3s each),
    # so the reported circuit-breaker states are the ones at request time.
    dashboard = metrics_collector.get_all_metrics()
    health_status = await get_system_health(request)
    return metrics_collector.add_dependency_health(dashboard, health_status)
