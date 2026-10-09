
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evidently_drift import (  # noqa: E402
    calculate_logged_evidently_drift,
    load_logged_monitoring_data,
)


print("=" * 60)
print("Evidently Logged Monitoring Demo")
print("=" * 60)

data = load_logged_monitoring_data(
    limit=100
)

print()
print(f"Logged monitoring samples : {len(data)}")

if data.empty:
    print()
    print(
        "RESULT: insufficient monitoring data."
    )
    print(
        "Send Iris prediction requests first."
    )
    raise SystemExit(0)

print()
print("Columns:")
print(list(data.columns))

print()
print("Running Evidently analysis...")

result = calculate_logged_evidently_drift(
    recent_limit=100
)

print()
print("Evidently analysis completed")
print("-" * 60)
print(
    f"Reference samples : "
    f"{result['reference_samples']}"
)
print(
    f"Recent samples    : "
    f"{result['recent_samples']}"
)

print()
print(
    "RESULT: Evidently analyzed "
    "real monitoring.db prediction data."
)

