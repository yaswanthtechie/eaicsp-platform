from threading import Event, Thread
from unittest.mock import MagicMock, patch

import pytest

from app.services.inventory_goods_received_runner import (
    InventoryGoodsReceivedRunner,
)


def test_start_creates_and_starts_background_thread():
    runner = InventoryGoodsReceivedRunner()

    with patch.object(Thread, "start") as start_thread:
        runner.start()

    assert runner._thread is not None
    assert runner._thread.name == (
        "supplier-portal-goods-received-consumer"
    )
    assert runner._thread.daemon is True
    start_thread.assert_called_once()


def test_start_does_not_start_duplicate_thread():
    runner = InventoryGoodsReceivedRunner()
    runner._thread = MagicMock()
    runner._thread.is_alive.return_value = True

    with patch.object(Thread, "start") as start_thread:
        runner.start()

    start_thread.assert_not_called()


def test_is_alive_returns_false_without_thread():
    runner = InventoryGoodsReceivedRunner()

    assert runner.is_alive() is False


def test_is_alive_reflects_thread_state():
    runner = InventoryGoodsReceivedRunner()
    runner._thread = MagicMock()
    runner._thread.is_alive.return_value = True

    assert runner.is_alive() is True

    runner._thread.is_alive.return_value = False
    assert runner.is_alive() is False


def test_run_starts_consumer_and_clears_reference_after_exit():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()

    with patch(
        "app.services.inventory_goods_received_runner."
        "InventoryGoodsReceivedConsumer",
        return_value=consumer,
    ):
        runner._run()

    consumer.run.assert_called_once()
    assert runner.consumer is None


def test_run_stops_consumer_if_shutdown_begins_during_creation():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()

    with (
        patch(
            "app.services.inventory_goods_received_runner."
            "InventoryGoodsReceivedConsumer",
            return_value=consumer,
        ),
        patch.object(runner._stopping, "is_set", side_effect=[False, True]),
    ):
        runner._run()

    consumer.stop.assert_called_once()
    consumer.run.assert_not_called()
    assert runner.consumer is None


def test_run_retries_after_consumer_crash():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()
    consumer.run.side_effect = RuntimeError("Kafka unavailable")

    with (
        patch(
            "app.services.inventory_goods_received_runner."
            "InventoryGoodsReceivedConsumer",
            return_value=consumer,
        ),
        patch.object(runner._stopping, "is_set", return_value=False),
        patch.object(runner._stopping, "wait", return_value=True) as wait,
    ):
        runner._run()

    wait.assert_called_once_with(5)
    assert runner.consumer is None


def test_stop_stops_consumer_and_joins_thread():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()
    thread = MagicMock()
    thread.is_alive.return_value = False

    runner.consumer = consumer
    runner._thread = thread

    runner.stop()

    assert runner._stopping.is_set()
    consumer.stop.assert_called_once()
    thread.join.assert_called_once_with(timeout=10)
    assert runner.consumer is None
    assert runner._thread is None


def test_stop_handles_consumer_stop_exception():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()
    consumer.stop.side_effect = RuntimeError("stop failed")
    thread = MagicMock()
    thread.is_alive.return_value = False

    runner.consumer = consumer
    runner._thread = thread

    runner.stop()

    thread.join.assert_called_once_with(timeout=10)
    assert runner.consumer is None
    assert runner._thread is None


def test_stop_retains_reference_if_thread_is_still_alive():
    runner = InventoryGoodsReceivedRunner()
    consumer = MagicMock()
    thread = MagicMock()
    thread.is_alive.return_value = True

    runner.consumer = consumer
    runner._thread = thread

    runner.stop()

    assert runner._thread is thread
    assert runner.consumer is consumer
