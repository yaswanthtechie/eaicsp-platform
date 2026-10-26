
from __future__ import annotations

import logging
from threading import Event, Thread

from app.services.inventory_po_approved_consumer import POApprovedConsumer

logger = logging.getLogger(__name__)


class POApprovedConsumerRunner:
    """Run the Inventory approved-PO consumer in a background thread."""

    def __init__(self) -> None:
        self.consumer: POApprovedConsumer | None = None
        self._thread: Thread | None = None
        self._stopping = Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stopping.clear()

        def run_consumer() -> None:
            while not self._stopping.is_set():
                try:
                    self.consumer = POApprovedConsumer()
                    self.consumer.run()
                except Exception:
                    if not self._stopping.is_set():
                        logger.exception(
                            "Approved-PO consumer failed; restarting"
                        )
                        self._stopping.wait(2)

        self._thread = Thread(
            target=run_consumer,
            name="po-approved-consumer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()

        if self.consumer is not None:
            self.consumer.stop()

        if self._thread is not None:
            self._thread.join(timeout=10)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


inv_po_approved_consumer_runner = POApprovedConsumerRunner()
