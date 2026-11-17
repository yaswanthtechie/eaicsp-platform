"""
The anomaly.sales.detected example and every event the builder makes must
satisfy the contract, and the contract must reject the mistakes consumers
care about.
"""

import copy
from datetime import UTC, date, datetime
import json
from pathlib import Path

import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource

from src.sales_anomaly_events import (
    EVENT_TYPE,
    anomaly_key,
    build_sales_anomaly_event,
    event_key,
    to_date_string,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EVENTS_DIR = REPO_ROOT / "contracts" / "events"
CONTRACT = EVENTS_DIR / "anomaly.sales.detected.v1.json"
EXAMPLE = EVENTS_DIR / "examples" / "anomaly.sales.detected.v1.json"

GOOD = dict(
    sku_id="SKU-000123",
    warehouse_id="WH-BLR-01",
    date="2026-11-14",
    expected_quantity=52.0,
    actual_quantity=214.0,
    score=8.2,
    severity="medium",
)


@pytest.fixture(scope="module")
def validator():

    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    envelope = json.loads((EVENTS_DIR / "envelope.v1.json").read_text(encoding="utf-8"))

    # `$ref: envelope.v1.json` must resolve to the local file, not the web.
    registry = (
        Registry()
        .with_resource("envelope.v1.json", Resource.from_contents(envelope))
        .with_resource(envelope["$id"], Resource.from_contents(envelope))
    )

    cls = validator_for(schema)
    cls.check_schema(schema)

    return cls(schema, registry=registry, format_checker=FormatChecker())


@pytest.fixture
def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def errors(validator, event):
    return [e.message for e in validator.iter_errors(event)]


# ---------------------------------------------------------------------
# the example and the builder match the contract
# ---------------------------------------------------------------------


def test_example_matches_contract(validator, example):
    assert errors(validator, example) == []


def test_built_event_matches_contract(validator):

    event = build_sales_anomaly_event(**GOOD)

    assert errors(validator, event) == []
    assert event["event_type"] == EVENT_TYPE == "anomaly.sales.detected"
    assert event["event_version"] == 1
    assert event["producer"] == "anomaly-detection-service"


@pytest.mark.parametrize("severity", ["high", "medium", "low"])
@pytest.mark.parametrize("actual", [0, 0.0, 214, 214.5])
def test_every_severity_and_quantity_shape_matches_contract(
    validator, severity, actual
):

    event = build_sales_anomaly_event(**{**GOOD, "actual_quantity": actual, "severity": severity})

    assert errors(validator, event) == []


def test_negative_score_for_a_drop_matches_contract(validator):

    event = build_sales_anomaly_event(
        **{**GOOD, "actual_quantity": 0, "score": -2.6, "severity": "high"}
    )

    assert errors(validator, event) == []


def test_event_ids_are_unique_uuids(validator):

    ids = {build_sales_anomaly_event(**GOOD)["event_id"] for _ in range(20)}

    assert len(ids) == 20


def test_pandas_timestamp_date_is_accepted(validator):

    import pandas as pd

    event = build_sales_anomaly_event(**{**GOOD, "date": pd.Timestamp("2026-11-14")})

    assert event["payload"]["date"] == "2026-11-14"
    assert errors(validator, event) == []


def test_occurred_at_can_be_passed_in():

    when = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
    event = build_sales_anomaly_event(**GOOD, occurred_at=when)

    assert event["occurred_at"] == "2026-11-17T03:00:00+00:00"


# ---------------------------------------------------------------------
# the contract rejects what consumers must never see
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "sku_id",
        "warehouse_id",
        "date",
        "expected_quantity",
        "actual_quantity",
        "score",
        "severity",
    ],
)
def test_payload_fields_are_required(validator, example, field):

    del example["payload"][field]

    assert errors(validator, example)


@pytest.mark.parametrize("bad", ["SKU-1", "sku-000001", "PRD-10482", "SKU-0000011"])
def test_non_canonical_sku_rejected(validator, example, bad):

    example["payload"]["sku_id"] = bad

    assert errors(validator, example)


@pytest.mark.parametrize("bad", ["WH-BLR-1", "wh1", "WH-blr-01", "HYD-01"])
def test_non_canonical_warehouse_rejected(validator, example, bad):

    example["payload"]["warehouse_id"] = bad

    assert errors(validator, example)


@pytest.mark.parametrize("bad", ["critical", "urgent", "HIGH", "", None])
def test_unknown_severity_rejected(validator, example, bad):

    example["payload"]["severity"] = bad

    assert errors(validator, example)


@pytest.mark.parametrize("bad", ["14/11/2026", "2026-11-14T00:00:00", "yesterday", 20261114])
def test_date_must_be_a_plain_iso_date(validator, example, bad):

    example["payload"]["date"] = bad

    assert errors(validator, example)


@pytest.mark.parametrize("field", ["expected_quantity", "actual_quantity"])
def test_negative_or_text_quantity_rejected(validator, example, field):

    example["payload"][field] = -1
    assert errors(validator, example)

    example["payload"][field] = "12"
    assert errors(validator, example)


def test_score_must_be_a_number(validator, example):

    example["payload"]["score"] = "8.2"

    assert errors(validator, example)


def test_extra_payload_field_rejected(validator, example):

    example["payload"]["direction"] = "spike"

    assert errors(validator, example)


def test_wrong_event_type_and_string_version_rejected(validator, example):

    wrong_type = copy.deepcopy(example)
    wrong_type["event_type"] = "iot.anomaly.detected"
    assert errors(validator, wrong_type)

    string_version = copy.deepcopy(example)
    string_version["event_version"] = "1"
    assert errors(validator, string_version)


def test_missing_envelope_field_rejected(validator, example):

    del example["producer"]

    assert errors(validator, example)


def test_bad_event_id_and_timestamp_rejected(validator, example):

    example["event_id"] = "not-a-uuid"
    example["occurred_at"] = "yesterday"

    assert len(errors(validator, example)) == 2


# ---------------------------------------------------------------------
# the builder refuses bad input before it can reach Kafka
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"sku_id": "PRD-10482"},
        {"warehouse_id": "HYD-01"},
        {"severity": "critical"},
        {"score": float("nan")},
        {"expected_quantity": float("inf")},
        {"actual_quantity": -1},
        {"actual_quantity": True},
        {"actual_quantity": "12"},
    ],
)
def test_builder_rejects_bad_input(change):

    with pytest.raises(ValueError):
        build_sales_anomaly_event(**{**GOOD, **change})

def test_numpy_numbers_are_accepted(validator):

    import numpy as np

    event = build_sales_anomaly_event(
        **{
            **GOOD,
            "expected_quantity": np.float64(52.0),
            "actual_quantity": np.int64(214),
            "score": np.float32(8.2),
        }
    )

    assert errors(validator, event) == []
    assert type(event["payload"]["actual_quantity"]) is float


def test_builder_rejects_a_non_date():

    with pytest.raises(TypeError):
        build_sales_anomaly_event(**{**GOOD, "date": 20261114})


# ---------------------------------------------------------------------
# identity of an anomaly and the Kafka key
# ---------------------------------------------------------------------


def test_anomaly_key_is_stable_across_date_types():

    keys = {
        anomaly_key("SKU-000123", "WH-BLR-01", "2026-11-14"),
        anomaly_key("SKU-000123", "WH-BLR-01", date(2026, 11, 14)),
        anomaly_key("SKU-000123", "WH-BLR-01", datetime(2026, 11, 14, 9, 30)),
    }

    assert keys == {"SKU-000123|WH-BLR-01|2026-11-14"}


def test_anomaly_key_differs_by_product_warehouse_and_day():

    base = anomaly_key("SKU-000123", "WH-BLR-01", "2026-11-14")

    assert base != anomaly_key("SKU-000124", "WH-BLR-01", "2026-11-14")
    assert base != anomaly_key("SKU-000123", "WH-BOM-01", "2026-11-14")
    assert base != anomaly_key("SKU-000123", "WH-BLR-01", "2026-11-15")


def test_kafka_key_keeps_one_series_together():

    event = build_sales_anomaly_event(**GOOD)

    assert event_key(event) == "SKU-000123|WH-BLR-01"


def test_to_date_string_rejects_other_types():

    assert to_date_string("2026-11-14") == "2026-11-14"

    with pytest.raises(TypeError):
        to_date_string(1.5)