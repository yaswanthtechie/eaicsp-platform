import os
import json
import sys
import subprocess
import tempfile
import pytest


@pytest.fixture
def mock_contracts_dir():
    with tempfile.TemporaryDirectory() as base_dir:
        events_dir = os.path.join(base_dir, "events")
        os.makedirs(events_dir)

        # Good Contract
        good_contract = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "event_type": {"const": "user_created"},
                "version": {"const": "1"},
                "payload": {"type": "string"}
            },
            "required": ["event_type", "version", "payload"],
            "examples": [
                {"event_type": "user_created", "version": "1", "payload": "data"}
            ]
        }
        with open(os.path.join(events_dir, "user_created_v1.json"), "w") as f:
            json.dump(good_contract, f)

        # Broken Contract (Filename mismatch & Bad example)
        broken_contract = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "event_type": {"const": "user_updated"},
                "version": {"const": "1"},
                "payload": {"type": "integer"}
            },
            "examples": [
                {"event_type": "user_updated", "version": "1", "payload": "not_an_integer"}  # Fails validation
            ]
        }
        # Deliberately named incorrectly
        with open(os.path.join(events_dir, "wrong_name_v2.json"), "w") as f:
            json.dump(broken_contract, f)

        yield base_dir


def test_contract_check(mock_contracts_dir):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "contract_check.py"))

    # Use sys.executable to ensure compatibility on Windows, macOS, and Linux
    result = subprocess.run(
        [sys.executable, script_path, mock_contracts_dir],
        capture_output=True,
        text=True
    )

    # The script should fail because of the broken contract
    assert result.returncode == 1

    # Verify clear error output naming file and field
    assert "[wrong_name_v2.json] Naming Error" in result.stdout
    assert "Expected 'user_updated_v1.json'" in result.stdout
    assert "[wrong_name_v2.json] Example 0 Validation Error on field 'payload'" in result.stdout
    assert "'not_an_integer' is not of type 'integer'" in result.stdout

    # Ensure good contract passed silently without errors
    assert "[user_created_v1.json]" not in result.stdout