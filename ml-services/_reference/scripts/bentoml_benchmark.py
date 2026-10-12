"""
Milestone 1: parity + latency benchmark, reference server vs BentoML container.

Sends the same 100 inputs (all three Iris classes) to both servers,
checks every output matches, and measures client-side latency.

Usage (both servers running, see docs/BENTOML.md):
    python -m scripts.bentoml_benchmark

Writes reports/bentoml_benchmark.json and prints a Markdown table.
"""

import json
import os
from pathlib import Path

import httpx
import numpy as np

from scripts.bentoml_parity import (
    generate_inputs,
    predict,
    prediction_match,
)


REFERENCE_URL = os.getenv(
    "BENTOML_REFERENCE_URL",
    "http://127.0.0.1:3000/predict",
)

BENTO_URL = os.getenv(
    "BENTOML_CONTAINER_URL",
    "http://127.0.0.1:3001/predict",
)

WARMUP_REQUESTS = 10

REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "reports"
    / "bentoml_benchmark.json"
)


def summarise_latencies(latencies_ms):
    """Mean, p50, p95, min and max in milliseconds."""

    values = np.asarray(latencies_ms, dtype=float)

    return {
        "requests": int(len(values)),
        "mean_ms": round(float(values.mean()), 2),
        "p50_ms": round(float(np.percentile(values, 50)), 2),
        "p95_ms": round(float(np.percentile(values, 95)), 2),
        "min_ms": round(float(values.min()), 2),
        "max_ms": round(float(values.max()), 2),
    }


def main():
    """Run parity and latency benchmark."""

    inputs = generate_inputs(100)

    latencies = {
        "reference": [],
        "bentoml": [],
    }

    matches = 0

    with httpx.Client(timeout=30.0) as client:
        # Warm both servers before collecting benchmark measurements.
        for features in inputs[:WARMUP_REQUESTS]:
            predict(client, REFERENCE_URL, features)
            predict(client, BENTO_URL, features)

        # Run the actual 100-request benchmark.
        for features in inputs:
            reference = predict(
                client,
                REFERENCE_URL,
                features,
            )

            bento = predict(
                client,
                BENTO_URL,
                features,
            )

            latencies["reference"].append(
                reference.latency_ms
            )

            latencies["bentoml"].append(
                bento.latency_ms
            )

            matches += prediction_match(
                reference,
                bento,
            )

    report = {
        "inputs": len(inputs),
        "matches": matches,
        "reference": summarise_latencies(
            latencies["reference"]
        ),
        "bentoml": summarise_latencies(
            latencies["bentoml"]
        ),
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(f"Parity: {matches}/{len(inputs)}")

    print(
        "| Server | mean | p50 | p95 | min | max |"
    )

    print(
        "|---|---:|---:|---:|---:|---:|"
    )

    for name in ("reference", "bentoml"):
        summary = report[name]

        print(
            f"| {name} "
            f"| {summary['mean_ms']} "
            f"| {summary['p50_ms']} "
            f"| {summary['p95_ms']} "
            f"| {summary['min_ms']} "
            f"| {summary['max_ms']} |"
        )

    if matches != len(inputs):
        raise SystemExit("Parity check failed.")


if __name__ == "__main__":
    main()