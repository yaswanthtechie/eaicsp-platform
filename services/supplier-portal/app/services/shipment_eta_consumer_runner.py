
import logging
import threading
import time

from app.core.config import settings
from app.services.shipment_eta_consumer import ShipmentETAConsumer

logger = logging.getLogger(__name__)


class ShipmentETAConsumerRunner:
    """Manage the ETA Kafka consumer in a background thread."""

    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._consumer = None
        self._lock = threading.Lock()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.is_alive:
                logger.info("ETA consumer runner is already running.")
                return

            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run,
                name="shipment-eta-consumer",
                daemon=True,
            )
            self._thread.start()

        logger.info("ETA consumer runner started.")

    def _run(self):
        while not self._stop_event.is_set():
            consumer = None

            try:
                consumer = ShipmentETAConsumer()
                self._consumer = consumer
                consumer.run()

            except Exception:
                if not self._stop_event.is_set():
                    logger.exception(
                        "ETA consumer stopped unexpectedly. "
                        "Restarting after 5 seconds."
                    )

            finally:
                self._consumer = None

            if not self._stop_event.is_set():
                self._stop_event.wait(5)

        logger.info("ETA consumer runner stopped.")

    def stop(self):
        self._stop_event.set()

        consumer = self._consumer
        if consumer is not None:
            consumer.stop()

        thread = self._thread

        if thread is not None and thread.is_alive():
            thread.join(timeout=10)

        logger.info("ETA consumer runner shutdown requested.")


shipment_eta_consumer_runner = ShipmentETAConsumerRunner()
