"""
Dead-Letter Queue (DLQ) router for Realtime WebSocket (R15-M3).

Routes malformed or invalid Kafka events to corresponding '<topic>.dlq' topics,
preserving the original payload, failure timestamp, and clear diagnostic error reason.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("api_gateway.realtime.dlq")


def build_dlq_payload(
    raw_message: Union[str, bytes, Dict[str, Any]],
    source_topic: str,
    error_reason: str,
    partition: Optional[int] = None,
    offset: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Construct a standardized DLQ envelope preserving original event and diagnostics.
    """
    failed_at = datetime.now(timezone.utc).isoformat()

    original_content: Any
    if isinstance(raw_message, dict):
        original_content = raw_message
    elif isinstance(raw_message, bytes):
        try:
            original_content = json.loads(raw_message.decode("utf-8"))
        except Exception:
            original_content = raw_message.decode("utf-8", errors="replace")
    elif isinstance(raw_message, str):
        try:
            original_content = json.loads(raw_message)
        except Exception:
            original_content = raw_message
    else:
        original_content = str(raw_message)

    return {
        "error_reason": error_reason,
        "failed_at": failed_at,
        "source_topic": source_topic,
        "source_partition": partition,
        "source_offset": offset,
        "original_message": original_content,
    }


def resolve_dlq_topic(source_topic: Optional[str], event_type: Optional[str] = None) -> str:
    """
    Determine the target DLQ topic name.
    Follows '<topic>.dlq' naming convention.
    """
    topic = source_topic or event_type or "api-gateway"
    clean_topic = topic.strip()
    if clean_topic.endswith(".dlq"):
        return clean_topic
    return f"{clean_topic}.dlq"


class DLQPublishError(RuntimeError):
    """An invalid message could not be published to its DLQ topic."""


class DLQService:
    """
    Service responsible for routing invalid messages to DLQ topics.
    """

    def __init__(self, producer: Optional[Any] = None) -> None:
        self._producer = producer

    def set_producer(self, producer: Any) -> None:
        """Set or swap the underlying Kafka producer."""
        self._producer = producer

    async def route(
        self,
        raw_message: Union[str, bytes, Dict[str, Any]],
        source_topic: str,
        error_reason: str,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> bool:
        """
        Package the invalid message into a DLQ record and publish to <topic>.dlq.

        Returns:
            True if successfully published to DLQ, False if publishing failed.
            Never raises out to avoid crashing the gateway consumer.
        """
        dlq_topic = resolve_dlq_topic(source_topic, event_type)
        payload = build_dlq_payload(
            raw_message=raw_message,
            source_topic=source_topic,
            error_reason=error_reason,
            partition=partition,
            offset=offset,
        )

        logger.warning(
            "Routing invalid message from topic '%s' (partition=%s, offset=%s) to DLQ '%s': %s",
            source_topic,
            partition,
            offset,
            dlq_topic,
            error_reason,
        )

        if self._producer is None:
            logger.warning("DLQ producer not configured; message logged but not published to Kafka DLQ.")
            return False

        try:
            val_bytes = json.dumps(payload, default=str).encode("utf-8")
            # Support both async send_and_wait (aiokafka) and sync produce (confluent-kafka/mock)
            if hasattr(self._producer, "send_and_wait"):
                await self._producer.send_and_wait(dlq_topic, val_bytes)
            elif hasattr(self._producer, "send"):
                future = self._producer.send(dlq_topic, val_bytes)
                if asyncio.iscoroutine(future):
                    await future
            elif hasattr(self._producer, "produce"):
                self._producer.produce(dlq_topic, value=val_bytes)
                if hasattr(self._producer, "flush"):
                    self._producer.flush(1.0)
            return True

        except Exception as exc:
            logger.error(
                "Failed to publish message to DLQ topic '%s': %s",
                dlq_topic,
                exc,
                exc_info=True,
            )
            return False


dlq_service = DLQService()
