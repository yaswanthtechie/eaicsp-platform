"""
Inventory Optimization Recommendation Service (Flow A, blueprint section 4)

Computes replenishment recommendations across inventory items:
1. Queries Forecast Service (GET /api/v1/demand/forecast/{sku_id}) for projected demand.
2. Falls back to 28-day moving average from sales history if unavailable.
3. Computes reorder points: reorder_point = int(daily_demand * lead_time + safety_stock).
4. Generates recommendation line items for SKUs where current_stock < reorder_point.
5. Looks up preferred / lowest-cost supplier to estimate total spend.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import Inventory
from app.schemas.optimization import (
    OptimizationRecommendationsResponse,
    RecommendationLineItem,
)
from app.services.forecast_client import ForecastClient, forecast_client
from app.services.purchase_order_service import select_supplier

logger = logging.getLogger(__name__)


def generate_recommendations(
    db: Session,
    warehouse_id: Optional[str] = None,
    sku_id: Optional[str] = None,
    client: Optional[ForecastClient] = None,
    horizon: Optional[int] = None,
    fallback_days: Optional[int] = None,
) -> OptimizationRecommendationsResponse:
    """
    Generate purchase order recommendations for inventory items below reorder points.
    """
    fc = client or forecast_client
    h = horizon or settings.FORECAST_HORIZON_DAYS
    fb_days = fallback_days or settings.FORECAST_FALLBACK_DAYS

    query = db.query(Inventory)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if sku_id:
        query = query.filter(Inventory.sku_id == sku_id)

    items = query.order_by(Inventory.warehouse_id, Inventory.sku_id).all()

    recommendations: List[RecommendationLineItem] = []

    for item in items:
        # Resolve demand via model forecast or 28-day history fallback
        demand_res = fc.resolve_demand(
            db=db,
            sku_id=item.sku_id,
            warehouse_id=item.warehouse_id,
            horizon=h,
            fallback_days=fb_days,
        )

        lead_time = item.lead_time_days if item.lead_time_days and item.lead_time_days > 0 else 7
        safety = item.safety_stock if item.safety_stock and item.safety_stock >= 0 else 0

        reorder_point = int(demand_res.daily_demand * lead_time + safety)

        # Check if item needs replenishment
        if item.quantity_on_hand < reorder_point:
            needed_qty = reorder_point - item.quantity_on_hand
            recommended_order_quantity = max(int(needed_qty), 1)

            # Determine supplier and unit cost
            try:
                supplier = select_supplier(db, sku_id=item.sku_id)
                supplier_id = supplier.supplier_id
                unit_cost = float(supplier.unit_cost)
            except Exception as exc:
                logger.warning(
                    "No supplier found for SKU %s, defaulting to SUP-00001: %s",
                    item.sku_id,
                    exc,
                )
                supplier_id = "SUP-00001"
                unit_cost = 0.0

            estimated_total_cost = round(recommended_order_quantity * unit_cost, 2)

            recommendations.append(
                RecommendationLineItem(
                    sku_id=item.sku_id,
                    warehouse_id=item.warehouse_id,
                    supplier_id=supplier_id,
                    current_stock=item.quantity_on_hand,
                    reorder_point=reorder_point,
                    safety_stock=safety,
                    forecast_demand=demand_res.forecast_demand,
                    forecast_source=demand_res.forecast_source,
                    recommended_order_quantity=recommended_order_quantity,
                    estimated_unit_cost=unit_cost,
                    estimated_total_cost=estimated_total_cost,
                )
            )

    total_recommended_spend = round(
        sum(r.estimated_total_cost for r in recommendations), 2
    )

    return OptimizationRecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        recommendations=recommendations,
        total_recommended_spend=total_recommended_spend,
    )

