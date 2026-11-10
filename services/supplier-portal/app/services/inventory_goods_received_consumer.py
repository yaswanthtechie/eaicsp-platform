import json
import logging
import re
import threading
import time
from uuid import UUID

from confluent_kafka import Consumer, KafkaError, Producer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database import SessionLocal
from app.models.inventory_goods_receipt_event import (
    InventoryGoodsReceiptEvent,
)

logger = logging.getLogger(__name__)

# Canonical ID patterns from contracts/events/inventory.goods.received.v1.json.
# tests/test_inventory_goods_received_consumer.py checks they stay in sync.
PAYLOAD_ID_PATTERNS = {
    "receipt_id": r"^GR-\d{4}-\d{6}$",
    "po_id": r"^PO-\d{4}-\d{6}$",
    "supplier_id": r"^SUP-\d{5}$",
    "warehouse_id": r"^WH-[A-Z]{3}-\d{2}$",
}
SKU_ID_PATTERN = r"^SKU-\d{6}$"


class ConflictingReceiptError(ValueError):
    """A different event arrived for a receipt_id that is already stored."""


class InventoryGoodsReceivedConsumer:
    """Consume and durably deduplicate Inventory goods receipt events."""

    def __init__(self) -> None:
        self._stopping = threading.Event()
        self.consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": settings.KAFKA_GOODS_RECEIVED_CONSUMER_GROUP,
                "auto.offset.reset": settings.KAFKA_AUTO_OFFSET_RESET,
                "enable.auto.commit": False,
            }
        )
        self.producer = Producer(
            {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
        )

    def stop(self) -> None:
        self._stopping.set()

    @staticmethod
    def _validate_event(event: dict) -> dict:
        if not isinstance(event, dict):
            raise ValueError("Event must be a JSON object")
        if event.get("event_type") != "inventory.goods.received":
            raise ValueError("Unexpected event_type")
        if event.get("event_version") != 1:
            raise ValueError("Unsupported event_version")
        if event.get("producer") != "inventory-service":
            raise ValueError("Unexpected producer")

        event_id = event.get("event_id")
        payload = event.get("payload")

        if not isinstance(event_id, str) or not event_id:
            raise ValueError("event_id is required")
        try:
            UUID(event_id)
        except ValueError:
            raise ValueError("event_id must be a UUID") from None
        if not event.get("occurred_at"):
            raise ValueError("occurred_at is required")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")

        for field in (
            "receipt_id",
            "po_id",
            "supplier_id",
            "warehouse_id",
            "received_by",
            "received_at",
            "status",
            "items",
        ):
            if field not in payload:
                raise ValueError(f"payload.{field} is required")

        for field, pattern in PAYLOAD_ID_PATTERNS.items():
            value = payload[field]
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError(
                    f"payload.{field} is not a canonical ID: {value!r}"
                )

        if payload["status"] != "received":
            raise ValueError("Receipt status must be received")
        if not isinstance(payload["items"], list) or not payload["items"]:
            raise ValueError("payload.items must be a non-empty list")

        for item in payload["items"]:
            if not isinstance(item, dict):
                raise ValueError("Each receipt item must be an object")
            sku_id = item.get("sku_id")
            quantity = item.get("quantity_received")
            if not isinstance(sku_id, str) or not sku_id:
                raise ValueError("item.sku_id is required")
            if not re.fullmatch(SKU_ID_PATTERN, sku_id):
                raise ValueError(
                    f"item.sku_id is not a canonical SKU ID: {sku_id!r}"
                )
            if type(quantity) is not int or quantity < 1:
                raise ValueError("item.quantity_received must be a positive integer")

        return event

    def _persist_event(self, event: dict) -> bool:
        """
        Store the event once. Returns False for a duplicate: the same
        event_id, or the same receipt re-sent with identical content.
        Raises ConflictingReceiptError if the receipt was already stored
        with different content.
        """
        payload = event["payload"]
        db = SessionLocal()

        try:
            record = InventoryGoodsReceiptEvent(
                event_id=event["event_id"],
                receipt_id=payload["receipt_id"],
                po_id=payload["po_id"],
                supplier_id=payload["supplier_id"],
                payload=event,
            )
            db.add(record)
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            # Same event_id already committed: safe to acknowledge.
            existing = db.get(
                InventoryGoodsReceiptEvent, event["event_id"]
            )
            if existing is not None:
                return False

            # receipt_id is unique: a second event for the same receipt
            # must never add its quantities to the match again.
            existing = db.scalars(
                select(InventoryGoodsReceiptEvent).where(
                    InventoryGoodsReceiptEvent.receipt_id
                    == payload["receipt_id"]
                )
            ).first()
            if existing is not None:
                if existing.payload.get("payload") == payload:
                    return False
                raise ConflictingReceiptError(
                    "Conflicting goods receipt event for "
                    f"receipt_id={payload['receipt_id']}: "
                    f"existing_event_id={existing.event_id}, "
                    f"incoming_event_id={event['event_id']}"
                )
            raise
        finally:
            db.close()

    def _send_to_dlq(self, message, reason: str) -> None:
        delivery_errors: list[str] = []

        def on_delivery(error, _message) -> None:
            if error is not None:
                delivery_errors.append(str(error))

        value = message.value()
        self.producer.produce(
            settings.KAFKA_GOODS_RECEIVED_DLQ_TOPIC,
            key=message.key(),
            value=json.dumps(
                {
                    "source_topic": message.topic(),
                    "source_partition": message.partition(),
                    "source_offset": message.offset(),
                    "reason": reason,
                    "original_value": (
                        value.decode("utf-8", errors="replace")
                        if value is not None
                        else None
                    ),
                }
            ),
            on_delivery=on_delivery,
        )
        pending = self.producer.flush(10)

        # The source offset is committed only after Kafka confirms the
        # DLQ copy; otherwise the bad message would be lost.
        if pending != 0 or delivery_errors:
            raise RuntimeError(
                "DLQ delivery not confirmed: "
                f"pending={pending}, errors={delivery_errors}"
            )

    def _commit(self, message) -> None:
        self.consumer.commit(message=message, asynchronous=False)

    def _process_message(self, message) -> None:
        """
        Validate, store and commit one message. A message is either
        stored, sent to the DLQ, or left uncommitted (the exception
        propagates and the runner restarts the consumer, which resumes
        from the last committed offset). It is never skipped.
        """
        try:
            raw = message.value()
            if raw is None:
                raise ValueError("Message has no value")
            event = self._validate_event(json.loads(raw.decode("utf-8")))
        except ValueError as exc:
            # json.JSONDecodeError and UnicodeDecodeError are ValueErrors.
            logger.warning("Invalid goods receipt event: %s", exc)
            self._send_to_dlq(message, str(exc))
            self._commit(message)
            return

        max_retries = max(1, settings.KAFKA_MAX_RETRIES)

        for attempt in range(1, max_retries + 1):
            try:
                self._persist_event(event)
                break
            except ConflictingReceiptError as exc:
                # A bad message, not a temporary failure: retrying cannot
                # help, so send it straight to the DLQ.
                logger.error("%s", exc)
                self._send_to_dlq(message, str(exc))
                self._commit(message)
                return
            except Exception:
                logger.exception(
                    "Goods receipt persistence failed (attempt %s/%s)",
                    attempt,
                    max_retries,
                )
                if attempt < max_retries:
                    time.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS * attempt)
        else:
            # Still failing after every retry: park it in the DLQ so the
            # partition keeps moving, and only then commit.
            self._send_to_dlq(
                message,
                f"Persistence failed after {max_retries} attempts",
            )
            self._commit(message)
            return

        self._commit(message)

    def run(self) -> None:
        topic = settings.KAFKA_GOODS_RECEIVED_TOPIC
        self.consumer.subscribe([topic])
        logger.info("Subscribed to Inventory goods receipts: %s", topic)

        try:
            while not self._stopping.is_set():
                message = self.consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    if message.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise RuntimeError(str(message.error()))

                # Failures that cannot be parked in the DLQ propagate: the
                # runner restarts the consumer from the last committed
                # offset, so this message is redelivered, not skipped.
                self._process_message(message)
        finally:
            self.consumer.close()
            self.producer.flush(10)