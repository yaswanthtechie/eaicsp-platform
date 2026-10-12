
from __future__ import annotations

import logging
from threading import Event
from unittest.mock import Mock, patch

from app.services.kafka_consumer_runner import KafkaConsumerRunner


CONSUMER_FACTORY = (
    "app.services.kafka_consumer_runner.SupplierStatusChangedConsumer"
)


def test_runner_restarts_after_consumer_crashes():
    runner = KafkaConsumerRunner()
    recovered_consumer = Mock()

    with (
        patch(
            CONSUMER_FACTORY,
            side_effect=[
                RuntimeError("Kafka crashed"),
                recovered_consumer,
            ],
        ) as factory,
        patch.object(
            runner._stopping,
            "wait",
            side_effect=[False, True],
        ),
    ):
        runner._run()

    assert factory.call_count == 2
    recovered_consumer.run.assert_called_once()


def test_runner_retries_when_consumer_constructor_fails():
    runner = KafkaConsumerRunner()
    recovered_consumer = Mock()

    with (
        patch(
            CONSUMER_FACTORY,
            side_effect=[
                RuntimeError("Kafka initialization failed"),
                recovered_consumer,
            ],
        ) as factory,
        patch.object(
            runner._stopping,
            "wait",
            side_effect=[False, True],
        ),
    ):
        runner._run()

    assert factory.call_count == 2
    recovered_consumer.run.assert_called_once()


def test_constructor_failure_does_not_raise_unbound_local_error():
    runner = KafkaConsumerRunner()

    with (
        patch(
            CONSUMER_FACTORY,
            side_effect=RuntimeError("Broker unavailable"),
        ),
        patch.object(
            runner._stopping,
            "wait",
            return_value=True,
        ),
    ):
        runner._run()

    assert runner.consumer is None


def test_normal_consumer_return_does_not_restart():
    runner = KafkaConsumerRunner()
    consumer = Mock()

    with (
        patch(CONSUMER_FACTORY, return_value=consumer) as factory,
        patch.object(runner._stopping, "wait") as wait,
    ):
        runner._run()

    factory.assert_called_once()
    consumer.run.assert_called_once()
    wait.assert_not_called()


def test_runner_does_not_start_if_already_stopping():
    runner = KafkaConsumerRunner()
    runner._stopping.set()

    with patch(CONSUMER_FACTORY) as factory:
        runner._run()

    factory.assert_not_called()


def test_stop_during_restart_delay_prevents_another_attempt():
    runner = KafkaConsumerRunner()

    def cancel_restart(_timeout):
        runner._stopping.set()
        return True

    with (
        patch(
            CONSUMER_FACTORY,
            side_effect=RuntimeError("Kafka unavailable"),
        ) as factory,
        patch.object(
            runner._stopping,
            "wait",
            side_effect=cancel_restart,
        ),
    ):
        runner._run()

    factory.assert_called_once()


def test_runner_clears_consumer_reference_after_crash():
    runner = KafkaConsumerRunner()
    failed_consumer = Mock()

    def stop_retry(_timeout):
        assert runner.consumer is None
        return True

    failed_consumer.run.side_effect = RuntimeError("Consumer crashed")

    with (
        patch(CONSUMER_FACTORY, return_value=failed_consumer),
        patch.object(
            runner._stopping,
            "wait",
            side_effect=stop_retry,
        ),
    ):
        runner._run()

    assert runner.consumer is None


def test_start_creates_background_thread():
    runner = KafkaConsumerRunner()
    started = Event()
    release = Event()
    consumer = Mock()

    def blocking_run():
        started.set()
        release.wait(timeout=3)

    consumer.run.side_effect = blocking_run

    with patch(CONSUMER_FACTORY, return_value=consumer):
        try:
            runner.start()
            assert started.wait(timeout=2)
            assert runner.is_alive()
        finally:
            release.set()
            runner.stop()

    assert not runner.is_alive()


def test_start_does_not_create_duplicate_thread():
    runner = KafkaConsumerRunner()
    started = Event()
    release = Event()
    consumer = Mock()

    def blocking_run():
        started.set()
        release.wait(timeout=3)

    consumer.run.side_effect = blocking_run

    with patch(CONSUMER_FACTORY, return_value=consumer) as factory:
        try:
            runner.start()
            assert started.wait(timeout=2)

            original_thread = runner._thread
            runner.start()

            assert runner._thread is original_thread
            factory.assert_called_once()
        finally:
            release.set()
            runner.stop()


def test_stop_stops_consumer_and_joins_thread():
    runner = KafkaConsumerRunner()
    started = Event()
    release = Event()
    consumer = Mock()

    def blocking_run():
        started.set()
        release.wait(timeout=3)

    def stop_consumer():
        release.set()

    consumer.run.side_effect = blocking_run
    consumer.stop.side_effect = stop_consumer

    with patch(CONSUMER_FACTORY, return_value=consumer):
        runner.start()
        assert started.wait(timeout=2)
        runner.stop()

    consumer.stop.assert_called_once()
    assert not runner.is_alive()
    assert runner._thread is None
    assert runner.consumer is None


def test_stop_without_started_thread_is_safe():
    runner = KafkaConsumerRunner()

    runner.stop()

    assert runner._stopping.is_set()
    assert not runner.is_alive()


def test_stop_handles_consumer_stop_exception(caplog):
    runner = KafkaConsumerRunner()
    started = Event()
    release = Event()
    consumer = Mock()

    def blocking_run():
        started.set()
        release.wait(timeout=3)

    def fail_to_stop():
        release.set()
        raise RuntimeError("Stop failed")

    consumer.run.side_effect = blocking_run
    consumer.stop.side_effect = fail_to_stop

    with (
        patch(CONSUMER_FACTORY, return_value=consumer),
        caplog.at_level(logging.ERROR),
    ):
        runner.start()
        assert started.wait(timeout=2)
        runner.stop()

    consumer.stop.assert_called_once()
    assert "Error while stopping the Kafka consumer." in caplog.text
    assert not runner.is_alive()


def test_stop_logs_when_thread_does_not_exit_within_timeout(caplog):
    runner = KafkaConsumerRunner()
    fake_thread = Mock()
    fake_thread.is_alive.return_value = True
    consumer = Mock()

    runner._thread = fake_thread
    runner.consumer = consumer

    with caplog.at_level(logging.WARNING):
        runner.stop()

    consumer.stop.assert_called_once()
    fake_thread.join.assert_called_once_with(timeout=10)
    assert "did not stop within timeout" in caplog.text
    assert runner._thread is fake_thread


def test_is_alive_returns_false_without_thread():
    runner = KafkaConsumerRunner()

    assert runner.is_alive() is False


def test_is_alive_returns_true_when_thread_is_alive():
    runner = KafkaConsumerRunner()
    fake_thread = Mock()
    fake_thread.is_alive.return_value = True
    runner._thread = fake_thread

    assert runner.is_alive() is True


def test_runner_logs_crash_before_retry(caplog):
    runner = KafkaConsumerRunner()

    with (
        patch(
            CONSUMER_FACTORY,
            side_effect=RuntimeError("Broker unavailable"),
        ),
        patch.object(
            runner._stopping,
            "wait",
            return_value=True,
        ),
        caplog.at_level(logging.ERROR),
    ):
        runner._run()

    assert "Kafka consumer crashed; restarting in 5 seconds." in caplog.text
