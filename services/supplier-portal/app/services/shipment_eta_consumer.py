from __future__ import annotations

import json
import logging
import time
from datetime import timezone
from typing import Any

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Producer,
)

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database import SessionLocal
from app.models.shipment import Shipment
from app.models.shipment_eta_event import ShipmentETAEvent
from app.schemas.events import ETAShipmentPredictedEvent

logger = logging.getLogger(__name__)


class ShipmentETAConsumer:
    """Consume ETA prediction events and update shipment records."""

    def __init__(self):
        self.topic = settings.ETA_PREDICTED_TOPIC
        self.dlq_topic = settings.ETA_DLQ_TOPIC
        self.max_retries = settings.KAFKA_MAX_RETRIES
        self.retry_backoff = settings.KAFKA_RETRY_BACKOFF_SECONDS

        self.consumer = Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.ETA_CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        })

        self.producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        })

        self.running = False

    # ---------------------------------------------------------
    # Main consumer loop
    # ---------------------------------------------------------

    def run(self):
        self.running = True

        logger.info(
            "Starting ETA consumer: topic=%s group=%s",
            self.topic,
            settings.ETA_CONSUMER_GROUP,
        )

        self.consumer.subscribe([self.topic])

        try:
            while self.running:
                message = self.consumer.poll(timeout=1.0)

                if message is None:
                    continue

                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue

                    raise KafkaException(message.error())

                self._process_with_retry(message)

        except Exception:
            logger.exception("ETA consumer loop failed.")
            raise

        finally:
            self.close()

    # ---------------------------------------------------------
    # Retry handling
    # ---------------------------------------------------------

    def _process_with_retry(self, message: Any):
        dlq_reason = "Maximum retries exceeded"

        for attempt in range(1, self.max_retries + 1):
            if not self.running:
                return

            try:
                self.process_message(message)

                self._commit_message(message)

                logger.info(
                    "ETA event processed: topic=%s partition=%s offset=%s",
                    message.topic(),
                    message.partition(),
                    message.offset(),
                )
                return

            except ValueError as exc:
                # Permanent failure: retrying cannot fix invalid data,
                # an unknown shipment, or a PO mismatch.
                logger.warning(
                    "Invalid ETA event: offset=%s reason=%s",
                    message.offset(),
                    exc,
                )
                dlq_reason = str(exc)
                break

            except Exception:
                # Transient or unexpected failure: retry with backoff.
                logger.exception(
                    "ETA processing failed: attempt=%s/%s topic=%s "
                    "partition=%s offset=%s",
                    attempt,
                    self.max_retries,
                    message.topic(),
                    message.partition(),
                    message.offset(),
                )

                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff)

        # Commit only after successful DLQ delivery.
        if self._publish_to_dlq(message, dlq_reason):
            self._commit_message(message)
        else:
            logger.error(
                "ETA DLQ delivery failed. Offset will not be committed: "
                "partition=%s offset=%s",
                message.partition(),
                message.offset(),
            )
            raise RuntimeError("Could not publish ETA event to DLQ.")

    # ---------------------------------------------------------
    # Event processing
    # ---------------------------------------------------------

    def process_message(self, message: Any) -> bool:
        event = self._deserialize_event(message)

        payload = event.payload

        db = SessionLocal()

        try:
            # Lock shipment row so concurrent predictions are serialized.
            shipment = db.execute(
                select(Shipment)
                .where(Shipment.shipment_id == payload.shipment_id)
                .with_for_update()
            ).scalar_one_or_none()

            if shipment is None:
                raise ValueError(
                    f"Unknown shipment: {payload.shipment_id}"
                )

            if shipment.po_number != payload.po_number:
                raise ValueError(
                    "ETA event PO number does not match shipment."
                )

            # Check event ID before inserting.
            existing_event = db.get(
                ShipmentETAEvent,
                str(event.event_id),
            )

            if existing_event is not None:
                logger.info(
                    "Duplicate ETA event ignored: event_id=%s",
                    event.event_id,
                )
                return True

            db.add(
                ShipmentETAEvent(
                    event_id=str(event.event_id),
                    shipment_id=payload.shipment_id,
                    predicted_at=payload.predicted_at,
                )
            )

            # Apply only newer predictions.
            if (
                shipment.predicted_at is None
                or self._as_utc(payload.predicted_at)
                > self._as_utc(shipment.predicted_at)
            ):
                shipment.eta_days = payload.eta_days
                shipment.confidence_low = payload.confidence_low
                shipment.confidence_high = payload.confidence_high
                shipment.model_version = payload.model_version
                shipment.predicted_at = payload.predicted_at

                shipment.top_features = (
                    [
                        feature.model_dump()
                        if hasattr(feature, "model_dump")
                        else feature
                        for feature in payload.top_features
                    ]
                    if payload.top_features is not None
                    else None
                )

            # Event record and shipment update are atomic.
            db.commit()

            logger.info(
                "ETA prediction stored: shipment_id=%s predicted_at=%s",
                payload.shipment_id,
                payload.predicted_at,
            )

            return True

        except IntegrityError:
            db.rollback()

            # Treat as duplicate only if that event ID now exists.
            duplicate = db.get(
                ShipmentETAEvent,
                str(event.event_id),
            )

            if duplicate is not None:
                logger.info(
                    "Concurrent duplicate ETA event ignored: %s",
                    event.event_id,
                )
                return True

            raise

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    # ---------------------------------------------------------
    # Event validation
    # ---------------------------------------------------------

    @staticmethod
    def _deserialize_event(message: Any) -> ETAShipmentPredictedEvent:
        raw_value = message.value()

        if raw_value is None:
            raise ValueError("Kafka message has no value.")

        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")

        if not isinstance(raw_value, str):
            raise ValueError("Kafka message must contain UTF-8 JSON.")

        try:
            data = json.loads(raw_value)
            event = ETAShipmentPredictedEvent.model_validate(data)

            # Contract timestamps must be UTC.
            if event.occurred_at.utcoffset().total_seconds() != 0:
                raise ValueError("occurred_at must be UTC.")

            if event.payload.predicted_at.utcoffset().total_seconds() != 0:
                raise ValueError("predicted_at must be UTC.")

            return event

        except Exception as exc:
            raise ValueError(
                "Invalid eta.shipment.predicted event."
            ) from exc

    @staticmethod
    def _as_utc(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    # ---------------------------------------------------------
    # Offset commit
    # ---------------------------------------------------------

    def _commit_message(self, message: Any):
        self.consumer.commit(
            message=message,
            asynchronous=False,
        )

    # ---------------------------------------------------------
    # Dead-letter queue
    # ---------------------------------------------------------

    def _publish_to_dlq(self, message: Any, reason: str) -> bool:
        delivery_result = {"success": False}

        def on_delivery(error, delivered_message):
            if error is None:
                delivery_result["success"] = True
            else:
                logger.error("ETA DLQ delivery failed: %s", error)

        dlq_record = {
            "failed_at": self._utc_now(),
            "error_reason": reason,
            "source_topic": message.topic(),
            "source_partition": message.partition(),
            "source_offset": message.offset(),
            "original_key": (
                message.key().decode("utf-8", errors="replace")
                if message.key() is not None
                else None
            ),
            "original_value": (
                message.value().decode("utf-8", errors="replace")
                if isinstance(message.value(), bytes)
                else message.value()
            ),
        }

        try:
            self.producer.produce(
                topic=self.dlq_topic,
                key=message.key(),
                value=json.dumps(dlq_record),
                on_delivery=on_delivery,
            )

            remaining = self.producer.flush(timeout=10)

            if remaining > 0 or not delivery_result["success"]:
                logger.error("ETA DLQ message was not confirmed.")
                return False

            logger.warning(
                "ETA event sent to DLQ: source_offset=%s",
                message.offset(),
            )

            return True

        except Exception:
            logger.exception("Failed to publish ETA event to DLQ.")
            return False

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime

        return datetime.now(timezone.utc).isoformat()

    # ---------------------------------------------------------
    # Shutdown
    # ---------------------------------------------------------

    def stop(self):
        self.running = False

    def close(self):
        try:
            self.consumer.close()
        finally:
            self.producer.flush(timeout=10)
