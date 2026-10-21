from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.inventory_po_approved_consumer import POApprovedConsumer


@pytest.fixture
def consumer():
    """Create a consumer with mocked Kafka clients."""
    instance = POApprovedConsumer()
    instance.consumer = MagicMock()
    instance.producer = MagicMock()
    return instance


@pytest.fixture
def valid_event():
    """Return an event matching the POApprovedEvent schema."""
    return {
        "event_id": "evt-po-approved-001",
        "event_type": "inventory.po.approved",
        "event_version": 1,
        "occurred_at": "2026-10-21T12:00:00Z",
        "producer": "inventory-service",
        "trace_id": None,
        "payload": {
            "po_id": "PO-2026-000123",
            "po_number": "PO-2026-000123",
            "supplier_id": "SUP-00045",
            "warehouse_id": "WH-BLR-01",
            "approval_status": "approved",
            "approved_by": "procurement-manager",
            "approved_at": "2026-10-21T11:59:00Z",
            "total_amount": 1250.00,
            "currency": "INR",
            "expected_delivery_date": "2026-10-30",
            "lines": [
                {
                    "line_number": 1,
                    "sku_id": "SKU-000123",
                    "quantity": 5,
                    "unit_cost": 250.00,
                    "expected_cost": 1250.00,
                }
            ],
        },
    }


def make_message(event):
    """Create a Kafka message mock containing the given event."""
    message = MagicMock()
    message.error.return_value = None
    message.value.return_value = json.dumps(event).encode("utf-8")
    message.topic.return_value = "inventory.po.approved"
    message.partition.return_value = 0
    message.offset.return_value = 10
    message.key.return_value = b"PO-2026-000123"
    return message


def mock_session():
    """Return a mocked SQLAlchemy context manager and session."""
    factory = MagicMock()
    db = factory.return_value.__enter__.return_value

    # First query checks event_id; second query checks po_id.
    db.query.return_value.filter.return_value.one_or_none.side_effect = [
        None,
        None,
    ]
    return factory, db


def test_valid_event_is_persisted_before_offset_commit(
    consumer, valid_event
):
    message = make_message(valid_event)
    factory, db = mock_session()
    call_order = []

    db.commit.side_effect = lambda: call_order.append("db_commit")
    consumer.consumer.commit.side_effect = (
        lambda **kwargs: call_order.append("kafka_commit")
    )

    with patch(
        "app.services.inventory_po_approved_consumer.SessionLocal",
        factory,
    ):
        consumer._process_message(message)

    db.add.assert_called_once()
    db.commit.assert_called_once()
    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )
    assert call_order == ["db_commit", "kafka_commit"]


def test_duplicate_event_is_not_inserted_twice(consumer, valid_event):
    message = make_message(valid_event)
    factory, db = mock_session()

    # The first event_id lookup finds the previously processed event.
    db.query.return_value.filter.return_value.one_or_none.side_effect = [
        MagicMock(),
    ]

    with (
        patch(
            "app.services.inventory_po_approved_consumer.SessionLocal",
            factory,
        ),
        patch.object(consumer, "_publish_dlq") as publish_dlq,
    ):
        consumer._process_message(message)

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called()
    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )
    publish_dlq.assert_not_called()


def test_invalid_event_is_sent_to_dlq(consumer):
    message = make_message({"event_id": "invalid"})

    with (
        patch.object(consumer, "_publish_dlq") as publish_dlq,
        patch(
            "app.services.inventory_po_approved_consumer.SessionLocal"
        ) as session_factory,
    ):
        consumer._process_message(message)

    publish_dlq.assert_called_once()
    assert publish_dlq.call_args.args[0] is message
    session_factory.assert_not_called()


def test_database_failure_is_retried_then_sent_to_dlq(
    consumer, valid_event
):
    message = make_message(valid_event)
    factory, db = mock_session()

    # Each retry queries by event_id and then by po_id.
    # Two retries therefore require four query results.
    db.query.return_value.filter.return_value.one_or_none.side_effect = [
        None,
        None,
        None,
        None,
    ]

    # Both database transaction attempts fail at commit.
    db.commit.side_effect = RuntimeError("database unavailable")

    with (
        patch(
            "app.services.inventory_po_approved_consumer.SessionLocal",
            factory,
        ),
        patch(
            "app.services.inventory_po_approved_consumer.settings"
        ) as mock_settings,
        patch(
            "app.services.inventory_po_approved_consumer.time.sleep"
        ) as mock_sleep,
        patch.object(consumer, "_publish_dlq") as publish_dlq,
    ):
        mock_settings.PO_MAX_RETRIES = 2
        mock_settings.PO_RETRY_BACKOFF_SECONDS = 0

        consumer._process_message(message)

    # Both attempts reach insertion and fail during database commit.
    assert db.add.call_count == 2
    assert db.commit.call_count == 2
    assert db.rollback.call_count >= 2

    mock_sleep.assert_called_once_with(0)
    publish_dlq.assert_called_once()
    assert publish_dlq.call_args.args[0] is message
    assert "Persistence failed after 2 attempts" in (
        publish_dlq.call_args.args[1]
    )

    # The mocked DLQ does not commit the source offset.
    consumer.consumer.commit.assert_not_called()

