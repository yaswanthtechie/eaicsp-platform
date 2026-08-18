import pandas as pd

from src.sku_forecast import forecast_sku_demand
from src.hierarchy import bottom_up_reconcile


# ============================================================
# LOAD HIERARCHY DATA
# ============================================================

hierarchy = pd.read_csv(
    "data/hierarchy_sales.csv"
)


# ============================================================
# FUTURE FORECAST DATE
# ============================================================

# 2025 data is historical.
# We forecast the next month.
forecast_date = "2026-01-01"


# ============================================================
# ACTUAL MODEL FORECAST
# ============================================================

sku_forecasts = forecast_sku_demand(
    hierarchy_df=hierarchy,
    forecast_date=forecast_date,
)


# ============================================================
# ADD HIERARCHY INFORMATION
# ============================================================

sku_forecasts = sku_forecasts.merge(
    hierarchy[
        [
            "sku_id",
            "category",
            "region",
        ]
    ].drop_duplicates(
        subset=["sku_id"]
    ),
    on="sku_id",
    how="left",
)


# ============================================================
# BOTTOM-UP RECONCILIATION
# ============================================================

(
    sku_result,
    category_result,
    region_result,
) = bottom_up_reconcile(
    sku_forecasts[
        [
            "date",
            "sku_id",
            "predicted",
        ]
    ],
    hierarchy,
)


# ============================================================
# DISPLAY SKU FORECASTS
# ============================================================

print("\n=== SKU MODEL FORECASTS ===")

print(
    sku_result
)


# ============================================================
# DISPLAY CATEGORY FORECASTS
# ============================================================

print("\n=== CATEGORY FORECASTS ===")

print(
    category_result
)


# ============================================================
# DISPLAY REGION FORECASTS
# ============================================================

print("\n=== REGION FORECASTS ===")

print(
    region_result
)


# ============================================================
# RECONCILIATION CHECK
# ============================================================

sku_total = sku_result[
    "predicted"
].sum()

category_total = category_result[
    "predicted"
].sum()

region_total = region_result[
    "predicted"
].sum()

print("\n=== PER-REGION RECONCILIATION CHECK ===")

region_predictions = (
    region_result
    .set_index("region")["predicted"]
)

for region, region_prediction in region_predictions.items():

    category_sum = category_result.loc[
        category_result["region"] == region,
        "predicted"
    ].sum()

    print(
        f"{region}: "
        f"Category total = {category_sum:.2f}, "
        f"Region total = {region_prediction:.2f}"
    )

    assert abs(category_sum - region_prediction) < 1e-9, (
        f"{region}: "
        f"{region_prediction} != {category_sum}"
    )

print("\nPer-region reconciliation successful!")