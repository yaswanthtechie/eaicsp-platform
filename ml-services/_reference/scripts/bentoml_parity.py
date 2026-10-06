"""
Reusable helpers for BentoML parity testing.

This module is used by:
    - scripts/test_bento_parity.py
    - tests/test_bentoml_parity.py

It provides:
    - deterministic 100-input generation
    - HTTP prediction calls
    - prediction output comparison
"""

from __future__ import annotations

from dataclasses import dataclass
import time

import httpx
import numpy as np
from sklearn.datasets import load_iris


PARITY_SEED = 42


@dataclass
class Prediction:
    """Prediction response returned by a model serving endpoint."""

    prediction: str
    confidence: float
    model_version: str
    probabilities: dict[str, float]
    latency_ms: float


def generate_inputs(count: int = 100) -> list[list[float]]:
    """
    Generate deterministic Iris inputs.

    A seeded sample is used so all three Iris classes are covered.
    The same inputs are produced on every run and are shared by
    the reference server and BentoML server.
    """

    iris = load_iris()

    if count > len(iris.data):
        raise ValueError(
            f"Requested {count} inputs, "
            f"but only {len(iris.data)} Iris samples exist."
        )

    # iris.data is sorted by class, so the first 100 rows would contain
    # no virginica. A seeded sample covers all three classes and is
    # still identical on every run.
    rng = np.random.default_rng(PARITY_SEED)
    indices = np.sort(
        rng.choice(
            len(iris.data),
            size=count,
            replace=False,
        )
    )

    return [
        [float(value) for value in iris.data[index]]
        for index in indices
    ]


def predict(
    client: httpx.Client,
    url: str,
    features: list[float],
) -> Prediction:
    """
    Send one prediction request to a model endpoint.
    """

    payload = {
        "request": {
            "features": features,
        }
    }

    start = time.perf_counter()

    response = client.post(
        url,
        json=payload,
    )

    elapsed_ms = (
        time.perf_counter() - start
    ) * 1000

    response.raise_for_status()

    data = response.json()

    return Prediction(
        prediction=str(data["prediction"]),
        confidence=float(data["confidence"]),
        model_version=str(data["model_version"]),
        probabilities={
            str(name): float(value)
            for name, value in data["probabilities"].items()
        },
        # Client-side round trip, measured the same way for both
        # servers (not each server's own self-reported timing).
        latency_ms=float(elapsed_ms),
    )


def prediction_match(
    reference: Prediction,
    bento: Prediction,
) -> bool:
    """
    Compare prediction outputs.

    Latency and model_version are intentionally ignored because
    they can legitimately differ between the two servers.

    The following must match:
        - prediction
        - confidence
        - probability class names
        - probability values
    """

    if reference.prediction != bento.prediction:
        return False

    if abs(
        reference.confidence - bento.confidence
    ) > 1e-6:
        return False

    if set(reference.probabilities) != set(
        bento.probabilities
    ):
        return False

    for class_name in reference.probabilities:
        if abs(
            reference.probabilities[class_name]
            - bento.probabilities[class_name]
        ) > 1e-6:
            return False

    return True