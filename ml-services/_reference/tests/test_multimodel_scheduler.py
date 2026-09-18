import time

import pytest

from src.multimodel_scheduler import (
    MultiModelRetrainingScheduler,
)


def test_scheduler_rejects_invalid_interval():
    with pytest.raises(ValueError):
        MultiModelRetrainingScheduler(
            check_function=lambda: {},
            interval_seconds=0,
        )


def test_scheduler_can_start_and_stop():
    calls = []

    scheduler = MultiModelRetrainingScheduler(
        check_function=lambda: calls.append(True),
        interval_seconds=1,
    )

    scheduler.start()

    assert scheduler._thread is not None
    assert scheduler._thread.is_alive()

    scheduler.stop()

    assert scheduler._thread is None


def test_scheduler_does_not_start_twice():
    scheduler = MultiModelRetrainingScheduler(
        check_function=lambda: {},
        interval_seconds=60,
    )

    scheduler.start()

    first_thread = scheduler._thread

    scheduler.start()

    assert scheduler._thread is first_thread

    scheduler.stop()