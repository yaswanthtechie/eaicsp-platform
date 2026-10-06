from datetime import date, timedelta

import pytest

from app.models.inventory import Inventory
from app.models.sales_history import SalesHistory
from app.services.network_optimization_service import (
    optimize_network_safety_stock,
)


def test_network_optimization_aggregates_child_demand(
    db_session,
):
    central = Inventory(
        sku_id="SKU-NET-001",
        warehouse_id="WH-CENTRAL",
        product_name="Network Product",
        category="Test",
        quantity_on_hand=500,
        avg_daily_demand=0,
        lead_time_days=5,
        safety_stock=20,
        warehouse_type="central",
        parent_warehouse_id=None,
        version=1,
    )

    regional = Inventory(
        sku_id="SKU-NET-001",
        warehouse_id="WH-REGIONAL",
        product_name="Network Product",
        category="Test",
        quantity_on_hand=200,
        avg_daily_demand=0,
        lead_time_days=4,
        safety_stock=15,
        warehouse_type="regional",
        parent_warehouse_id="WH-CENTRAL",
        version=1,
    )

    local = Inventory(
        sku_id="SKU-NET-001",
        warehouse_id="WH-LOCAL",
        product_name="Network Product",
        category="Test",
        quantity_on_hand=50,
        avg_daily_demand=0,
        lead_time_days=3,
        safety_stock=10,
        warehouse_type="local",
        parent_warehouse_id="WH-REGIONAL",
        version=1,
    )

    db_session.add_all(
        [
            central,
            regional,
            local,
        ]
    )

    db_session.commit()

    today = date.today()

    for index in range(30):
        sale_date = today - timedelta(days=index)

        db_session.add(
            SalesHistory(
                sku_id="SKU-NET-001",
                warehouse_id="WH-CENTRAL",
                sale_date=sale_date,
                quantity_sold=2,
            )
        )

        db_session.add(
            SalesHistory(
                sku_id="SKU-NET-001",
                warehouse_id="WH-REGIONAL",
                sale_date=sale_date,
                quantity_sold=3,
            )
        )

        db_session.add(
            SalesHistory(
                sku_id="SKU-NET-001",
                warehouse_id="WH-LOCAL",
                sale_date=sale_date,
                quantity_sold=5,
            )
        )

    db_session.commit()

    result = optimize_network_safety_stock(
        db=db_session,
        days=30,
    )

    assert result["warehouses"]

    local_result = next(
        item
        for item in result["warehouses"]
        if item["warehouse_id"] == "WH-LOCAL"
    )

    regional_result = next(
        item
        for item in result["warehouses"]
        if item["warehouse_id"] == "WH-REGIONAL"
    )

    central_result = next(
        item
        for item in result["warehouses"]
        if item["warehouse_id"] == "WH-CENTRAL"
    )

    assert local_result["own_daily_demand"] == 5.0

    assert (
        local_result["downstream_daily_demand"]
        == 5.0
    )

    assert (
        regional_result["downstream_daily_demand"]
        == 8.0
    )

    assert (
        central_result["downstream_daily_demand"]
        == 10.0
    )


def test_network_optimization_rejects_invalid_window(
    db_session,
):
    with pytest.raises(ValueError) as exc_info:
        optimize_network_safety_stock(
            db=db_session,
            days=0,
        )

    assert (
        "Demand window must be greater than zero"
        in str(exc_info.value)
    )


def test_network_optimization_detects_hierarchy_cycle(
    db_session,
):
    first = Inventory(
        sku_id="SKU-CYCLE",
        warehouse_id="WH001",
        product_name="Cycle Product",
        category="Test",
        quantity_on_hand=100,
        avg_daily_demand=0,
        lead_time_days=2,
        safety_stock=10,
        warehouse_type="regional",
        parent_warehouse_id="WH002",
        version=1,
    )

    second = Inventory(
        sku_id="SKU-CYCLE",
        warehouse_id="WH002",
        product_name="Cycle Product",
        category="Test",
        quantity_on_hand=100,
        avg_daily_demand=0,
        lead_time_days=2,
        safety_stock=10,
        warehouse_type="central",
        parent_warehouse_id="WH001",
        version=1,
    )

    db_session.add_all(
        [
            first,
            second,
        ]
    )

    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        optimize_network_safety_stock(
            db=db_session,
            days=30,
        )

    assert (
        "Warehouse hierarchy contains a cycle"
        in str(exc_info.value)
    )