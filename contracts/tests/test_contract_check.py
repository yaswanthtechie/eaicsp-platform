import os
import json
import sys
import subprocess
import tempfile
import pytest

REPO_CONTRACTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


def test_contract_check_passes_on_the_real_contracts_directory():
    """Regression guard: contract_check.py must actually validate this repo's
    real contracts/events/ files, not just an invented schema shape."""
    script_path = os.path.join(REPO_CONTRACTS_DIR, "contract_check.py")

    result = subprocess.run(
        [sys.executable, script_path, REPO_CONTRACTS_DIR],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"contract_check.py found problems in the real contracts:\n{result.stdout}"
    )


@pytest.fixture
def mock_contracts_dir():
    with tempfile.TemporaryDirectory() as base_dir:
        events_dir = os.path.join(base_dir, "events")
        examples_dir = os.path.join(events_dir, "examples")
        os.makedirs(examples_dir)

        # Good contract, using this repo's real conventions: dotted
        # "<domain>.<entity>.<action>.v<N>.json" filename, event_type/event_version
        # as top-level const properties, example in events/examples/.
        good_contract = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "event_type": {"const": "user.account.created"},
                "event_version": {"const": 1},
                "payload": {"type": "object"},
            },
            "required": ["event_type", "event_version", "payload"],
        }
        with open(os.path.join(events_dir, "user.account.created.v1.json"), "w") as f:
            json.dump(good_contract, f)
        with open(os.path.join(examples_dir, "user.account.created.v1.json"), "w") as f:
            json.dump(
                {"event_type": "user.account.created", "event_version": 1, "payload": {}},
                f,
            )

        # Broken contract: wrong filename, and an example that fails its own schema.
        broken_contract = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "event_type": {"const": "user.account.updated"},
                "event_version": {"const": 1},
                "payload": {"type": "integer"},
            },
            "required": ["event_type", "event_version", "payload"],
        }
        with open(os.path.join(events_dir, "wrong_name.v2.json"), "w") as f:
            json.dump(broken_contract, f)
        with open(os.path.join(examples_dir, "wrong_name.v2.json"), "w") as f:
            json.dump(
                {"event_type": "user.account.updated", "event_version": 1, "payload": "not_an_integer"},
                f,
            )

        yield base_dir


def test_contract_check(mock_contracts_dir):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "contract_check.py"))

    result = subprocess.run(
        [sys.executable, script_path, mock_contracts_dir],
        capture_output=True,
        text=True,
    )

    # Fails because of the broken contract's bad name and bad example.
    assert result.returncode == 1

    assert "[wrong_name.v2.json] Naming Error" in result.stdout
    assert "[wrong_name.v2.json] Example 0 Validation Error on field 'payload'" in result.stdout
    assert "'not_an_integer' is not of type 'integer'" in result.stdout

    # The good contract passed silently.
    assert "[user.account.created.v1.json]" not in result.stdout