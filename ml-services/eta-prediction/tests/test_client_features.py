
import pandas as pd

from src.client_features import prepare_client_features


def sample_shipments():
    return pd.DataFrame(
        {
            "shipment_id": ["S001", "S002", "S003"],
            "carrier_name": ["Carrier A", "Carrier B", "Carrier A"],
            "dispatch_date": [
                "2026-01-01",
                "2026-01-05",
                "2026-01-10",
            ],
            "planned_delivery_date": [
                "2026-01-04",
                "2026-01-09",
                "2026-01-14",
            ],
            "actual_delivery_date": [
                "2026-01-05",
                "2026-01-08",
                "2026-01-15",
            ],
            "distance_km": [100.0, 200.0, 300.0],
            "weight_kg": [10.0, None, 30.0],
            "volume_m3": [1.0, 2.0, None],
        }
    )


def test_creates_expected_features_and_target():
    X, y, metadata, diagnostics = prepare_client_features(
        sample_shipments()
    )

    assert list(X.columns) == [
        "dispatch_month",
        "dispatch_day_of_week",
        "distance_km",
        "weight_kg",
        "volume_m3",
        "planned_delivery_days",
        "carrier_name",
    ]

    assert y.tolist() == [4.0, 3.0, 5.0]
    assert X["planned_delivery_days"].tolist() == [3.0, 4.0, 4.0]
    assert X["carrier_name"].tolist() == [
        "Carrier A",
        "Carrier B",
        "Carrier A",
    ]
    assert len(metadata) == 3
    assert diagnostics["prepared_shipments"] == 3


def test_actual_date_is_not_a_model_feature():
    X, _, metadata, _ = prepare_client_features(sample_shipments())

    assert "actual_delivery_date" not in X.columns
    assert "planned_delivery_date" not in X.columns
    assert "delivery_days" not in X.columns

    assert "planned_delivery_days" in X.columns
    assert "planned_delivery_days" in metadata.columns
    assert "actual_delivery_date" in metadata.columns


def test_missing_weight_and_volume_are_preserved():
    X, _, _, diagnostics = prepare_client_features(sample_shipments())

    assert pd.isna(X.loc[1, "weight_kg"])
    assert pd.isna(X.loc[2, "volume_m3"])
    assert diagnostics["missing_weight_count"] == 1
    assert diagnostics["missing_volume_count"] == 1


def test_invalid_target_rows_are_excluded_and_counted():
    shipments = sample_shipments()
    shipments.loc[1, "actual_delivery_date"] = None
    shipments.loc[2, "actual_delivery_date"] = "2026-01-09"

    X, y, metadata, diagnostics = prepare_client_features(shipments)

    assert len(X) == 1
    assert len(y) == 1
    assert len(metadata) == 1
    assert diagnostics["invalid_actual_delivery_date_count"] == 1
    assert diagnostics["negative_delivery_days_count"] == 1
    assert diagnostics["excluded_target_rows"] == 2


def test_missing_planned_date_does_not_exclude_training_row():
    shipments = sample_shipments()
    shipments.loc[0, "planned_delivery_date"] = None

    X, y, metadata, diagnostics = prepare_client_features(shipments)

    assert len(X) == 3
    assert len(y) == 3
    assert pd.isna(X.loc[0, "planned_delivery_days"])
    assert pd.isna(metadata.loc[0, "planned_delivery_days"])
    assert diagnostics["missing_planned_baseline_count"] == 1


def test_infinite_numeric_features_are_converted_to_missing():
    shipments = pd.DataFrame(
        {
            "shipment_id": ["SHP001"],
            "carrier_name": ["Express Logistics"],
            "dispatch_date": ["2026-01-01"],
            "planned_delivery_date": ["2026-01-05"],
            "actual_delivery_date": ["2026-01-06"],
            "distance_km": [float("inf")],
            "weight_kg": [float("inf")],
            "volume_m3": [float("-inf")],
        }
    )

    X, y, metadata, diagnostics = prepare_client_features(shipments)

    assert len(X) == 1
    assert X["distance_km"].isna().all()
    assert X["weight_kg"].isna().all()
    assert X["volume_m3"].isna().all()

    assert diagnostics["missing_distance_count"] == 1
    assert diagnostics["missing_weight_count"] == 1
    assert diagnostics["missing_volume_count"] == 1


def test_missing_carrier_is_replaced_with_unknown():
    shipments = sample_shipments()
    shipments.loc[1, "carrier_name"] = None

    X, _, _, _ = prepare_client_features(shipments)

    assert X.loc[1, "carrier_name"] == "Unknown"


def test_same_day_actual_delivery_is_valid():
    shipments = sample_shipments()
    shipments.loc[0, "actual_delivery_date"] = "2026-01-01"

    X, y, metadata, diagnostics = prepare_client_features(shipments)

    assert len(X) == 3
    assert y.loc[0] == 0.0
    assert metadata.loc[0, "actual_delivery_date"] == pd.Timestamp(
        "2026-01-01"
    )
    assert diagnostics["negative_delivery_days_count"] == 0


def test_same_day_planned_delivery_is_valid():
    shipments = sample_shipments()
    shipments.loc[0, "planned_delivery_date"] = "2026-01-01"

    X, _, metadata, diagnostics = prepare_client_features(shipments)

    assert X.loc[0, "planned_delivery_days"] == 0.0
    assert metadata.loc[0, "planned_delivery_days"] == 0.0
    assert diagnostics["missing_planned_baseline_count"] == 0


def test_negative_delivery_duration_is_excluded():
    shipments = sample_shipments()
    shipments.loc[0, "actual_delivery_date"] = "2025-12-31"

    X, y, metadata, diagnostics = prepare_client_features(shipments)

    assert len(X) == 2
    assert len(y) == 2
    assert len(metadata) == 2
    assert diagnostics["negative_delivery_days_count"] == 1
    assert diagnostics["excluded_target_rows"] == 1
