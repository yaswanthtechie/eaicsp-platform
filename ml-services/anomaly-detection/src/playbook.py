"""
Milestone 3 - incident playbook generation.

INFERENCE SIDE ONLY. Pure Python: no model, SHAP or file access, so it
is safe to import anywhere (predict.py, app.py, scripts).

Given a prediction result (from predict(), adaptive_predict() or
adaptive_engine_predict()), suggest a specific response playbook:

    anomaly type X detected  ->  playbook for X

The incident type comes from the M4 root_cause_hint
(src/root_cause.match_incident). Temporal drift reported by the
adaptive engine takes priority, because drift is handled differently
from a point anomaly. Anything unrecognised gets a generic triage
playbook rather than a guess.

Usage:

    from src.playbook import generate_playbook

    playbook = generate_playbook(prediction)   # None if not anomalous
"""

import copy


# Below this root-cause similarity the match is flagged low-confidence.
LOW_CONFIDENCE_SIMILARITY = 0.90

SEVERITY_ORDER = ["medium", "high", "critical"]


PLAYBOOKS = {
    "temperature_spike": {
        "title": "Temperature spike response",
        "severity": "critical",
        "owner": "Facilities / Cold-chain operations",
        "response_sla_minutes": 15,
        "immediate_actions": [
            "Confirm the reading on a second sensor or handheld probe.",
            "Check that doors and dock bays are closed.",
            "Check HVAC / cooling unit status and alarms.",
            "Move temperature-sensitive stock to a unit in range if the "
            "reading is confirmed.",
        ],
        "investigate": [
            "Review the door-open log for the last hour.",
            "Check cooling unit maintenance history.",
            "Compare with neighbouring sensors to see whether the spike "
            "is local or zone-wide.",
        ],
        "escalate_if": [
            "Temperature has not returned to range within 30 minutes.",
            "More than one zone shows a spike.",
        ],
        "close_when": [
            "Temperature is back in range and stable for 30 minutes.",
            "Affected stock has been assessed and logged.",
        ],
    },
    "stock_anomaly": {
        "title": "Stock-count anomaly response",
        "severity": "high",
        "owner": "Inventory control",
        "response_sla_minutes": 60,
        "immediate_actions": [
            "Check for an unlogged bulk receipt or transfer.",
            "Check the scanner for a double-count or duplicate scan.",
            "Hold related orders if the count affects fulfilment.",
        ],
        "investigate": [
            "Compare the count with the last cycle count.",
            "Review receiving and dispatch logs around the reading.",
            "Check whether other SKUs in the same location are off.",
        ],
        "escalate_if": [
            "A physical recount does not match the system count.",
            "The pattern repeats within the same shift.",
        ],
        "close_when": [
            "System count matches a physical recount, or an adjustment "
            "is approved and logged.",
        ],
    },
    "combined_anomaly": {
        "title": "Combined heat and moisture response",
        "severity": "critical",
        "owner": "Facilities / Warehouse operations",
        "response_sla_minutes": 15,
        "immediate_actions": [
            "Check for a leak, condensation or standing water.",
            "Check ventilation and dehumidifier status.",
            "Inspect moisture-sensitive stock in the affected zone.",
        ],
        "investigate": [
            "Check roof, pipe and cooling-unit drainage.",
            "Review HVAC alarms and recent maintenance.",
            "Compare with neighbouring sensors to find the source.",
        ],
        "escalate_if": [
            "Visible water or damaged stock is found.",
            "Humidity and temperature are still elevated after 30 minutes.",
        ],
        "close_when": [
            "Temperature and humidity are back in range and stable.",
            "Affected stock has been inspected and logged.",
        ],
    },
    "relationship_break": {
        "title": "Sensor relationship-break response",
        "severity": "medium",
        "owner": "Maintenance / Instrumentation",
        "response_sla_minutes": 120,
        "immediate_actions": [
            "Check the humidity sensor against a calibrated reference.",
            "Check for a local moisture source near the sensor.",
        ],
        "investigate": [
            "Review sensor calibration date and drift history.",
            "Compare humidity with neighbouring sensors at the same "
            "temperature.",
        ],
        "escalate_if": [
            "The reference reading confirms the real humidity is off.",
            "The same sensor flags repeatedly.",
        ],
        "close_when": [
            "Sensor is recalibrated or replaced, or the moisture source "
            "is removed.",
        ],
    },
    "temperature_drift": {
        "title": "Sustained temperature drift response",
        "severity": "high",
        "owner": "Facilities / Cold-chain operations",
        "response_sla_minutes": 60,
        "immediate_actions": [
            "Confirm the trend on a second sensor.",
            "Check the cooling unit setpoint and compressor status.",
            "Do NOT treat the new temperature as the new normal; the "
            "adaptive threshold is frozen while drift is active.",
        ],
        "investigate": [
            "Check for a slow refrigerant leak, blocked airflow or a "
            "failing sensor.",
            "Review how long the drift has been under way and its rate.",
        ],
        "escalate_if": [
            "The drift continues after the first corrective action.",
            "Projected temperature will leave the allowed range within "
            "the shift.",
        ],
        "close_when": [
            "Temperature has returned to baseline and the engine has "
            "recovered from drift lock.",
        ],
    },
    "unknown": {
        "title": "General anomaly triage",
        "severity": "medium",
        "owner": "On-call operations",
        "response_sla_minutes": 60,
        "immediate_actions": [
            "Verify the reading is real (sensor fault vs real event).",
            "Check the primary contributing feature in the explanation.",
        ],
        "investigate": [
            "Compare the reading with recent history for this sensor.",
            "Check whether other sensors in the zone are also abnormal.",
        ],
        "escalate_if": [
            "The anomaly repeats or spreads to other sensors.",
        ],
        "close_when": [
            "Root cause is identified and logged. Consider adding it as "
            "a new labelled incident type.",
        ],
    },
}


def list_incident_types():
    """Incident types that have a dedicated playbook."""

    return sorted(PLAYBOOKS)


def get_playbook(incident_type):
    """
    Return a copy of the playbook template for an incident type.

    Unrecognised types fall back to the generic triage playbook.
    """

    template = PLAYBOOKS.get(str(incident_type), PLAYBOOKS["unknown"])

    return copy.deepcopy(template)


def _incident_type(prediction):
    """Choose the playbook key for a prediction."""

    if prediction.get("temporal_drift"):
        return "temperature_drift"

    hint = prediction.get("root_cause_hint")

    if hint and hint.get("incident_type") in PLAYBOOKS:
        return hint["incident_type"]

    return "unknown"


def generate_playbook(prediction):
    """
    Build a response playbook for one prediction result.

    Returns None when the reading is not an anomaly. Otherwise returns
    the playbook template plus context from the prediction.
    """

    if not prediction.get("is_anomaly"):
        return None

    incident_type = _incident_type(prediction)

    playbook = get_playbook(incident_type)

    hint = prediction.get("root_cause_hint") or {}
    similarity = hint.get("similarity")

    primary = prediction.get("primary_reason") or {}

    if incident_type in ("unknown", "temperature_drift"):
        match_confidence = None
    elif similarity is not None and similarity < LOW_CONFIDENCE_SIMILARITY:
        match_confidence = "low"
    else:
        match_confidence = "high"

    playbook.update(
        {
            "incident_type": incident_type,
            "match_confidence": match_confidence,
            "similarity": similarity,
            "primary_feature": primary.get("feature"),
            "model": prediction.get("model"),
            "score": prediction.get("score"),
            "explanation": prediction.get("explanation"),
        }
    )

    if match_confidence == "low":
        playbook["immediate_actions"].insert(
            0,
            "Low-confidence match: verify the incident type before "
            "acting on the steps below.",
        )

    return playbook


def format_playbook(playbook):
    """Plain-text rendering for logs, tickets or the console."""

    if playbook is None:
        return "No incident: reading is normal."

    lines = [
        f"{playbook['title']}  [{playbook['severity'].upper()}]",
        f"Owner: {playbook['owner']}  |  "
        f"Respond within {playbook['response_sla_minutes']} min",
        f"Type: {playbook['incident_type']}  "
        f"(confidence: {playbook['match_confidence']})",
    ]

    for heading, key in (
        ("Immediate actions", "immediate_actions"),
        ("Investigate", "investigate"),
        ("Escalate if", "escalate_if"),
        ("Close when", "close_when"),
    ):
        lines.append("")
        lines.append(f"{heading}:")
        lines.extend(f"  - {item}" for item in playbook[key])

    return "\n".join(lines)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.predict import predict

    samples = {
        "temperature_spike": {
            "temperature": 34.0, "humidity": 45.0, "stock_count": 500,
        },
        "stock_anomaly": {
            "temperature": 22.0, "humidity": 45.0, "stock_count": 850,
        },
        "combined_anomaly": {
            "temperature": 30.0, "humidity": 68.0, "stock_count": 500,
        },
    }

    generated = {}

    for name, reading in samples.items():
        result = predict(reading, "lof")
        playbook = generate_playbook(result)

        print("=" * 60)
        print(f"Sample: {name}  is_anomaly={result['is_anomaly']}")
        print(format_playbook(playbook))

        generated[name] = playbook

    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "incident_playbook_examples.json", "w") as file:
        json.dump(generated, file, indent=2)

    print("\nSaved: output/incident_playbook_examples.json")