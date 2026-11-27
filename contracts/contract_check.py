import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from tools.breaking_checker import check_breaking_changes
from tools.event_checker import (
    FILENAME_RE,
    NON_EVENT_FILES,
    _load_registry,
    check_events,
    find_const as _find_const,
)
from tools.models import Finding
from tools.openapi_checker import check_openapi_dir

__all__ = [
    "FILENAME_RE",
    "NON_EVENT_FILES",
    "_find_const",
    "_load_registry",
    "check_contracts",
    "main",
]


def check_contracts(target_dir: str, against: str | None = None) -> list[Finding]:
    """Run event, OpenAPI, and optional breaking-change contract checks."""
    findings: list[Finding] = []
    findings.extend(check_events(target_dir))
    findings.extend(check_openapi_dir(target_dir))
    if against:
        findings.extend(check_breaking_changes(target_dir, against))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate event contracts, OpenAPI specs, and breaking changes."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Base contracts directory (e.g., contracts/ or .)",
    )
    parser.add_argument(
        "--against",
        default=None,
        help="Git ref to diff changed contracts against (e.g., origin/develop)",
    )
    args = parser.parse_args(argv)

    findings = check_contracts(args.directory, against=args.against)
    for finding in findings:
        print(finding.format())

    errors = [f for f in findings if f.severity == "ERROR"]
    if errors:
        print(f"\nContract check FAILED with {len(errors)} error(s).")
        return 1

    print("Contract check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())