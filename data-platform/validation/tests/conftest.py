import sys
from pathlib import Path

# 1. Resolve the absolute path to the project root (one level up from the tests/ directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 2. Inject the project root at the front of Python's module search path
sys.path.insert(0, str(PROJECT_ROOT))