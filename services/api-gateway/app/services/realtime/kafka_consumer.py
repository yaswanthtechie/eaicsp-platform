"""
Kafka Consumer Service for Realtime Analytics KPI Dashboard (R15-M3).

Consumes the six canonical dashboard event types using dedicated consumer group
'api-gateway-bff', validates messages against contract schemas, performs bounded
deduplication, broadcasts valid events to connected WebSocket clients, and routes
invalid events to '<topic>.dlq'.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from app.core.config import settings
from app.schemas.realtime_events import CANONICAL_EVENT_TYPES, validate_realtime_event
from app.services.realtime.connection_manager import ConnectionManager, connection_manager
from app.services.realtime.deduplicator import Deduplicator
from app.services.realtime.dlq import DLQPublishError, DLQService, dlq_service

logger = logging.getLogger("api_gateway.realtime.kafka_consumer")


class RealtimeKafkaConsumerService:
    """
    Dedicated Kafka consumer service for the API Gateway BFF.
    """

    def __init__(
        self,
        bootstrap_servers: Optional[str] = None,
        group_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        conn_mgr: Optional[ConnectionManager] = None,
        dedup: Optional[Deduplicator] = None,
        dlq_svc: Optional[DLQService] = None,
        auto_offset_reset: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers or getattr(
            settings, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.group_id = group_id or getattr(
            settings, "KAFKA_CONSUMER_GROUP", "api-gateway-bff"
        )
        self.topics = topics or getattr(
            settings, "KAFKA_TOPICS", sorted(list(CANONICAL_EVENT_TYPES))
        )
        self.auto_offset_reset = auto_offset_reset or getattr(
            settings, "KAFKA_CONSUMER_AUTO_OFFSET_RESET", "latest"
        )
        self.connection_manager = conn_mgr or connection_manager
        dedup_size = getattr(settings, "KAFKA_DEDUPLICATION_CACHE_SIZE", 1000)
        self.deduplicator = dedup or Deduplicator(max_size=dedup_size)
        self.dlq_service = dlq_svc or dlq_service
        self.enabled = (
            getattr(settings, "KAFKA_CONSUMER_ENABLED", True)
            if enabled is None
            else enabled
        )

        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._consumer: Optional[Any] = None
        self._producer: Optional[Any] = None

    async def _route_to_dlq_then_commit(
        self,
        raw_message: Union[str, bytes, Dict[str, Any]],
        source_topic: str,
        error_reason: str,
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        event_type: Optional[str] = None,
        commit_callback: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        """
        Route invalid message to DLQ and commit offset only on successful DLQ publish.
        Raises DLQPublishError if DLQ publishing fails.
        """
        success = await self.dlq_service.route(
            raw_message=raw_message,
            source_topic=source_topic,
            error_reason=error_reason,
            partition=partition,
            offset=offset,
            event_type=event_type,
        )
        if not success:
            raise DLQPublishError(
                f"Failed to publish invalid message to DLQ for topic '{source_topic}', offset={offset}"
            )

        if commit_callback:
            await commit_callback()

    async def process_message(
        self,
        topic: str,
        value: Union[str, bytes, Dict[str, Any]],
        partition: Optional[int] = None,
        offset: Optional[int] = None,
        commit_callback: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ) -> bool:
        """
        Process a single consumed Kafka message.

        Steps:
        1. Decode and parse JSON.
        2. Validate envelope and payload schema against contract.
        3. If invalid, route original message to DLQ (<topic>.dlq) and commit offset.
        4. If valid, check deduplication cache:
           - ordinary events -> event_id
           - iot.anomaly.detected -> payload.episode_id
           If duplicate, drop without broadcast and commit offset.
        5. If valid and not duplicate, broadcast original envelope to connected WebSocket clients.
        6. Commit offset.

        Returns:
            True if valid (whether broadcast or duplicate), False if invalid/malformed.
        """
        # 1. Decode & parse JSON
        data: Dict[str, Any]
        if isinstance(value, dict):
            data = value
        else:
            raw_str: str
            if isinstance(value, bytes):
                try:
                    raw_str = value.decode("utf-8")
                except UnicodeDecodeError as u_err:
                    logger.warning("Message on topic '%s' is not valid UTF-8: %s", topic, u_err)
                    await self._route_to_dlq_then_commit(
                        raw_message=value,
                        source_topic=topic,
                        error_reason=f"Unicode decode error: {u_err}",
                        partition=partition,
                        offset=offset,
                        commit_callback=commit_callback,
                    )
                    return False
            else:
                raw_str = str(value)

            try:
                data = json.loads(raw_str)
            except json.JSONDecodeError as j_err:
                logger.warning("Malformed JSON on topic '%s': %s", topic, j_err)
                await self._route_to_dlq_then_commit(
                    raw_message=raw_str,
                    source_topic=topic,
                    error_reason=f"Malformed JSON: {j_err}",
                    partition=partition,
                    offset=offset,
                    commit_callback=commit_callback,
                )
                return False

        # 2. Validate envelope & payload against M1 contract
        is_valid, dedup_key, error_reason = validate_realtime_event(data)
        if not is_valid:
            logger.info("Invalid event on topic '%s': %s", topic, error_reason)
            event_type = data.get("event_type") if isinstance(data, dict) else None
            await self._route_to_dlq_then_commit(
                raw_message=data,
                source_topic=topic,
                error_reason=error_reason or "Schema validation failed",
                partition=partition,
                offset=offset,
                event_type=event_type,
                commit_callback=commit_callback,
            )
            return False

        # 3. Deduplication check
        if dedup_key:
            is_dup = await self.deduplicator.is_duplicate(dedup_key)
            if is_dup:
                logger.info(
                    "Dropping duplicate event (dedup_key=%s) on topic '%s'",
                    dedup_key,
                    topic,
                )
                if commit_callback:
                    await commit_callback()
                return True

        # 4. Broadcast original event envelope as UTF-8 JSON text frame
        try:
            json_text = json.dumps(data)
            sent_count = await self.connection_manager.broadcast(json_text)
            logger.debug(
                "Broadcast event '%s' (type=%s) to %d client(s)",
                data.get("event_id"),
                data.get("event_type"),
                sent_count,
            )
        except Exception as b_exc:
            logger.error("Error during WebSocket fanout broadcast: %s", b_exc, exc_info=True)

        # 5. Commit offset
        if commit_callback:
            try:
                await commit_callback()
            except Exception as c_exc:
                logger.warning("Failed to commit offset for topic %s: %s", topic, c_exc)

        return True

    async def start(self) -> None:
        """Start the background Kafka consumer task if enabled."""
        if self._running:
            return

        if not self.enabled:
            logger.info("Kafka consumer disabled by configuration (KAFKA_CONSUMER_ENABLED=False).")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(
            self._run_consumer(),
            name="realtime_kafka_consumer_bff",
        )
        logger.info("Started RealtimeKafkaConsumerService background task.")

    async def stop(self) -> None:
        """Cleanly stop the consumer and close connections."""
        if not self._running:
            return

        logger.info("Stopping RealtimeKafkaConsumerService...")
        self._running = False

        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await asyncio.wait_for(self._consumer_task, timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._consumer_task = None

        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception as exc:
                logger.debug("Error stopping Kafka consumer: %s", exc)
            self._consumer = None

        if self._producer:
            try:
                await self._producer.stop()
            except Exception as exc:
                logger.debug("Error stopping Kafka producer: %s", exc)
            self._producer = None

        logger.info("RealtimeKafkaConsumerService stopped.")

    async def _run_consumer(self) -> None:
        """
        Long-running background task consuming from Kafka with bounded reconnection backoff.
        """
        backoff = 1.0

        while self._running:
            consumer = None
            producer = None
            try:
                try:
                    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
                except ImportError as imp_err:
                    logger.error(
                        "aiokafka is not installed. Kafka consumer cannot start: %s",
                        imp_err,
                    )
                    break

                logger.info(
                    "Connecting to Kafka at '%s', group='%s', topics=%s",
                    self.bootstrap_servers,
                    self.group_id,
                    self.topics,
                )

                consumer = AIOKafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.group_id,
                    enable_auto_commit=False,
                    auto_offset_reset=self.auto_offset_reset,
                )
                producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)

                await consumer.start()
                await producer.start()

                self._consumer = consumer
                self._producer = producer
                self.dlq_service.set_producer(producer)

                backoff = 1.0
                logger.info("Kafka consumer successfully connected and subscribed.")

                while self._running:
                    try:
                        msg_set = await consumer.getmany(timeout_ms=1000, max_records=50)
                    except Exception as poll_exc:
                        if not self._running:
                            break
                        raise poll_exc

                    for tp, messages in msg_set.items():
                        for msg in messages:
                            if not self._running:
                                break

                            async def commit_offset(tp_obj=tp, offset_val=msg.offset):
                                try:
                                    await consumer.commit({tp_obj: offset_val + 1})
                                except Exception as c_err:
                                    logger.warning(
                                        "Offset commit failed for %s[%s]=%s: %s",
                                        tp_obj.topic,
                                        tp_obj.partition,
                                        offset_val,
                                        c_err,
                                    )

                            await self.process_message(
                                topic=msg.topic,
                                value=msg.value,
                                partition=msg.partition,
                                offset=msg.offset,
                                commit_callback=commit_offset,
                            )

            except asyncio.CancelledError:
                logger.info("Kafka consumer background task cancelled.")
                break
            except Exception as exc:
                if not self._running:
                    break
                logger.warning(
                    "Kafka connection or consumer exception (%s: %s). Backing off for %.1fs...",
                    type(exc).__name__,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
            finally:
                if consumer:
                    try:
                        await consumer.stop()
                    except Exception:
                        pass
                if producer:
                    try:
                        await producer.stop()
                    except Exception:
                        pass
                self._consumer = None
                self._producer = None


# Global singleton instance
realtime_consumer_service = RealtimeKafkaConsumerService()
