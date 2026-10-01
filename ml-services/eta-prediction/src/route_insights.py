import pandas as pd


# A route whose standard deviation is under this fraction of its mean is
# reliably slow rather than occasionally disastrous.
CONSISTENCY_RATIO = 0.5


def build_route_insights(
    datasets: dict[str, pd.DataFrame],
    min_orders: int = 10,
) -> pd.DataFrame:
    """
    Build route-level delivery performance insights.

    A route is defined as:
        seller_city -> customer_city

    Only delivered orders with a valid delivery_days value
    are included.

    Parameters
    ----------
    datasets:
        Raw Olist datasets loaded by load_dataset().

    min_orders:
        Minimum number of orders required for a route to be included.

    Returns
    -------
    pd.DataFrame
        Route-level aggregated delivery performance.
    """

    if min_orders < 1:
        raise ValueError("min_orders must be at least 1")

    orders = datasets["orders"].copy()
    customers = datasets["customers"].copy()
    sellers = datasets["sellers"].copy()
    order_items = datasets["order_items"].copy()

    # Parse timestamps.
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"],
        errors="coerce",
    )

    orders["order_delivered_customer_date"] = pd.to_datetime(
        orders["order_delivered_customer_date"],
        errors="coerce",
    )

    # Keep delivered orders with valid delivery dates.
    orders = orders[
        orders["order_status"].eq("delivered")
        & orders["order_purchase_timestamp"].notna()
        & orders["order_delivered_customer_date"].notna()
    ].copy()

    orders["delivery_days"] = (
        orders["order_delivered_customer_date"]
        - orders["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400.0

    orders = orders[
        orders["delivery_days"].notna()
        & (orders["delivery_days"] > 0)
    ].copy()

    # Select one deterministic seller for each order.
    order_sellers = (
        order_items[
            [
                "order_id",
                "seller_id",
            ]
        ]
        .sort_values(
            [
                "order_id",
                "seller_id",
            ]
        )
        .drop_duplicates(
            "order_id",
            keep="first",
        )
    )

    # Customer route endpoint.
    customer_locations = customers[
        [
            "customer_id",
            "customer_city",
            "customer_state",
        ]
    ].copy()

    # Seller route endpoint.
    seller_locations = sellers[
        [
            "seller_id",
            "seller_city",
            "seller_state",
        ]
    ].copy()

    # Build one row per order.
    route_data = (
        orders[
            [
                "order_id",
                "customer_id",
                "delivery_days",
            ]
        ]
        .merge(
            order_sellers,
            on="order_id",
            how="left",
            validate="one_to_one",
        )
        .merge(
            customer_locations,
            on="customer_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            seller_locations,
            on="seller_id",
            how="left",
            validate="many_to_one",
        )
    )

    # Remove rows where route endpoints are unavailable.
    route_data = route_data[
        route_data["seller_city"].notna()
        & route_data["customer_city"].notna()
    ].copy()

    # Normalize city names for consistent grouping.
    route_data["origin"] = (
        route_data["seller_city"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    route_data["destination"] = (
        route_data["customer_city"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # Aggregate route-level performance.
    insights = (
        route_data
        .groupby(
            [
                "origin",
                "destination",
            ],
            as_index=False,
        )
        .agg(
            order_count=(
                "order_id",
                "nunique",
            ),
            average_delivery_days=(
                "delivery_days",
                "mean",
            ),
            median_delivery_days=(
                "delivery_days",
                "median",
            ),
            # Spread separates a route that is RELIABLY slow from one
            # whose average is dragged up by a few bad deliveries.
            delivery_days_std=(
                "delivery_days",
                "std",
            ),
            min_delivery_days=(
                "delivery_days",
                "min",
            ),
            max_delivery_days=(
                "delivery_days",
                "max",
            ),
        )
    )

    # A single-order route has no spread; treat that as 0.0 rather than NaN.
    insights["delivery_days_std"] = (
        insights["delivery_days_std"].fillna(0.0)
    )

    # Keep routes with enough historical observations.
    insights = insights[
        insights["order_count"] >= min_orders
    ].copy()

    # Slowest routes first.
    insights = insights.sort_values(
        [
            "average_delivery_days",
            "order_count",
        ],
        ascending=[
            False,
            False,
        ],
    ).reset_index(drop=True)

    # Human-readable route name.
    insights["route"] = (
        insights["origin"]
        + " -> "
        + insights["destination"]
    )

    return insights[
        [
            "route",
            "origin",
            "destination",
            "order_count",
            "average_delivery_days",
            "median_delivery_days",
            "delivery_days_std",
            "min_delivery_days",
            "max_delivery_days",
        ]
    ]


def get_slowest_routes(
    insights: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Return the slowest routes based on average delivery time.
    """

    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    required_columns = {
        "route",
        "average_delivery_days",
        "order_count",
    }

    missing = required_columns - set(insights.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    return (
        insights
        .sort_values(
            "average_delivery_days",
            ascending=False,
        )
        .head(top_n)
        .reset_index(drop=True)
    )


def generate_route_findings(
    insights: pd.DataFrame,
    top_n: int = 5,
) -> list[str]:
    """
    Generate plain-English findings for the slowest routes.

    Each finding compares the route against the network median so the
    number carries meaning. "18.4 days" says nothing on its own;
    "18.4 days, 2.3x the network median of 7.9" is a finding.

    Routes whose spread is small relative to their average are called
    out as consistently slow, which is what the ranking is for.
    """

    slowest = get_slowest_routes(
        insights,
        top_n=top_n,
    )

    if insights.empty:
        return []

    # Network baseline: the typical route, not the typical order.
    network_median = float(
        insights["average_delivery_days"].median()
    )

    findings = []

    for _, row in slowest.iterrows():
        average = float(
            row["average_delivery_days"]
        )

        orders = int(
            row["order_count"]
        )

        finding = (
            f"{row['route']} has an average delivery time "
            f"of {average:.2f} days across {orders} orders"
        )

        ratio = None

        if network_median > 0:
            ratio = average / network_median

            finding += (
                f", {ratio:.1f}x the network median "
                f"of {network_median:.2f} days"
            )

        # "Consistently slow" needs BOTH:
        # 1. slower than the network
        # 2. low spread relative to its average
        std = float(
            row.get("delivery_days_std", 0.0) or 0.0
        )

        is_slower_than_network = (
            ratio is not None
            and ratio > 1.0
        )

        is_consistent = (
            average > 0
            and std / average <= CONSISTENCY_RATIO
        )

        if is_slower_than_network and is_consistent:
            finding += " (consistently slow)"

        findings.append(
            finding + "."
        )

    return findings