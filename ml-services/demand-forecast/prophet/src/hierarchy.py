import pandas as pd


# ============================================================
# HIERARCHY VALIDATION
# ============================================================

def validate_hierarchy(hierarchy: pd.DataFrame) -> None:
    """
    Validate the SKU -> Category -> Region hierarchy.

    Expected hierarchy:

        SKU
         ↓
      Category
         ↓
       Region
    """

    required_columns = [
        "sku_id",
        "category",
        "region",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in hierarchy.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Hierarchy is missing required columns: "
            f"{missing_columns}"
        )

    if hierarchy.empty:
        raise ValueError(
            "Hierarchy data is empty."
        )

    # Missing hierarchy values
    if hierarchy["sku_id"].isna().any():
        raise ValueError(
            "Hierarchy contains missing sku_id values."
        )

    if hierarchy["category"].isna().any():
        raise ValueError(
            "Hierarchy contains missing category values."
        )

    if hierarchy["region"].isna().any():
        raise ValueError(
            "Hierarchy contains missing region values."
        )

    # --------------------------------------------------------
    # One SKU must belong to exactly one Category + Region
    # --------------------------------------------------------

    sku_mapping = (
        hierarchy[
            [
                "sku_id",
                "category",
                "region",
            ]
        ]
        .drop_duplicates()
    )

    mapping_counts = (
        sku_mapping
        .groupby("sku_id")
        .size()
    )

    invalid_skus = mapping_counts[
        mapping_counts > 1
    ]

    if not invalid_skus.empty:
        raise ValueError(
            "A SKU is mapped to multiple "
            "category/region combinations: "
            f"{invalid_skus.index.tolist()}"
        )


# ============================================================
# RECONCILIATION PROOF
# ============================================================

def verify_reconciliation(
    sku_result: pd.DataFrame,
    category_result: pd.DataFrame,
    region_result: pd.DataFrame,
) -> None:
    """
    Prove hierarchical sum consistency.

    Level 1:
        Sum of SKU forecasts = Category forecast

    Level 2:
        Sum of Category forecasts = Region forecast

    Checks are performed independently for every
    date/category/region combination.
    """

    tolerance = 1e-9

    # ========================================================
    # LEVEL 1
    # SKU -> CATEGORY
    # ========================================================

    sku_category_sum = (
        sku_result
        .groupby(
            [
                "date",
                "category",
                "region",
            ],
            as_index=False,
        )["predicted"]
        .sum()
        .rename(
            columns={
                "predicted":
                    "sku_sum"
            }
        )
    )

    category_check = sku_category_sum.merge(
        category_result,
        on=[
            "date",
            "category",
            "region",
        ],
        how="outer",
        validate="one_to_one",
    )

    if category_check[
        ["sku_sum", "predicted"]
    ].isna().any().any():

        raise AssertionError(
            "SKU -> Category reconciliation "
            "contains missing aggregation rows."
        )

    category_check[
        "difference"
    ] = (
        category_check["sku_sum"]
        -
        category_check["predicted"]
    )

    invalid_category = category_check[
        category_check["difference"].abs()
        > tolerance
    ]

    if not invalid_category.empty:

        raise AssertionError(
            "SKU -> Category reconciliation failed:\n"
            +
            invalid_category.to_string(
                index=False
            )
        )

    # ========================================================
    # LEVEL 2
    # CATEGORY -> REGION
    # ========================================================

    category_region_sum = (
        category_result
        .groupby(
            [
                "date",
                "region",
            ],
            as_index=False,
        )["predicted"]
        .sum()
        .rename(
            columns={
                "predicted":
                    "category_sum"
            }
        )
    )

    region_check = category_region_sum.merge(
        region_result,
        on=[
            "date",
            "region",
        ],
        how="outer",
        validate="one_to_one",
    )

    if region_check[
        ["category_sum", "predicted"]
    ].isna().any().any():

        raise AssertionError(
            "Category -> Region reconciliation "
            "contains missing aggregation rows."
        )

    region_check[
        "difference"
    ] = (
        region_check["category_sum"]
        -
        region_check["predicted"]
    )

    invalid_region = region_check[
        region_check["difference"].abs()
        > tolerance
    ]

    if not invalid_region.empty:

        raise AssertionError(
            "Category -> Region reconciliation failed:\n"
            +
            invalid_region.to_string(
                index=False
            )
        )

    # ========================================================
    # GLOBAL TOTAL CHECK
    # ========================================================

    sku_total = sku_result[
        "predicted"
    ].sum()

    category_total = category_result[
        "predicted"
    ].sum()

    region_total = region_result[
        "predicted"
    ].sum()

    if not (
        abs(sku_total - category_total)
        <= tolerance
    ):
        raise AssertionError(
            "Global SKU -> Category total "
            "reconciliation failed."
        )

    if not (
        abs(category_total - region_total)
        <= tolerance
    ):
        raise AssertionError(
            "Global Category -> Region total "
            "reconciliation failed."
        )

    print(
        "\n========================================"
    )

    print(
        "HIERARCHICAL RECONCILIATION PROOF"
    )

    print(
        "========================================"
    )

    print(
        "SKU -> Category: PASSED"
    )

    print(
        "Category -> Region: PASSED"
    )

    print(
        f"SKU total      : {sku_total:.6f}"
    )

    print(
        f"Category total : {category_total:.6f}"
    )

    print(
        f"Region total   : {region_total:.6f}"
    )

    print(
        "\n3-level hierarchy is sum-consistent."
    )


# ============================================================
# BOTTOM-UP RECONCILIATION
# ============================================================

def bottom_up_reconcile(
    sku_forecasts: pd.DataFrame,
    hierarchy: pd.DataFrame,
):
    """
    Bottom-up hierarchical forecasting.

    Hierarchy:

        SKU
         ↓
      Category
         ↓
       Region

    SKU forecasts are aggregated to category level,
    then category forecasts are aggregated to region level.

    Returns:
        sku_result
        category_forecasts
        region_forecasts
    """

    # ========================================================
    # VALIDATE INPUTS
    # ========================================================

    validate_hierarchy(
        hierarchy
    )

    required_forecast_columns = [
        "date",
        "sku_id",
        "predicted",
    ]

    missing_forecast_columns = [
        column
        for column in required_forecast_columns
        if column not in sku_forecasts.columns
    ]

    if missing_forecast_columns:
        raise ValueError(
            "SKU forecasts are missing required "
            f"columns: {missing_forecast_columns}"
        )

    if sku_forecasts.empty:
        raise ValueError(
            "SKU forecasts are empty."
        )

    if sku_forecasts[
        "predicted"
    ].isna().any():

        raise ValueError(
            "SKU forecasts contain missing "
            "predicted values."
        )

    # ========================================================
    # SKU -> CATEGORY -> REGION MAPPING
    # ========================================================

    mapping = (
        hierarchy[
            [
                "sku_id",
                "category",
                "region",
            ]
        ]
        .drop_duplicates()
    )

    # ========================================================
    # ATTACH HIERARCHY TO SKU FORECASTS
    # ========================================================

    merged = sku_forecasts.merge(
        mapping,
        on="sku_id",
        how="left",
        validate="many_to_one",
    )

    # ========================================================
    # VALIDATE MAPPINGS
    # ========================================================

    if merged[
        "category"
    ].isnull().any():

        raise ValueError(
            "Missing category mapping for "
            "one or more SKUs."
        )

    if merged[
        "region"
    ].isnull().any():

        raise ValueError(
            "Missing region mapping for "
            "one or more SKUs."
        )

    # ========================================================
    # LEVEL 1
    # SKU -> CATEGORY
    # ========================================================

    category_forecasts = (
        merged
        .groupby(
            [
                "date",
                "category",
                "region",
            ],
            as_index=False,
        )[
            "predicted"
        ]
        .sum()
    )

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
        category_forecasts.to_string(
            index=False
        )
    )

    # ========================================================
    # LEVEL 2
    # CATEGORY -> REGION
    # ========================================================

    region_forecasts = (
        category_forecasts
        .groupby(
            [
                "date",
                "region",
            ],
            as_index=False,
        )[
            "predicted"
        ]
        .sum()
    )

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
        region_forecasts.to_string(
            index=False
        )
    )

    # ========================================================
    # RECONCILIATION PROOF
    # ========================================================

    verify_reconciliation(
        merged,
        category_forecasts,
        region_forecasts,
    )

    return (
        merged,
        category_forecasts,
        region_forecasts,
    )