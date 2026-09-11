import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.validator import SAFE_FUNCTION_REGISTRY
import src.custom_rules as custom_rules

# 1. Resolve the absolute path to the project root (one level up from the tests/ directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. Inject the project root at the front of Python's module search path
sys.path.insert(0, str(PROJECT_ROOT))

CLI_SCRIPT = PROJECT_ROOT / "src" / "validate_cli.py"

def run_cli(*args):
    """Run the CLI in a child process.

    conftest.py's sys.path insert only affects THIS process -- a subprocess
    inherits os.environ, not sys.path -- so PROJECT_ROOT has to be handed over
    via PYTHONPATH or the child dies on `import src`.
    """
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(autouse=True)
def reset_safe_function_registry():
    """
    Prevents Test Pollution: Resets the SAFE_FUNCTION_REGISTRY to its real,
    pristine state before and after every single test runs.
    """
    pristine_registry = {
        "src.custom_rules.check_composite_unique": custom_rules.check_composite_unique,
        "src.custom_rules.check_composite_unique_stream": custom_rules.check_composite_unique_stream,
        "src.custom_rules.check_unparseable_dates": custom_rules.check_unparseable_dates,
        "src.custom_rules.check_outliers": custom_rules.check_outliers,
        "src.custom_rules.check_negatives": custom_rules.check_negatives,
        "src.custom_rules.check_duplicate_rows": custom_rules.check_duplicate_rows,
        "src.custom_rules.standardize_products": custom_rules.standardize_products,
        "src.custom_rules.flag_negatives": custom_rules.flag_negatives,
        "src.custom_rules.standardize_dates": custom_rules.standardize_dates,
        "src.custom_rules.drop_duplicate_rows": custom_rules.drop_duplicate_rows,
    }

    # Reset before the test
    SAFE_FUNCTION_REGISTRY.clear()
    SAFE_FUNCTION_REGISTRY.update(pristine_registry)

    yield  # The test runs here

    # Clean up after the test
    SAFE_FUNCTION_REGISTRY.clear()
    SAFE_FUNCTION_REGISTRY.update(pristine_registry)