"""
Milestone 3 scheduled multi-model retraining loop.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class MultiModelRetrainingScheduler:
    """
    Periodically executes the multi-model retraining orchestrator.

    Disabled by default for safety.
    """

    def __init__(
        self,
        check_function: Callable[[], dict],
        interval_seconds: int = 3600,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than 0."
            )

        self.check_function = check_function
        self.interval_seconds = interval_seconds

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background scheduler."""

        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="multi-model-retraining-scheduler",
            daemon=True,
        )

        self._thread.start()

        logger.info(
            "Multi-model retraining scheduler started "
            "(interval=%s seconds)",
            self.interval_seconds,
        )

    def _run(self) -> None:
        while not self._stop_event.wait(
            self.interval_seconds
        ):
            try:
                result = self.check_function()

                logger.info(
                    "Multi-model scheduled retraining result: %s",
                    result,
                )

            except Exception:
                logger.exception(
                    "Multi-model scheduled retraining failed"
                )

    def stop(self) -> None:
        """Stop the scheduler."""

        self._stop_event.set()

        if (
            self._thread is not None
            and self._thread.is_alive()
        ):
            self._thread.join(timeout=2)

        self._thread = None