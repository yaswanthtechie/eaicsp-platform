"""
The eta.shipment.predicted example must satisfy its own contract, and the
contract must reject the mistakes consumers care about.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[3]

CONTRACT = REPO_ROOT / "contracts" / "events" / "eta.shipment.predicted.v1.json"
EXAMPLE = REPO_ROOT / "contracts" / "events" / "examples" / "eta.shipment.predicted.v1.json"
DISPATCHED_EXAMPLE = (
    REPO_ROOT
    / "contracts"
    / "events"
    / "examples"
    / "supplierportal.shipment.dispatched.v1.json"
)

REQUIRED_PAYLOAD_FIELDS = [
    "shipment_id",
    "po_number",
    "eta_days",
    "confidence_low",
    "confidence_high",
    "model_version",
    "predicted_at",
]

ENVELOPE_FIELDS = [
    "event_id",
    "event_type",
    "event_version",
    "occurred_at",
    "producer",
    "payload",
]


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def errors(validator, event):
    return [e.message for e in validator.iter_errors(event)]


def test_example_matches_contract(validator, example):
    assert errors(validator, example) == []


def test_example_confidence_interval_is_ordered(example):
    payload = example["payload"]
    assert payload["confidence_low"] <= payload["confidence_high"]


def test_example_follows_the_dispatched_shipment():
    """Flow B: the ETA is for the shipment the dispatched example announces."""
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    dispatched = json.loads(DISPATCHED_EXAMPLE.read_text(encoding="utf-8"))

    assert example["payload"]["shipment_id"] == dispatched["payload"]["shipment_id"]
    assert example["payload"]["po_number"] == dispatched["payload"]["po_number"]


@pytest.mark.parametrize("field", ENVELOPE_FIELDS)
def test_envelope_fields_are_required(validator, example, field):
    del example[field]
    assert errors(validator, example)


@pytest.mark.parametrize("field", REQUIRED_PAYLOAD_FIELDS)
def test_payload_fields_consumers_depend_on_are_required(validator, example, field):
    del example["payload"][field]
    assert errors(validator, example)


def test_top_features_is_optional(validator, example):
    del example["payload"]["top_features"]
    assert errors(validator, example) == []


@pytest.mark.parametrize(
    "bad_id", ["SHIP-12345", "SHP-12345", "SHP-2026-77", "shp-2026-000077"]
)
def test_non_canonical_shipment_id_rejected(validator, example, bad_id):
    example["payload"]["shipment_id"] = bad_id
    assert errors(validator, example)


@pytest.mark.parametrize(
    "bad_po", ["PO-98765", "PO-2026-123", "po-2026-000123"]
)
def test_non_canonical_po_number_rejected(validator, example, bad_po):
    example["payload"]["po_number"] = bad_po
    assert errors(validator, example)


def test_event_version_is_integer_one(validator, example):
    example["event_version"] = "1.0"
    assert errors(validator, example), "string version must be rejected"


def test_wrong_event_type_rejected(validator, example):
    example["event_type"] = "eta.predicted"
    assert errors(validator, example)


def test_non_uuid_event_id_rejected(validator, example):
    example["event_id"] = "evt-1"
    assert errors(validator, example)


@pytest.mark.parametrize(
    "field", ["eta_days", "confidence_low", "confidence_high"]
)
def test_negative_days_rejected(validator, example, field):
    example["payload"][field] = -1.0
    assert errors(validator, example)


@pytest.mark.parametrize(
    "field", ["eta_days", "confidence_low", "confidence_high"]
)
def test_days_as_string_rejected(validator, example, field):
    example["payload"][field] = "5.2"
    assert errors(validator, example)


def test_invalid_predicted_at_rejected(validator, example):
    example["payload"]["predicted_at"] = "23/10/2026 10:30"
    assert errors(validator, example)


def test_blank_model_version_rejected(validator, example):
    example["payload"]["model_version"] = "   "
    assert errors(validator, example)


def test_unknown_payload_field_rejected(validator, example):
    example["payload"]["eta_date"] = "2026-10-20"
    assert errors(validator, example)


def test_eta_outside_interval_is_allowed(validator, example):
    """Asymmetric calibration: the point estimate may sit outside the interval."""
    example["payload"].update(
        eta_days=5.2,
        confidence_low=7.2,
        confidence_high=12.2,
    )
    assert errors(validator, example) == []