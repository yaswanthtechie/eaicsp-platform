from etl.src.load import _dedupe_records


def test_dedupe_keeps_last_occurrence():
    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5},
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 99},
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"])

    assert len(result) == 1
    assert result[0]["quantity_sold"] == 99  # last one wins


def test_dedupe_preserves_distinct_records():
    records = [
        {"date": "2024-01-01", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 5},
        {"date": "2024-01-01", "sku_id": "SKU2", "warehouse_id": "WH1", "quantity_sold": 10},
        {"date": "2024-01-02", "sku_id": "SKU1", "warehouse_id": "WH1", "quantity_sold": 15},
    ]

    result = _dedupe_records(records, ["date", "sku_id", "warehouse_id"])

    assert len(result) == 3


def test_dedupe_empty_list_returns_empty_list():
    assert _dedupe_records([], ["date", "sku_id", "warehouse_id"]) == []
