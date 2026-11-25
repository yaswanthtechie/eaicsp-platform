import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, cast

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.sales_history import SalesHistory
from app.models.supplier import SupplierLeadTime


def calculate_z_score(service_level: float) -> float:
    """Calculate normal distribution quantile z from target service level (0 < service_level < 1)."""
    if not (0.0 < service_level < 1.0):
        raise ValueError(
            f"Service level must be strictly between 0 and 1, got {service_level}"
        )
    return float(statistics.NormalDist().inv_cdf(service_level))


def calculate_demand_statistics(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    weeks: int | None = None,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """
    Per SKU and warehouse: average daily demand and its standard deviation (last N weeks, config),
    from imported sales. Days with zero sales in the observed window are counted as 0.
    """
    if weeks is None:
        weeks = settings.SAFETY_STOCK_DEMAND_HISTORY_WEEKS

    end_date = as_of_date or date.today()
    start_date = end_date - timedelta(days=weeks * 7 - 1)

    records = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.sku_id == sku_id,
            SalesHistory.warehouse_id == warehouse_id,
            SalesHistory.sale_date >= start_date,
            SalesHistory.sale_date <= end_date,
        )
        .order_by(SalesHistory.sale_date)
        .all()
    )

    if not records:
        return {
            "avg_daily_demand": 0.0,
            "sd_daily_demand": 0.0,
            "cv": 0.0,
            "observed_days": 0,
            "demand_window_weeks": weeks,
            "has_sufficient_history": False,
        }

    daily_sales: dict[date, float] = defaultdict(float)
    for record in records:
        daily_sales[cast(date, record.sale_date)] += float(record.quantity_sold)

    first_day = min(daily_sales)
    observed_days = (end_date - first_day).days + 1

    values = [
        daily_sales.get(first_day + timedelta(days=offset), 0.0)
        for offset in range(observed_days)
    ]

    total_days = len(values)
    avg_daily_demand = sum(values) / total_days if total_days > 0 else 0.0

    if total_days >= 2:
        sd_daily_demand = statistics.stdev(values)
    else:
        sd_daily_demand = 0.0

    cv = (sd_daily_demand / avg_daily_demand) if avg_daily_demand > 0 else 0.0
    distinct_sale_days = len(daily_sales)
    has_sufficient = (
        observed_days >= settings.SAFETY_STOCK_MIN_DEMAND_DAYS
        and distinct_sale_days >= 2
    )

    return {
        "avg_daily_demand": round(avg_daily_demand, 4),
        "sd_daily_demand": round(sd_daily_demand, 4),
        "cv": round(cv, 4),
        "observed_days": observed_days,
        "distinct_sale_days": distinct_sale_days,
        "demand_window_weeks": weeks,
        "has_sufficient_history": has_sufficient,
    }


def calculate_lead_time_statistics(
    db: Session,
    sku_id: str,
    warehouse_id: str | None = None,
    supplier_id: str | None = None,
) -> dict[str, Any]:
    """
    Per supplier (and SKU where available): average lead time and its standard deviation,
    from PO history (received_date minus order_date, Received POs only).
    """
    base_query = db.query(PurchaseOrder).filter(
        func.lower(PurchaseOrder.status) == "received",
        PurchaseOrder.order_date.isnot(None),
        PurchaseOrder.received_date.isnot(None),
        PurchaseOrder.received_date >= PurchaseOrder.order_date,
    )

    sku_filter = base_query.filter(PurchaseOrder.sku_id == sku_id)
    if supplier_id:
        sku_filter = sku_filter.filter(PurchaseOrder.supplier_id == supplier_id)

    sku_pos = sku_filter.all()
    sku_lead_times = [
        (po.received_date - po.order_date).days
        for po in sku_pos
        if po.received_date and po.order_date
    ]

    if len(sku_lead_times) >= settings.SAFETY_STOCK_MIN_PO_COUNT:
        avg_lt = sum(sku_lead_times) / len(sku_lead_times)
        sd_lt = statistics.stdev(sku_lead_times) if len(sku_lead_times) >= 2 else 0.0
        return {
            "avg_lead_time": round(avg_lt, 4),
            "sd_lead_time": round(sd_lt, 4),
            "po_count": len(sku_lead_times),
            "lead_time_source": "po_history_sku",
            "has_sufficient_history": True,
            "supplier_id": supplier_id,
        }

    resolved_supplier_id = supplier_id
    if not resolved_supplier_id:
        product = db.query(Product).filter(Product.sku_id == sku_id).first()
        if product and product.supplier_id:
            resolved_supplier_id = product.supplier_id

    if resolved_supplier_id:
        supplier_pos = base_query.filter(
            PurchaseOrder.supplier_id == resolved_supplier_id
        ).all()
        supplier_lead_times = [
            (po.received_date - po.order_date).days
            for po in supplier_pos
            if po.received_date and po.order_date
        ]
        if len(supplier_lead_times) >= settings.SAFETY_STOCK_MIN_PO_COUNT:
            avg_lt = sum(supplier_lead_times) / len(supplier_lead_times)
            sd_lt = (
                statistics.stdev(supplier_lead_times)
                if len(supplier_lead_times) >= 2
                else 0.0
            )
            return {
                "avg_lead_time": round(avg_lt, 4),
                "sd_lead_time": round(sd_lt, 4),
                "po_count": len(supplier_lead_times),
                "lead_time_source": "po_history_supplier",
                "has_sufficient_history": True,
                "supplier_id": resolved_supplier_id,
            }

    # Fallback to static lead time (from SupplierLeadTime or Inventory)
    static_lt = None
    lead_time_source = "static_lead_time"
    if resolved_supplier_id:
        slt = (
            db.query(SupplierLeadTime)
            .filter(
                SupplierLeadTime.supplier_id == resolved_supplier_id,
                SupplierLeadTime.sku_id == sku_id,
            )
            .first()
        )
        if slt and slt.average_lead_time_days:
            static_lt = float(slt.average_lead_time_days)
            lead_time_source = "supplier_lead_time"

    if static_lt is None:
        inv_query = db.query(Inventory).filter(Inventory.sku_id == sku_id)
        if warehouse_id:
            inv_query = inv_query.filter(Inventory.warehouse_id == warehouse_id)
        inv = inv_query.first()
        if inv and inv.lead_time_days:
            static_lt = float(inv.lead_time_days)
            lead_time_source = "inventory_lead_time"

    if static_lt is None:
        static_lt = float(settings.SAFETY_STOCK_DEFAULT_LEAD_TIME_DAYS)
        lead_time_source = "default_config"

    return {
        "avg_lead_time": round(static_lt, 4),
        "sd_lead_time": 0.0,
        "po_count": len(sku_lead_times),
        "lead_time_source": lead_time_source,
        "has_sufficient_history": False,
        "supplier_id": resolved_supplier_id,
    }


def get_abc_tier_from_cumulative_share(cum_share: float) -> str:
    """
    Helper to classify ABC tier from cumulative revenue share (0.0 to 1.0).
    Boundary tests:
    - cum_share <= A_threshold -> 'A'
    - cum_share <= B_threshold -> 'B'
    - else -> 'C'
    """
    if cum_share <= settings.ABC_REVENUE_A_THRESHOLD:
        return "A"
    elif cum_share <= settings.ABC_REVENUE_B_THRESHOLD:
        return "B"
    return "C"


def classify_abc_by_revenue(
    db: Session,
    sku_id: str,
) -> str:
    """
    ABC classification by revenue from sales history and unit price.
    If Product.abc_class is explicitly set, it takes precedence.
    Otherwise, computes revenue contribution per SKU across the catalog.
    """
    product = db.query(Product).filter(Product.sku_id == sku_id).first()
    if product and product.abc_class in ("A", "B", "C"):
        return str(product.abc_class)

    revenues = (
        db.query(
            SalesHistory.sku_id,
            func.sum(SalesHistory.quantity_sold * Product.unit_price).label(
                "total_revenue"
            ),
        )
        .join(Product, Product.sku_id == SalesHistory.sku_id)
        .group_by(SalesHistory.sku_id)
        .all()
    )

    if not revenues:
        return "C"

    sorted_rev = sorted(
        revenues,
        key=lambda r: float(r.total_revenue or 0.0),
        reverse=True,
    )
    total_rev = sum(float(r.total_revenue or 0.0) for r in sorted_rev)
    if total_rev <= 0:
        return "C"

    prior_cum = 0.0
    for r in sorted_rev:
        prior_ratio = prior_cum / total_rev
        if r.sku_id == sku_id:
            return get_abc_tier_from_cumulative_share(prior_ratio)
        prior_cum += float(r.total_revenue or 0.0)

    return "C"


def classify_xyz_by_cv(cv: float) -> str:
    """
    XYZ classification by demand variability (coefficient of variation = sd_demand / avg_demand).
    - CV <= XYZ_CV_X_THRESHOLD (default 0.50): 'X' (steady, low variability)
    - XYZ_CV_X_THRESHOLD < CV <= XYZ_CV_Y_THRESHOLD (default 1.00): 'Y' (moderate variability)
    - CV > XYZ_CV_Y_THRESHOLD: 'Z' (high variability)
    """
    if cv <= settings.XYZ_CV_X_THRESHOLD:
        return "X"
    elif cv <= settings.XYZ_CV_Y_THRESHOLD:
        return "Y"
    else:
        return "Z"


def get_service_level_and_z(abc_class: str, xyz_class: str) -> tuple[float, float]:
    """Look up target service level for the ABC-XYZ class and calculate z-score."""
    class_key = f"{abc_class}{xyz_class}".upper()
    service_level = settings.SAFETY_STOCK_SERVICE_LEVELS.get(
        class_key,
        settings.SAFETY_STOCK_SERVICE_LEVELS.get("CZ", 0.90),
    )
    z = calculate_z_score(service_level)
    return service_level, z


def calculate_safety_stock_formula(
    avg_demand: float,
    sd_demand: float,
    avg_lead_time: float,
    sd_lead_time: float,
    z: float,
) -> float:
    """
    Safety stock = z * sqrt(LT * sd_demand^2 + avg_demand^2 * sd_LT^2).
    """
    variance_term = (avg_lead_time * (sd_demand**2)) + (
        (avg_demand**2) * (sd_lead_time**2)
    )
    if variance_term <= 0.0:
        return 0.0
    return float(z * math.sqrt(variance_term))


def calculate_service_level_safety_stock(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    weeks: int | None = None,
    as_of_date: date | None = None,
    base_safety_stock: int | None = None,
    abc_class: str | None = None,
) -> dict[str, Any]:
    """
    Computes service-level safety stock from demand and lead-time variability.
    Falls back to current safety stock if history is below configured minimums.
    """
    inventory = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )

    product = db.query(Product).filter(Product.sku_id == sku_id).first()
    supplier_id = product.supplier_id if product else None

    # Current safety stock on the item, or fallback to default
    if base_safety_stock is not None:
        current_ss = int(base_safety_stock)
    elif inventory is not None and inventory.safety_stock is not None:
        current_ss = int(inventory.safety_stock)
    else:
        current_ss = int(settings.DEFAULT_SAFETY_STOCK)

    # 1. Demand Statistics
    demand_stats = calculate_demand_statistics(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        weeks=weeks,
        as_of_date=as_of_date,
    )

    # 2. Lead Time Statistics
    lt_stats = calculate_lead_time_statistics(
        db=db,
        sku_id=sku_id,
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
    )

    # 3. ABC & XYZ Classification
    resolved_abc = abc_class or classify_abc_by_revenue(db=db, sku_id=sku_id)
    xyz_class = classify_xyz_by_cv(demand_stats["cv"])
    abc_xyz_class = f"{resolved_abc}{xyz_class}"

    # 4. Service Level & Z-Score
    service_level, z_score = get_service_level_and_z(resolved_abc, xyz_class)

    # 5. Check if history is sufficient or if fallback is required
    inputs_used = {
        "avg_daily_demand": demand_stats["avg_daily_demand"],
        "sd_daily_demand": demand_stats["sd_daily_demand"],
        "demand_cv": demand_stats["cv"],
        "demand_history_days": demand_stats["observed_days"],
        "demand_window_weeks": demand_stats["demand_window_weeks"],
        "avg_lead_time_days": lt_stats["avg_lead_time"],
        "sd_lead_time_days": lt_stats["sd_lead_time"],
        "lead_time_po_count": lt_stats["po_count"],
        "lead_time_source": lt_stats["lead_time_source"],
        "supplier_id": lt_stats["supplier_id"],
    }

    if not demand_stats["has_sufficient_history"]:
        is_fallback = True
        method = "fallback"
        fallback_reason: str | None = (
            f"Insufficient demand history: observed {demand_stats['observed_days']} days "
            f"(minimum {settings.SAFETY_STOCK_MIN_DEMAND_DAYS} required)"
        )
        safety_stock = current_ss
        calculated_ss = float(current_ss)
    else:
        is_fallback = False
        fallback_reason = None
        if not lt_stats["has_sufficient_history"]:
            method = "statistical_static_lead_time"
        else:
            method = "statistical"

        calculated_ss = calculate_safety_stock_formula(
            avg_demand=demand_stats["avg_daily_demand"],
            sd_demand=demand_stats["sd_daily_demand"],
            avg_lead_time=lt_stats["avg_lead_time"],
            sd_lead_time=lt_stats["sd_lead_time"],
            z=z_score,
        )
        safety_stock = max(0, math.ceil(calculated_ss))

    return {
        "sku_id": sku_id,
        "warehouse_id": warehouse_id,
        "abc_class": resolved_abc,
        "xyz_class": xyz_class,
        "abc_xyz_class": abc_xyz_class,
        "service_level": round(service_level, 4),
        "z_score": round(z_score, 4),
        "inputs_used": inputs_used,
        "calculated_safety_stock": round(calculated_ss, 4),
        "safety_stock": safety_stock,
        "current_safety_stock": current_ss,
        "method": method,
        "is_fallback": is_fallback,
        "fallback_reason": fallback_reason,
    }
