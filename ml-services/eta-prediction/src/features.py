import numpy as np
import pandas as pd

from .paths import PROCESSED_DATA_DIR


TARGET_COLUMN = "delivery_days"

OUTPUT_FILENAME = "eta_features.csv"

LEAKAGE_COLUMNS = {
    "order_status",
    "order_delivered_customer_date",
    "order_delivered_carrier_date",
}


def _parse_order_dates(orders):
    """
    Convert order timestamp columns to pandas datetime.

    Date parsing is required for target and purchase-time feature
    extraction. Missing-value handling belongs to preprocessing.
    """
    orders = orders.copy()

    date_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    for column in date_columns:
        if column in orders.columns:
            orders[column] = pd.to_datetime(
                orders[column],
                errors="coerce",
            )

    return orders


def _filter_delivered_orders(orders):
    """
    Keep delivered orders.

    order_status is used only to identify the population for which
    a valid delivery target can be constructed. It is never returned
    as a model feature.
    """
    orders = orders.copy()

    return orders[
        orders["order_status"].eq("delivered")
    ].copy()


def _create_target(orders):
    """
    Create delivery_days from purchase timestamp to actual
    customer delivery timestamp.

    Rows without a valid target cannot be used for supervised
    training and are therefore excluded here.
    """
    orders = orders.copy()

    delivery_delta = (
        orders["order_delivered_customer_date"]
        - orders["order_purchase_timestamp"]
    )

    orders[TARGET_COLUMN] = (
        delivery_delta.dt.total_seconds()
        / 86400.0
    )

    # Target construction requires a valid target.
    orders = orders[
        orders[TARGET_COLUMN].notna()
        & (orders[TARGET_COLUMN] > 0)
    ].copy()

    return orders


def _aggregate_order_items(
    order_items,
    products,
    category_translation,
):
    """
    Aggregate item-level information to exactly one row per order.

    Numerical item/product attributes are aggregated across all
    items belonging to an order.

    For an order containing multiple categories, the first
    deterministic non-null category is used as the representative
    category.
    """
    items = order_items.copy()
    products = products.copy()

    # Translate Portuguese categories where a translation exists.
    if (
        "product_category_name" in products.columns
        and not category_translation.empty
    ):
        translation = category_translation[
            [
                "product_category_name",
                "product_category_name_english",
            ]
        ].drop_duplicates(
            subset=["product_category_name"]
        )

        products = products.merge(
            translation,
            on="product_category_name",
            how="left",
            validate="many_to_one",
        )

        products["category"] = (
            products["product_category_name_english"]
            .fillna(products["product_category_name"])
        )
    else:
        products["category"] = (
            products["product_category_name"]
        )

    product_columns = [
        "product_id",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "category",
    ]

    products = products[
        [
            column
            for column in product_columns
            if column in products.columns
        ]
    ].copy()

    items = items.merge(
        products,
        on="product_id",
        how="left",
        validate="many_to_one",
    )

    # Weight: grams → kilograms.
    items["weight_kg"] = (
        pd.to_numeric(
            items["product_weight_g"],
            errors="coerce",
        )
        / 1000.0
    )

    length = pd.to_numeric(
        items["product_length_cm"],
        errors="coerce",
    )

    height = pd.to_numeric(
        items["product_height_cm"],
        errors="coerce",
    )

    width = pd.to_numeric(
        items["product_width_cm"],
        errors="coerce",
    )

    # Volume in cubic centimeters.
    items["volume_cm3"] = (
        length * height * width
    )

    # Numerical aggregation to order level.
    aggregated = (
        items.groupby(
            "order_id",
            as_index=False,
        )
        .agg(
            item_count=(
                "order_item_id",
                "count",
            ),
            total_weight_kg=(
                "weight_kg",
                "sum",
            ),
            total_volume_cm3=(
                "volume_cm3",
                "sum",
            ),
            total_freight_value=(
                "freight_value",
                "sum",
            ),
        )
    )

    # Deterministic representative category.
    category_values = (
        items.sort_values(
            [
                "order_id",
                "product_id",
            ],
            na_position="last",
        )
        .groupby("order_id")["category"]
        .first()
        .rename(
            "product_category_name"
        )
    )

    aggregated = aggregated.merge(
        category_values,
        left_on="order_id",
        right_index=True,
        how="left",
        validate="one_to_one",
    )

    return aggregated


def _aggregate_geolocation(geolocation):
    """
    Reduce multiple geolocation observations for the same ZIP prefix
    to one representative coordinate.

    The aggregation is required before joining because the Olist
    geolocation table contains multiple observations per ZIP prefix.
    """
    geo = geolocation.copy()

    return (
        geo.groupby(
            "geolocation_zip_code_prefix",
            as_index=False,
        )
        .agg(
            latitude=(
                "geolocation_lat",
                "mean",
            ),
            longitude=(
                "geolocation_lng",
                "mean",
            ),
        )
    )


def _add_distance(dataframe):
    """
    Calculate great-circle distance between origin and destination
    using the Haversine formula.

    This is a geographic distance proxy, not road/network distance.
    """
    dataframe = dataframe.copy()

    lat1 = np.radians(
        dataframe["origin_lat"]
    )
    lon1 = np.radians(
        dataframe["origin_lng"]
    )

    lat2 = np.radians(
        dataframe["destination_lat"]
    )
    lon2 = np.radians(
        dataframe["destination_lng"]
    )

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        np.sin(delta_lat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(delta_lon / 2.0) ** 2
    )

    a = np.clip(
        a,
        0.0,
        1.0,
    )

    dataframe["distance_km"] = (
        6371.0
        * 2.0
        * np.arcsin(
            np.sqrt(a)
        )
    )

    return dataframe


def build_eta_features(datasets):
    """
    Extract the ETA feature dataset from the raw Olist datasets.

    This function is responsible only for feature extraction and
    target construction.

    Missing-value handling, duplicate cleaning, encoding,
    train/test splitting, and model preprocessing are handled
    elsewhere.
    """
    orders = _parse_order_dates(
        datasets["orders"]
    )

    # Only delivered orders can provide an observed delivery target.
    orders = _filter_delivered_orders(
        orders
    )

    # Construct the supervised-learning target.
    orders = _create_target(
        orders
    )

    # Aggregate order-item/product information.
    items = _aggregate_order_items(
        datasets["order_items"],
        datasets["products"],
        datasets["category_translation"],
    )

    # Customer destination.
    customers = datasets["customers"][
        [
            "customer_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ]
    ].copy()

    # Seller origin.
    sellers = datasets["sellers"][
        [
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ]
    ].copy()

    # Aggregate geolocation BEFORE joining.
    geo = _aggregate_geolocation(
        datasets["geolocation"]
    )

    # Start from one row per valid delivered order.
    features = orders[
        [
            "order_id",
            "customer_id",
            "order_purchase_timestamp",
            TARGET_COLUMN,
        ]
    ].merge(
        items,
        on="order_id",
        how="left",
        validate="one_to_one",
    )

    # Destination information.
    features = features.merge(
        customers,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )

    # Seller information comes through order_items.
    #
    # An order can contain multiple sellers. For this baseline,
    # choose one deterministic seller rather than duplicating
    # the order.
    order_sellers = (
        datasets["order_items"][
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

    features = features.merge(
        order_sellers,
        on="order_id",
        how="left",
        validate="one_to_one",
    )

    features = features.merge(
        sellers,
        on="seller_id",
        how="left",
        validate="many_to_one",
    )

    # Destination coordinates.
    destination_geo = geo.rename(
        columns={
            "geolocation_zip_code_prefix":
                "customer_zip_code_prefix",
            "latitude":
                "destination_lat",
            "longitude":
                "destination_lng",
        }
    )

    features = features.merge(
        destination_geo,
        on="customer_zip_code_prefix",
        how="left",
        validate="many_to_one",
    )

    # Origin coordinates.
    origin_geo = geo.rename(
        columns={
            "geolocation_zip_code_prefix":
                "seller_zip_code_prefix",
            "latitude":
                "origin_lat",
            "longitude":
                "origin_lng",
        }
    )

    features = features.merge(
        origin_geo,
        on="seller_zip_code_prefix",
        how="left",
        validate="many_to_one",
    )

    # Geographic distance.
    features = _add_distance(
        features
    )

    # Purchase-time features.
    purchase_time = features[
        "order_purchase_timestamp"
    ]

    features["purchase_year"] = (
        purchase_time.dt.year
    )

    features["purchase_month"] = (
        purchase_time.dt.month
    )

    features["purchase_day_of_week"] = (
        purchase_time.dt.dayofweek
    )

    features["purchase_hour"] = (
        purchase_time.dt.hour
    )

    # Explicit model feature selection.
    #
    # order_purchase_timestamp is intentionally excluded from the
    # saved feature dataset. split.py gets the original timestamp
    # directly from the orders dataset for chronological splitting.
    feature_columns = [
        "order_id",
        "purchase_year",
        "purchase_month",
        "purchase_day_of_week",
        "purchase_hour",
        "origin_lat",
        "origin_lng",
        "destination_lat",
        "destination_lng",
        "distance_km",
        "item_count",
        "total_weight_kg",
        "total_volume_cm3",
        "total_freight_value",
        "product_category_name",
        TARGET_COLUMN,
    ]

    features = features[
        feature_columns
    ].copy()

    # Explicit leakage guard.
    illegal_columns = (
        LEAKAGE_COLUMNS
        & set(features.columns)
    )

    if illegal_columns:
        raise ValueError(
            "Leakage columns found in feature dataset: "
            f"{sorted(illegal_columns)}"
        )

    # Feature extraction must produce one row per order.
    # Do not silently remove duplicates here.
    if features["order_id"].duplicated().any():
        raise ValueError(
            "Feature extraction produced duplicate order_id values."
        )

    return features


def save_eta_features(features):
    """
    Save the extracted ETA feature dataset to the processed-data
    directory.

    No cleaning or preprocessing is performed here.
    """
    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        PROCESSED_DATA_DIR
        / OUTPUT_FILENAME
    )

    features.to_csv(
        output_path,
        index=False,
    )

    return output_path