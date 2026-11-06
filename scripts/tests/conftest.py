import sys
from pathlib import Path

# Let tests import `scripts.a5_e2e_smoke` from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))