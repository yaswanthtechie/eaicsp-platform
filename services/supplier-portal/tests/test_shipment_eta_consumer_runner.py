from threading import Event
from unittest.mock import Mock, patch

from app.services.shipment_eta_consumer_runner import (
    ShipmentETAConsumerRunner,
)


def test_runner_starts_consumer_in_background_thread():
    runner = ShipmentETAConsumerRunner()

    with patch(
        "app.services.shipment_eta_consumer_runner.threading.Thread"
    ) as thread_class:
        thread = Mock()
        thread.is_alive.return_value = False
        thread_class.return_value = thread

        runner.start()

        thread_class.assert_called_once()
        thread.start.assert_called_once()


def test_runner_does_not_start_duplicate_thread():
    runner = ShipmentETAConsumerRunner()

    existing_thread = Mock()
    existing_thread.is_alive.return_value = True
    runner._thread = existing_thread

    with patch(
        "app.services.shipment_eta_consumer_runner.threading.Thread"
    ) as thread_class:
        runner.start()

        thread_class.assert_not_called()


def test_runner_stop_signals_consumer_and_joins_thread():
    runner = ShipmentETAConsumerRunner()

    consumer = Mock()
    thread = Mock()

    runner._consumer = consumer
    runner._thread = thread

    runner.stop()

    consumer.stop.assert_called_once()
    thread.join.assert_called_once_with(timeout=10)


def test_runner_run_creates_and_runs_consumer():
    runner = ShipmentETAConsumerRunner()
    stop_event = Event()
    runner._stop_event = stop_event

    with patch(
        "app.services.shipment_eta_consumer_runner.ShipmentETAConsumer"
    ) as consumer_class:
        consumer = consumer_class.return_value
        consumer.run.side_effect = stop_event.set

        runner._run()

        consumer_class.assert_called_once()
        consumer.run.assert_called_once()


def test_runner_restarts_after_consumer_failure():
    runner = ShipmentETAConsumerRunner()
    stop_event = Event()
    runner._stop_event = stop_event

    with (
        patch(
            "app.services.shipment_eta_consumer_runner.ShipmentETAConsumer"
        ) as consumer_class,
        patch.object(stop_event, "wait") as wait_mock,
    ):
        first_consumer = Mock()
        second_consumer = Mock()

        consumer_class.side_effect = [
            first_consumer,
            second_consumer,
        ]

        first_consumer.run.side_effect = RuntimeError(
            "Kafka connection failed"
        )

        second_consumer.run.side_effect = stop_event.set

        runner._run()

        assert consumer_class.call_count == 2
        first_consumer.run.assert_called_once()
        second_consumer.run.assert_called_once()
        wait_mock.assert_called_once_with(5)

