import logging
import threading
from typing import Callable

from src.config import RETRAINING_INTERVAL_SECONDS


logger = logging.getLogger(__name__)


class RetrainingScheduler:

    def __init__(
        self,
        check_function: Callable,
        interval_seconds=RETRAINING_INTERVAL_SECONDS,
    ):

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than 0"
            )

        self.check_function = check_function
        self.interval_seconds = interval_seconds

        self._stop_event = threading.Event()
        self._thread = None

    def run_once(self):

        logger.info(
            "Running scheduled retraining check"
        )

        try:

            result = self.check_function()

            logger.info(
                "Scheduled result: %s",
                result,
            )

            return result

        except Exception as exc:

            logger.exception(
                "Scheduled retraining failed"
            )

            return {
                "status": "error",
                "error": str(exc),
            }

    def _loop(self):

        logger.info(
            "R5 RETRAINING SCHEDULER STARTED "
            "(interval=%s seconds)",
            self.interval_seconds,
        )

        while not self._stop_event.is_set():

            self.run_once()

            self._stop_event.wait(
                self.interval_seconds
            )

        logger.info(
            "R5 RETRAINING SCHEDULER STOPPED"
        )

    def start(self):

        if (
            self._thread
            and self._thread.is_alive()
        ):
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="r5-retraining-scheduler",
        )

        self._thread.start()

    def stop(self):

        self._stop_event.set()

        if (
            self._thread
            and self._thread.is_alive()
        ):
            self._thread.join(
                timeout=5
            )

        self._thread = None