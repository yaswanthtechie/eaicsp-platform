"""
R15-H2: features, training, and the serving path against the contract.
"""

import json
import re
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src import h2_predict
from src.h2_features import H2_FEATURES, build_h2_features
from src.h2_train import evaluate_h2_model, train_h2_model
from src.paths import SEED_SAMPLES_DIR
from src.seed_routes import load_seed_routes


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "contracts" / "events" / "eta.shipment.predicted.v1.json"


# ---------------------------------------------------------
# Features
# ---------------------------------------------------------
def test_h2_columns_are_only_dispatch_time_features(sample_datasets):
    features = build_h2_features(sample_datasets)

    assert list(features.columns) == [
        "order_id",
        *H2_FEATURES,
        "delivery_days",
    ]


def test_h2_target_is_measured_from_carrier_handoff(sample_datasets):
    """eta_days in the contract counts from dispatched_at, not purchase."""

    features = build_h2_features(sample_datasets).set_index("order_id")

    # conftest: carrier hand-off -> customer delivery is 3, 4, 4 days;
    # purchase -> delivery would be 4, 5, 5.
    assert features["delivery_days"].to_dict() == pytest.approx(
        {"order_1": 3.0, "order_2": 4.0, "order_3": 4.0}
    )


def test_h2_time_features_come_from_carrier_handoff(sample_datasets):
    features = build_h2_features(sample_datasets).set_index("order_id")

    # order_1 handed to carrier Tue 2018-01-02.
    assert features.loc["order_1", "dispatch_month"] == 1
    assert features.loc["order_1", "dispatch_day_of_week"] == 1


def test_h2_drops_rows_without_a_valid_handoff(sample_datasets):
    orders = sample_datasets["orders"].copy()
    orders.loc[0, "order_delivered_carrier_date"] = None
    orders.loc[1, "order_delivered_carrier_date"] = "2018-01-09 00:00:00"
    sample_datasets = {**sample_datasets, "orders": orders}

    features = build_h2_features(sample_datasets)

    assert features["order_id"].tolist() == ["order_3"]


# ---------------------------------------------------------
# Training
# ---------------------------------------------------------
def _synthetic_training_data(rows=200):
    rng = np.random.default_rng(42)
    X = pd.DataFrame(
        {
            "dispatch_month": rng.integers(1, 13, rows),
            "dispatch_day_of_week": rng.integers(0, 7, rows),
            "distance_km": rng.uniform(5, 3000, rows),
        }
    )
    y = pd.Series(2 + X["distance_km"] / 300 + rng.normal(0, 1, rows))
    return X, y


def test_train_h2_writes_its_own_pair(tmp_path):
    X, y = _synthetic_training_data()
    model_path = tmp_path / "h2.joblib"
    calibration_path = tmp_path / "h2_interval.joblib"

    model, calibration = train_h2_model(
        X,
        y,
        model_path=model_path,
        calibration_path=calibration_path,
    )

    assert model_path.exists() and calibration_path.exists()
    assert calibration["residual_lower"] <= calibration["residual_upper"]
    assert len(model.predict(X.head(3))) == 3


def test_production_gate_refuses_tiny_calibration(tmp_path):
    X, y = _synthetic_training_data(rows=20)
    model_path = tmp_path / "h2.joblib"

    with pytest.raises(ValueError, match="Do not ship"):
        train_h2_model(
            X,
            y,
            enforce_production_gate=True,
            model_path=model_path,
            calibration_path=tmp_path / "h2_interval.joblib",
        )

    assert not model_path.exists()


def test_evaluate_h2_reports_prefixed_metrics(tmp_path):
    X, y = _synthetic_training_data()
    model, calibration = train_h2_model(
        X,
        y,
        model_path=tmp_path / "m.joblib",
        calibration_path=tmp_path / "c.joblib",
    )

    test = X.assign(delivery_days=y)
    results = evaluate_h2_model(model, calibration, test)

    assert set(results) == {
        "h2_mae",
        "h2_interval_coverage",
        "h2_nominal_coverage",
    }
    assert 0.0 <= results["h2_interval_coverage"] <= 1.0


# ---------------------------------------------------------
# Serving: committed artifacts + seed routes + contract
# ---------------------------------------------------------
@pytest.fixture(scope="module")
def seed_routes():
    return load_seed_routes(SEED_SAMPLES_DIR)


@pytest.fixture(scope="module")
def contract_validator():
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _dispatched(supplier_id, warehouse_id):
    return {
        "supplier_id": supplier_id,
        "destination_warehouse": warehouse_id,
        "carrier": "BlueDart",
        "dispatched_at": "2026-10-15T06:30:00Z",
    }


def test_seed_samples_build_every_route(seed_routes):
    suppliers = pd.read_csv(SEED_SAMPLES_DIR / "suppliers.csv")
    warehouses = pd.read_csv(SEED_SAMPLES_DIR / "warehouses.csv")

    assert len(seed_routes) == len(suppliers) * len(warehouses)
    assert seed_routes["supplier_id"].str.fullmatch(r"SUP-\d{5}").all()
    assert seed_routes["warehouse_id"].str.fullmatch(
        r"WH-[A-Z]{3}-\d{2}"
    ).all()


def test_committed_h2_model_serves_every_seed_route_within_contract(
    seed_routes,
    contract_validator,
):
    """The committed pair, real seed routes, real contract."""

    for route in seed_routes.itertuples():
        result = h2_predict.predict_h2(
            _dispatched(route.supplier_id, route.warehouse_id),
            seed_routes,
        )

        assert result["confidence_low"] <= result["confidence_high"]

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "eta.shipment.predicted",
            "event_version": 1,
            "occurred_at": "2026-10-15T06:31:05Z",
            "producer": "eta-prediction",
            "payload": {
                "shipment_id": "SHP-2026-000077",
                "po_number": "PO-2026-000123",
                "model_version": "eta_seed_routes/1",
                "predicted_at": "2026-10-15T06:31:04Z",
                **result,
            },
        }

        errors = [e.message for e in contract_validator.iter_errors(event)]
        assert errors == [], f"{route.supplier_id}->{route.warehouse_id}: {errors}"


def test_top_features_are_named_like_the_model_inputs(seed_routes):
    route = seed_routes.iloc[0]
    result = h2_predict.predict_h2(
        _dispatched(route["supplier_id"], route["warehouse_id"]),
        seed_routes,
    )

    names = [item["feature"] for item in result["top_features"]]
    assert set(names) <= set(H2_FEATURES)
    assert not any(re.match(r"\w+__", name) for name in names)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"supplier_id": "SUP-99999"}, "Unknown supplier_id"),
        ({"destination_warehouse": "WH-XXX-99"}, "Unknown warehouse_id"),
        ({"dispatched_at": "not a date"}, "Invalid dispatched_at"),
    ],
)
def test_bad_dispatch_payload_is_rejected(seed_routes, change, message):
    route = seed_routes.iloc[0]
    payload = {
        **_dispatched(route["supplier_id"], route["warehouse_id"]),
        **change,
    }

    with pytest.raises(ValueError, match=message):
        h2_predict.predict_h2(payload, seed_routes)


def test_missing_field_is_rejected(seed_routes):
    with pytest.raises(ValueError, match="carrier"):
        h2_predict.predict_h2(
            {
                "supplier_id": "SUP-00001",
                "destination_warehouse": "WH-BLR-01",
                "dispatched_at": "2026-10-15T06:30:00Z",
            },
            seed_routes,
        )