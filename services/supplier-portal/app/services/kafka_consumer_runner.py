
from __future__ import annotations

import logging
from threading import Event, Thread

from app.services.kafka_consumer import SupplierStatusChangedConsumer

logger = logging.getLogger(__name__)


class KafkaConsumerRunner:
    """Run the Supplier Portal Kafka consumer in a background thread."""

    def __init__(self) -> None:
        self.consumer: SupplierStatusChangedConsumer | None = None
        self._thread: Thread | None = None
        self._stopping = Event()

    def start(self) -> None:
        """Start the runner unless its thread is already running."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Kafka consumer is already running.")
            return

        self._stopping.clear()

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
        """Run the consumer and retry after initialization or runtime errors."""
        while not self._stopping.is_set():
            consumer: SupplierStatusChangedConsumer | None = None

            try:
                consumer = SupplierStatusChangedConsumer()
                self.consumer = consumer

                # Do not start a consumer if shutdown was requested
                # while its constructor was running.
                if self._stopping.is_set():
                    try:
                        consumer.stop()
                    except Exception:
                        logger.exception(
                            "Error while stopping the Kafka consumer."
                        )
                    return

                consumer.run()

                # Per the consumer contract, a normal return means stop.
                return

            except Exception:
                if self._stopping.is_set():
                    return

                logger.exception(
                    "Kafka consumer crashed; restarting in 5 seconds."
                )

            finally:
                if consumer is not None and self.consumer is consumer:
                    self.consumer = None

            if self._stopping.wait(5):
                return

    def is_alive(self) -> bool:
        """Return whether the background runner thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        """Request shutdown, stop the consumer, and join the thread."""
        self._stopping.set()

        consumer = self.consumer
        if consumer is not None:
            try:
                consumer.stop()
            except Exception:
                logger.exception("Error while stopping the Kafka consumer.")

        thread = self._thread
        if thread is not None:
            thread.join(timeout=10)

            if thread.is_alive():
                logger.warning(
                    "Kafka consumer thread did not stop within timeout."
                )
            else:
                logger.info(
                    "Supplier Portal Kafka consumer background thread stopped."
                )

        if thread is None or not thread.is_alive():
            self._thread = None
            self.consumer = None


kafka_consumer_runner = KafkaConsumerRunner()
