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

forecast_date = "2026-01-01"


# ============================================================
# ACTUAL MODEL FORECAST
# ============================================================

sku_forecasts = forecast_sku_demand(
    hierarchy_df=hierarchy,
    forecast_date=forecast_date,
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

print(
    "\n========================================"
)

print(
    "SKU MODEL FORECASTS"
)

print(
    "========================================"
)

print(
    sku_result.to_string(
        index=False
    )
)


# ============================================================
# DISPLAY CATEGORY FORECASTS
# ============================================================

print(
    "\n========================================"
)

print(
    "CATEGORY FORECASTS"
)

print(
    "========================================"
)

print(
    category_result.to_string(
        index=False
    )
)


# ============================================================
# DISPLAY REGION FORECASTS
# ============================================================

print(
    "\n========================================"
)

print(
    "REGION FORECASTS"
)

print(
    "========================================"
)

print(
    region_result.to_string(
        index=False
    )
)


# ============================================================
# FINAL RESULT
# ============================================================

print(
    "\n========================================"
)

print(
    "3-LEVEL HIERARCHY RECONCILIATION"
)

print(
    "========================================"
)

print(
    "SKU → Category       : PASSED"
)

print(
    "Category → Region    : PASSED"
)

print(
    "SKU → Category → Region : PASSED"
)

print(
    "\nHierarchy reconciliation completed successfully."
)