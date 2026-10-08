from __future__ import annotations

import logging
from threading import Thread

from app.services.kafka_consumer import SupplierStatusChangedConsumer

logger = logging.getLogger(__name__)


class KafkaConsumerRunner:
    """
    Runs the Supplier Portal Kafka consumer in a background thread.
    """

    def __init__(self) -> None:
        self.consumer: SupplierStatusChangedConsumer | None = None
        self._thread: Thread | None = None

    def start(self) -> None:
        """Create and start the Kafka consumer."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Kafka consumer is already running.")
            return

        self.consumer = SupplierStatusChangedConsumer()

        self._thread = Thread(
            target=self._run,
            name="supplier-portal-kafka-consumer",
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "Supplier Portal Kafka consumer background thread started."
        )

    def _run(self) -> None:
        """Run the blocking Kafka consumer loop."""
        if self.consumer is None:
            return

        try:
            self.consumer.run()
        except Exception:
            logger.exception(
                "Supplier Portal Kafka consumer stopped unexpectedly."
            )

    def stop(self) -> None:
        """Stop the Kafka consumer and wait for its thread."""
        if self.consumer is None:
            return

        self.consumer.stop()

        if self._thread is not None:
            self._thread.join(timeout=10)

            if self._thread.is_alive():
                logger.warning(
                    "Kafka consumer thread did not stop within timeout."
                )
            else:
                logger.info(
                    "Supplier Portal Kafka consumer background thread stopped."
                )

        self._thread = None
        self.consumer = None


kafka_consumer_runner = KafkaConsumerRunner()