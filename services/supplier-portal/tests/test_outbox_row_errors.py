import json
from unittest.mock import MagicMock

import pytest

from app.models.po_ack_outbox import POAckOutbox
from app.models.shipment_outbox import ShipmentOutbox
from app.services.po_ack_outbox_publisher import POAckOutboxPublisher
from app.services.shipment_outbox_publisher import ShipmentOutboxPublisher

GOOD_1 = "11111111-1111-4111-8111-111111111111"
BAD = "22222222-2222-4222-8222-222222222222"
GOOD_2 = "33333333-3333-4333-8333-333333333333"


def producer_failing_on(bad_event_id):
    """Delivers every row except bad_event_id, where produce() raises TypeError."""
    producer = MagicMock()
    callbacks = []

    def produce(**kwargs):
        if json.loads(kwargs["value"])["event_id"] == bad_event_id:
            raise TypeError("payload is not serializable")
        callbacks.append(kwargs["on_delivery"])

    def flush(_timeout):
        for callback in callbacks:
            callback(None, None)
        callbacks.clear()
        return 0

    producer.produce.side_effect = produce
    producer.flush.side_effect = flush
    return producer


@pytest.mark.parametrize(
    "model, publisher_class",
    [(POAckOutbox, POAckOutboxPublisher), (ShipmentOutbox, ShipmentOutboxPublisher)],
)
def test_one_bad_row_does_not_roll_back_delivered_rows(po_db, model, publisher_class):
    with po_db() as db:
        for event_id in (GOOD_1, BAD, GOOD_2):
            db.add(
                model(
                    event_id=event_id,
                    topic="test.topic",
                    message_key="KEY-1",
                    payload={"event_id": event_id},
                    status="pending",
                    attempts=0,
                )
            )
        db.commit()

    published = publisher_class(producer_failing_on(BAD)).publish_pending()

    assert published == 2
    with po_db() as db:
        assert db.get(model, GOOD_1).status == "published"
        assert db.get(model, GOOD_2).status == "published"
        bad = db.get(model, BAD)
        assert bad.status == "pending"
        assert bad.attempts == 1
        assert "not serializable" in bad.last_error
