import pandas as pd

from src.seed_checks import run_checks


def _seed():
    return {
        "skus": pd.DataFrame({"sku_id": ["SKU-000001"], "supplier_id": ["SUP-00001"],
                              "unit_price": [10.0], "unit_cost": [6.0]}),
        "suppliers": pd.DataFrame({"supplier_id": ["SUP-00001"]}),
        "warehouses": pd.DataFrame({"warehouse_id": ["WH-BLR-01"]}),
        "sales_daily": pd.DataFrame({
            "date": ["2026-10-12", "2026-10-13"],
            "sku_id": ["SKU-000001"] * 2, "warehouse_id": ["WH-BLR-01"] * 2,
            "quantity_sold": [3, 4], "unit_price": [10.0, 10.0]}),
        "opening_stock": pd.DataFrame({"sku_id": ["SKU-000001"], "warehouse_id": ["WH-BLR-01"],
                                       "quantity_on_hand": [20]}),
        "current_stock": pd.DataFrame({"sku_id": ["SKU-000001"], "warehouse_id": ["WH-BLR-01"],
                                       "quantity_on_hand": [15]}),
    }


def _failed(data):
    return {r["check"] for r in run_checks(data) if not r["ok"]}


def test_clean_seed_passes():
    assert _failed(_seed()) == set()


def test_negative_stock_fails():
    data = _seed()
    data["current_stock"].loc[0, "quantity_on_hand"] = -1
    assert "current_stock: negative quantity_on_hand" in _failed(data)


def test_unknown_sku_fails():
    data = _seed()
    data["sales_daily"].loc[0, "sku_id"] = "SKU-999999"
    assert "sales_daily.sku_id exists in skus" in _failed(data)


def test_date_gap_fails():
    data = _seed()
    data["sales_daily"].loc[1, "date"] = "2026-10-14"   # 10-13 now missing
    assert "sales_daily: date gaps per SKU/warehouse" in _failed(data)


def test_non_canonical_id_fails():
    data = _seed()
    data["warehouses"].loc[0, "warehouse_id"] = "BLR-01"
    assert "warehouses.warehouse_id: canonical format" in _failed(data)