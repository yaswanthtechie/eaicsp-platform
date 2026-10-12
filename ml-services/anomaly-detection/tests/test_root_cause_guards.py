"""M4 - root-cause edge cases: zero spread and a reading at the normal centre."""

import numpy as np

from src.root_cause import FEATURES, match_incident, reading_signature


def _library(std=1.0, residual_std=1.0):
    return {
        "stats": {
            "mean": {f: 10.0 for f in FEATURES},
            "std": {f: std for f in FEATURES},
            "humidity_intercept": 10.0,
            "humidity_slope": 0.0,
            "residual_std": residual_std,
        },
        "signatures": np.array([[1.0, 0.0, 0.0, 0.0]]),
        "labels": ["temperature_spike"],
        "descriptions": {"temperature_spike": "Looks like a temperature spike."},
    }


def test_zero_standard_deviation_does_not_divide_by_zero():
    library = _library(std=0.0, residual_std=0.0)
    reading = {"temperature": 12.0, "humidity": 10.0, "stock_count": 10.0}

    signature = reading_signature(reading, library["stats"])

    assert np.all(np.isfinite(signature))


def test_reading_at_the_normal_centre_returns_unknown_not_none():
    reading = {f: 10.0 for f in FEATURES}

    hint = match_incident(reading, _library())

    assert hint is not None
    assert hint["incident_type"] == "unknown"
    assert hint["similarity"] == 0.0