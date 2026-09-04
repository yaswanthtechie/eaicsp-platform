import os
import subprocess
import sys
from pathlib import Path

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