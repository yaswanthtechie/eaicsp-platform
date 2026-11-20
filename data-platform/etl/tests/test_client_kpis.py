from datetime import date
from client_ingest.build_client_kpis import calculate_daily_sales, calculate_stock_cover, calculate_supplier_on_time

def test_daily_sales_aggregates_quantity_and_revenue():
    rows = [
        {"sale_date": "2026-01-10", "sku_id": "SKU-1", "warehouse_id": "WH-1", "quantity_sold": 2, "sales_amount": 20},
        {"sale_date": "2026-01-10", "sku_id": "SKU-1", "warehouse_id": "WH-1", "quantity_sold": 3, "sales_amount": 45},
    ]
    assert calculate_daily_sales(rows) == [(date(2026, 1, 10), "SKU-1", "WH-1", 5, 65.0)]

def test_zero_sales_returns_null_stock_cover():
    inventory = [{"snapshot_date": "2026-01-28", "sku_id": "SKU-1", "warehouse_id": "WH-1", "quantity_on_hand": 100}]
    result = calculate_stock_cover(inventory, [])
    assert result[0][4] == 0
    assert result[0][5] is None

def test_supplier_on_time_excludes_cancelled_orders():
    rows = [
        {"po_status": "Received", "received_date": "2026-01-10", "expected_date": "2026-01-10", "supplier_id": "SUP-1"},
        {"po_status": "Received", "received_date": "2026-01-12", "expected_date": "2026-01-10", "supplier_id": "SUP-1"},
        {"po_status": "Cancelled", "received_date": "2026-01-10", "expected_date": "2026-01-10", "supplier_id": "SUP-1"},
    ]
    result = calculate_supplier_on_time(rows)
    assert result == [(date(2026, 1, 1), "SUP-1", 2, 1, 50.0)]
