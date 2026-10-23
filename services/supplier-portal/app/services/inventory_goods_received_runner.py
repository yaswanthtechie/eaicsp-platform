
import logging
from threading import Event, Thread

from app.services.inventory_goods_received_consumer import (
    InventoryGoodsReceivedConsumer,
)

logger = logging.getLogger(__name__)


class InventoryGoodsReceivedRunner:
    """Run the Inventory goods receipt consumer in a background thread."""

    def __init__(self) -> None:
        self.consumer: InventoryGoodsReceivedConsumer | None = None
        self._thread: Thread | None = None
        self._stopping = Event()

    def start(self) -> None:
        if self.is_alive():
            logger.warning("Goods receipt consumer is already running.")
            return

        self._stopping.clear()
        self._thread = Thread(
            target=self._run,
            name="supplier-portal-goods-received-consumer",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stopping.is_set():
            consumer = None
            try:
                consumer = InventoryGoodsReceivedConsumer()
                self.consumer = consumer

                if self._stopping.is_set():
                    consumer.stop()
                    return

                consumer.run()
                return
            except Exception:
                if self._stopping.is_set():
                    return
                logger.exception(
                    "Goods receipt consumer crashed; retrying in 5 seconds."
                )
            finally:
                if self.consumer is consumer:
                    self.consumer = None

            if self._stopping.wait(5):
                return

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self) -> None:
        self._stopping.set()

        consumer = self.consumer
        if consumer is not None:
            try:
                consumer.stop()
            except Exception:
                logger.exception("Error stopping goods receipt consumer.")

        thread = self._thread
        if thread is not None:
            thread.join(timeout=10)

        if thread is None or not thread.is_alive():
            self._thread = None
            self.consumer = None


inventory_goods_received_runner = InventoryGoodsReceivedRunner()
