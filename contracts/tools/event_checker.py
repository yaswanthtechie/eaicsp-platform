import json
import os
import re
from typing import Any

from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

from tools.formats import build_format_checker
from tools.models import Finding

# Foundational files, not concrete events.
NON_EVENT_FILES = {"envelope.v1.json", "_template.v1.json"}
ENVELOPE_FILENAME = "envelope.v1.json"

# Canonical convention: "<domain>.<entity>.<action>.v<N>.json"
FILENAME_RE = re.compile(r"^(?P<event_type>.+)\.v(?P<version>\d+)\.json$")
LEGACY_EXAMPLE_SUFFIX = ".example.json"


def find_const(schema: dict[str, Any], key: str) -> Any:
    """Locate a const value at top level or inside nested allOf branches."""
    props = schema.get("properties", {})
    if isinstance(props, dict) and key in props and isinstance(props[key], dict):
        if "const" in props[key]:
            return props[key]["const"]
    for branch in schema.get("allOf", []):
        if isinstance(branch, dict):
            value = find_const(branch, key)
            if value is not None:
                return value
    return None


def _load_registry(events_dir: str) -> Registry:
    """Register every local event schema by filename and $id for $ref resolution."""
    registry = Registry()
    for filename in sorted(os.listdir(events_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(events_dir, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                contents = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        resource = Resource.from_contents(contents)
        registry = registry.with_resource(filename, resource)
        if isinstance(contents, dict) and "$id" in contents:
            registry = registry.with_resource(contents["$id"], resource)
    return registry


def _format_error_path(path_parts: Any) -> str:
    parts = [str(p) for p in path_parts]
    return ".".join(parts) if parts else "<root>"


def _validate_payload(
    validator: Any,
    payload: Any,
    rel_file: str,
    rule: str,
    seen_errors: set[tuple[str, str]],
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda e: [str(p) for p in e.path],
        )
    except Unresolvable as exc:
        return [
            Finding(
                file=rel_file,
                field="<root>",
                rule="unresolved_ref",
                message=f"Could not resolve $ref: {exc}",
            )
        ]

    for error in errors:
        field_path = _format_error_path(error.path)
        key = (field_path, error.message)
        if key in seen_errors:
            continue
        seen_errors.add(key)
        findings.append(
            Finding(
                file=rel_file,
                field=field_path,
                rule=rule,
                message=error.message,
            )
        )
    return findings


def check_events(contracts_dir: str) -> list[Finding]:
    findings: list[Finding] = []
    events_dir = os.path.join(contracts_dir, "events")

    if not os.path.isdir(events_dir):
        findings.append(
            Finding(
                file="events",
                field="<directory>",
                rule="missing_directory",
                message=f"Events directory not found: {events_dir}",
            )
        )
        return findings

    format_checker = build_format_checker()
    registry = _load_registry(events_dir)
    valid_schemas: dict[str, tuple[dict[str, Any], Any]] = {}

    # 1. Validate every schema in contracts/events/*.json
    for filename in sorted(os.listdir(events_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(events_dir, filename)
        if not os.path.isfile(filepath):
            continue
        rel_file = f"events/{filename}"

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                contract = json.load(f)
        except json.JSONDecodeError as exc:
            findings.append(
                Finding(
                    file=rel_file,
                    field="<root>",
                    rule="json_parse_error",
                    message=str(exc),
                )
            )
            continue

        validator_cls = validator_for(contract)
        try:
            validator_cls.check_schema(contract)
        except SchemaError as exc:
            findings.append(
                Finding(
                    file=rel_file,
                    field=_format_error_path(exc.path),
                    rule="invalid_schema",
                    message=exc.message,
                )
            )
            continue

        valid_schemas[filename] = (contract, validator_cls)

        if filename in NON_EVENT_FILES:
            continue

        # 2. Enforce event_type / event_version filename convention
        event_type = find_const(contract, "event_type")
        event_version = find_const(contract, "event_version")
        match = FILENAME_RE.match(filename)
        filename_version = match.group("version") if match else None

        if event_type is None:
            findings.append(
                Finding(
                    file=rel_file,
                    field="properties.event_type",
                    rule="missing_event_type",
                    message="Schema must define a const 'event_type'.",
                )
            )
        elif match is None or match.group("event_type") != event_type:
            expected = f"{event_type}.v{event_version or filename_version or '<N>'}.json"
            findings.append(
                Finding(
                    file=rel_file,
                    field="<filename>",
                    rule="event_naming",
                    message=(
                        f"Filename does not match event_type '{event_type}'. "
                        f"Expected '{expected}'."
                    ),
                )
            )

        if event_version is None:
            findings.append(
                Finding(
                    file=rel_file,
                    field="properties.event_version",
                    rule="missing_event_version",
                    message="Schema must define a const 'event_version'.",
                )
            )
        elif filename_version is not None and str(event_version) != filename_version:
            findings.append(
                Finding(
                    file=rel_file,
                    field="properties.event_version",
                    rule="event_version_mismatch",
                    message=(
                        f"Filename version 'v{filename_version}' does not match "
                        f"schema event_version '{event_version}'."
                    ),
                )
            )

    # Load envelope validator for explicit envelope checks
    envelope_validator = None
    if ENVELOPE_FILENAME in valid_schemas:
        env_schema, env_cls = valid_schemas[ENVELOPE_FILENAME]
        envelope_validator = env_cls(
            env_schema,
            registry=registry,
            format_checker=format_checker,
        )
    else:
        findings.append(
            Finding(
                file=f"events/{ENVELOPE_FILENAME}",
                field="<file>",
                rule="missing_envelope",
                message="envelope.v1.json is missing or invalid; cannot validate examples against envelope.",
            )
        )

    # 3. Ensure every event schema has a matching canonical example file
    examples_dir = os.path.join(events_dir, "examples")
    existing_examples = (
        sorted(
            f
            for f in os.listdir(examples_dir)
            if f.endswith(".json") and os.path.isfile(os.path.join(examples_dir, f))
        )
        if os.path.isdir(examples_dir)
        else []
    )
    existing_example_set = set(existing_examples)

    for schema_filename in sorted(valid_schemas):
        if schema_filename in NON_EVENT_FILES:
            continue
        if schema_filename not in existing_example_set:
            findings.append(
                Finding(
                    file=f"events/{schema_filename}",
                    field="<example>",
                    rule="missing_example",
                    message=(
                        f"Missing matching example file 'events/examples/{schema_filename}'."
                    ),
                )
            )

    # 4. Validate every contracts/events/examples/*.json against envelope AND schema
    for ex_filename in existing_examples:
        ex_path = os.path.join(examples_dir, ex_filename)
        rel_ex = f"events/examples/{ex_filename}"

        try:
            with open(ex_path, "r", encoding="utf-8") as f:
                example_payload = json.load(f)
        except json.JSONDecodeError as exc:
            findings.append(
                Finding(
                    file=rel_ex,
                    field="<root>",
                    rule="json_parse_error",
                    message=str(exc),
                )
            )
            continue

        # Check example naming convention
        schema_key = ex_filename
        if ex_filename.endswith(LEGACY_EXAMPLE_SUFFIX):
            canonical_name = ex_filename[: -len(LEGACY_EXAMPLE_SUFFIX)] + ".json"
            findings.append(
                Finding(
                    file=rel_ex,
                    field="<filename>",
                    rule="example_naming",
                    message=(
                        f"Example file uses disallowed '.example.json' suffix. "
                        f"Rename to '{canonical_name}'."
                    ),
                )
            )
            schema_key = canonical_name
        elif ex_filename not in valid_schemas:
            findings.append(
                Finding(
                    file=rel_ex,
                    field="<filename>",
                    rule="orphan_example",
                    message=(
                        f"No matching event schema 'events/{ex_filename}' found."
                    ),
                )
            )

        seen_errors: set[tuple[str, str]] = set()

        # 4a. Validate explicitly against envelope.v1.json
        if envelope_validator is not None:
            findings.extend(
                _validate_payload(
                    envelope_validator,
                    example_payload,
                    rel_ex,
                    rule="envelope_validation",
                    seen_errors=seen_errors,
                )
            )

        # 4b. Validate against the matching event schema
        if schema_key in valid_schemas and schema_key not in NON_EVENT_FILES:
            contract, validator_cls = valid_schemas[schema_key]
            schema_validator = validator_cls(
                contract,
                registry=registry,
                format_checker=format_checker,
            )
            findings.extend(
                _validate_payload(
                    schema_validator,
                    example_payload,
                    rel_ex,
                    rule="example_schema_validation",
                    seen_errors=seen_errors,
                )
            )

    return findings