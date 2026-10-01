"""Pipeline event publication (R12-13 M3) using a PostgreSQL outbox.

Contract (see round doc "Standard event envelope"):
    {event_id, event_type, event_version, occurred_at, producer, payload}
Topic name == event_type. Timestamps are UTC.

Delivery model
--------------
Persist first, publish second. The event row is written to ``etl_event_outbox``
before any Kafka I/O, so:

* a Kafka outage can never fail or roll back a successful load;
* an unpublished event stays ``PENDING`` and is retried by the
  ``etl_event_outbox_retry`` DAG;
* delivery is *at-least-once*: a crash between "Kafka acked" and "row marked
  PUBLISHED" re-sends the event. Consumers must de-duplicate on ``event_id``.

Nothing in this module raises into the caller. Every failure is logged and
reported through the returned dict.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from database import get_engine

logger = logging.getLogger(__name__)

EVENT_VERSION = 1
PRODUCER_NAME = "etl"
EVENT_COMPLETED = "data.pipeline.completed"
EVENT_FAILED = "data.pipeline.failed"

_PG_OUTBOX_DDL = """
CREATE TABLE IF NOT EXISTS etl_event_outbox (
    event_id UUID PRIMARY KEY,
    run_id BIGINT,
    event_type VARCHAR(100) NOT NULL,
    event_version INTEGER NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    producer VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
)
"""

# Only used by the Docker-free unit tests (SQLite has no NOW()/JSONB).
_SQLITE_OUTBOX_DDL = """
CREATE TABLE IF NOT EXISTS etl_event_outbox (
    event_id TEXT PRIMARY KEY,
    run_id INTEGER,
    event_type TEXT NOT NULL,
    event_version INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    producer TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT
)
"""


def _iso_utc(value) -> str:
    """Render a datetime (or ISO string) as an ISO-8601 UTC string ending in Z."""
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_envelope(event_type, payload, event_id=None, occurred_at=None) -> dict:
    """Build the standard event envelope. Pure function, no I/O."""
    return {
        "event_id": str(event_id or uuid.uuid4()),
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "occurred_at": _iso_utc(occurred_at or datetime.now(timezone.utc)),
        "producer": PRODUCER_NAME,
        "payload": payload or {},
    }


def ensure_outbox():
    engine = get_engine()
    ddl = _SQLITE_OUTBOX_DDL if engine.dialect.name == "sqlite" else _PG_OUTBOX_DDL
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _timeout_ms() -> int:
    return int(float(os.getenv("KAFKA_PUBLISH_TIMEOUT_S", "5")) * 1000)


def _producer():
    """Create a KafkaProducer with short, bounded timeouts.

    Imported lazily so that merely importing this module (e.g. when Airflow
    parses the DAG) never depends on the Kafka client being healthy.
    """
    from kafka import KafkaProducer

    servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
    t = _timeout_ms()
    return KafkaProducer(
        bootstrap_servers=[s.strip() for s in servers if s.strip()],
        acks="all",
        retries=3,
        linger_ms=5,
        api_version_auto_timeout_ms=t,
        request_timeout_ms=t,
        max_block_ms=t,
        key_serializer=lambda v: v.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v, separators=(",", ":")).encode("utf-8"),
    )


def _send(producer, envelope: dict):
    future = producer.send(
        envelope["event_type"], key=envelope["event_id"], value=envelope
    )
    future.get(timeout=_timeout_ms() / 1000)


def _close(producer):
    try:
        producer.flush(timeout=5)
        producer.close(timeout=5)
    except Exception:  # noqa: BLE001 - closing must never mask the real result
        logger.debug("Ignoring error while closing Kafka producer", exc_info=True)


def _mark_published(event_id):
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE etl_event_outbox
            SET status='PUBLISHED', published_at=CURRENT_TIMESTAMP, last_error=NULL
            WHERE event_id=:event_id
        """), {"event_id": str(event_id)})


def _mark_failed(event_id, error):
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE etl_event_outbox
            SET attempts=attempts+1, last_attempt_at=CURRENT_TIMESTAMP, last_error=:error
            WHERE event_id=:event_id
        """), {"event_id": str(event_id), "error": str(error)[:4000]})


def queue_and_publish(event_type, run_id, payload) -> dict:
    """Persist the event, then try to publish it. Never raises."""
    envelope = build_envelope(event_type, payload)
    event_id = envelope["event_id"]

    try:
        ensure_outbox()
        with get_engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO etl_event_outbox
                (event_id, run_id, event_type, event_version, occurred_at, producer, payload)
                VALUES (:event_id, :run_id, :event_type, :event_version,
                        :occurred_at, :producer, :payload)
            """), {
                "event_id": event_id,
                "run_id": run_id,
                "event_type": event_type,
                "event_version": EVENT_VERSION,
                "occurred_at": envelope["occurred_at"],
                "producer": PRODUCER_NAME,
                "payload": json.dumps(envelope["payload"]),
            })
    except Exception as exc:  # noqa: BLE001
        # The outbox itself is unavailable. The load already succeeded and must
        # stay successful; this event cannot be retried later, so log loudly.
        logger.error("EVENT LOST: could not persist %s for run %s: %s",
                     event_type, run_id, exc)
        return {"event_id": event_id, "published": False, "persisted": False,
                "error": f"outbox unavailable: {exc}"}

    producer = None
    try:
        producer = _producer()
        _send(producer, envelope)
        _mark_published(event_id)
        return {"event_id": event_id, "published": True, "persisted": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kafka publish of %s failed, left PENDING for retry: %s",
                       event_id, exc)
        try:
            _mark_failed(event_id, f"{type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            logger.exception("Could not record publish failure for %s", event_id)
        return {"event_id": event_id, "published": False, "persisted": True,
                "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if producer is not None:
            _close(producer)


def retry_pending_events(limit=100) -> dict:
    """Retry PENDING events with ONE producer and a circuit breaker.

    The first failure stops the batch: when Kafka is down we pay one timeout,
    not one per pending event. Remaining events stay PENDING, untouched.
    """
    results = {"attempted": 0, "published": 0, "failed": 0, "skipped": 0}
    ensure_outbox()
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT event_id, event_type, event_version, occurred_at, producer, payload
            FROM etl_event_outbox
            WHERE status='PENDING'
            ORDER BY created_at
            LIMIT :limit
        """), {"limit": limit}).mappings().all()
    if not rows:
        return results

    try:
        producer = _producer()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kafka unavailable, %d events stay PENDING: %s", len(rows), exc)
        _mark_failed(rows[0]["event_id"], f"{type(exc).__name__}: {exc}")
        results["attempted"] = 1
        results["failed"] = 1
        results["skipped"] = len(rows) - 1
        return results

    try:
        for i, row in enumerate(rows):
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            envelope = {
                "event_id": str(row["event_id"]),
                "event_type": row["event_type"],
                "event_version": row["event_version"],
                "occurred_at": _iso_utc(row["occurred_at"]),
                "producer": row["producer"],
                "payload": payload,
            }
            results["attempted"] += 1
            try:
                _send(producer, envelope)
                _mark_published(row["event_id"])
                results["published"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Retry of %s failed, stopping batch: %s",
                               envelope["event_id"], exc)
                _mark_failed(row["event_id"], f"{type(exc).__name__}: {exc}")
                results["failed"] += 1
                results["skipped"] = len(rows) - i - 1
                break
    finally:
        _close(producer)
    return results
