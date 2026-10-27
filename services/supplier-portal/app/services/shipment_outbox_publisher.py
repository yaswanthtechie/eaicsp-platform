
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Any

from confluent_kafka import Producer

from app.core.config import settings
from app.database import SessionLocal
from app.models.shipment_outbox import ShipmentOutbox

logger = logging.getLogger(__name__)


class ShipmentOutboxPublisher:
    """Publish pending shipment dispatch events to Kafka."""

    def __init__(self, producer: Any | None = None) -> None:
        self.producer = producer

    def _get_producer(self) -> Any:
        if self.producer is None:
            self.producer = Producer(
                {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
            )
        return self.producer

    def publish_pending(self, batch_size: int | None = None) -> int:
        limit = batch_size or settings.SHIPMENT_OUTBOX_BATCH_SIZE
        producer = self._get_producer()
        published = 0

        with SessionLocal() as db:
            try:
                rows = (
                    db.query(ShipmentOutbox)
                    .filter(ShipmentOutbox.status == "pending")
                    .order_by(ShipmentOutbox.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                    .all()
                )

                for row in rows:
                    delivery_errors: list[str] = []

                    def on_delivery(error: Any, _message: Any) -> None:
                        if error is not None:
                            delivery_errors.append(str(error))

                    row.attempts += 1

                    try:
                        producer.produce(
                            topic=row.topic,
                            key=row.message_key,
                            value=json.dumps(row.payload),
                            on_delivery=on_delivery,
                        )
                        pending = producer.flush(10)
                    except Exception as exc:
                        row.last_error = str(exc)[:1000]
                        continue

                    if pending or delivery_errors:
                        row.last_error = (
                            f"pending={pending}, errors={delivery_errors}"
                        )[:1000]
                        continue

                    row.status = "published"
                    row.published_at = datetime.now(timezone.utc)
                    row.last_error = None
                    published += 1

                db.commit()

            except Exception:
                db.rollback()
                raise

        return published


class ShipmentOutboxPublisherRunner:
    """Run shipment outbox publishing in a background thread."""

    def __init__(self) -> None:
        self.publisher = ShipmentOutboxPublisher()
        self._thread: Thread | None = None
        self._stopping = Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stopping.clear()

        def run_publisher() -> None:
            while not self._stopping.is_set():
                try:
                    self.publisher.publish_pending()
                except Exception:
                    logger.exception(
                        "Shipment outbox publish failed; will retry"
                    )

                self._stopping.wait(
                    settings.SHIPMENT_OUTBOX_POLL_SECONDS
                )

        self._thread = Thread(
            target=run_publisher,
            name="shipment-outbox-publisher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()

        if self._thread is not None:
            self._thread.join(timeout=10)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


shipment_outbox_publisher_runner = ShipmentOutboxPublisherRunner()
