import logging
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.core.config import settings
from app.database import get_db
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.supplier import Supplier
from app.schemas.forecast import ForecastContract
from app.schemas.optimization import (
    OptimizationRecommendationsResponse,
    RecommendationLineItem,
)
from app.services.abc_service import (
    classify_skus,
    calculate_tier_safety_stock,
)
from app.services.demand_service import calculate_rolling_average_demand
from app.services.forecast_adapter import resolve_daily_demand

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["Optimization"])

FALLBACK_DEMAND_DAYS = 28
FORECAST_HORIZON = 30


def fetch_forecast(
    client: httpx.Client,
    sku_id: str,
    warehouse_id: str,
):
    """Fetch a forecast contract. Return None when unavailable."""
    try:
        response = client.get(
            f"{settings.FORECAST_SERVICE_URL.rstrip('/')}"
            f"/api/v1/demand/forecast/{sku_id}",
            params={
                "warehouse_id": warehouse_id,
                "horizon": FORECAST_HORIZON,
            },
        )

        if response.status_code != 200:
            logger.warning(
                "Forecast unavailable for %s/%s: HTTP %s",
                sku_id,
                warehouse_id,
                response.status_code,
            )
            return None

        return ForecastContract.model_validate(response.json())

    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Forecast request failed for %s/%s: %s",
            sku_id,
            warehouse_id,
            exc,
        )
        return None


@router.get(
    "/recommendations",
    response_model=OptimizationRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get reorder recommendations using demand forecast (Flow A)",
    description=(
        "Uses Forecast Service demand when available and falls back "
        "to 28-day historical demand."
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
):
    inventories = db.query(Inventory).all()

    if not inventories:
        return OptimizationRecommendationsResponse(
            generated_at=datetime.now(timezone.utc),
            recommendations=[],
            total_recommended_spend=0.0,
        )

    classifications = classify_skus(db)
    recommendations = []
    total_spend = 0.0
    forecast_cache = {}

    with httpx.Client(timeout=5.0) as client:
        for inventory in inventories:
            key = (inventory.sku_id, inventory.warehouse_id)

            product = (
                db.query(Product)
                .filter(Product.sku_id == inventory.sku_id)
                .first()
            )

            if product is None:
                logger.warning(
                    "Skipping %s: product record not found",
                    inventory.sku_id,
                )
                continue

            supplier = None
            if product.supplier_id:
                supplier = (
                    db.query(Supplier)
                    .filter(
                        Supplier.supplier_id == product.supplier_id,
                        Supplier.sku_id == inventory.sku_id,
                    )
                    .first()
                )

            # The response contract requires a supplier ID.
            if supplier is None:
                logger.warning(
                    "Skipping %s: matching supplier record not found",
                    inventory.sku_id,
                )
                continue

            if key not in forecast_cache:
                forecast_cache[key] = fetch_forecast(
                    client,
                    inventory.sku_id,
                    inventory.warehouse_id,
                )

            contract = forecast_cache[key]

            history_demand = calculate_rolling_average_demand(
                db=db,
                sku_id=inventory.sku_id,
                warehouse_id=inventory.warehouse_id,
                days=FALLBACK_DEMAND_DAYS,
            )

            demand = resolve_daily_demand(
                contract=contract,
                sku_id=inventory.sku_id,
                warehouse_id=inventory.warehouse_id,
                on_date=(
                    contract.forecast[0].date
                    if contract and contract.forecast
                    else date.today()
                ),
                now=datetime.now(timezone.utc),
                history_daily_demand=history_demand,
            )

            daily_demand = demand["daily_demand"]
            forecast_source = (
                "model"
                if demand["source"] == "forecast"
                else "fallback"
            )

            classification = classifications.get(key)
            abc_tier = (
                classification["abc_tier"]
                if classification
                else "C"
            )

            adjusted_safety_stock = int(
                calculate_tier_safety_stock(
                    base_safety_stock=inventory.safety_stock,
                    abc_tier=abc_tier,
                )
            )

            lead_time = supplier.lead_time_days

            reorder_point = int(
                daily_demand * lead_time + adjusted_safety_stock
            )

            order_quantity = max(
                0,
                reorder_point - inventory.quantity_on_hand,
            )

            if order_quantity <= 0:
                continue

            unit_cost = float(supplier.unit_cost or product.unit_cost or 0)
            estimated_total_cost = round(
                order_quantity * unit_cost,
                2,
            )

            recommendations.append(
                RecommendationLineItem(
                    sku_id=inventory.sku_id,
                    warehouse_id=inventory.warehouse_id,
                    supplier_id=supplier.supplier_id,
                    current_stock=inventory.quantity_on_hand,
                    reorder_point=reorder_point,
                    safety_stock=adjusted_safety_stock,
                    forecast_demand=daily_demand,
                    forecast_source=forecast_source,
                    recommended_order_quantity=order_quantity,
                    estimated_unit_cost=unit_cost,
                    estimated_total_cost=estimated_total_cost,
                )
            )

            total_spend += estimated_total_cost

    return OptimizationRecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        recommendations=recommendations,
        total_recommended_spend=round(total_spend, 2),
    )
