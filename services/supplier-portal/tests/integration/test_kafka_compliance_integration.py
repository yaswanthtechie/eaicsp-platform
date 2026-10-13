from __future__ import annotations

import json
import threading
import time
import uuid

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
    supplier_name = "Kafka Integration Test Supplier"

    admin = AdminClient(
        {"bootstrap.servers": bootstrap_servers}
    )
    producer = Producer(
        {"bootstrap.servers": bootstrap_servers}
    )

    isolated_service = SupplierComplianceService(
        db_path=tmp_path / "compliance_state.db"
    )
    monkeypatch.setattr(
        kafka_consumer_module,
        "supplier_compliance_service",
        isolated_service,
    )

    # Preserve any pre-existing registry entry and restore it in finally.
    previous_supplier = suppliers.get(supplier_id)

    # The consumer matches the supplier using payload.supplier_name,
    # not the Kafka key. The key is used for partitioning.
    suppliers[supplier_id] = {
        "supplier_id": supplier_id,
        "company_name": supplier_name,
        "contact_name": "Integration Test",
        "email": f"{suffix}@example.test",
        "country": "India",
        "status": "active",
    }

    consumer_instance = None
    consumer_thread = None
    thread_errors: list[BaseException] = []
    delivery_result = []
    delivery_error = []
    topic_names = [topic, dlq_topic]

    try:
        # Create uniquely named topics on the real Kafka broker.
        futures = admin.create_topics(
            [
                NewTopic(
                    topic,
                    num_partitions=1,
                    replication_factor=1,
                ),
                NewTopic(
                    dlq_topic,
                    num_partitions=1,
                    replication_factor=1,
                ),
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
                "supplier_name": supplier_name,
                "country": "India",
                "old_status": "CLEAR",
                "new_status": "BLOCK",
                "matched_list": ["OFAC"],
                "reason": "Integration test BLOCK event",
                "screening_run_id": f"run-{suffix}",
            },
        }

        def on_delivery(error, message):
            if error is not None:
                delivery_error.append(error)
            else:
                delivery_result.append(
                    (message.partition(), message.offset())
                )

        # Match the real producer: key by supplier_name.
        producer.produce(
            topic=topic,
            key="Kafka Integration Test Supplier",
            value=json.dumps(event),
            on_delivery=on_delivery,
        )

        assert producer.flush(timeout=15) == 0, (
            "Kafka producer still had messages pending after flush"
        )
        assert not delivery_error, (
            f"Kafka publish failed: {delivery_error}"
        )
        assert delivery_result, (
            "Kafka did not confirm message delivery"
        )

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
            if thread_errors:
                pytest.fail(
                    f"Kafka consumer failed: {thread_errors[0]}"
                )

            status = isolated_service.get_access_status(supplier_id)

            if (
                status is not None
                and getattr(status, "value", status) == "suspended"
            ):
                break

            time.sleep(0.1)

        assert getattr(status, "value", status) == "suspended", (
            f"Expected supplier {supplier_id} to be suspended; "
            f"got {status!r}"
        )

        # Stop only after processing the event. The consumer run loop
        # should commit the successfully processed message before exit.
        consumer_instance.stop()
        consumer_thread.join(timeout=10)

        assert not consumer_thread.is_alive(), (
            "Kafka consumer did not stop"
        )
        assert not thread_errors, (
            f"Kafka consumer failed: {thread_errors}"
        )

        # Verify the consumer group's committed offset using Kafka.
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

        assert committed_offset >= 0, (
            "Kafka offset was not committed"
        )
        assert committed_offset > produced_offset, (
            "Expected committed offset to be greater than the "
            f"message offset ({committed_offset=} {produced_offset=})"
        )

    finally:
        # Stop the consumer before deleting topics or restoring state.
        if consumer_instance is not None:
            consumer_instance.stop()

        if consumer_thread is not None and consumer_thread.is_alive():
            consumer_thread.join(timeout=10)

        # Restore the registry exactly as it was before this test.
        if previous_supplier is None:
            suppliers.pop(supplier_id, None)
        else:
            suppliers[supplier_id] = previous_supplier

        # Flush any remaining producer messages before cleanup.
        producer.flush(timeout=10)

        # Delete only this test's uniquely named topics.
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
