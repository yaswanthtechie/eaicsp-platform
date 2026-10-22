import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError, FormatChecker


ROOT = Path(__file__).resolve().parents[3]
EVENTS_DIR = ROOT / "contracts" / "events"
EXAMPLES_DIR = EVENTS_DIR / "examples"

CONTRACT_CASES = [
    (
        "supplierportal.po.acknowledged.v1.json",
        "supplierportal.po.acknowledged.v1.json",
    ),
    (
        "supplierportal.shipment.dispatched.v1.json",
        "supplierportal.shipment.dispatched.v1.json",
    ),
]


def load_json(path: Path) -> dict:
    """Load a JSON contract or example using UTF-8 encoding."""
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def load_contract_and_example(schema_name: str, example_name: str):
    schema = load_json(EVENTS_DIR / schema_name)
    example = load_json(EXAMPLES_DIR / example_name)
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    return validator, example


@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_event_example_matches_schema(schema_name, example_name):
    """Every published example must satisfy its event contract."""
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )

    validator.validate(example)


@pytest.mark.parametrize(
    ("schema_name", "example_name", "invalid_field"),
    [
        (
            "supplierportal.po.acknowledged.v1.json",
            "supplierportal.po.acknowledged.v1.json",
            "event_id",
        ),
        (
            "supplierportal.shipment.dispatched.v1.json",
            "supplierportal.shipment.dispatched.v1.json",
            "event_id",
        ),
    ],
)
def test_event_rejects_invalid_uuid(schema_name, example_name, invalid_field):
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )
    invalid_event = copy.deepcopy(example)
    invalid_event[invalid_field] = "not-a-valid-uuid"

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_event_rejects_missing_envelope_field(schema_name, example_name):
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )
    invalid_event = copy.deepcopy(example)
    del invalid_event["producer"]

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


def test_po_acknowledged_rejects_wrong_event_type():
    validator, example = load_contract_and_example(*CONTRACT_CASES[0])
    invalid_event = copy.deepcopy(example)
    invalid_event["event_type"] = "supplierportal.po.created"

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("shipment_id", "SHIP-123"),
        ("po_number", "PO1001"),
        ("supplier_id", "SUP001"),
        ("destination_warehouse", "WAREHOUSE-1"),
    ],
)
def test_shipment_rejects_invalid_identifier(field, invalid_value):
    validator, example = load_contract_and_example(*CONTRACT_CASES[1])
    invalid_event = copy.deepcopy(example)
    invalid_event["payload"][field] = invalid_value

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize(
    "required_field",
    [
        "shipment_id",
        "po_number",
        "supplier_id",
        "origin",
        "destination_warehouse",
        "carrier",
        "dispatched_at",
    ],
)
def test_shipment_rejects_missing_required_payload_field(required_field):
    validator, example = load_contract_and_example(*CONTRACT_CASES[1])
    invalid_event = copy.deepcopy(example)
    del invalid_event["payload"][required_field]

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


def test_shipment_rejects_invalid_dispatch_timestamp():
    validator, example = load_contract_and_example(*CONTRACT_CASES[1])
    invalid_event = copy.deepcopy(example)
    invalid_event["payload"]["dispatched_at"] = "not-a-timestamp"

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


def test_shipment_rejects_wrong_event_version():
    validator, example = load_contract_and_example(*CONTRACT_CASES[1])
    invalid_event = copy.deepcopy(example)
    invalid_event["event_version"] = 2

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)

@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_schema_itself_is_valid(schema_name, example_name):
    """A broken schema would make every validation test meaningless."""
    schema = load_json(EVENTS_DIR / schema_name)

    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_event_accepts_optional_trace_id(schema_name, example_name):
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )
    event = copy.deepcopy(example)
    event["trace_id"] = "trace-123"

    validator.validate(event)


@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_event_rejects_non_v4_uuid(schema_name, example_name):
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )
    invalid_event = copy.deepcopy(example)
    invalid_event["event_id"] = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize(
    ("schema_name", "example_name"),
    CONTRACT_CASES,
)
def test_event_rejects_string_event_version(schema_name, example_name):
    validator, example = load_contract_and_example(
        schema_name,
        example_name,
    )
    invalid_event = copy.deepcopy(example)
    invalid_event["event_version"] = "1"

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("po_number", "PO1001"),
        ("supplier_id", "SUP001"),
    ],
)
def test_po_acknowledged_rejects_invalid_identifier(field, invalid_value):
    validator, example = load_contract_and_example(*CONTRACT_CASES[0])
    invalid_event = copy.deepcopy(example)
    invalid_event["payload"][field] = invalid_value

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)


@pytest.mark.parametrize("field", ["origin", "carrier"])
def test_shipment_rejects_blank_text_field(field):
    validator, example = load_contract_and_example(*CONTRACT_CASES[1])
    invalid_event = copy.deepcopy(example)
    invalid_event["payload"][field] = "   "

    with pytest.raises(ValidationError):
        validator.validate(invalid_event)
