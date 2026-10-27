
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data-platform" / "out"
loaders = sorted((ROOT / "services").glob("*/scripts/load_seed.py"))

if not loaders:
    print("No service seed loaders found; generated data only.")
    raise SystemExit(0)

for loader in loaders:
    print(f"==> {loader.relative_to(ROOT)}", flush=True)
    subprocess.run(
        [
            sys.executable,
            str(loader),
            "--data-dir",
            str(DATA_DIR),
        ],
        cwd=ROOT,
        check=True,
    )
