from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.events import SupplierStatusChangedEvent
from app.services.kafka_consumer import (
    KafkaDeadLetterError,
    KafkaMessageValidationError,
    SupplierStatusChangedConsumer,
)
from app.services.supplier_compliance_service import (
    SupplierComplianceStatus,
    SupplierNotFoundError,
    suppliers,
)


TOPIC = "compliance.supplier.status_changed"
DLQ_TOPIC = "compliance.supplier.status_changed.dlq"
GROUP_ID = "supplier-portal-service"


def make_event(
    *,
    event_id: str = "event-001",
    supplier_id: str = "SUP001",
    old_status: str = "CLEAR",
    new_status: str = "BLOCK",
    occurred_at: str = "2026-10-08T09:00:00+00:00",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": TOPIC,
        "event_version": 1,
        "occurred_at": occurred_at,
        "producer": "compliance",
        "payload": {
            "supplier_id": supplier_id,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": ["OFAC"] if new_status == "BLOCK" else [],
            "reason": "Compliance status changed",
        },
    }


def make_message(
    event: dict | str | None,
    *,
    key: str = "SUP001",
    topic: str = TOPIC,
    partition: int = 0,
    offset: int = 1,
):
    message = MagicMock()

    if isinstance(event, dict):
        value = json.dumps(event).encode("utf-8")
    elif isinstance(event, str):
        value = event.encode("utf-8")
    else:
        value = None

    message.value.return_value = value
    message.key.return_value = key.encode("utf-8")
    message.topic.return_value = topic
    message.partition.return_value = partition
    message.offset.return_value = offset
    message.error.return_value = None

    return message


@pytest.fixture
def consumer():
    with (
        patch("app.services.kafka_consumer.Consumer") as mock_consumer,
        patch("app.services.kafka_consumer.Producer") as mock_producer,
    ):
        mock_consumer_instance = mock_consumer.return_value
        mock_producer_instance = mock_producer.return_value

        # IMPORTANT: flush() must return an integer
        mock_producer_instance.flush.return_value = 0

        instance = SupplierStatusChangedConsumer(
            bootstrap_servers="localhost:9092",
            topic=TOPIC,
            group_id=GROUP_ID,
            dlq_topic=DLQ_TOPIC,
            auto_offset_reset="earliest",
        )

    return instance


@pytest.fixture(autouse=True)
def clear_supplier_state():
    """
    Keep supplier and compliance-service state isolated between tests.

    Supplier records are in-memory and the compliance service also keeps
    idempotency, ordering, and audit state in memory.
    """
    from app.services.supplier_compliance_service import (
        supplier_compliance_service,
    )

    suppliers.clear()

    suppliers["SUP001"] = {
        "supplier_id": "SUP001",
        "company_name": "ABC Supplies",
        "contact_name": "Supplier User",
        "email": "supplier@company.com",
        "country": "India",
        "status": "active",
    }

    suppliers["SUP002"] = {
        "supplier_id": "SUP002",
        "company_name": "XYZ Supplies",
        "contact_name": "Supplier B",
        "email": "supplierb@example.com",
        "country": "India",
        "status": "active",
    }

    # Reset the in-memory compliance state used by the singleton.
    supplier_compliance_service._processed_event_ids.clear()
    supplier_compliance_service._latest_event_times.clear()
    supplier_compliance_service._audit_history.clear()

    yield

    suppliers.clear()

    supplier_compliance_service._processed_event_ids.clear()
    supplier_compliance_service._latest_event_times.clear()
    supplier_compliance_service._audit_history.clear()


def test_consumer_uses_supplier_portal_consumer_group(consumer):
    assert consumer.group_id == GROUP_ID
    assert consumer.topic == TOPIC
    assert consumer.dlq_topic == DLQ_TOPIC


def test_consumer_disables_auto_commit(consumer):
    config = consumer.consumer

    assert config is not None


def test_block_event_suspends_supplier(consumer):
    event = make_event(
        event_id="event-block-001",
        new_status="BLOCK",
    )

    message = make_message(event)

    assert consumer.process_message(message) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )


def test_review_event_sets_needs_review(consumer):
    event = make_event(
        event_id="event-review-001",
        old_status="CLEAR",
        new_status="REVIEW",
    )

    message = make_message(event)

    assert consumer.process_message(message) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.needs_review.value
    )


def test_clear_event_restores_access(consumer):
    suppliers["SUP001"]["compliance_access_status"] = (
        SupplierComplianceStatus.suspended.value
    )

    event = make_event(
        event_id="event-clear-001",
        old_status="BLOCK",
        new_status="CLEAR",
    )

    message = make_message(event)

    assert consumer.process_message(message) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.cleared.value
    )


def test_duplicate_event_is_idempotent(consumer):
    event = make_event(
        event_id="event-duplicate-001",
        new_status="BLOCK",
    )

    first_message = make_message(
        event,
        offset=10,
    )

    second_message = make_message(
        event,
        offset=11,
    )

    assert consumer.process_message(first_message) is True
    assert consumer.process_message(second_message) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )


def test_out_of_order_event_is_ignored(consumer):
    newer_event = make_event(
        event_id="event-newer-001",
        new_status="BLOCK",
        occurred_at="2026-10-08T10:00:00+00:00",
    )

    older_event = make_event(
        event_id="event-older-001",
        old_status="CLEAR",
        new_status="REVIEW",
        occurred_at="2026-10-08T09:00:00+00:00",
    )

    assert consumer.process_message(
        make_message(newer_event)
    )

    assert consumer.process_message(
        make_message(older_event)
    )

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )


def test_invalid_json_raises_validation_error(consumer):
    message = make_message(
        '{"this-is": "not-a-valid-event"}'
    )

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_invalid_json_syntax_raises_validation_error(consumer):
    message = make_message(
        '{"event_id": '
    )

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_empty_message_raises_validation_error(consumer):
    message = make_message(None)

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_wrong_event_type_is_rejected(consumer):
    event = make_event()
    event["event_type"] = "some.other.event"

    message = make_message(event)

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_unsupported_event_version_is_rejected(consumer):
    event = make_event()
    event["event_version"] = 99

    message = make_message(event)

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_unknown_supplier_is_rejected(consumer):
    event = make_event(
        supplier_id="SUP999",
    )

    message = make_message(
        event,
        key="SUP999",
    )

    with pytest.raises(SupplierNotFoundError):
        consumer.process_message(message)


def test_offset_committed_after_successful_processing(consumer):
    event = make_event(
        event_id="event-commit-001",
        new_status="BLOCK",
    )

    message = make_message(event)

    consumer.process_message(message)
    consumer._commit(message)

    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_offset_is_not_committed_when_processing_fails(consumer):
    event = make_event(
        event_id="event-failure-001",
        supplier_id="SUP999",
    )

    message = make_message(
        event,
        key="SUP999",
    )

    with pytest.raises(SupplierNotFoundError):
        consumer.process_message(message)

    consumer.consumer.commit.assert_not_called()


def test_dlq_contains_original_message(consumer):
    event = make_event(
        event_id="event-dlq-001",
    )

    message = make_message(
        event,
        offset=42,
    )

    consumer._publish_to_dlq(
        message=message,
        error_reason="Invalid event",
    )

    producer = consumer._dlq_producer

    producer.produce.assert_called_once()

    call = producer.produce.call_args

    assert call.kwargs["topic"] == DLQ_TOPIC

    dlq_payload = json.loads(
        call.kwargs["value"]
    )

    assert dlq_payload["error_reason"] == "Invalid event"
    assert dlq_payload["source_topic"] == TOPIC
    assert dlq_payload["source_partition"] == 0
    assert dlq_payload["source_offset"] == 42


def test_dlq_failure_raises_error(consumer):
    producer = consumer._dlq_producer

    producer.flush.return_value = 1

    message = make_message(
        make_event(
            event_id="event-dlq-failure-001",
        )
    )

    with pytest.raises(KafkaDeadLetterError):
        consumer._publish_to_dlq(
            message=message,
            error_reason="Invalid event",
        )


def test_successful_dlq_processing_allows_commit(consumer):
    event = make_event(
        event_id="event-dlq-commit-001",
    )

    message = make_message(event)

    consumer._publish_to_dlq(
        message=message,
        error_reason="Invalid event",
    )

    consumer._commit(message)

    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_dlq_failure_does_not_commit_original_message(consumer):
    event = make_event(
        event_id="event-dlq-no-commit-001",
    )

    message = make_message(event)

    consumer._publish_to_dlq = MagicMock(
        side_effect=KafkaDeadLetterError(
            "DLQ unavailable"
        )
    )

    with pytest.raises(KafkaDeadLetterError):
        consumer._publish_to_dlq(
            message=message,
            error_reason="Invalid event",
        )

    consumer.consumer.commit.assert_not_called()


def test_audit_is_created_for_accepted_event(consumer):
    event = make_event(
        event_id="event-audit-001",
        new_status="BLOCK",
    )

    message = make_message(event)

    consumer.process_message(message)

    from app.services.supplier_compliance_service import (
        supplier_compliance_service,
    )

    audit = supplier_compliance_service.get_audit_history(
        "SUP001"
    )

    assert len(audit) == 1
    assert audit[0].event_id == "event-audit-001"
    assert audit[0].supplier_id == "SUP001"
    assert audit[0].new_status == (
        SupplierComplianceStatus.suspended
    )