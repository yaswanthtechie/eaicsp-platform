"""GET /api/v1/analytics/kpis, per contracts/openapi/analytics-kpis.yaml."""

from datetime import date, datetime
import re
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.schemas.analytics import KpiDashboardResponse
from app.services.analytics import KpiUnavailableError, analytics_kpi_service
from app.services.auth import auth_precheck_service

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

WAREHOUSE_RE = re.compile(r"^WH-[A-Z]{3}-\d{2}$")
MAX_WINDOW_DAYS = 365
MAX_CATEGORY_LENGTH = 64


class InvalidParameter(Exception):
    def __init__(self, parameter: str, message: str, **details: Any):
        self.message = message
        self.details = {"parameter": parameter, **details}


def _error(status_code: int, error_code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message, "details": details},
    )


def _parse_date(name: str, value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise InvalidParameter(name, f"Invalid {name} '{value}'. Expected format: YYYY-MM-DD.")


def _check_window(days: int) -> int:
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise InvalidParameter(
            "window_days",
            f"window_days must be from 1 to {MAX_WINDOW_DAYS}.",
            minimum=1,
            maximum=MAX_WINDOW_DAYS,
        )
    return days


@router.get(
    "/kpis",
    response_model=KpiDashboardResponse,
    summary="Get Analytics KPIs",
    description="Aggregated live KPIs from the Redis `live_kpis` cache or ClickHouse.",
)
async def get_analytics_kpis(
    request: Request,
    warehouse_id: str | None = Query(None, description="Canonical warehouse ID, e.g. WH-BLR-01"),
    category: str | None = Query(None, description="Product category filter"),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    window_days: str | None = Query(None, description="Rolling window in days, 1 to 365 (default 30)"),
    force_refresh: bool = Query(False, description="Bypass the Redis cache"),
) -> Any:
    auth_error = await auth_precheck_service.verify_request(request, "/api/v1/analytics")
    if auth_error is not None:
        return auth_error

    try:
        if warehouse_id is not None and not WAREHOUSE_RE.fullmatch(warehouse_id):
            raise InvalidParameter(
                "warehouse_id",
                f"Invalid warehouse_id format '{warehouse_id}'. Expected format: WH-XXX-NN (e.g. WH-BLR-01).",
                expected_pattern=WAREHOUSE_RE.pattern,
            )
        if category is not None and len(category) > MAX_CATEGORY_LENGTH:
            raise InvalidParameter("category", f"category must be at most {MAX_CATEGORY_LENGTH} characters.")

        d_start = _parse_date("start_date", start_date)
        d_end = _parse_date("end_date", end_date)
        if d_start and d_end and d_start > d_end:
            raise InvalidParameter("start_date", "start_date cannot be after end_date.")

        if window_days is not None:
            try:
                days = _check_window(int(window_days))
            except ValueError:
                days = _check_window(0)
        elif d_start and d_end:
            days = _check_window(max(1, (d_end - d_start).days))
        else:
            days = 30
    except InvalidParameter as exc:
        return _error(400, "INVALID_PARAMETER", exc.message, exc.details)

    try:
        return await analytics_kpi_service.get_kpis(
            warehouse_id=warehouse_id,
            category=category,
            start_date=start_date,
            end_date=end_date,
            window_days=days,
            force_refresh=force_refresh,
        )
    except KpiUnavailableError:
        return _error(
            503,
            "SERVICE_UNAVAILABLE",
            "Downstream analytical store (ClickHouse) is temporarily unavailable.",
        )
