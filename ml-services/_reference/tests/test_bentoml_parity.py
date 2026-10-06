"""
Milestone 1 - BentoML parity tests.

Unit tests do not require running servers.

The integration test requires:
    - Reference/current server running on port 3000
    - BentoML container running on port 3001
"""

from __future__ import annotations

import os

import httpx
import pytest

from scripts.bentoml_parity import (
    generate_inputs,
    prediction_match,
    predict,
)


REFERENCE_URL = os.getenv(
    "BENTOML_REFERENCE_URL",
    "http://127.0.0.1:3000/predict",
)

BENTO_URL = os.getenv(
    "BENTOML_CONTAINER_URL",
    "http://127.0.0.1:3001/predict",
)


def test_generate_100_deterministic_inputs():
    """Verify that exactly 100 deterministic inputs are generated."""

    inputs = generate_inputs(100)

    assert len(inputs) == 100

    for features in inputs:
        assert len(features) == 4
        assert all(
            isinstance(value, float)
            for value in features
        )

    # Verify deterministic generation.
    inputs_again = generate_inputs(100)

    assert inputs == inputs_again


def test_prediction_match_ignores_latency():
    """
    Verify that prediction comparison ignores latency
    and model version.
    """

    reference = type(
        "Prediction",
        (),
        {
            "prediction": "setosa",
            "confidence": 1.0,
            "model_version": "1",
            "probabilities": {
                "setosa": 1.0,
                "versicolor": 0.0,
                "virginica": 0.0,
            },
            "latency_ms": 10.0,
        },
    )()

    bento = type(
        "Prediction",
        (),
        {
            "prediction": "setosa",
            "confidence": 1.0,
            "model_version": "local",
            "probabilities": {
                "setosa": 1.0,
                "versicolor": 0.0,
                "virginica": 0.0,
            },
            "latency_ms": 100.0,
        },
    )()

    assert prediction_match(
        reference,
        bento,
    )


@pytest.mark.integration
def test_reference_and_bento_have_parity():
    """
    Compare the reference server and BentoML server
    using the same 100 inputs.
    """

    inputs = generate_inputs(100)

    matches = 0

    with httpx.Client(timeout=30.0) as client:

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

            if prediction_match(
                reference,
                bento,
            ):
                matches += 1

    parity = matches / len(inputs)

    print()
    print("=" * 60)
    print("BentoML 100-Input Parity Test")
    print("=" * 60)
    print(f"Total inputs       : {len(inputs)}")
    print(
        f"Prediction matches : "
        f"{matches}/{len(inputs)}"
    )
    print(
        f"Prediction parity  : "
        f"{parity * 100:.2f}%"
    )
    print("=" * 60)

    assert matches == 100


# ------------------------------------------------------------------
# Fix 8b: Parity inputs cover all three Iris classes
# ------------------------------------------------------------------


def test_parity_inputs_cover_all_three_classes():
    from sklearn.datasets import load_iris

    iris = load_iris()

    row_to_class = {
        tuple(map(float, row)): int(target)
        for row, target in zip(
            iris.data,
            iris.target,
        )
    }

    classes = {
        row_to_class[tuple(features)]
        for features in generate_inputs(100)
    }

    assert classes == {0, 1, 2}


def test_latency_summary():
    from scripts.bentoml_benchmark import summarise_latencies

    summary = summarise_latencies(
        [10.0, 20.0, 30.0, 40.0]
    )

    assert summary["requests"] == 4
    assert summary["mean_ms"] == 25.0
    assert summary["min_ms"] == 10.0
    assert summary["max_ms"] == 40.0