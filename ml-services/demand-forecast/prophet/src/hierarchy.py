import pandas as pd


def bottom_up_reconcile(
    sku_forecasts: pd.DataFrame,
    hierarchy: pd.DataFrame,
):
    """
    Bottom-up hierarchical forecasting.

    SKU forecasts are aggregated to category level,
    then category forecasts are aggregated to region level.
    """

    # SKU -> Category -> Region mapping
    mapping = hierarchy[
        ["sku_id", "category", "region"]
    ].drop_duplicates("sku_id")

    # Attach hierarchy information to SKU forecasts
    merged = sku_forecasts.merge(
        mapping,
        on="sku_id",
        how="left",
        validate="many_to_one",
    )

    # Validate mappings
    if merged["category"].isnull().any():
        raise ValueError(
            "Missing category mapping for one or more SKUs."
        )

    if merged["region"].isnull().any():
        raise ValueError(
            "Missing region mapping for one or more SKUs."
        )

    # Category forecast = sum of SKU forecasts
    category_forecasts = (
        merged
        .groupby(
            ["date", "category", "region"],
            as_index=False
        )["predicted"]
        .sum()
    )

    # Region forecast = sum of category forecasts
    region_forecasts = (
        category_forecasts
        .groupby(
            ["date", "region"],
            as_index=False
        )["predicted"]
        .sum()
    )

    return (
        merged,
        category_forecasts,
        region_forecasts,
    )