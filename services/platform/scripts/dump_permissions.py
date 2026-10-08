"""
Write the FROZEN v1 permission baseline.

This file is the backward-compatibility contract for the 8 original roles.
It must only be (re)generated deliberately, so the script refuses to
overwrite it unless --force is passed.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.permissions import ROLE_PERMISSIONS  # noqa: E402

V1_ROLES = (
    "ceo",
    "vp_operations",
    "procurement_manager",
    "logistics_manager",
    "compliance_officer",
    "warehouse_manager",
    "analyst",
    "supplier",
)

def main() -> int:
    output_path = PROJECT_ROOT / "tests" / "fixtures" / "permissions_v1.json"

    if output_path.exists() and "--force" not in sys.argv:
        print(
            f"{output_path} already exists. It is the frozen v1 baseline; "
            "refusing to overwrite it. Use --force only if you really intend "
            "to change the v1 contract."
        )
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {role: sorted(ROLE_PERMISSIONS[role]) for role in V1_ROLES}

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")

    print(f"Saved v1 permission snapshot to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())