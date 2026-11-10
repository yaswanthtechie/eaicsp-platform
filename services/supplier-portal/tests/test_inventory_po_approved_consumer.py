
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.po_mirror import POMirror
from app.services.inventory_po_approved_consumer import POApprovedConsumer


INVENTORY_EXAMPLE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "events"
    / "examples"
    / "inventory.po.approved.v1.json"
)


def load_inventory_example():
    return json.loads(
        INVENTORY_EXAMPLE.read_text(encoding="utf-8-sig")
    )


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
            "approved_by": "3f2b8c1e-7a4d-4e9b-9c2f-1d5e6a7b8c90",
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

def test_inventory_example_event_is_persisted(consumer, po_db):
    """Balaji's published example must go into po_mirror unchanged."""
    event = load_inventory_example()
    message = make_message(event)

    with patch.object(consumer, "_publish_dlq") as publish_dlq:
        consumer._process_message(message)

    publish_dlq.assert_not_called()
    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )

    with po_db() as db:
        po = db.query(POMirror).one()

    payload = event["payload"]
    assert po.po_id == payload["po_id"]
    assert po.event_id == event["event_id"]
    assert po.supplier_id == payload["supplier_id"]
    assert po.warehouse_id == payload["warehouse_id"]
    assert po.approved_by == payload["approved_by"]
    assert po.trace_id == event["trace_id"]
    assert po.lines == payload["lines"]
    assert po.status == "approved"


def test_mirror_columns_fit_inventory_example_values():
    """SQLite ignores String(n); PostgreSQL does not. Check widths here."""
    payload = load_inventory_example()["payload"]
    columns = POMirror.__table__.c

    for field in ("po_id", "po_number", "supplier_id", "warehouse_id",
                  "approved_by"):
        assert len(payload[field]) <= columns[field].type.length, field


def test_replayed_example_event_is_stored_once(consumer, po_db):
    event = load_inventory_example()

    consumer._process_message(make_message(event))
    consumer._process_message(make_message(event))

    with po_db() as db:
        assert db.query(POMirror).count() == 1
    assert consumer.consumer.commit.call_count == 2


def test_conflicting_event_for_same_po_goes_to_dlq_without_retry(
    consumer, po_db
):
    first = load_inventory_example()
    consumer._process_message(make_message(first))

    conflicting = load_inventory_example()
    conflicting["event_id"] = "b5c7d9e1-f3a5-4b7c-9d1e-2f4a6b8c0d2e"
    conflicting["payload"]["total_amount"] = 99999.0

    with (
        patch.object(consumer, "_publish_dlq") as publish_dlq,
        patch(
            "app.services.inventory_po_approved_consumer.time.sleep"
        ) as mock_sleep,
    ):
        consumer._process_message(make_message(conflicting))

    publish_dlq.assert_called_once()
    assert "Conflicting approved PO event" in publish_dlq.call_args.args[1]
    mock_sleep.assert_not_called()

    with po_db() as db:
        assert float(db.query(POMirror).one().total_amount) == 45000.0


