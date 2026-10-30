from pathlib import Path

import numpy as np
import pandas as pd


SUPPLIER_ID_COLUMN = "supplier_id"
WAREHOUSE_ID_COLUMN = "warehouse_id"
DISTANCE_COLUMN = "distance_km"

ROUTE_COLUMNS = [
    SUPPLIER_ID_COLUMN,
    WAREHOUSE_ID_COLUMN,
    DISTANCE_COLUMN,
]


def _calculate_haversine_distance(
    origin_lat,
    origin_lng,
    destination_lat,
    destination_lng,
):
    """Calculate great-circle distance in kilometres."""

    lat1 = np.radians(origin_lat)
    lon1 = np.radians(origin_lng)
    lat2 = np.radians(destination_lat)
    lon2 = np.radians(destination_lng)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        np.sin(delta_lat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(delta_lon / 2.0) ** 2
    )

    a = np.clip(a, 0.0, 1.0)

    return (
        6371.0
        * 2.0
        * np.arcsin(np.sqrt(a))
    )


def build_seed_route_table(
    suppliers,
    warehouses,
):
    """
    Build all supplier-to-warehouse routes from seed data.

    Routes are identified by canonical supplier and warehouse IDs.
    No delivery target is generated for seed routes.
    """

    required_supplier_columns = {
        SUPPLIER_ID_COLUMN,
        "lat",
        "lng",
    }

    required_warehouse_columns = {
        WAREHOUSE_ID_COLUMN,
        "lat",
        "lng",
    }

    missing_supplier_columns = (
        required_supplier_columns
        - set(suppliers.columns)
    )

    if missing_supplier_columns:
        raise ValueError(
            "Missing supplier columns: "
            f"{sorted(missing_supplier_columns)}"
        )

    missing_warehouse_columns = (
        required_warehouse_columns
        - set(warehouses.columns)
    )

    if missing_warehouse_columns:
        raise ValueError(
            "Missing warehouse columns: "
            f"{sorted(missing_warehouse_columns)}"
        )

    suppliers = suppliers[
        [
            SUPPLIER_ID_COLUMN,
            "lat",
            "lng",
        ]
    ].copy()

    warehouses = warehouses[
        [
            WAREHOUSE_ID_COLUMN,
            "lat",
            "lng",
        ]
    ].copy()

    if suppliers[SUPPLIER_ID_COLUMN].duplicated().any():
        raise ValueError(
            "Duplicate supplier_id values found."
        )

    if warehouses[WAREHOUSE_ID_COLUMN].duplicated().any():
        raise ValueError(
            "Duplicate warehouse_id values found."
        )

    suppliers = suppliers.rename(
        columns={
            "lat": "supplier_lat",
            "lng": "supplier_lng",
        }
    )

    warehouses = warehouses.rename(
        columns={
            "lat": "warehouse_lat",
            "lng": "warehouse_lng",
        }
    )

    # Cartesian product: every supplier × every warehouse.
    routes = suppliers.merge(
        warehouses,
        how="cross",
    )

    routes[DISTANCE_COLUMN] = _calculate_haversine_distance(
        routes["supplier_lat"],
        routes["supplier_lng"],
        routes["warehouse_lat"],
        routes["warehouse_lng"],
    )

    routes = routes[
        ROUTE_COLUMNS
    ].copy()

    expected_route_count = (
        len(suppliers) * len(warehouses)
    )

    if len(routes) != expected_route_count:
        raise ValueError(
            "Unexpected seed route count: "
            f"expected {expected_route_count}, "
            f"got {len(routes)}."
        )

    if routes[DISTANCE_COLUMN].isna().any():
        raise ValueError(
            "Seed route distance contains missing values."
        )

    if (
        routes[DISTANCE_COLUMN] < 0
    ).any():
        raise ValueError(
            "Seed route distance cannot be negative."
        )

    return routes

def get_seed_route(
    routes,
    supplier_id,
    warehouse_id,
):
    """
    Look up one supplier-to-warehouse route by canonical IDs.
    """

    supplier_exists = (
        routes[SUPPLIER_ID_COLUMN] == supplier_id
    ).any()

    if not supplier_exists:
        raise ValueError(
            f"Unknown supplier_id: {supplier_id}"
        )

    warehouse_exists = (
        routes[WAREHOUSE_ID_COLUMN] == warehouse_id
    ).any()

    if not warehouse_exists:
        raise ValueError(
            f"Unknown warehouse_id: {warehouse_id}"
        )

    matches = routes[
        (routes[SUPPLIER_ID_COLUMN] == supplier_id)
        & (
            routes[WAREHOUSE_ID_COLUMN]
            == warehouse_id
        )
    ]

    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one seed route for "
            f"{supplier_id} -> {warehouse_id}, "
            f"found {len(matches)}."
        )

    return matches.iloc[0].copy()
def load_seed_routes(seed_dir):
    """
    Build the route table from a seed folder.

    seed_dir holds suppliers.csv and warehouses.csv: either the
    committed data-platform/seed/samples, or the full output of
    `python -m seed.generate --out <dir>` (60 x 6 = 360 routes).
    """

    seed_dir = Path(seed_dir)

    return build_seed_route_table(
        pd.read_csv(seed_dir / "suppliers.csv"),
        pd.read_csv(seed_dir / "warehouses.csv"),
    )
