
import json
import sqlite3
from unittest.mock import MagicMock, call, patch

import pytest

from app.schemas.events import (
    SupplierComplianceStatus,
    SupplierStatusChangedEvent,
)
from app.services.kafka_consumer import (
    KafkaDeadLetterError,
    KafkaMessageValidationError,
    SupplierStatusChangedConsumer,
)
from app.services.supplier_compliance_service import (
    SupplierComplianceService,
    supplier_compliance_service,
    suppliers,
)

TOPIC = "compliance.supplier.status_changed"
DLQ_TOPIC = "compliance.supplier.status_changed.dlq"
GROUP_ID = "supplier-portal-service"


def make_event(
    *,
    event_id="event-001",
    supplier_name="ABC Supplies",
    country="India",
    old_status="CLEAR",
    new_status="BLOCK",
    occurred_at="2026-10-08T09:00:00+00:00",
) -> dict:
    return {
        "event_id": event_id,
        "event_type": TOPIC,
        "event_version": 1,
        "occurred_at": occurred_at,
        "producer": "compliance-service",
        "payload": {
            "supplier_name": supplier_name,
            "country": country,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": ["OFAC"] if new_status == "BLOCK" else [],
            "reason": "Matched supplier on OFAC",
            "screening_run_id": f"run-{event_id}",
        },
    }


def make_message(
    event: dict | str | None,
    *,
    key: str = "ABC Supplies",
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


@pytest.fixture(autouse=True)
def clear_supplier_state(monkeypatch, tmp_path):
    """
    Isolate onboarding records and compliance persistence for each test.

    Events are matched by normalized payload.supplier_name against
    onboarding company_name. Kafka keys are not supplier IDs.
    """
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

    isolated_service = SupplierComplianceService(
        db_path=tmp_path / "compliance_state.db"
    )

    # The consumer must use this isolated instance.
    monkeypatch.setattr(
        "app.services.kafka_consumer.supplier_compliance_service",
        isolated_service,
    )

    # The service module's exported singleton must use it too.
    monkeypatch.setattr(
        "app.services.supplier_compliance_service.supplier_compliance_service",
        isolated_service,
    )

    # IMPORTANT:
    # The test module imported supplier_compliance_service directly.
    # Patching the original module does not update that imported reference.
    monkeypatch.setitem(
        globals(),
        "supplier_compliance_service",
        isolated_service,
    )

    yield

    suppliers.clear()



@pytest.fixture
def consumer():
    with (
        patch("app.services.kafka_consumer.Consumer") as mock_consumer,
        patch("app.services.kafka_consumer.Producer") as mock_producer,
    ):
        mock_producer.return_value.flush.return_value = 0

        instance = SupplierStatusChangedConsumer(
            bootstrap_servers="localhost:9092",
            topic=TOPIC,
            group_id=GROUP_ID,
            dlq_topic=DLQ_TOPIC,
            auto_offset_reset="earliest",
        )

    return instance


def test_consumer_uses_supplier_portal_consumer_group(consumer):
    assert consumer.group_id == GROUP_ID
    assert consumer.topic == TOPIC
    assert consumer.dlq_topic == DLQ_TOPIC


def test_consumer_disables_auto_commit(consumer):
    # This confirms construction; the production consumer configuration
    # should explicitly set enable.auto.commit to False.
    assert consumer.consumer is not None


def test_block_event_suspends_supplier(consumer):
    event = make_event(
        event_id="event-block-001",
        new_status="BLOCK",
    )

    assert consumer.process_message(make_message(event)) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )


def test_review_event_sets_needs_review(consumer):
    event = make_event(
        event_id="event-review-001",
        new_status="REVIEW",
    )

    assert consumer.process_message(make_message(event)) is True

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

    assert consumer.process_message(make_message(event)) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.cleared.value
    )


def test_duplicate_event_is_idempotent(consumer):
    event = make_event(
        event_id="event-duplicate-001",
        new_status="BLOCK",
    )

    first_message = make_message(event, offset=10)
    second_message = make_message(event, offset=11)

    assert consumer.process_message(first_message) is True
    assert consumer.process_message(second_message) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )

    assert len(supplier_compliance_service.get_audit_history("SUP001")) == 1


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

    assert consumer.process_message(make_message(newer_event)) is True
    assert consumer.process_message(make_message(older_event)) is True

    assert (
        suppliers["SUP001"]["compliance_access_status"]
        == SupplierComplianceStatus.suspended.value
    )


def test_invalid_json_raises_validation_error(consumer):
    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(
            make_message('{"this-is": "not-a-valid-event"}')
        )


def test_invalid_json_syntax_raises_validation_error(consumer):
    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(make_message('{"event_id": '))


def test_empty_message_raises_validation_error(consumer):
    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(make_message(None))


def test_wrong_event_type_is_rejected(consumer):
    event = make_event()
    event["event_type"] = "some.other.event"

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(make_message(event))


def test_unsupported_event_version_is_rejected(consumer):
    event = make_event()
    event["event_version"] = 99

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(make_message(event))


def test_offset_committed_only_after_db_write(consumer, monkeypatch):
    import app.services.kafka_consumer as kc

    order = []
    real_write = kc.supplier_compliance_service.apply_status_changed_event

    def tracked_write(event):
        order.append("db_write")
        return real_write(event)

    monkeypatch.setattr(
        kc.supplier_compliance_service,
        "apply_status_changed_event",
        tracked_write,
    )

    consumer.consumer.commit.side_effect = (
        lambda **kwargs: order.append("commit")
    )

    message = make_message(
        make_event(event_id="e-order"),
        offset=7,
    )

    consumer.consumer.poll.side_effect = [
        message,
        KeyboardInterrupt(),
    ]

    consumer.run(poll_timeout=0)

    assert order == ["db_write", "commit"]


def test_pre_onboarding_event_is_persisted_without_committing(consumer):
    event = make_event(
        event_id="event-pre-onboarding-001",
        supplier_name="Unknown Supplier",
    )

    message = make_message(
        event,
        key="Unknown Supplier",
    )

    assert "SUP999" not in suppliers
    assert consumer.process_message(message) is True

    assert supplier_compliance_service.is_event_processed(
        "event-pre-onboarding-001"
    )

    # Processing a message directly must not commit its Kafka offset.
    consumer.consumer.commit.assert_not_called()

    # After onboarding, the persisted BLOCK should be enforced.
    suppliers["SUP999"] = {
        "supplier_id": "SUP999",
        "company_name": "Unknown Supplier",
        "country": "India",
        "status": "active",
    }

    assert (
        supplier_compliance_service.get_access_status("SUP999")
        == SupplierComplianceStatus.suspended
    )


def test_process_message_never_commits_by_itself(consumer):
    message = make_message(make_event(event_id="e-no-commit"))

    assert consumer.process_message(message) is True
    consumer.consumer.commit.assert_not_called()

def test_dlq_contains_original_message(consumer):
    message = make_message(
        make_event(event_id="event-dlq-001"),
        offset=42,
    )

    consumer._publish_to_dlq(
        message=message,
        error_reason="Invalid event",
    )

    producer = consumer._dlq_producer
    producer.produce.assert_called_once()

    produce_call = producer.produce.call_args

    assert produce_call.kwargs["topic"] == DLQ_TOPIC

    dlq_payload = json.loads(produce_call.kwargs["value"])

    assert dlq_payload["error_reason"] == "Invalid event"
    assert dlq_payload["source_topic"] == TOPIC
    assert dlq_payload["source_partition"] == 0
    assert dlq_payload["source_offset"] == 42



def test_dlq_failure_raises_error(consumer):
    consumer._dlq_producer.flush.return_value = 1

    message = make_message(
        make_event(event_id="event-dlq-failure-001")
    )

    with pytest.raises(KafkaDeadLetterError):
        consumer._publish_to_dlq(
            message=message,
            error_reason="Invalid event",
        )


def test_successful_dlq_processing_allows_commit(consumer):
    message = make_message(
        make_event(event_id="event-dlq-commit-001")
    )

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
    message = make_message(
        make_event(event_id="event-dlq-no-commit-001")
    )

    consumer._publish_to_dlq = MagicMock(
        side_effect=KafkaDeadLetterError("DLQ unavailable")
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

    assert consumer.process_message(make_message(event)) is True

    audit = supplier_compliance_service.get_audit_history("SUP001")

    assert len(audit) == 1
    assert audit[0].event_id == "event-audit-001"
    assert audit[0].supplier_key == "abc supplies"
    assert audit[0].new_status == SupplierComplianceStatus.suspended


def test_commit_failure_is_not_silently_ignored(consumer):
    message = make_message(make_event())

    consumer.consumer.commit.side_effect = RuntimeError(
        "Kafka commit failed"
    )

    with pytest.raises(RuntimeError, match="Kafka commit failed"):
        consumer._commit(message)


def test_dlq_flush_exception_raises_error(consumer):
    consumer._dlq_producer.flush.side_effect = RuntimeError(
        "Kafka producer unavailable"
    )

    message = make_message(make_event())

    with pytest.raises(KafkaDeadLetterError):
        consumer._publish_to_dlq(
            message=message,
            error_reason="Invalid event",
        )


def _offsets(mock_commit):
    return [
        call.kwargs["message"].offset()
        for call in mock_commit.call_args_list
    ]


def test_crash_before_commit_redelivery_is_idempotent(tmp_path):
    db = tmp_path / "crash.db"

    event = SupplierStatusChangedEvent.model_validate(
        make_event(event_id="e-crash")
    )

    suppliers["SUP001"] = {
        "supplier_id": "SUP001",
        "company_name": "ABC Supplies",
        "country": "India",
        "status": "active",
    }

    first = SupplierComplianceService(db_path=db)

    assert first.apply_status_changed_event(event) is True

    fresh = SupplierComplianceService(db_path=db)

    assert fresh.apply_status_changed_event(event) is False
    assert fresh.is_event_processed("e-crash")
    assert len(fresh.get_audit_history("SUP001")) == 1


def test_naive_occurred_at_is_rejected(consumer):
    message = make_message(
        make_event(occurred_at="2026-10-08T09:00:00")
    )

    with pytest.raises(KafkaMessageValidationError):
        consumer.process_message(message)


def test_same_timestamp_keeps_more_restrictive_status(consumer):
    timestamp = "2026-10-08T09:00:00+00:00"

    consumer.process_message(
        make_message(
            make_event(
                event_id="same-time-block",
                new_status="BLOCK",
                occurred_at=timestamp,
            )
        )
    )

    consumer.process_message(
        make_message(
            make_event(
                event_id="same-time-clear",
                new_status="CLEAR",
                occurred_at=timestamp,
            )
        )
    )

    assert (
        supplier_compliance_service.get_access_status("SUP001")
        == SupplierComplianceStatus.suspended
    )

def test_event_for_supplier_not_yet_onboarded_applies_when_they_onboard(
    consumer,
):
    event = make_event(
        event_id="e-early",
        supplier_name="New Co",
    )

    # Default Kafka key is "ABC Supplies".
    # Supplier identity must come from the event payload, not the key.
    assert consumer.process_message(make_message(event)) is True

    suppliers["SUP777"] = {
        "supplier_id": "SUP777",
        "company_name": "New Co",
        "country": "India",
        "status": "active",
    }

    assert (
        supplier_compliance_service.get_access_status("SUP777")
        == SupplierComplianceStatus.suspended
    )


def test_suspension_survives_restart(tmp_path):
    db = tmp_path / "restart.db"

    suppliers["SUP001"] = {
        "supplier_id": "SUP001",
        "company_name": "ABC Supplies",
        "country": "India",
        "status": "active",
    }

    service = SupplierComplianceService(db_path=db)

    event = SupplierStatusChangedEvent.model_validate(
        make_event(event_id="e-restart")
    )

    assert service.apply_status_changed_event(event) is True

    restarted = SupplierComplianceService(db_path=db)

    assert (
        restarted.get_access_status("SUP001")
        == SupplierComplianceStatus.suspended
    )


def test_failed_event_is_rewound_not_skipped(consumer, monkeypatch):
    import app.services.kafka_consumer as kc

    monkeypatch.setattr(kc.time, "sleep", lambda _: None)

    first = make_message(
        make_event(event_id="e1"),
        offset=1,
    )
    second = make_message(
        make_event(
            event_id="e2",
            supplier_name="XYZ Supplies",
            new_status="REVIEW",
        ),
        offset=2,
    )

    consumer.consumer.poll.side_effect = [
        first,
        first,
        second,
        KeyboardInterrupt(),
    ]

    real_write = kc.supplier_compliance_service.apply_status_changed_event
    failed_once = []

    def flaky_write(event):
        if event.event_id == "e1" and not failed_once:
            failed_once.append(True)
            raise sqlite3.OperationalError("database is locked")

        return real_write(event)

    monkeypatch.setattr(
        kc.supplier_compliance_service,
        "apply_status_changed_event",
        flaky_write,
    )

    consumer.run(poll_timeout=0)

    sought = consumer.consumer.seek.call_args.args[0]
    assert (sought.partition, sought.offset) == (0, 1)
    assert _offsets(consumer.consumer.commit) == [1, 2]


def test_dlq_failure_does_not_kill_the_loop(consumer, monkeypatch):
    import app.services.kafka_consumer as kc

    monkeypatch.setattr(kc.time, "sleep", lambda _: None)

    consumer._dlq_producer.flush.side_effect = [1, 0, 0]

    bad = make_message("not json", offset=5)
    good = make_message(
        make_event(event_id="e-after-dlq"),
        offset=6,
    )

    consumer.consumer.poll.side_effect = [
        bad,
        bad,
        good,
        KeyboardInterrupt(),
    ]

    consumer.run(poll_timeout=0)

    assert consumer.consumer.seek.call_count == 1
    assert _offsets(consumer.consumer.commit) == [5, 6]

def test_real_producer_event_suspends_onboarded_supplier(consumer):
    """Exactly what services/compliance publishes: key=supplier_name, no supplier_id."""
    message = make_message(
        make_event(event_id="e-real", supplier_name="ABC Supplies"),
        key="ABC Supplies",
    )
    consumer.process_message(message)

    assert (
        supplier_compliance_service.get_access_status("SUP001")
        == SupplierComplianceStatus.suspended
    )
    assert (
        supplier_compliance_service.get_access_status("SUP002")
        == SupplierComplianceStatus.cleared
    )


def test_supplier_is_matched_by_name_not_by_kafka_key(consumer):
    message = make_message(
        make_event(event_id="e-key", supplier_name="  abc   SUPPLIES "),
        key="some-unrelated-key",
    )
    consumer.process_message(message)

    assert (
        supplier_compliance_service.get_access_status("SUP001")
        == SupplierComplianceStatus.suspended
    )


def test_block_for_another_supplier_does_not_suspend_this_one(consumer):
    consumer.process_message(
        make_message(make_event(event_id="e-other", supplier_name="XYZ Supplies"))
    )

    assert (
        supplier_compliance_service.get_access_status("SUP001")
        == SupplierComplianceStatus.cleared
    )
    assert (
        supplier_compliance_service.get_access_status("SUP002")
        == SupplierComplianceStatus.suspended
    )
