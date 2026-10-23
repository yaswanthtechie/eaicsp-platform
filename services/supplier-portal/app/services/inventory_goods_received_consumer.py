
import json
import logging
import threading
import time

from confluent_kafka import Consumer, KafkaError, Producer
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database import SessionLocal
from app.models.inventory_goods_receipt_event import (
    InventoryGoodsReceiptEvent,
)

logger = logging.getLogger(__name__)


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
            if type(quantity) is not int or quantity < 1:
                raise ValueError("item.quantity_received must be a positive integer")

        return event

    def _persist_event(self, event: dict) -> bool:
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
            raise
        finally:
            db.close()

    def _send_to_dlq(self, message, reason: str) -> None:
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
                        message.value().decode("utf-8", errors="replace")
                    ),
                }
            ),
        )
        self.producer.flush(10)

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

                try:
                    raw = message.value().decode("utf-8")
                    event = self._validate_event(json.loads(raw))
                    self._persist_event(event)
                    self.consumer.commit(message=message, asynchronous=False)
                except (ValueError, json.JSONDecodeError) as exc:
                    logger.warning("Invalid goods receipt event: %s", exc)
                    self._send_to_dlq(message, str(exc))
                    self.consumer.commit(message=message, asynchronous=False)
                except Exception:
                    logger.exception(
                        "Goods receipt processing failed; offset not committed"
                    )
                    # Keep the offset uncommitted so Kafka can redeliver it.
                    time.sleep(settings.KAFKA_RETRY_BACKOFF_SECONDS)
        finally:
            self.consumer.close()
            self.producer.flush(10)
