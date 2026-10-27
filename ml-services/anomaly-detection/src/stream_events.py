"""
Event envelope for iot.anomaly.detected (contract: contracts/events/
iot.anomaly.detected.v1.json).

Pure logic: no Kafka, no InfluxDB, no pydantic.

Envelope field names follow the inventory-service schema; event_version is
the integer 1, like every other platform event.

occurred_at is the wall-clock time the event was created.
Simulated/sensor time lives only in the payload.

warehouse_id, severity and message are added when warehouse_id is given
(the consumer always gives it). Severity rule, fixed before any run and
not tuned on results:
    critical: severe and n_flagged >= 10
    high:     severe
    medium:   n_flagged >= 3
    low:      otherwise
"""

from datetime import UTC, datetime
import math
import re
import uuid


EVENT_TYPE = "iot.anomaly.detected"
PRODUCER = "anomaly-detection-service"
EVENT_VERSION = 1

CLOSED_BY_VALUES = ("quiet", "shutdown")
DIRECTION_VALUES = ("high", "low")
SEVERITY_VALUES = ("low", "medium", "high", "critical")

WAREHOUSE_PATTERN = re.compile(r"WH-[A-Z]{3}-[0-9]{2}")

CRITICAL_MIN_FLAGGED = 10
MEDIUM_MIN_FLAGGED = 3
MESSAGE_MAX = 300

FEATURE_LABELS = {
    "temperature": "Temperature",
    "humidity": "Humidity",
    "door_open": "Door-open state",
    "power": "Power draw",
}


def severity_for(severe, n_flagged):

    if severe and n_flagged >= CRITICAL_MIN_FLAGGED:
        return "critical"

    if severe:
        return "high"

    if n_flagged >= MEDIUM_MIN_FLAGGED:
        return "medium"

    return "low"


def to_utc_iso(value):
    """
    Return an ISO-8601 UTC string for a datetime or ISO string.

    A datetime without a timezone is treated as UTC.
    """

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if not isinstance(value, datetime):
        raise TypeError(
            "Expected a datetime or ISO string, "
            f"got {type(value).__name__}."
        )

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat()


def make_episode_id(sensor_id, window_start):
    """Deterministic id: the same episode always gets the same id."""

    return f"{sensor_id}|{to_utc_iso(window_start)}"


def make_message(
    *,
    warehouse_id,
    sensor_id,
    window_start,
    window_end,
    n_flagged,
    top_feature,
):
    """One human-readable line for an alerts panel."""

    label = FEATURE_LABELS.get(top_feature["feature"], top_feature["feature"])
    start = datetime.fromisoformat(to_utc_iso(window_start))
    end = datetime.fromisoformat(to_utc_iso(window_end))

    if n_flagged == 1:
        when = f"1 abnormal reading at {start:%H:%M} UTC"
    else:
        when = (
            f"{n_flagged} abnormal readings between "
            f"{start:%H:%M} and {end:%H:%M} UTC"
        )

    text = (
        f"{label} unusually {top_feature['direction']} at {warehouse_id} "
        f"(sensor {sensor_id}): {when}."
    )

    return text[:MESSAGE_MAX]


def _validate_top_features(top_features):

    if not isinstance(top_features, (list, tuple)) or not top_features:
        raise ValueError("top_features must be a non-empty list.")

    cleaned = []

    for item in top_features:

        feature = item.get("feature")
        contribution = item.get("contribution")
        direction = item.get("direction")
        shap_value = item.get("shap_value")

        if not feature:
            raise ValueError("Each top feature needs a name.")

        if (
            not isinstance(contribution, (int, float))
            or not math.isfinite(contribution)
            or not 0.0 <= contribution <= 1.0
        ):
            raise ValueError(
                "contribution must be a number between 0 and 1."
            )

        if direction not in DIRECTION_VALUES:
            raise ValueError(
                f"direction must be one of {DIRECTION_VALUES}."
            )

        if (
            isinstance(shap_value, bool)
            or not isinstance(shap_value, (int, float))
            or not math.isfinite(shap_value)
        ):
            raise ValueError("shap_value must be a finite number.")

        cleaned.append(
            {
                "feature": str(feature),
                "contribution": float(contribution),
                "shap_value": float(shap_value),
                "direction": direction,
            }
        )

    return cleaned


def build_anomaly_event(
    *,
    sensor_id,
    window_start,
    window_end,
    first_flag_time,
    confirmed_time,
    peak_time,
    peak_score,
    threshold,
    n_flagged,
    closed_by,
    top_features,
    model_version,
    severe=False,
    warehouse_id=None,
    severity=None,
    message=None,
    trace_id=None,
    event_id=None,
    occurred_at=None,
):
    """
    Build one iot.anomaly.detected event (one per episode).

    Score convention: higher = more anomalous, score >= threshold
    means anomaly.

    If warehouse_id is given, the payload also carries warehouse_id,
    severity and message (required by the v1 contract). severity and
    message are derived when not passed.

    event_id and occurred_at can be passed in so tests are
    deterministic. In production leave them as None.
    """

    if not sensor_id:
        raise ValueError("sensor_id is required.")

    start_iso = to_utc_iso(window_start)
    end_iso = to_utc_iso(window_end)

    if datetime.fromisoformat(end_iso) < datetime.fromisoformat(start_iso):
        raise ValueError("window_end must not be before window_start.")

    if closed_by not in CLOSED_BY_VALUES:
        raise ValueError(
            f"closed_by must be one of {CLOSED_BY_VALUES}."
        )

    for name, number in (
        ("peak_score", peak_score),
        ("threshold", threshold),
    ):
        if not math.isfinite(float(number)):
            raise ValueError(f"{name} must be finite.")

    if int(n_flagged) < 1:
        raise ValueError("n_flagged must be at least 1.")

    cleaned_features = _validate_top_features(top_features)

    payload = {
        "episode_id": make_episode_id(sensor_id, window_start),
        "sensor_id": str(sensor_id),
        "window_start": start_iso,
        "window_end": end_iso,
        "first_flag_time": to_utc_iso(first_flag_time),
        "confirmed_time": to_utc_iso(confirmed_time),
        "peak_time": to_utc_iso(peak_time),
        "peak_score": float(peak_score),
        "threshold": float(threshold),
        "n_flagged": int(n_flagged),
        "severe": bool(severe),
        "closed_by": closed_by,
        "top_features": cleaned_features,
        "model_version": str(model_version),
    }

    if warehouse_id is not None:

        if not WAREHOUSE_PATTERN.fullmatch(str(warehouse_id)):
            raise ValueError(f"Bad warehouse_id: {warehouse_id!r}")

        level = severity or severity_for(bool(severe), int(n_flagged))

        if level not in SEVERITY_VALUES:
            raise ValueError(f"severity must be one of {SEVERITY_VALUES}.")

        payload["warehouse_id"] = str(warehouse_id)
        payload["severity"] = level
        payload["message"] = message or make_message(
            warehouse_id=warehouse_id,
            sensor_id=sensor_id,
            window_start=window_start,
            window_end=window_end,
            n_flagged=int(n_flagged),
            top_feature=cleaned_features[0],
        )

    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": EVENT_TYPE,
        "producer": PRODUCER,
        "occurred_at": (
            to_utc_iso(occurred_at)
            if occurred_at is not None
            else datetime.now(UTC).isoformat()
        ),
        "event_version": EVENT_VERSION,
        "trace_id": trace_id,
        "payload": payload,
    }


def event_key(event):
    """Kafka partition key: the sensor, so one sensor stays ordered."""

    return event["payload"]["sensor_id"]