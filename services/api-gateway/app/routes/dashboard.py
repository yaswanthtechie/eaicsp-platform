"""
Aggregated Health Dashboard route for the API Gateway.
"""

from fastapi import APIRouter

from app.services.metrics import metrics_collector

router = APIRouter(
    prefix="",
    tags=["Dashboard"],
)


@router.get(
    "/dashboard",
    summary="Aggregated Health & Metrics Dashboard",
)
async def get_gateway_dashboard():
    """
    Return aggregated real-time gateway metrics for downstream microservices.
    Includes circuit breaker state, cache hit rate, request volume, p50 and p95 latency.
    """
    return metrics_collector.get_all_metrics()
