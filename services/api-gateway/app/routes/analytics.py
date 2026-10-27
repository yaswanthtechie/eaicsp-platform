"""
Analytics Routes for the API Gateway.

Provides live KPI analytics from ClickHouse and Redis for the frontend dashboard:
GET /api/v1/analytics/kpis
"""

from datetime import datetime
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.analytics import KpiDashboardResponse
from app.services.analytics import analytics_kpi_service
from app.services.auth import auth_precheck_service

logger = logging.getLogger("api_gateway.analytics_route")

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
)


def _validate_dates(start_date: str | None, end_date: str | None) -> None:
    """Validate ISO YYYY-MM-DD date formats and range."""
    d_start = None
    d_end = None

    if start_date is not None:
        try:
            d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid start_date format, expected YYYY-MM-DD",
            )

    if end_date is not None:
        try:
            d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid end_date format, expected YYYY-MM-DD",
            )

    if d_start is not None and d_end is not None and d_start > d_end:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date",
        )


@router.get(
    "/kpis",
    response_model=KpiDashboardResponse,
    summary="Get Analytics KPIs",
    description="Retrieve aggregated live KPIs from Redis cache or ClickHouse analytics store.",
)
async def get_analytics_kpis(
    request: Request,
    warehouse_id: str | None = Query(
        None,
        description="Optional warehouse identifier (e.g. WH-ORD-01)",
    ),
    category: str | None = Query(
        None,
        description="Optional product category filter",
    ),
    start_date: str | None = Query(
        None,
        description="Optional start date in YYYY-MM-DD format",
    ),
    end_date: str | None = Query(
        None,
        description="Optional end date in YYYY-MM-DD format",
    ),
    window_days: int = Query(
        30,
        ge=1,
        description="Historical window in days for trend computation (default: 30)",
    ),
) -> Any:
    """
    Get live analytics KPIs across:
    1. Fill Rate
    2. Inventory Stockouts
    3. Open Purchase Orders
    4. Logistics On-Time Delivery

    Results are cached in Redis under the configured TTL (default: 300 seconds).
    """
    # 1. Gateway-level authentication pre-check
    auth_error = await auth_precheck_service.verify_request(
        request, "/api/v1/analytics"
    )
    if auth_error is not None:
        return auth_error

    # 2. Date format and range validation
    _validate_dates(start_date, end_date)

    eff_window_days = window_days
    if start_date is not None and end_date is not None:
        if request.query_params.get("window_days") is None:
            d_s = datetime.strptime(start_date, "%Y-%m-%d").date()
            d_e = datetime.strptime(end_date, "%Y-%m-%d").date()
            eff_window_days = max(1, (d_e - d_s).days)

    # 3. Retrieve live KPIs via service
    return await analytics_kpi_service.get_kpis(
        warehouse_id=warehouse_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
        window_days=eff_window_days,
    )
