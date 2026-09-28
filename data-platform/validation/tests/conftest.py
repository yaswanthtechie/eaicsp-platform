import os
import subprocess
import sys
from pathlib import Path
import pytest

# 1. Resolve the absolute path to the project root (one level up from the tests/ directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. Inject the project root at the front of Python's module search path
sys.path.insert(0, str(PROJECT_ROOT))

CLI_SCRIPT = PROJECT_ROOT / "src" / "validate_cli.py"

def run_cli(*args):
    """Run the CLI in a child process."""
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(autouse=True)
def reset_dynamic_rule_registry():
    """
    Prevents Test Pollution: Clears and reloads the dynamic registry
    before and after every single test runs.
    """
    from src.registry import clear_registry, discover_rules

    # 1. Fully clear both the registry AND the loaded files cache
    clear_registry()

    # 2. Reload the standard rules from your new rules/ directory
    rules_dir = PROJECT_ROOT / "rules"
    discover_rules(rules_dir)

    yield

    # 3. Teardown: clear the registry after the test completes
    clear_registry()


@pytest.fixture(autouse=True)
def clean_environment_variables():
    """
    Prevents terminal environment variables (like VALIDATOR_ENV)
    from leaking into the test suite and altering path resolution.
    """
    env_var = "VALIDATOR_ENV"
    original_value = os.environ.get(env_var)

    # Clear the variable so tests run in a clean, default state
    if env_var in os.environ:
        del os.environ[env_var]

    yield  # Run the test

    # Restore the variable after the test finishes
    if original_value is not None:
        os.environ[env_var] = original_value