import json
from pathlib import Path
import jsonschema
from referencing import Registry, Resource

CONTRACTS_DIR = Path(__file__).resolve().parent.parent


def _load(name):
    return json.loads((CONTRACTS_DIR / name).read_text())


def test_compliance_status_changed_example_matches_schema():
    schema = _load("compliance.supplier.status_changed.v1.json")
    example = json.loads(
        (CONTRACTS_DIR / "examples" / "compliance.supplier.status_changed.v1.example.json").read_text()
    )

    envelope_schema = _load("envelope.v1.json")

    # Map the remote URL to the local schema using the referencing Registry
    registry = Registry().with_resource(
        "https://eaicsp.internal/contracts/events/envelope.v1.json",
        Resource.from_contents(envelope_schema)
    )

    jsonschema.validate(example, schema, registry=registry)