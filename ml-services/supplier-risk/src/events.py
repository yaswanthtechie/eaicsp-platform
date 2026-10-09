"""
Event contract and publishing abstractions for Supplier Risk score-change events.

Defines the standard event envelope, payload schema, tier mapping,
and testable publisher abstractions for 'supplierrisk.score.changed'.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Set
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# Standard Event Constants
EVENT_TYPE: str = "supplierrisk.score.changed"
EVENT_VERSION: int = 1
TOPIC: str = EVENT_TYPE
DEFAULT_PRODUCER: str = "supplier-risk-service"

# Valid 3-tier operational event classifications
VALID_EVENT_TIERS: Set[str] = {"low", "medium", "high"}


def map_tier_to_event_tier(tier: str) -> str:
    """
    Map internal 4-tier risk classification to the event's standard 3-tier contract.

    Contract mappings:
    - 'Low' / 'low' -> 'low'
    - 'Medium' / 'medium' -> 'medium'
    - 'High' / 'high' -> 'high'
    - 'Critical' / 'critical' -> 'high'

    Preserves existing scoring outputs while ensuring downstream systems receive
    one of the three standardized tiers ('low', 'medium', 'high').

    Raises:
        ValueError: If tier cannot be mapped to a known event tier.
    """
    if not isinstance(tier, str):
        raise ValueError(f"Risk tier must be a string, got {type(tier).__name__}: {tier}")

    cleaned = tier.strip().lower()
    if cleaned == "low":
        return "low"
    if cleaned == "medium":
        return "medium"
    if cleaned in ("high", "critical"):
        return "high"

    raise ValueError(
        f"Invalid risk tier '{tier}'. Expected 'Low', 'Medium', 'High', or 'Critical'."
    )


class SupportingArticle(BaseModel):
    """Schema for individual supporting articles contributing to risk score."""

    model_config = ConfigDict(extra="ignore")

    headline: str
    date: Optional[str] = None
    score: Optional[float] = None


class ScoreChangedPayload(BaseModel):
    """Payload schema for supplierrisk.score.changed events."""

    model_config = ConfigDict(extra="ignore")

    supplier: str
    previous_tier: str
    new_tier: str
    risk_score: float
    supporting_articles: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_count: int
    explanation: str

    @field_validator("previous_tier", "new_tier")
    @classmethod
    def validate_event_tier(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_EVENT_TIERS:
            # Attempt to map if passed as e.g. "Critical"
            mapped = map_tier_to_event_tier(v)
            return mapped
        return clean


class ScoreChangedEvent(BaseModel):
    """
    Standard event envelope conforming to repository architectural patterns
    (as in services/compliance and services/inventory).
    """

    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = EVENT_TYPE
    event_version: int = EVENT_VERSION
    occurred_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    producer: str = DEFAULT_PRODUCER
    payload: ScoreChangedPayload


def format_supporting_articles(
    articles: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Format supporting articles list to ensure standard dictionary fields
    ('headline', 'date', 'score' where available).
    """
    if not articles:
        return []

    formatted: List[Dict[str, Any]] = []
    seen = set()

    for item in articles:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).strip()
        if not headline:
            continue

        date_val = item.get("date")
        date_str = str(date_val).strip() if date_val is not None else None

        score_val = item.get("score")
        score_float = round(float(score_val), 2) if score_val is not None else None

        key = (headline.lower(), date_str)
        if key in seen:
            continue
        seen.add(key)

        article_dict: Dict[str, Any] = {"headline": headline}
        if date_str:
            article_dict["date"] = date_str
        if score_float is not None:
            article_dict["score"] = score_float

        formatted.append(article_dict)

    return formatted


def build_score_changed_event(
    *,
    supplier: str,
    previous_tier: str,
    new_tier: str,
    risk_score: float,
    supporting_articles: Optional[List[Dict[str, Any]]] = None,
    evidence_count: Optional[int] = None,
    explanation: Optional[str] = None,
    occurred_at: Optional[str | datetime] = None,
    event_id: Optional[str] = None,
    event_version: int = EVENT_VERSION,
    producer: str = DEFAULT_PRODUCER,
) -> Dict[str, Any]:
    """
    Build a dictionary representation of a 'supplierrisk.score.changed' event
    using the repository's standard envelope fields.

    Args:
        supplier: Name of the supplier.
        previous_tier: Previous accepted tier ('low', 'medium', 'high', or internal tiers).
        new_tier: New accepted tier ('low', 'medium', 'high', or internal tiers).
        risk_score: Current continuous risk score (0.0 to 100.0).
        supporting_articles: Supporting articles containing headline, date, score.
        evidence_count: Distinct count of supporting evidence (defaults to count of articles).
        explanation: Human-readable narrative explanation.
        occurred_at: ISO timestamp or datetime object (defaults to current UTC time).
        event_id: UUID string (defaults to new UUID4).
        event_version: Schema version number (default 1).
        producer: Service identifier (default 'supplier-risk-service').

    Returns:
        Dict[str, Any] representing the full event envelope and payload.
    """
    mapped_previous = map_tier_to_event_tier(previous_tier)
    mapped_new = map_tier_to_event_tier(new_tier)
    clean_supplier = str(supplier).strip()

    clean_articles = format_supporting_articles(supporting_articles)
    actual_evidence_count = (
        evidence_count if evidence_count is not None else len(clean_articles)
    )

    if explanation is None or not explanation.strip():
        explanation = (
            f"Supplier '{clean_supplier}' risk tier transitioned from '{mapped_previous}' "
            f"to '{mapped_new}' with accepted score {risk_score:.2f} "
            f"backed by {actual_evidence_count} supporting article(s)."
        )

    # Determine timezone-aware UTC ISO timestamp
    if occurred_at is None:
        occurred_at_str = datetime.now(timezone.utc).isoformat()
    elif isinstance(occurred_at, datetime):
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        occurred_at_str = occurred_at.isoformat()
    else:
        occurred_at_str = str(occurred_at).strip()

    actual_event_id = str(event_id) if event_id else str(uuid.uuid4())

    payload = ScoreChangedPayload(
        supplier=clean_supplier,
        previous_tier=mapped_previous,
        new_tier=mapped_new,
        risk_score=round(float(risk_score), 2),
        supporting_articles=clean_articles,
        evidence_count=actual_evidence_count,
        explanation=explanation.strip(),
    )

    envelope = ScoreChangedEvent(
        event_id=actual_event_id,
        event_type=EVENT_TYPE,
        event_version=event_version,
        occurred_at=occurred_at_str,
        producer=producer,
        payload=payload,
    )

    return envelope.model_dump()


# ------------------------------------------------------------------
# Publisher Abstraction
# ------------------------------------------------------------------


class EventPublisher(ABC):
    """Abstract base class for event publishers."""

    @abstractmethod
    def publish(
        self,
        event: Dict[str, Any],
        topic: str = TOPIC,
        key: Optional[str] = None,
    ) -> bool:
        """Publish an event to the underlying transport."""
        pass


class InMemoryEventPublisher(EventPublisher):
    """
    In-memory publisher storing published events for deterministic testing
    and historical comparison replays.
    """

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def publish(
        self,
        event: Dict[str, Any],
        topic: str = TOPIC,
        key: Optional[str] = None,
    ) -> bool:
        self.events.append(
            {
                "topic": topic,
                "key": key or event.get("payload", {}).get("supplier"),
                "event": event,
            }
        )
        return True

    def clear(self) -> None:
        self.events.clear()

    def get_events(self) -> List[Dict[str, Any]]:
        return [entry["event"] for entry in self.events]

    def count(self) -> int:
        return len(self.events)


class LoggingEventPublisher(EventPublisher):
    """Publisher that logs events without broker dependency."""

    def __init__(self, log_level: int = logging.INFO) -> None:
        self.log_level = log_level

    def publish(
        self,
        event: Dict[str, Any],
        topic: str = TOPIC,
        key: Optional[str] = None,
    ) -> bool:
        logger.log(
            self.log_level,
            "Event published to %s (key=%s): %s",
            topic,
            key or event.get("payload", {}).get("supplier"),
            json.dumps(event),
        )
        return True


class MockKafkaProducer:
    """Mock Kafka producer implementation for testing without a live broker."""

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.fail_delivery: bool = False

    def produce(
        self,
        topic: str,
        value: str | bytes,
        key: Optional[str | bytes] = None,
        callback: Optional[Any] = None,
    ) -> None:
        record = {"topic": topic, "key": key, "value": value}
        self.messages.append(record)
        if callback is not None:
            if self.fail_delivery:
                callback(RuntimeError("Mock delivery failure"), record)
            else:
                callback(None, record)

    def flush(self, timeout: float = 1.0) -> int:
        return 0 if not self.fail_delivery else 1


class KafkaEventPublisher(EventPublisher):
    """
    Kafka event publisher that wraps a Kafka producer.
    Allows passing either a real or mock Producer instance.
    Does not initialize a broker connection on import.
    """

    def __init__(
        self,
        producer: Any = None,
        bootstrap_servers: Optional[str] = None,
        flush_timeout_seconds: float = 2.0,
    ) -> None:
        self.flush_timeout_seconds = flush_timeout_seconds
        self._producer = producer

        if self._producer is None and bootstrap_servers:
            try:
                from confluent_kafka import Producer  # type: ignore

                self._producer = Producer(
                    {
                        "bootstrap.servers": bootstrap_servers,
                        "enable.idempotence": True,
                        "message.timeout.ms": 10000,
                    }
                )
            except ImportError as err:
                raise RuntimeError(
                    "confluent_kafka is required to initialize KafkaEventPublisher "
                    "with bootstrap_servers."
                ) from err

    def publish(
        self,
        event: Dict[str, Any],
        topic: str = TOPIC,
        key: Optional[str] = None,
    ) -> bool:
        if self._producer is None:
            logger.warning("KafkaEventPublisher called without an initialized producer.")
            return False

        supplier_key = key or event.get("payload", {}).get("supplier", "")
        delivery_errors: List[str] = []

        def delivery_callback(err: Any, msg: Any) -> None:
            if err is not None:
                delivery_errors.append(str(err))

        try:
            val_bytes = json.dumps(event).encode("utf-8")
            key_bytes = supplier_key.encode("utf-8") if supplier_key else None

            self._producer.produce(
                topic,
                key=key_bytes,
                value=val_bytes,
                callback=delivery_callback,
            )

            remaining = self._producer.flush(self.flush_timeout_seconds)
            if delivery_errors or remaining:
                logger.error(
                    "Kafka delivery failed for %s: errors=%s, remaining=%s",
                    topic,
                    delivery_errors,
                    remaining,
                )
                return False
            return True
        except Exception:
            logger.exception("Kafka publish exception for topic %s", topic)
            return False
