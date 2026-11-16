
"""Integration test for the R15 client shipment data pipeline."""

import pandas as pd
from src.paths import SEED_SAMPLES_DIR
from src.client_data import load_client_shipments
from src.client_features import (
    FEATURE_COLUMNS,
    CATEGORICAL_COLUMNS,
    prepare_client_features,
)
from src.client_routes import add_client_route_distances

CLIENT_SAMPLES = (
    SEED_SAMPLES_DIR.parents[1]
    / "etl"
    / "client_ingest"
    / "samples"
    / "client_format"
)

def test_client_shipment_pipeline_end_to_end(tmp_path):
    """Test CSV loading, route enrichment and feature preparation."""

    # 1. Create a small synthetic client shipment-history CSV.
    shipment_file = tmp_path / "shipment_history.csv"

    shipments = pd.DataFrame(
        {
            "shipment_id": ["S001", "S002"],
            "po_number": ["PO001", "PO002"],
            "origin_city": ["Hyderabad", "Mumbai"],
            "destination_warehouse_code": ["WH-BLR", "WH-CHE"],
            "carrier_name": ["Air Cargo", "Express Logistics"],
            "dispatch_date": ["2025-01-01", "2025-01-02"],
            "planned_delivery_date": ["2025-01-04", "2025-01-05"],
            "actual_delivery_date": ["2025-01-03", "2025-01-06"],
            "weight_kg": [100.0, 200.0],
            "volume_m3": [1.5, 2.5],
        }
    )

    shipments.to_csv(shipment_file, index=False)

    # 2. Load and validate the client shipment data.
    loaded_shipments = load_client_shipments(shipment_file)

    assert len(loaded_shipments) == 2
    assert loaded_shipments["shipment_id"].tolist() == ["S001", "S002"]
    assert loaded_shipments.attrs["duplicate_shipment_count"] == 0

    # 3. Create synthetic seed coordinate data.
    suppliers = pd.DataFrame(
        {
            "city": ["Hyderabad", "Mumbai"],
            "lat": [17.3850, 19.0760],
            "lng": [78.4867, 72.8777],
        }
    )

    warehouses = pd.DataFrame(
        {
            "city": ["Bengaluru", "Chennai"],
            "lat": [12.9716, 13.0827],
            "lng": [77.5946, 80.2707],
        }
    )

    warehouse_master = pd.DataFrame(
        {
            "warehouse_code": ["WH-BLR", "WH-CHE"],
            "city": ["Bengaluru", "Chennai"],
        }
    )

    # 4. Resolve destination warehouses and calculate route distances.
    enriched_shipments, route_diagnostics = add_client_route_distances(
        shipments=loaded_shipments,
        suppliers=suppliers,
        warehouses=warehouses,
        warehouse_master=warehouse_master,
    )

    assert len(enriched_shipments) == 2
    assert "distance_km" in enriched_shipments.columns
    assert enriched_shipments["distance_km"].notna().all()
    assert (enriched_shipments["distance_km"] > 0).all()
    assert route_diagnostics["unknown_location_count"] == 0

    # 5. Prepare model features, target and evaluation metadata.
    X, y, metadata, feature_diagnostics = prepare_client_features(
        enriched_shipments
    )

    # 6. Verify the complete pipeline output.
    expected_features = FEATURE_COLUMNS + CATEGORICAL_COLUMNS

    assert list(X.columns) == expected_features
    assert len(X) == len(y) == len(metadata) == 2

    assert y.tolist() == [2.0, 4.0]
    assert metadata["shipment_id"].tolist() == ["S001", "S002"]

    assert X["carrier_name"].tolist() == [
        "Air Cargo",
        "Express Logistics",
    ]

    assert X["distance_km"].notna().all()
    assert X["planned_delivery_days"].tolist() == [3.0, 3.0]

    # Actual delivery date must remain metadata, not a model feature.
    assert "actual_delivery_date" in metadata.columns
    assert "actual_delivery_date" not in X.columns

    assert feature_diagnostics["total_shipments"] == 2
    assert feature_diagnostics["prepared_shipments"] == 2
    assert feature_diagnostics["excluded_target_rows"] == 0

def test_pipeline_on_committed_client_sample_files():
    """Test the pipeline using the committed #322 client sample files."""

    shipments = load_client_shipments(
        CLIENT_SAMPLES / "shipment_history.csv"
    )

    suppliers = pd.read_csv(SEED_SAMPLES_DIR / "suppliers.csv")
    warehouses = pd.read_csv(SEED_SAMPLES_DIR / "warehouses.csv")

    warehouse_master = pd.read_csv(
        CLIENT_SAMPLES / "warehouse_master.csv"
    )

    enriched, route_diagnostics = add_client_route_distances(
        shipments,
        suppliers,
        warehouses,
        warehouse_master,
    )

    _, _, _, feature_diagnostics = prepare_client_features(enriched)

    assert route_diagnostics["unknown_location_count"] == 0
    assert feature_diagnostics["prepared_shipments"] == 340