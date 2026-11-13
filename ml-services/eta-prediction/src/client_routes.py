
"""City-to-warehouse distance mapping for R15 client shipments."""

import logging

import numpy as np
import pandas as pd

from .seed_routes import _calculate_haversine_distance


logger = logging.getLogger(__name__)

DISTANCE_COLUMN = "distance_km"


def _normalize_city(values):
    """Normalize city names for case- and whitespace-insensitive matching."""
    return values.astype("string").str.strip().str.casefold()


def _build_city_coordinates(suppliers, warehouses):
    """Build one validated coordinate lookup from both seed CSVs."""

    required = {"city", "lat", "lng"}

    for name, frame in (
        ("suppliers", suppliers),
        ("warehouses", warehouses),
    ):
        missing = required - set(frame.columns)

        if missing:
            raise ValueError(
                f"Missing {name} coordinate columns: {sorted(missing)}"
            )

    cities = pd.concat(
        [
            suppliers[["city", "lat", "lng"]],
            warehouses[["city", "lat", "lng"]],
        ],
        ignore_index=True,
    ).copy()

    cities["_city_key"] = _normalize_city(cities["city"])

    cities["lat"] = pd.to_numeric(cities["lat"], errors="coerce")
    cities["lng"] = pd.to_numeric(cities["lng"], errors="coerce")

    valid = (
        cities["_city_key"].notna()
        & cities["_city_key"].ne("")
        & np.isfinite(cities["lat"])
        & np.isfinite(cities["lng"])
        & cities["lat"].between(-90, 90)
        & cities["lng"].between(-180, 180)
    )

    cities = cities.loc[valid].copy()

    # Check coordinate differences using a tolerance instead of rounding.
    coordinate_spread = cities.groupby("_city_key")[["lat", "lng"]].agg(
        lambda values: values.max() - values.min()
    )

    conflicting = coordinate_spread[
        (coordinate_spread["lat"] > 1e-3)
        | (coordinate_spread["lng"] > 1e-3)
    ]

    if not conflicting.empty:
        raise ValueError(
            "Conflicting coordinates found for cities: "
            f"{conflicting.index.tolist()}"
        )

    return (
        cities.drop_duplicates("_city_key")
        .set_index("_city_key")[["lat", "lng"]]
    )


def _build_client_warehouse_city_lookup(warehouse_master):
    """Map client warehouse codes to normalized client city names."""

    required = {"warehouse_code", "city"}
    missing = required - set(warehouse_master.columns)

    if missing:
        raise ValueError(
            "Missing client warehouse master columns: "
            f"{sorted(missing)}"
        )

    result = warehouse_master[["warehouse_code", "city"]].copy()

    result["warehouse_code"] = (
        result["warehouse_code"].astype("string").str.strip()
    )
    result["_city_key"] = _normalize_city(result["city"])

    if (
        result["warehouse_code"].isna().any()
        or result["warehouse_code"].eq("").any()
    ):
        raise ValueError(
            "Client warehouse codes contain missing or empty values."
        )

    if result["warehouse_code"].duplicated().any():
        raise ValueError("Duplicate warehouse_code values found.")

    return result.set_index("warehouse_code")["_city_key"]


def add_client_route_distances(
    shipments,
    suppliers,
    warehouses,
    warehouse_master,
):
    """
    Add distance_km to client shipments.

    City coordinates come from both seed CSVs.
    Destination warehouse codes are resolved through the client
    warehouse master before looking up their coordinates.

    Returns
    -------
    tuple[pandas.DataFrame, dict]
        Enriched shipments and location diagnostics.

    Unknown locations are retained with a missing distance.
    """

    required = {
        "origin_city",
        "destination_warehouse_code",
    }
    missing = required - set(shipments.columns)

    if missing:
        raise ValueError(
            f"Missing shipment location columns: {sorted(missing)}"
        )

    result = shipments.copy()

    # 1. Build the combined seed city-coordinate lookup.
    city_coordinates = _build_city_coordinates(
        suppliers,
        warehouses,
    )

    # 2. Resolve client warehouse codes to client cities.
    warehouse_city_lookup = (
        _build_client_warehouse_city_lookup(warehouse_master)
    )

    # 3. Normalize origin cities and destination warehouse codes.
    origin_keys = _normalize_city(result["origin_city"])

    warehouse_keys = (
        result["destination_warehouse_code"]
        .astype("string")
        .str.strip()
    )

    # 4. Resolve destination warehouse codes to normalized city names.
    destination_keys = warehouse_keys.map(warehouse_city_lookup)

    # 5. Resolve both origin and destination coordinates.
    origin_lat = origin_keys.map(city_coordinates["lat"])
    origin_lng = origin_keys.map(city_coordinates["lng"])

    destination_lat = destination_keys.map(city_coordinates["lat"])
    destination_lng = destination_keys.map(city_coordinates["lng"])

    # 6. Identify unknown origins and destination locations.
    unknown_origins = (
        origin_keys.isna()
        | origin_keys.eq("")
        | ~origin_keys.isin(city_coordinates.index)
    )

    unknown_warehouse_codes_mask = (
        warehouse_keys.isna()
        | warehouse_keys.eq("")
        | destination_keys.isna()
    ).fillna(True)

    unknown_destination_cities_mask = (
        destination_keys.notna()
        & ~destination_keys.isin(city_coordinates.index)
    ).fillna(False)

    unknown_destinations = (
        unknown_warehouse_codes_mask
        | unknown_destination_cities_mask
    )

    known_locations = ~(unknown_origins | unknown_destinations)

    # 7. Calculate distances without dropping unknown-location rows.
    result[DISTANCE_COLUMN] = np.nan

    result.loc[known_locations, DISTANCE_COLUMN] = (
        _calculate_haversine_distance(
            origin_lat.loc[known_locations].to_numpy(dtype=float),
            origin_lng.loc[known_locations].to_numpy(dtype=float),
            destination_lat.loc[known_locations].to_numpy(dtype=float),
            destination_lng.loc[known_locations].to_numpy(dtype=float),
        )
    )

    # 8. Collect diagnostics.
    unknown_destination_cities = destination_keys[
        unknown_destination_cities_mask
    ].dropna()

    diagnostics = {
        "total_shipments": len(result),
        "unknown_origin_count": int(unknown_origins.sum()),
        "unknown_warehouse_count": int(
            unknown_warehouse_codes_mask.sum()
        ),
        "unknown_destination_city_count": int(
            unknown_destination_cities_mask.sum()
        ),
        "unknown_location_count": int(
            (unknown_origins | unknown_destinations).sum()
        ),
        "missing_distance_count": int(
            result[DISTANCE_COLUMN].isna().sum()
        ),
        "unknown_origin_cities": sorted(
            origin_keys[unknown_origins].dropna().unique().tolist()
        ),
        "unknown_warehouse_codes": sorted(
            warehouse_keys[unknown_warehouse_codes_mask]
            .dropna()
            .unique()
            .tolist()
        ),
        "unknown_destination_cities": sorted(
            unknown_destination_cities.unique().tolist()
        ),
    }

    if diagnostics["unknown_location_count"]:
        logger.warning(
            "Unknown shipment locations: %s",
            diagnostics,
        )

    return result, diagnostics
