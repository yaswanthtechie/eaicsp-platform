import json
from unittest.mock import MagicMock

import pytest

from app.models.po_ack_outbox import POAckOutbox
from app.services.po_ack_outbox_publisher import POAckOutboxPublisher


def add_outbox_row(factory, event_id, status="pending"):
    with factory() as db:
        db.add(
            POAckOutbox(
                event_id=event_id,
                topic="supplierportal.po.acknowledged",
                message_key="PO-2026-000123",
                payload={"event_id": event_id},
                status=status,
                attempts=0,
            )
        )
        db.commit()


def make_producer(delivery_error=None, pending=0):
    """Producer mock that calls on_delivery like confluent_kafka does."""
    producer = MagicMock()
    callbacks = []

    def produce(**kwargs):
        callbacks.append(kwargs["on_delivery"])

    def flush(_timeout):
        for callback in callbacks:
            callback(delivery_error, None)
        callbacks.clear()
        return pending

    producer.produce.side_effect = produce
    producer.flush.side_effect = flush
    return producer


def get_row(factory, event_id):
    with factory() as db:
        return db.get(POAckOutbox, event_id)


def test_pending_row_is_published_and_marked(po_db):
    event_id = "11111111-1111-4111-8111-111111111111"
    add_outbox_row(po_db, event_id)
    producer = make_producer()

    published = POAckOutboxPublisher(producer).publish_pending()

    assert published == 1
    sent = producer.produce.call_args.kwargs
    assert sent["topic"] == "supplierportal.po.acknowledged"
    assert sent["key"] == "PO-2026-000123"
    assert json.loads(sent["value"]) == {"event_id": event_id}

    row = get_row(po_db, event_id)
    assert row.status == "published"
    assert row.published_at is not None
    assert row.attempts == 1


@pytest.mark.parametrize(
    "delivery_error, pending",
    [("broker down", 0), (None, 1)],
)
def test_failed_delivery_keeps_row_pending(po_db, delivery_error, pending):
    event_id = "22222222-2222-4222-8222-222222222222"
    add_outbox_row(po_db, event_id)
    producer = make_producer(delivery_error=delivery_error, pending=pending)

    published = POAckOutboxPublisher(producer).publish_pending()

    assert published == 0
    row = get_row(po_db, event_id)
    assert row.status == "pending"
    assert row.published_at is None
    assert row.attempts == 1
    assert row.last_error


def test_published_rows_are_not_sent_again(po_db):
    add_outbox_row(
        po_db,
        "33333333-3333-4333-8333-333333333333",
        status="published",
    )
    producer = make_producer()

    published = POAckOutboxPublisher(producer).publish_pending()

    assert published == 0
    producer.produce.assert_not_called()