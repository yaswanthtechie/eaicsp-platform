"""
Milestone 3 - incident playbook generation.
"""

import pytest

from src.data import (
    generate_normal_data,
    inject_stock_anomalies,
)
from src.incident_library import (
    INCIDENT_DESCRIPTIONS,
    build_incident_library,
    default_history,
)
from src.playbook import (
    LOW_CONFIDENCE_SIMILARITY,
    PLAYBOOKS,
    SEVERITY_ORDER,
    format_playbook,
    generate_playbook,
    get_playbook,
    list_incident_types,
)
from src.root_cause import FEATURES, match_incident


REQUIRED_KEYS = [
    "title",
    "severity",
    "owner",
    "response_sla_minutes",
    "immediate_actions",
    "investigate",
    "escalate_if",
    "close_when",
]


def _prediction(
    incident_type="stock_anomaly",
    similarity=0.97,
    is_anomaly=True,
    **extra,
):
    return {
        "model": "lof",
        "is_anomaly": is_anomaly,
        "score": 0.5,
        "primary_reason": {"feature": "stock_count", "contribution": 0.99},
        "root_cause_hint": {
            "incident_type": incident_type,
            "similarity": similarity,
            "description": "x",
            "similar_past_incidents": 5,
        },
        "explanation": "Anomaly driven mainly by stock_count.",
        **extra,
    }


def test_every_incident_type_in_the_library_has_a_playbook():
    # Guards against adding an incident type without a response.
    for incident_type in INCIDENT_DESCRIPTIONS:
        assert incident_type in PLAYBOOKS


def test_unknown_and_drift_playbooks_exist():
    assert "unknown" in PLAYBOOKS
    assert "temperature_drift" in PLAYBOOKS


@pytest.mark.parametrize("incident_type", list_incident_types())
def test_every_playbook_is_complete(incident_type):
    playbook = PLAYBOOKS[incident_type]

    for key in REQUIRED_KEYS:
        assert key in playbook

    assert playbook["severity"] in SEVERITY_ORDER
    assert playbook["response_sla_minutes"] > 0

    for key in (
        "immediate_actions",
        "investigate",
        "escalate_if",
        "close_when",
    ):
        assert len(playbook[key]) >= 1


def test_get_playbook_returns_a_copy():
    first = get_playbook("stock_anomaly")
    first["immediate_actions"].append("mutated")

    assert "mutated" not in PLAYBOOKS["stock_anomaly"]["immediate_actions"]


def test_get_playbook_falls_back_to_unknown():
    assert get_playbook("never_heard_of_it")["title"] == (
        PLAYBOOKS["unknown"]["title"]
    )


def test_normal_reading_gets_no_playbook():
    assert generate_playbook(_prediction(is_anomaly=False)) is None


def test_matched_incident_gets_its_own_playbook():
    playbook = generate_playbook(_prediction("temperature_spike"))

    assert playbook["incident_type"] == "temperature_spike"
    assert playbook["title"] == PLAYBOOKS["temperature_spike"]["title"]
    assert playbook["match_confidence"] == "high"
    assert playbook["primary_feature"] == "stock_count"
    assert playbook["model"] == "lof"


def test_unknown_hint_gets_generic_triage():
    playbook = generate_playbook(_prediction("unknown", similarity=0.0))

    assert playbook["incident_type"] == "unknown"
    assert playbook["match_confidence"] is None


def test_missing_hint_gets_generic_triage():
    prediction = _prediction()
    prediction["root_cause_hint"] = None

    assert generate_playbook(prediction)["incident_type"] == "unknown"


def test_low_similarity_is_flagged_and_warns_first():
    playbook = generate_playbook(
        _prediction(similarity=LOW_CONFIDENCE_SIMILARITY - 0.05)
    )

    assert playbook["match_confidence"] == "low"
    assert "Low-confidence" in playbook["immediate_actions"][0]


def test_temporal_drift_takes_priority_over_the_hint():
    playbook = generate_playbook(
        _prediction("stock_anomaly", temporal_drift=True)
    )

    assert playbook["incident_type"] == "temperature_drift"


def test_generating_does_not_mutate_the_templates():
    before = len(PLAYBOOKS["stock_anomaly"]["immediate_actions"])

    generate_playbook(_prediction(similarity=0.5))

    assert len(PLAYBOOKS["stock_anomaly"]["immediate_actions"]) == before


def test_format_playbook_renders_text():
    text = format_playbook(generate_playbook(_prediction()))

    assert "Immediate actions" in text
    assert "STOCK" in text.upper()
    assert format_playbook(None) == "No incident: reading is normal."


def test_real_stock_anomaly_flows_to_the_stock_playbook():
    train = generate_normal_data(n=5000, seed=42)
    library = build_incident_library(train, default_history())

    df = inject_stock_anomalies(
        generate_normal_data(n=5000, seed=456),
        n_anomalies=20,
        seed=1002,
    )

    reading = df[df["is_anomaly"] == 1][FEATURES].iloc[0].to_dict()

    prediction = _prediction()
    prediction["root_cause_hint"] = match_incident(reading, library)

    playbook = generate_playbook(prediction)

    assert playbook["incident_type"] == "stock_anomaly"
    assert playbook["severity"] == "high"