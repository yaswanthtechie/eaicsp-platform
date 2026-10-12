
from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest
from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from app.services import kafka_consumer as kafka_consumer_module
from app.services.kafka_consumer import SupplierStatusChangedConsumer
from app.services.supplier_compliance_service import (
    SupplierComplianceService,
    suppliers,
)

pytestmark = pytest.mark.integration


def test_real_kafka_block_event_updates_sqlite_and_commits_offset(
    tmp_path,
    monkeypatch,
):
    bootstrap_servers = "localhost:9092"
    suffix = uuid.uuid4().hex[:12]
    topic = f"test-compliance-status-{suffix}"
    dlq_topic = f"test-compliance-dlq-{suffix}"
    group_id = f"supplier-portal-integration-{suffix}"
    supplier_id = f"TEST-{suffix.upper()}"

    admin = AdminClient({"bootstrap.servers": bootstrap_servers})
    producer = Producer({"bootstrap.servers": bootstrap_servers})

    isolated_service = SupplierComplianceService(
        db_path=tmp_path / "compliance_state.db"
    )
    monkeypatch.setattr(
        kafka_consumer_module,
        "supplier_compliance_service",
        isolated_service,
    )

    # The consumer expects the supplier identity to exist in the
    # application's supplier registry; identity comes from the Kafka key.
    suppliers[supplier_id] = {
        "supplier_id": supplier_id,
        "company_name": "Kafka Integration Test Supplier",
        "contact_name": "Integration Test",
        "email": f"{suffix}@example.test",
        "country": "India",
        "status": "active",
    }

    consumer_instance = None
    consumer_thread = None
    thread_errors: list[BaseException] = []
    stop_monitor = threading.Event()
    topic_names = [topic, dlq_topic]

    try:
        # Use real broker-created topics, not mocked Kafka clients.
        futures = admin.create_topics(
            [
                NewTopic(topic, num_partitions=1, replication_factor=1),
                NewTopic(dlq_topic, num_partitions=1, replication_factor=1),
            ],
            request_timeout=10,
        )
        for future in futures.values():
            future.result(timeout=15)

        event = {
            "event_id": f"event-{suffix}",
            "event_type": "compliance.supplier.status_changed",
            "event_version": 1,
            "occurred_at": "2026-10-12T00:00:00+00:00",
            "producer": "compliance-service",
            "payload": {
                "supplier_name": "Kafka Integration Test Supplier",
                "country": "India",
                "old_status": "CLEAR",
                "new_status": "BLOCK",
                "matched_list": ["OFAC"],
                "reason": "Integration test BLOCK event",
                "screening_run_id": f"run-{suffix}",
            },
        }

        delivery_result = []
        delivery_error = []

        def on_delivery(error, message):
            if error is not None:
                delivery_error.append(error)
            else:
                delivery_result.append(
                    (message.partition(), message.offset())
                )

        producer.produce(
            topic=topic,
            key=supplier_id,
            value=json.dumps(event),
            on_delivery=on_delivery,
        )
        assert producer.flush(timeout=15) == 0
        assert not delivery_error, f"Kafka publish failed: {delivery_error}"
        assert delivery_result, "Kafka did not confirm message delivery"

        produced_partition, produced_offset = delivery_result[0]

        consumer_instance = SupplierStatusChangedConsumer(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            group_id=group_id,
            dlq_topic=dlq_topic,
            auto_offset_reset="earliest",
        )

        def run_consumer():
            try:
                consumer_instance.run(poll_timeout=0.2)
            except BaseException as exc:
                thread_errors.append(exc)

        consumer_thread = threading.Thread(
            target=run_consumer,
            daemon=True,
        )
        consumer_thread.start()

        # Wait for the real consumer to apply the BLOCK event.
        deadline = time.monotonic() + 20
        status = None

        while time.monotonic() < deadline:
            status = isolated_service.get_access_status(supplier_id)

            if status is not None and getattr(status, "value", status) == "suspended":
                break

            if thread_errors:
                pytest.fail(f"Kafka consumer failed: {thread_errors[0]}")

            time.sleep(0.1)

        assert getattr(status, "value", status) == "suspended", (
            f"Expected supplier {supplier_id} to be suspended; "
            f"got {status!r}"
        )

        # Stop only after the state update. The consumer's run loop commits
        # the successfully processed message before it exits.
        consumer_instance.stop()
        consumer_thread.join(timeout=10)

        assert not consumer_thread.is_alive(), "Kafka consumer did not stop"
        assert not thread_errors, f"Kafka consumer failed: {thread_errors}"

        # Inspect the committed group offset using a real Kafka client.
        observer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "enable.auto.commit": False,
            }
        )
        try:
            committed = observer.committed(
                [TopicPartition(topic, produced_partition)],
                timeout=10,
            )
        finally:
            observer.close()

        assert committed, "Kafka returned no committed offset"
        committed_offset = committed[0].offset

        assert committed_offset >= 0, "Kafka offset was not committed"
        assert committed_offset > produced_offset, (
            f"Expected committed offset > message offset "
            f"({committed_offset=} {produced_offset=})"
        )

    finally:
        stop_monitor.set()

        if consumer_instance is not None:
            consumer_instance.stop()

        if consumer_thread is not None and consumer_thread.is_alive():
            consumer_thread.join(timeout=10)

        suppliers.pop(supplier_id, None)

        # Remove only the uniquely named integration-test topics.
        try:
            futures = admin.delete_topics(
                topic_names,
                request_timeout=10,
            )
            for future in futures.values():
                try:
                    future.result(timeout=15)
                except Exception:
                    pass
        except Exception:
            pass
