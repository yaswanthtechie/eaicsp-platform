
import json

import joblib
import pandas as pd
import pytest

from client_train import train_client_eta


class FakePipeline:
    """Lightweight model for testing training orchestration."""

    def fit(self, X, y):
        self.training_rows = len(X)
        self.feature_columns = list(X.columns)
        return self

    def predict(self, X):
        return [3.0] * len(X)


@pytest.fixture
def training_data(tmp_path):
    rows = []

    for index in range(10):
        dispatch = (
            pd.Timestamp("2026-01-01")
            + pd.Timedelta(days=index)
        )

        rows.append({
            "shipment_id": f"SHP{index:03d}",
            "po_number": f"PO{index:03d}",
            "origin_city": "Hyderabad",
            "destination_warehouse_code": "HYD-01",
            "carrier_name": (
                "BlueDart" if index % 2 == 0 else "Delhivery"
            ),
            "dispatch_date": dispatch,
            "planned_delivery_date": (
                dispatch + pd.Timedelta(days=4)
            ),
            "actual_delivery_date": (
                dispatch + pd.Timedelta(days=3)
            ),
            "weight_kg": 10.0 + index,
            "volume_m3": 0.5 + index * 0.1,
        })

    shipment_file = tmp_path / "shipments.csv"

    pd.DataFrame(rows).to_csv(
        shipment_file,
        index=False,
    )

    suppliers = pd.DataFrame({
        "city": ["Hyderabad", "Mumbai", "New Delhi"],
        "lat": [17.385, 19.076, 28.6139],
        "lng": [78.4867, 72.8777, 77.2090],
    })

    warehouses = pd.DataFrame({
        "warehouse_id": ["WH-BOM-01", "WH-DEL-01"],
        "city": ["Bhiwandi", "Gurugram"],
        "lat": [19.3002, 28.4595],
        "lng": [73.0581, 77.0266],
    })

    warehouse_master = pd.DataFrame({
        "warehouse_code": ["HYD-01", "MUM-01", "DEL-01"],
        "city": ["Hyderabad", "Mumbai", "New Delhi"],
    })

    return (
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    )


@pytest.fixture
def artifact_paths(tmp_path, monkeypatch):
    model_path = tmp_path / "client_model.joblib"
    metadata_path = tmp_path / "client_metadata.json"

    monkeypatch.setattr(
        "client_train.H4_MODEL_PATH",
        model_path,
    )

    monkeypatch.setattr(
        "client_train.H4_METADATA_PATH",
        metadata_path,
    )

    monkeypatch.setattr(
        "client_train.ensure_directories",
        lambda: None,
    )

    monkeypatch.setattr(
        "client_train.create_client_pipeline",
        FakePipeline,
    )

    return model_path, metadata_path


def test_training_workflow_saves_model_and_metadata(
    training_data,
    artifact_paths,
):
    (
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    ) = training_data

    model_path, metadata_path = artifact_paths

    result = train_client_eta(
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    )

    assert model_path.is_file()
    assert metadata_path.is_file()

    saved_model = joblib.load(model_path)

    assert isinstance(saved_model, FakePipeline)
    assert saved_model.training_rows == 8

    with metadata_path.open(encoding="utf-8") as file:
        saved_metadata = json.load(file)

    assert saved_metadata["model_name"] == "R15-H4-client-eta"
    assert saved_metadata["training_shipments"] == 8
    assert saved_metadata["test_shipments"] == 2

    assert result["evaluation"]["evaluated_shipments"] == 2
    assert result["evaluation"]["model_beats_baseline"] is True


def test_training_reports_route_diagnostics(
    training_data,
    artifact_paths,
):
    (
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    ) = training_data

    result = train_client_eta(
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    )

    assert result["route_diagnostics"]["unknown_location_count"] == 0
    assert result["route_diagnostics"]["missing_distance_count"] == 0


def test_model_is_not_saved_when_evaluation_fails(
    training_data,
    artifact_paths,
    monkeypatch,
):
    (
        shipment_file,
        suppliers,
        warehouses,
        warehouse_master,
    ) = training_data

    model_path, metadata_path = artifact_paths

    def fail_evaluation(**kwargs):
        raise ValueError("Evaluation failed")

    monkeypatch.setattr(
        "client_train.compare_client_baseline_and_model",
        fail_evaluation,
    )

    with pytest.raises(ValueError, match="Evaluation failed"):
        train_client_eta(
            shipment_file,
            suppliers,
            warehouses,
            warehouse_master,
        )

    assert not model_path.exists()
    assert not metadata_path.exists()


def test_training_rejects_missing_shipment_file(
    tmp_path,
    artifact_paths,
):
    suppliers = pd.DataFrame({
        "city": ["Hyderabad"],
        "lat": [17.385],
        "lng": [78.4867],
    })

    warehouses = pd.DataFrame({
        "warehouse_id": ["WH-HYD-01"],
        "city": ["Hyderabad"],
        "lat": [17.385],
        "lng": [78.4867],
    })

    warehouse_master = pd.DataFrame({
        "warehouse_code": ["HYD-01"],
        "city": ["Hyderabad"],
    })

    missing_file = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        train_client_eta(
            missing_file,
            suppliers,
            warehouses,
            warehouse_master,
        )
