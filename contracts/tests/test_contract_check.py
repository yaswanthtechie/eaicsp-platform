import json
from pathlib import Path
import subprocess
import sys

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[2]
if str(CONTRACTS_DIR) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_DIR))

from contract_check import check_contracts
from tools.breaking_checker import check_breaking_changes, diff_schemas, normalize_schema


ENVELOPE_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://eaicsp.internal/contracts/events/envelope.v1.json",
    "type": "object",
    "properties": {
        "event_id": {"type": "string", "format": "uuid"},
        "event_type": {"type": "string"},
        "event_version": {"type": "integer", "minimum": 1},
        "occurred_at": {"type": "string", "format": "date-time"},
        "producer": {"type": "string"},
        "payload": {"type": "object"},
    },
    "required": [
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer",
        "payload",
    ],
    "additionalProperties": False,
}


def _base_event_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [
            {"$ref": "envelope.v1.json"},
            {
                "type": "object",
                "properties": {
                    "event_type": {"const": "orders.order.created"},
                    "event_version": {"const": 1},
                    "payload": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string"},
                            "amount": {"type": "number"},
                            "status": {
                                "type": "string",
                                "enum": ["PENDING", "APPROVED", "REJECTED"],
                            },
                            "notes": {"type": "string"},
                        },
                        "required": ["order_id", "amount", "status"],
                    },
                },
            },
        ],
    }


def _valid_example() -> dict:
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "orders.order.created",
        "event_version": 1,
        "occurred_at": "2026-11-24T10:30:00Z",
        "producer": "order-service",
        "payload": {
            "order_id": "ORD-1001",
            "amount": 125.5,
            "status": "PENDING",
        },
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_contract_repo(tmp_path: Path) -> Path:
    contracts = tmp_path / "contracts"
    _write_json(contracts / "events" / "envelope.v1.json", ENVELOPE_V1)
    _write_json(
        contracts / "events" / "orders.order.created.v1.json",
        _base_event_schema(),
    )
    _write_json(
        contracts / "events" / "examples" / "orders.order.created.v1.json",
        _valid_example(),
    )

    _git(tmp_path, "init", "-b", "develop")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial contracts")
    return contracts


# --- Breaking-change rule unit tests ---


def test_required_field_removed_fails():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    del new_raw["allOf"][1]["properties"]["payload"]["properties"]["amount"]
    new_raw["allOf"][1]["properties"]["payload"]["required"].remove("amount")
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    assert any(
        f.rule == "required_field_removed" and f.field == "payload.amount"
        for f in findings
    )


def test_required_field_renamed_fails():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    payload = new_raw["allOf"][1]["properties"]["payload"]
    payload["properties"]["total_amount"] = payload["properties"].pop("amount")
    payload["required"] = ["order_id", "total_amount", "status"]
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    rules = {(f.field, f.rule) for f in findings}
    assert ("payload.amount", "required_field_removed") in rules
    assert ("payload.total_amount", "field_became_required") in rules


def test_type_changed_fails():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    new_raw["allOf"][1]["properties"]["payload"]["properties"]["amount"]["type"] = "string"
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    assert any(
        f.rule == "type_changed" and f.field == "payload.amount"
        for f in findings
    )


def test_enum_value_removed_fails():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    new_raw["allOf"][1]["properties"]["payload"]["properties"]["status"]["enum"] = [
        "PENDING",
        "APPROVED",
    ]
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    assert any(
        f.rule == "enum_value_removed" and f.field == "payload.status"
        for f in findings
    )


def test_optional_field_becoming_required_fails():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    new_raw["allOf"][1]["properties"]["payload"]["required"].append("notes")
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    assert any(
        f.rule == "field_became_required" and f.field == "payload.notes"
        for f in findings
    )


def test_adding_optional_field_passes():
    old = normalize_schema(_base_event_schema(), lambda ref: ENVELOPE_V1)
    new_raw = _base_event_schema()
    new_raw["allOf"][1]["properties"]["payload"]["properties"]["warehouse_id"] = {
        "type": "string"
    }
    new = normalize_schema(new_raw, lambda ref: ENVELOPE_V1)

    findings = diff_schemas(old, new, "events/orders.order.created.v1.json")
    assert findings == []


# --- Git integration tests (--against) ---


def test_breaking_change_in_new_v2_file_passes(tmp_path: Path):
    contracts = _init_contract_repo(tmp_path)

    # Create v2 with breaking payload changes while leaving v1 untouched
    v2_schema = _base_event_schema()
    v2_schema["allOf"][1]["properties"]["event_version"]["const"] = 2
    v2_schema["allOf"][1]["properties"]["payload"]["properties"]["amount"]["type"] = "string"
    del v2_schema["allOf"][1]["properties"]["payload"]["properties"]["status"]
    v2_schema["allOf"][1]["properties"]["payload"]["required"] = ["order_id", "amount"]

    v2_example = _valid_example()
    v2_example["event_version"] = 2
    v2_example["payload"] = {"order_id": "ORD-1002", "amount": "125.50"}

    _write_json(contracts / "events" / "orders.order.created.v2.json", v2_schema)
    _write_json(contracts / "events" / "examples" / "orders.order.created.v2.json", v2_example)

    _git(tmp_path, "add", ".")
    findings = check_contracts(str(contracts), against="develop")
    assert findings == []


def test_same_version_breaking_change_caught_via_git_against(tmp_path: Path):
    contracts = _init_contract_repo(tmp_path)
    broken = _base_event_schema()
    broken["allOf"][1]["properties"]["payload"]["properties"]["amount"]["type"] = "integer"
    _write_json(contracts / "events" / "orders.order.created.v1.json", broken)

    findings = check_breaking_changes(str(contracts), against_ref="develop")
    assert any(
        f.file == "events/orders.order.created.v1.json"
        and f.field == "payload.amount"
        and f.rule == "type_changed"
        for f in findings
    )


# --- Event, Envelope, Naming & OpenAPI checks ---


def test_envelope_and_legacy_example_naming_caught(tmp_path: Path):
    contracts = tmp_path / "contracts"
    _write_json(contracts / "events" / "envelope.v1.json", ENVELOPE_V1)
    _write_json(
        contracts / "events" / "orders.order.created.v1.json",
        _base_event_schema(),
    )

    bad_example = _valid_example()
    bad_example["occurred_at"] = "not-a-timestamp"
    bad_example["extra_root_key"] = "disallowed"
    _write_json(
        contracts / "events" / "examples" / "orders.order.created.v1.example.json",
        bad_example,
    )

    findings = check_contracts(str(contracts))
    rules = {f.rule for f in findings}
    assert "missing_example" in rules
    assert "example_naming" in rules
    assert "envelope_validation" in rules


def test_openapi_valid_and_invalid_inline_example(tmp_path: Path):
    contracts = tmp_path / "contracts"
    _write_json(contracts / "events" / "envelope.v1.json", ENVELOPE_V1)

    openapi_dir = contracts / "openapi"
    openapi_dir.mkdir(parents=True)
    # Non-YAML companion file should be ignored cleanly
    (openapi_dir / "notes.md").write_text("# Notes\n", encoding="utf-8")

    (openapi_dir / "inventory.yaml").write_text(
        """
openapi: 3.0.3
info:
  title: Inventory API
  version: 1.0.0
paths:
  /stock:
    get:
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StockItem'
              example:
                sku: SKU-1
                qty: "not-an-integer"
components:
  schemas:
    StockItem:
      type: object
      required: [sku, qty]
      properties:
        sku:
          type: string
        qty:
          type: integer
""".strip(),
        encoding="utf-8",
    )

    findings = check_contracts(str(contracts))
    assert any(
        f.file == "openapi/inventory.yaml"
        and f.rule == "openapi_example_invalid"
        and "qty" in f.field
        for f in findings
    )