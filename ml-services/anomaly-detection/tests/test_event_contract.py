"""
The iot.anomaly.detected example must satisfy its own contract,
and the contract must reject the mistakes consumers care about.
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "contracts" / "events" / "iot.anomaly.detected.v1.json"
EXAMPLE = REPO_ROOT / "contracts" / "events" / "examples" / "iot.anomaly.detected.v1.json"


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


def test_event_version_is_integer_one(validator, example):
    example["event_version"] = "1.0"
    assert errors(validator, example), "string version must be rejected"


@pytest.mark.parametrize("bad_id", ["WH-BLR-1", "wh1", "WH-blr-01", "WAREHOUSE-01"])
def test_non_canonical_warehouse_id_rejected(validator, example, bad_id):
    example["payload"]["warehouse_id"] = bad_id
    assert errors(validator, example)


@pytest.mark.parametrize(
    "field", ["warehouse_id", "severity", "message", "top_features", "episode_id"]
)
def test_fields_consumers_depend_on_are_required(validator, example, field):
    del example["payload"][field]
    assert errors(validator, example)


def test_unknown_severity_rejected(validator, example):
    example["payload"]["severity"] = "urgent"
    assert errors(validator, example)


def test_more_than_three_top_features_rejected(validator, example):
    extra = copy.deepcopy(example["payload"]["top_features"][0])
    extra["feature"] = "door_open"
    example["payload"]["top_features"].append(extra)
    assert errors(validator, example)


def test_bad_event_id_and_timestamp_rejected(validator, example):
    example["event_id"] = "not-a-uuid"
    example["occurred_at"] = "yesterday"
    assert len(errors(validator, example)) == 2
