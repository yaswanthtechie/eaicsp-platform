from datetime import date, timedelta
from math import sqrt
from statistics import stdev

import pytest

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
from app.services.network_optimization_service import (
    optimize_network_safety_stock,
)


def add_warehouse(db_session, warehouse_id, parent, lead_time, safety_stock=0):
    db_session.add(
        Inventory(
            sku_id="SKU-NET",
            product_name="Network Widget",
            warehouse_id=warehouse_id,
            category="Widgets",
            quantity_on_hand=100,
            lead_time_days=lead_time,
            safety_stock=safety_stock,
            warehouse_type="central" if parent is None else "local",
            parent_warehouse_id=parent,
        )
    )


def add_sales(db_session, warehouse_id, daily_quantities):
    """daily_quantities[0] is today, [1] yesterday, and so on."""
    for offset, quantity in enumerate(daily_quantities):
        db_session.add(
            SalesHistory(
                sku_id="SKU-NET",
                warehouse_id=warehouse_id,
                sale_date=date.today() - timedelta(days=offset),
                quantity_sold=quantity,
            )
        )


def by_warehouse(result):
    return {
        item["warehouse_id"]: item
        for item in result["warehouses"]
    }


def test_steady_demand_needs_no_statistical_safety_stock(db_session):
    # Perfectly steady demand has no variability to buffer against,
    # so safety stock falls back to the configured floor.
    add_warehouse(db_session, "C1", None, lead_time=5, safety_stock=20)
    add_warehouse(db_session, "L1", "C1", lead_time=3, safety_stock=10)
    add_sales(db_session, "L1", [5] * 30)
    db_session.commit()

    result = by_warehouse(optimize_network_safety_stock(db_session, days=30))

    assert result["L1"]["downstream_demand_std"] == 0
    assert result["L1"]["optimized_safety_stock"] == 10
    assert result["C1"]["optimized_safety_stock"] == 20

    # target = safety stock + lead-time demand, counted once
    assert result["L1"]["lead_time_demand"] == 15
    assert result["L1"]["target_quantity"] == 10 + 15


def test_safety_stock_follows_z_sigma_sqrt_lead_time(db_session, monkeypatch):
    monkeypatch.setattr(settings, "NETWORK_SERVICE_LEVEL_Z", 1.65)

    pattern = [0, 10] * 15
    add_warehouse(db_session, "L1", None, lead_time=4)
    add_sales(db_session, "L1", pattern)
    db_session.commit()

    local = by_warehouse(optimize_network_safety_stock(db_session, days=30))["L1"]

    sigma = stdev(pattern)
    assert local["downstream_demand_std"] == pytest.approx(sigma, abs=0.01)
    assert local["optimized_safety_stock"] == pytest.approx(
        1.65 * sigma * sqrt(4), abs=1
    )


def test_parent_pools_child_variability(db_session):
    add_warehouse(db_session, "C1", None, lead_time=5)
    add_warehouse(db_session, "L1", "C1", lead_time=3)
    add_warehouse(db_session, "L2", "C1", lead_time=3)
    add_sales(db_session, "L1", [0, 10] * 15)
    add_sales(db_session, "L2", [10, 0] * 15)
    db_session.commit()

    result = by_warehouse(optimize_network_safety_stock(db_session, days=30))

    child_std = result["L1"]["downstream_demand_std"]
    parent_std = result["C1"]["downstream_demand_std"]

    # Variances add, standard deviations don't: pooling at the
    # parent needs less buffer than the children's buffers summed.
    assert parent_std == pytest.approx(sqrt(2) * child_std, abs=0.01)
    assert parent_std < 2 * child_std
    assert result["C1"]["downstream_daily_demand"] == 10.0
