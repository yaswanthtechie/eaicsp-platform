import pandas as pd
import pytest
from src.seed_routes import (
    DISTANCE_COLUMN,
    ROUTE_COLUMNS,
    build_seed_route_table,
    get_seed_route,
)
@pytest.fixture
def suppliers():
    return pd.DataFrame(
        {
            "supplier_id": [
                "SUP-00001",
                "SUP-00002",
            ],
            "lat": [20.2961, 17.3850],
            "lng": [85.8245, 78.4867],
        }
    )


@pytest.fixture
def warehouses():
    return pd.DataFrame(
        {
            "warehouse_id": [
                "WH-BLR-01",
                "WH-MAA-01",
            ],
            "lat": [12.9716, 13.0827],
            "lng": [77.5946, 80.2707],
        }
    )


def test_build_seed_route_table_creates_all_routes(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    assert len(routes) == 4
    assert list(routes.columns) == ROUTE_COLUMNS


def test_seed_route_ids_are_unique(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    assert not routes[
        ["supplier_id", "warehouse_id"]
    ].duplicated().any()


def test_seed_route_distances_are_valid(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    assert routes[DISTANCE_COLUMN].notna().all()
    assert (routes[DISTANCE_COLUMN] >= 0).all()


def test_same_location_has_zero_distance():
    suppliers = pd.DataFrame(
        {
            "supplier_id": ["SUP-00001"],
            "lat": [12.9716],
            "lng": [77.5946],
        }
    )

    warehouses = pd.DataFrame(
        {
            "warehouse_id": ["WH-BLR-01"],
            "lat": [12.9716],
            "lng": [77.5946],
        }
    )

    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    assert routes.loc[0, DISTANCE_COLUMN] == pytest.approx(
        0.0,
        abs=1e-6,
    )


def test_duplicate_supplier_id_is_rejected(
    suppliers,
    warehouses,
):
    suppliers = pd.concat(
        [suppliers, suppliers.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate supplier_id",
    ):
        build_seed_route_table(
            suppliers,
            warehouses,
        )


def test_duplicate_warehouse_id_is_rejected(
    suppliers,
    warehouses,
):
    warehouses = pd.concat(
        [warehouses, warehouses.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate warehouse_id",
    ):
        build_seed_route_table(
            suppliers,
            warehouses,
        )


def test_missing_supplier_columns_are_rejected(
    warehouses,
):
    suppliers = pd.DataFrame(
        {
            "supplier_id": ["SUP-00001"],
            "lat": [20.2961],
        }
    )

    with pytest.raises(
        ValueError,
        match="Missing supplier columns",
    ):
        build_seed_route_table(
            suppliers,
            warehouses,
        )


def test_missing_warehouse_columns_are_rejected(
    suppliers,
):
    warehouses = pd.DataFrame(
        {
            "warehouse_id": ["WH-BLR-01"],
            "lat": [12.9716],
        }
    )

    with pytest.raises(
        ValueError,
        match="Missing warehouse columns",
    ):
        build_seed_route_table(
            suppliers,
            warehouses,
        )

def test_seed_route_lookup_by_canonical_ids(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    route = get_seed_route(
        routes,
        "SUP-00001",
        "WH-BLR-01",
    )

    assert route["supplier_id"] == "SUP-00001"
    assert route["warehouse_id"] == "WH-BLR-01"
    assert route["distance_km"] >= 0


def test_unknown_supplier_is_rejected(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    with pytest.raises(
        ValueError,
        match="Unknown supplier_id",
    ):
        get_seed_route(
            routes,
            "SUP-99999",
            "WH-BLR-01",
        )


def test_unknown_warehouse_is_rejected(
    suppliers,
    warehouses,
):
    routes = build_seed_route_table(
        suppliers,
        warehouses,
    )

    with pytest.raises(
        ValueError,
        match="Unknown warehouse_id",
    ):
        get_seed_route(
            routes,
            "SUP-00001",
            "WH-XXX-01",
        )        