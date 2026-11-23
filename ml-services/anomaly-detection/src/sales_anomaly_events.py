"""
Event envelope for anomaly.sales.detected (contract: contracts/events/
anomaly.sales.detected.v1.json).

Pure logic: no Kafka, no files. One event per sales anomaly incident; the
payload carries the first day of the incident.

occurred_at is the wall-clock time the event was created. The sales day is
in the payload.
"""

import math
import numbers
import re
import uuid
from datetime import UTC, date, datetime

EVENT_TYPE = "anomaly.sales.detected"
PRODUCER = "anomaly-detection-service"
EVENT_VERSION = 1

SEVERITY_VALUES = ("low", "medium", "high")

# Same patterns as the contract: only canonical ids are published.
SKU_PATTERN = re.compile(r"SKU-\d{6}")
WAREHOUSE_PATTERN = re.compile(r"WH-[A-Z]{3}-[0-9]{2}")


def to_date_string(value):
    """Return YYYY-MM-DD for a date, datetime, pandas Timestamp or ISO string."""

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    raise TypeError(f"Expected a date or ISO string, got {type(value).__name__}.")


def anomaly_key(sku_id, warehouse_id, day):
    """
    Identity of one anomaly: the same product, warehouse and day always give
    the same key. The batch job uses it so a re-run publishes nothing new.
    """

    return f"{sku_id}|{warehouse_id}|{to_date_string(day)}"


def _finite_number(name, value, minimum=None):

    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"{name} must be a number.")  # noqa: TRY004 - the contract raises ValueError

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")

    return float(value)


def build_sales_anomaly_event(
    *,
    sku_id,
    warehouse_id,
    date,
    expected_quantity,
    actual_quantity,
    score,
    severity,
    event_id=None,
    occurred_at=None,
):
    """
    Build one anomaly.sales.detected event.

    event_id and occurred_at can be passed in so tests are deterministic.
    In production leave them as None.
    """

    if not SKU_PATTERN.fullmatch(str(sku_id)):
        raise ValueError(f"Bad sku_id: {sku_id!r}")

    if not WAREHOUSE_PATTERN.fullmatch(str(warehouse_id)):
        raise ValueError(f"Bad warehouse_id: {warehouse_id!r}")

    if severity not in SEVERITY_VALUES:
        raise ValueError(f"severity must be one of {SEVERITY_VALUES}.")

    payload = {
        "sku_id": str(sku_id),
        "warehouse_id": str(warehouse_id),
        "date": to_date_string(date),
        "expected_quantity": round(
            _finite_number("expected_quantity", expected_quantity, 0), 2
        ),
        "actual_quantity": round(
            _finite_number("actual_quantity", actual_quantity, 0), 2
        ),
        "score": round(_finite_number("score", score), 3),
        "severity": severity,
    }

    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_type": EVENT_TYPE,
        "event_version": EVENT_VERSION,
        "occurred_at": (
            occurred_at.astimezone(UTC).isoformat()
            if isinstance(occurred_at, datetime)
            else (occurred_at or datetime.now(UTC).isoformat())
        ),
        "producer": PRODUCER,
        "payload": payload,
    }


def event_key(event):
    """Kafka partition key: one product at one warehouse stays ordered."""

    payload = event["payload"]

    return f"{payload['sku_id']}|{payload['warehouse_id']}"
