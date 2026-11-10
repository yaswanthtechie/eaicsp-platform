import os
import re
import sys
import json
import argparse
from jsonschema.validators import validator_for
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

# Foundational files, not real events - excluded from the event_type/filename check.
NON_EVENT_FILES = {"envelope.v1.json", "_template.v1.json"}

# Real convention: "<domain>.<entity>.<action>.v<N>.json" (dots, not underscores).
FILENAME_RE = re.compile(r"^(?P<event_type>.+)\.v(?P<version>\d+)\.json$")


def _find_const(schema, key):
    """event_type/event_version live either at the top level, or nested inside
    an allOf branch when the schema extends envelope.v1.json via $ref."""
    props = schema.get("properties", {})
    if key in props and "const" in props[key]:
        return props[key]["const"]
    for branch in schema.get("allOf", []):
        value = _find_const(branch, key)
        if value is not None:
            return value
    return None


def _load_registry(events_dir):
    """So `$ref: envelope.v1.json` resolves locally instead of as a real URL."""
    registry = Registry()
    for filename in os.listdir(events_dir):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(events_dir, filename)) as f:
            try:
                contents = json.load(f)
            except json.JSONDecodeError:
                continue
        registry = registry.with_resource(filename, Resource.from_contents(contents))
        if "$id" in contents:
            registry = registry.with_resource(contents["$id"], Resource.from_contents(contents))
    return registry


def _load_example(events_dir, filename):
    """Real examples live in events/examples/, under either naming convention
    actually used in this repo: same filename as the schema, or
    '<name-without-.json>.example.json'."""
    examples_dir = os.path.join(events_dir, "examples")

    same_name = os.path.join(examples_dir, filename)
    if os.path.exists(same_name):
        with open(same_name) as f:
            return [json.load(f)]

    dotted_name = os.path.join(examples_dir, filename[:-len(".json")] + ".example.json")
    if os.path.exists(dotted_name):
        with open(dotted_name) as f:
            return [json.load(f)]

    return []


def check_contracts(target_dir):
    events_dir = os.path.join(target_dir, "events")
    if not os.path.exists(events_dir):
        print(f"Error: Directory {events_dir} not found.")
        sys.exit(1)

    has_errors = False
    registry = _load_registry(events_dir)

    for filename in os.listdir(events_dir):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(events_dir, filename)
        with open(filepath, "r") as f:
            try:
                contract = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[{filename}] JSON Parse Error: {str(e)}")
                has_errors = True
                continue

        # 1. Validate the schema itself, using the validator the schema's own
        # $schema asks for (several real schemas declare draft 2020-12, not draft-07).
        ValidatorClass = validator_for(contract)
        try:
            ValidatorClass.check_schema(contract)
        except SchemaError as e:
            print(f"[{filename}] Invalid Schema Error at path {list(e.path)}: {e.message}")
            has_errors = True
            continue

        if filename in NON_EVENT_FILES:
            continue

        # 2. Check file name matches event_type and version.
        event_type = _find_const(contract, "event_type")
        event_version = _find_const(contract, "event_version")

        match = FILENAME_RE.match(filename)
        filename_version = match.group("version") if match else None

        if event_type is None:
            print(f"[{filename}] Naming Error: no const 'event_type' found to check filename against.")
            has_errors = True
        elif match is None or match.group("event_type") != event_type:
            expected_filename = f"{event_type}.v{event_version or filename_version or '<N>'}.json"
            print(
                f"[{filename}] Naming Error: File name does not match event_type '{event_type}'. "
                f"Expected '{expected_filename}'."
            )
            has_errors = True
        elif event_version is not None and str(event_version) != filename_version:
            print(
                f"[{filename}] Naming Error: File name version 'v{filename_version}' does not match "
                f"schema event_version '{event_version}'."
            )
            has_errors = True

        # 3. Validate the real example(s) against this schema + envelope.
        examples = _load_example(events_dir, filename)
        if not examples:
            print(f"[{filename}] Warning: No example found in events/examples/ to validate.")

        validator = ValidatorClass(contract, registry=registry)
        for i, example in enumerate(examples):
            errors = sorted(validator.iter_errors(example), key=lambda e: [str(p) for p in e.path])
            for error in errors:
                field_path = "->".join(str(p) for p in error.path) if error.path else "root"
                print(f"[{filename}] Example {i} Validation Error on field '{field_path}': {error.message}")
                has_errors = True

    return has_errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate event contracts.")
    parser.add_argument("directory", help="Base contracts directory (e.g., contracts/)")
    args = parser.parse_args()

    errors_found = check_contracts(args.directory)
    sys.exit(1 if errors_found else 0)