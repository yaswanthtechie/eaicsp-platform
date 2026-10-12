"""
Kafka streaming validation (Round 12-13, Milestone 2).

Reads records from the input topic, validates each one with validate_row(),
sends good records to the .valid topic and bad ones to the .dlq topic with
the failing rules and a human-readable reason for each.

Delivery guarantee: AT-LEAST-ONCE.
- The input offset is committed only AFTER the broker has confirmed the
  write to .valid or .dlq. If that write fails, the offset is NOT committed
  and the consumer seeks back to re-read the same record, so nothing is lost.
- If the consumer dies after the write but before the commit, the record is
  processed again on restart and written a second time. Downstream must
  de-duplicate by transaction_id. Kafka's idempotent producer does NOT
  prevent this: it only removes its own retries within one session.

Observability: every record updates the Prometheus metrics, and every
STREAM_PERSIST_EVERY records (plus once on shutdown) a run summary is saved
to Postgres.
"""

import json
import logging
import os
import time

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Producer,
    TopicPartition,
)

from data_validator.metrics import (
    increment_dlq_count,
    record_persist_failure,
    start_metrics_server,
    update_batch_metrics,
)
from data_validator.postgres_client import (
    PersistenceError,
    persist_validation_result,
)
from data_validator.validator import DataValidator, ValidationResult

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 10.0
RETRY_BACKOFF_SECONDS = 2.0


def load_settings() -> dict:
    """Read every setting from the environment (see .env.example)."""
    env = os.environ.get
    return {
        "bootstrap_servers": env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "group_id": env("KAFKA_GROUP_ID", "validation-group-v1"),
        "input_topic": env("KAFKA_INPUT_TOPIC", "sales.raw"),
        "valid_topic": env("KAFKA_VALID_TOPIC", "sales.valid"),
        "dlq_topic": env("KAFKA_DLQ_TOPIC", "sales.dlq"),
        "config_path": env("VALIDATOR_CONFIG", "configs/dev/sales_rules.yaml"),
        "persist_every": int(env("STREAM_PERSIST_EVERY", "100")),
        "metrics_port": int(env("METRICS_PORT", "8000")),
    }


class StreamingValidator:
    """One consumer loop. Kafka clients are passed in so tests can fake them."""

    def __init__(
        self,
        validator,
        consumer,
        producer,
        settings: dict,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        self.validator = validator
        self.consumer = consumer
        self.producer = producer
        self.settings = settings
        self.clock = clock
        self.sleep = sleep

        self.rule_names = [rule.name for rule in validator.rules]
        self.rule_descriptions = {
            rule.name: (rule.description or rule.name)
            for rule in validator.rules
        }

        self.started_at = clock()
        self.total_processed = 0
        self.total_failed = 0
        self._reset_window()

    # ------------------------------------------------------------------
    # Routing (pure: decides where a record goes, never raises)
    # ------------------------------------------------------------------

    def _dlq_value(self, original, failed_rules, reasons, warnings=None) -> bytes:
        payload = {
            "original_record": original,
            "failed_rules": failed_rules,
            "reasons": reasons,
            "warnings": warnings or [],
        }
        return json.dumps(payload, default=str).encode("utf-8")

    def route(self, raw_payload: str):
        """Return (topic, value_bytes, passed) for one raw record."""
        dlq = self.settings["dlq_topic"]

        try:
            record = json.loads(raw_payload)
        except json.JSONDecodeError:
            return dlq, self._dlq_value(
                raw_payload,
                ["json_parse_error"],
                {"json_parse_error": "The message is not valid JSON."},
            ), False

        if not isinstance(record, dict):
            return dlq, self._dlq_value(
                record,
                ["not_a_json_object"],
                {"not_a_json_object": "The message must be a JSON object."},
            ), False

        try:
            result = self.validator.validate_row(record)
        except Exception as exc:  # a bad record must never stop the consumer
            logger.exception("Validator crashed on a record; routing to DLQ")
            return dlq, self._dlq_value(
                record,
                ["validator_exception"],
                {"validator_exception": f"{type(exc).__name__}: {exc}"},
            ), False

        if result.passed:
            return self.settings["valid_topic"], raw_payload.encode("utf-8"), True

        failed = list(result.errors)
        reasons = {rule: self.rule_descriptions.get(rule, rule) for rule in failed}

        # A rule that crashed never checked the row; say so explicitly.
        for skipped in result.skipped_rules:
            rule = skipped.get("rule", "unknown_rule")
            if rule not in reasons:
                failed.append(rule)
            reasons[rule] = f"Rule could not run: {skipped.get('reason', 'unknown error')}"

        return dlq, self._dlq_value(record, failed, reasons, result.warnings), False

    # ------------------------------------------------------------------
    # Delivery: only commit after the broker confirms the write
    # ------------------------------------------------------------------

    def _produce_and_confirm(self, topic: str, value: bytes) -> bool:
        errors = []

        def on_delivery(err, _msg):
            if err is not None:
                errors.append(err)

        try:
            self.producer.produce(topic, value, on_delivery=on_delivery)
            undelivered = self.producer.flush(DELIVERY_TIMEOUT_SECONDS)
        except (BufferError, KafkaException) as exc:
            logger.error("Could not write to %s: %s", topic, exc)
            return False

        if undelivered or errors:
            logger.error(
                "Write to %s not confirmed (undelivered=%s, errors=%s)",
                topic, undelivered, errors,
            )
            return False

        return True

    def handle_message(self, msg) -> bool:
        """Process one message. Returns True only if its offset was committed."""
        raw = (msg.value() or b"").decode("utf-8", errors="replace")
        topic, value, passed = self.route(raw)

        if not self._produce_and_confirm(topic, value):
            # Do NOT commit. Re-read this same record after a pause, so a
            # Kafka outage delays records instead of losing them.
            self.consumer.seek(
                TopicPartition(msg.topic(), msg.partition(), msg.offset())
            )
            self.sleep(RETRY_BACKOFF_SECONDS)
            return False

        try:
            self.consumer.commit(message=msg, asynchronous=False)
        except KafkaException as exc:
            # The record IS safely written; if the commit is lost it will be
            # processed again after a restart (at-least-once).
            logger.error("Offset commit failed (record may be re-processed): %s", exc)

        self._record(passed)
        return True

    # ------------------------------------------------------------------
    # Metrics and run persistence
    # ------------------------------------------------------------------

    def _reset_window(self):
        self.window_started_at = self.clock()
        self.window_processed = 0
        self.window_failed = 0

    def _record(self, passed: bool):
        self.total_processed += 1
        self.window_processed += 1

        if not passed:
            self.total_failed += 1
            self.window_failed += 1
            increment_dlq_count()

        update_batch_metrics(
            total_rows=self.total_processed,
            affected_rows=self.total_failed,
            duration_seconds=self.clock() - self.started_at,
        )

        if self.window_processed >= self.settings["persist_every"]:
            self.flush_run_summary()

    def flush_run_summary(self):
        """Save one 'stream' run for the records since the last save."""
        if self.window_processed == 0:
            return None

        result = ValidationResult(
            config_version=getattr(self.validator, "version", "unknown"),
            passed=self.window_failed == 0,
            batch_rejected=False,
            total_rows=self.window_processed,
            total_rows_affected=self.window_failed,
            sla_breached=False,
            evaluated_rules=self.rule_names,
        )
        duration = self.clock() - self.window_started_at

        try:
            run_id = persist_validation_result(
                dataset_name=self.settings["input_topic"],
                result=result,
                duration_seconds=duration,
                mode="stream",
            )
        except PersistenceError as exc:
            # Streaming must keep going; the failure is visible in logs and
            # in validation_persist_failures_total on /metrics.
            logger.error("Stream run summary NOT saved: %s", exc)
            record_persist_failure()
            run_id = None

        self._reset_window()
        return run_id

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    def run(self):
        self.consumer.subscribe([self.settings["input_topic"]])
        logger.info("Listening to '%s'...", self.settings["input_topic"])

        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Consumer error: %s", msg.error())
                    continue
                self.handle_message(msg)
        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
        finally:
            self.flush_run_summary()
            self.consumer.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    settings = load_settings()

    validator = DataValidator.from_config(settings["config_path"])
    start_metrics_server(settings["metrics_port"])

    consumer = Consumer({
        "bootstrap.servers": settings["bootstrap_servers"],
        "group.id": settings["group_id"],
        "auto.offset.reset": "earliest",
        # Commit manually, only after the output write is confirmed.
        "enable.auto.commit": False,
    })
    producer = Producer({
        "bootstrap.servers": settings["bootstrap_servers"],
        # Removes duplicates from the producer's OWN retries only.
        "enable.idempotence": True,
    })

    StreamingValidator(validator, consumer, producer, settings).run()


if __name__ == "__main__":
    main()