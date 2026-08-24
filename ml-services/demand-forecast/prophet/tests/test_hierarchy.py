import pandas as pd

from src.hierarchy import bottom_up_reconcile


def test_bottom_up_reconciliation():

    hierarchy = pd.DataFrame({
        "sku_id": [
            "SKU001",
            "SKU002",
            "SKU003",
            "SKU004",
        ],
        "category": [
            "Electronics",
            "Electronics",
            "Furniture",
            "Furniture",
        ],
        "region": [
            "South",
            "South",
            "South",
            "South",
        ],
    })

    sku_forecasts = pd.DataFrame({
        "date": [
            "2025-04-01",
            "2025-04-01",
            "2025-04-01",
            "2025-04-01",
        ],
        "sku_id": [
            "SKU001",
            "SKU002",
            "SKU003",
            "SKU004",
        ],
        "predicted": [
            100,
            150,
            80,
            70,
        ],
    })

    (
        sku_result,
        category_result,
        region_result,
    ) = bottom_up_reconcile(
        sku_forecasts,
        hierarchy,
    )

    # SKU total
    sku_total = sku_result["predicted"].sum()

    # Category total
    category_total = category_result["predicted"].sum()

    # Region total
    region_total = region_result["predicted"].sum()

    assert sku_total == 400
    assert category_total == 400
    assert region_total == 400

    assert sku_total == category_total
    assert category_total == region_total