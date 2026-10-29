import os
import sys
import json
import argparse
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError, ValidationError


def check_contracts(target_dir):
    events_dir = os.path.join(target_dir, 'events')
    if not os.path.exists(events_dir):
        print(f"Error: Directory {events_dir} not found.")
        sys.exit(1)

    has_errors = False

    for filename in os.listdir(events_dir):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(events_dir, filename)
        with open(filepath, 'r') as f:
            try:
                contract = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[{filename}] JSON Parse Error: {str(e)}")
                has_errors = True
                continue

        # 1. Validate Schema itself
        try:
            Draft7Validator.check_schema(contract)
        except SchemaError as e:
            print(f"[{filename}] Invalid Schema Error at path {list(e.path)}: {e.message}")
            has_errors = True
            continue

        # 2. Check File Name matches event_type and version
        # Assuming filename format: {event_type}_v{version}.json
        # and schema contains these as const or default values at the top level
        event_type = contract.get("properties", {}).get("event_type", {}).get("const", "")
        version = contract.get("properties", {}).get("version", {}).get("const", "")

        expected_filename = f"{event_type}_v{version}.json"
        if filename != expected_filename:
            print(
                f"[{filename}] Naming Error: File name does not match event_type '{event_type}' and version '{version}'. Expected '{expected_filename}'.")
            has_errors = True

        # 3. Validate Examples against Schema and Envelope
        examples = contract.get("examples", [])
        if not examples:
            print(f"[{filename}] Warning: No examples found to validate.")

        validator = Draft7Validator(contract)
        for i, example in enumerate(examples):
            errors = sorted(validator.iter_errors(example), key=lambda e: e.path)
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