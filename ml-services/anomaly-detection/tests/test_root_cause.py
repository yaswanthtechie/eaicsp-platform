"""
M4 - incident-type matching.

The library is built from HISTORY seeds; every check below uses
different TEST seeds, so a pass means the matching generalises
to incidents it has not seen.
"""

from collections import Counter

import pytest

from src.data import (
    generate_correlated_normal_data,
    generate_normal_data,
    inject_combined_anomalies,
    inject_relationship_breaks,
    inject_stock_anomalies,
    inject_temperature_spikes,
)
from src.incident_library import build_incident_library, default_history
from src.root_cause import FEATURES, match_incident


def _match_rate(library, df, expected_type):
    incidents = df[df["is_anomaly"] == 1][FEATURES].to_dict("records")
    got = Counter(match_incident(r, library)["incident_type"] for r in incidents)
    return got[expected_type] / len(incidents)


@pytest.fixture(scope="module")
def library():
    train = generate_normal_data(n=5000, seed=42)
    return build_incident_library(train, default_history())


@pytest.fixture(scope="module")
def test_base():
    return generate_normal_data(n=5000, seed=456)


@pytest.mark.parametrize(
    "incident_type, inject, seed",
    [
        ("temperature_spike", inject_temperature_spikes, 1001),
        ("stock_anomaly", inject_stock_anomalies, 1002),
        ("combined_anomaly", inject_combined_anomalies, 1004),
    ],
)
def test_held_out_incidents_match_their_type(
    library, test_base, incident_type, inject, seed
):
    df = inject(test_base, n_anomalies=20, seed=seed)

    assert _match_rate(library, df, incident_type) >= 0.9


@pytest.mark.parametrize(
    "reading",
    [
        {"temperature": 22.0, "humidity": 45.0, "stock_count": 100},  # stock DROP
        {"temperature": 10.0, "humidity": 45.0, "stock_count": 500},  # temperature DROP
    ],
)
def test_never_seen_patterns_are_unknown(library, reading):
    assert match_incident(reading, library)["incident_type"] == "unknown"


def test_relationship_break_is_recognised_in_correlated_world():
    train = generate_correlated_normal_data(n=5000, seed=42)
    history_base = generate_correlated_normal_data(n=5000, seed=2000)

    library = build_incident_library(
        train,
        {
            "temperature_spike": inject_temperature_spikes(history_base, 50, seed=2001),
            "combined_anomaly": inject_combined_anomalies(history_base, 50, seed=2003),
            "relationship_break": inject_relationship_breaks(history_base, 50, seed=2004),
        },
    )

    test_df = inject_relationship_breaks(
        generate_correlated_normal_data(n=5000, seed=456),
        n_anomalies=20,
        seed=1005,
    )

    assert _match_rate(library, test_df, "relationship_break") >= 0.9