"""
Event envelope for iot.anomaly.detected.

Pure logic: no Kafka, no InfluxDB, no pydantic.

Envelope fields follow the real inventory-service schema
(services/inventory/app/schemas/events.py):

    event_id, event_type, producer, occurred_at,
    event_version, trace_id, payload

occurred_at is the wall-clock time the event was created.
Simulated/sensor time lives only in the payload.
"""

from datetime import UTC, datetime
import math
import uuid


EVENT_TYPE = "iot.anomaly.detected"
PRODUCER = "anomaly-detection-service"
EVENT_VERSION = "1.0"

CLOSED_BY_VALUES = ("quiet", "shutdown")
DIRECTION_VALUES = ("high", "low")


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


def _validate_top_features(top_features):

    if not isinstance(top_features, (list, tuple)) or not top_features:
        raise ValueError("top_features must be a non-empty list.")

    cleaned = []

    for item in top_features:

        feature = item.get("feature")
        contribution = item.get("contribution")
        direction = item.get("direction")

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

        cleaned.append(
            {
                "feature": str(feature),
                "contribution": float(contribution),
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
    trace_id=None,
    event_id=None,
    occurred_at=None,
):
    """
    Build one iot.anomaly.detected event (one per episode).

    Score convention: higher = more anomalous, score >= threshold
    means anomaly.

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
        "top_features": _validate_top_features(top_features),
        "model_version": str(model_version),
    }

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