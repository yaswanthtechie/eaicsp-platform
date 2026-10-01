
"""
Milestone 2 Evidently drift demonstration.

Runs:
1. Normal reference vs recent data
2. Deliberately shifted data
3. Generates the Evidently HTML report
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the project root to Python's import path so that
# `python scripts\evidently_drift_demo.py` works.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evidently_drift import (  # noqa: E402
    DEFAULT_REPORT_PATH,
    calculate_evidently_drift,
    create_recent_inputs,
    create_shifted_inputs,
    generate_drift_report,
    load_reference_inputs,
)


def main() -> None:
    print("=" * 60)
    print("Evidently Drift Detection Demo")
    print("=" * 60)

    reference = load_reference_inputs()

    recent = create_recent_inputs(
        reference,
        sample_count=100,
    )

    shifted = create_shifted_inputs(
        reference,
        shift=2.0,
    )

    print()
    print("Reference samples :", len(reference))
    print("Recent samples    :", len(recent))
    print("Shifted samples   :", len(shifted))

    print()
    print("Generating Evidently report...")

    result = generate_drift_report(
        reference_data=reference,
        recent_data=shifted,
        report_path=DEFAULT_REPORT_PATH,
    )

    print()
    print("Report generated")
    print("-" * 60)
    print("Report path :", result["report_path"])

    print()
    print("Running Evidently drift analysis...")

    drift_result = calculate_evidently_drift(
        reference_data=reference,
        recent_data=shifted,
    )

    print()
    print("Evidently analysis completed")
    print("-" * 60)
    print(
        "Reference samples :",
        drift_result["reference_samples"],
    )
    print(
        "Recent samples    :",
        drift_result["recent_samples"],
    )

    print()
    print("RESULT: deliberate shifted-data scenario executed.")
    print("Open the HTML report to inspect the detected drift.")


if __name__ == "__main__":
    main()

