import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.permissions import ROLE_PERMISSIONS


def main():
    output_path = PROJECT_ROOT / "tests" / "fixtures" / "permissions_v1.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        role: sorted(permissions)
        for role, permissions in ROLE_PERMISSIONS.items()
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")

    print(f"Saved permission snapshot to: {output_path}")


if __name__ == "__main__":
    main()