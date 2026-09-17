"""
BFF Aggregation Routes for the API Gateway.

Provides Backend-For-Frontend endpoints that aggregate data from multiple
downstream microservices concurrently.
"""

from typing import Any

from fastapi import APIRouter, Request

from app.services.aggregation import AggregationService

router = APIRouter(
    tags=["BFF Aggregation"],
)


@router.get(
    "/api/v1/dashboard/summary",
    summary="Aggregated Dashboard Summary",
    description="Fans out to Inventory, Compliance, and Logistics services concurrently and returns an aggregated status and payload.",
)
async def get_dashboard_summary(request: Request) -> dict[str, Any]:
    """
    Get aggregated dashboard summary by querying Inventory, Compliance,
    and Logistics microservices in parallel.
    """
    return await AggregationService.get_dashboard_summary(request)
