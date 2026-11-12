
import logging

import pandas as pd
import pytest

from src.client_routes import add_client_route_distances


@pytest.fixture
def suppliers():
    return pd.DataFrame({
        "city": ["Hyderabad", "Mumbai", "New Delhi"],
        "lat": [17.385, 19.076, 28.6139],
        "lng": [78.4867, 72.8777, 77.2090],
    })


@pytest.fixture
def warehouses():
    return pd.DataFrame({
        "warehouse_id": [
            "WH-BLR-01",
            "WH-CHE-01",
            "WH-BOM-01",
            "WH-DEL-01",
        ],
        "city": [
            "Bengaluru",
            "Chennai",
            "Bhiwandi",
            "Gurugram",
        ],
        "lat": [
            12.9716,
            13.0827,
            19.3002,
            28.4595,
        ],
        "lng": [
            77.5946,
            80.2707,
            73.0581,
            77.0266,
        ],
    })


@pytest.fixture
def warehouse_master():
    return pd.DataFrame({
        "warehouse_code": [
            "HYD-01",
            "BLR-01",
            "MUM-01",
            "DEL-01",
            "CHE-01",
        ],
        "city": [
            "Hyderabad",
            "Bengaluru",
            "Mumbai",
            "New Delhi",
            "Chennai",
        ],
    })


@pytest.fixture
def shipments():
    return pd.DataFrame({
        "shipment_id": ["SHP001", "SHP002"],
        "origin_city": ["Mumbai", "New Delhi"],
        "destination_warehouse_code": [
            "MUM-01",
            "DEL-01",
        ],
    })


def test_distance_is_calculated_for_known_locations(
    shipments, suppliers, warehouses, warehouse_master
):
    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert result["distance_km"].notna().all()
    assert result.loc[0, "distance_km"] == pytest.approx(0.0)
    assert result.loc[1, "distance_km"] == pytest.approx(0.0)
    assert diagnostics["unknown_location_count"] == 0


def test_client_mumbai_code_uses_mumbai_coordinates(
    suppliers, warehouses, warehouse_master
):
    shipment = pd.DataFrame({
        "origin_city": ["Mumbai"],
        "destination_warehouse_code": ["MUM-01"],
    })

    result, diagnostics = add_client_route_distances(
        shipment, suppliers, warehouses, warehouse_master
    )

    # A zero distance proves Mumbai coordinates were used,
    # rather than the seed warehouse city Bhiwandi.
    assert result.loc[0, "distance_km"] == pytest.approx(0.0)
    assert diagnostics["unknown_location_count"] == 0


def test_client_delhi_code_uses_new_delhi_coordinates(
    suppliers, warehouses, warehouse_master
):
    shipment = pd.DataFrame({
        "origin_city": ["New Delhi"],
        "destination_warehouse_code": ["DEL-01"],
    })

    result, diagnostics = add_client_route_distances(
        shipment, suppliers, warehouses, warehouse_master
    )

    # A zero distance proves New Delhi coordinates were used,
    # rather than the seed warehouse city Gurugram.
    assert result.loc[0, "distance_km"] == pytest.approx(0.0)
    assert diagnostics["unknown_location_count"] == 0


def test_city_matching_ignores_case_and_whitespace(
    shipments, suppliers, warehouses, warehouse_master
):
    shipments.loc[0, "origin_city"] = "  mUmBaI  "
    warehouse_master.loc[
        warehouse_master["warehouse_code"] == "MUM-01",
        "city",
    ] = "  MUMBAI  "

    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert result.loc[0, "distance_km"] == pytest.approx(0.0)
    assert diagnostics["unknown_origin_count"] == 0
    assert diagnostics["unknown_location_count"] == 0


def test_city_found_only_in_warehouses_is_resolved(
    suppliers, warehouses, warehouse_master
):
    shipment = pd.DataFrame({
        "origin_city": ["Bengaluru"],
        "destination_warehouse_code": ["BLR-01"],
    })

    result, diagnostics = add_client_route_distances(
        shipment, suppliers, warehouses, warehouse_master
    )

    assert result.loc[0, "distance_km"] == pytest.approx(0.0)
    assert diagnostics["unknown_location_count"] == 0


def test_unknown_origin_is_counted_and_row_is_preserved(
    shipments, suppliers, warehouses, warehouse_master
):
    shipments.loc[0, "origin_city"] = "MadeUpOriginCity"

    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert len(result) == len(shipments)
    assert pd.isna(result.loc[0, "distance_km"])
    assert diagnostics["unknown_origin_count"] == 1
    assert diagnostics["unknown_location_count"] == 1
    assert "madeuporigincity" in diagnostics["unknown_origin_cities"]


def test_unknown_destination_city_is_counted_and_row_is_preserved(
    shipments, suppliers, warehouses, warehouse_master
):
    warehouse_master.loc[
        warehouse_master["warehouse_code"] == "MUM-01",
        "city",
    ] = "MadeUpDestinationCity"

    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert len(result) == len(shipments)
    assert pd.isna(result.loc[0, "distance_km"])
    assert diagnostics["unknown_warehouse_count"] == 1
    assert diagnostics["unknown_destination_city_count"] == 1
    assert diagnostics["unknown_location_count"] == 1
    assert "madeupdestinationcity" in (
        diagnostics["unknown_destination_cities"]
    )


def test_unknown_warehouse_code_is_counted_and_row_is_preserved(
    shipments, suppliers, warehouses, warehouse_master
):
    shipments.loc[0, "destination_warehouse_code"] = "UNKNOWN-01"

    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert len(result) == len(shipments)
    assert pd.isna(result.loc[0, "distance_km"])
    assert diagnostics["unknown_warehouse_count"] == 1
    assert diagnostics["unknown_location_count"] == 1


def test_conflicting_coordinates_across_seed_files_are_rejected(
    shipments, suppliers, warehouses, warehouse_master
):
    warehouses.loc[2, "city"] = "Mumbai"

    with pytest.raises(ValueError, match="Conflicting coordinates"):
        add_client_route_distances(
            shipments, suppliers, warehouses, warehouse_master
        )


def test_duplicate_client_warehouse_codes_are_rejected(
    shipments, suppliers, warehouses, warehouse_master
):
    warehouse_master.loc[1, "warehouse_code"] = "MUM-01"

    with pytest.raises(ValueError, match="Duplicate warehouse_code"):
        add_client_route_distances(
            shipments, suppliers, warehouses, warehouse_master
        )


def test_unknown_location_generates_warning(
    shipments, suppliers, warehouses, warehouse_master, caplog
):
    shipments.loc[0, "origin_city"] = "MadeUpOriginCity"

    with caplog.at_level(logging.WARNING):
        add_client_route_distances(
            shipments, suppliers, warehouses, warehouse_master
        )

    assert "Unknown shipment locations" in caplog.text

def test_missing_origin_and_warehouse_code_are_counted_and_rows_preserved(
    shipments, suppliers, warehouses, warehouse_master
):
    shipments.loc[0, "origin_city"] = None
    shipments.loc[1, "destination_warehouse_code"] = None

    result, diagnostics = add_client_route_distances(
        shipments, suppliers, warehouses, warehouse_master
    )

    assert len(result) == 2
    assert pd.isna(result.loc[0, "distance_km"])
    assert pd.isna(result.loc[1, "distance_km"])

    assert diagnostics["unknown_origin_count"] == 1
    assert diagnostics["unknown_warehouse_count"] == 1
    assert diagnostics["unknown_location_count"] == 2
    assert diagnostics["missing_distance_count"] == 2  
