import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.inventory_goods_receipt_event import (
    InventoryGoodsReceiptEvent,
)
from app.services.inventory_goods_received_consumer import (
    PAYLOAD_ID_PATTERNS,
    SKU_ID_PATTERN,
    InventoryGoodsReceivedConsumer,
)

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts" / "events"
GOODS_RECEIVED_CONTRACT = CONTRACTS / "inventory.goods.received.v1.json"
GOODS_RECEIVED_EXAMPLE = (
    CONTRACTS / "examples" / "inventory.goods.received.v1.json"
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def make_message(value, offset=15):
    message = MagicMock()
    message.error.return_value = None
    message.key.return_value = b"PO-2026-000123"
    message.topic.return_value = "inventory.goods.received"
    message.partition.return_value = 0
    message.offset.return_value = offset
    message.value.return_value = (
        None if value is None else json.dumps(value).encode("utf-8")
    )
    return message


@pytest.fixture
def valid_event():
    return {
        "event_id": "b7c8d9e0-f1a2-4b3c-8d5e-6f7a8b9c0d1e",
        "event_type": "inventory.goods.received",
        "event_version": 1,
        "occurred_at": "2026-10-15T14:15:00Z",
        "producer": "inventory-service",
        "payload": {
            "receipt_id": "GR-2026-000077",
            "po_id": "PO-2026-000123",
            "supplier_id": "SUP-00045",
            "warehouse_id": "WH-BLR-01",
            "received_by": "warehouse.manager@company.com",
            "received_at": "2026-10-15T14:15:00Z",
            "status": "received",
            "items": [
                {
                    "sku_id": "SKU-000123",
                    "quantity_received": 100,
                    "unit_cost": 450.0,
                }
            ],
        },
    }

@pytest.fixture
def consumer():
    with (
        patch(
            "app.services.inventory_goods_received_consumer.Consumer"
        ),
        patch(
            "app.services.inventory_goods_received_consumer.Producer"
        ),
    ):
        instance = InventoryGoodsReceivedConsumer()

        # flush() returns the number of undelivered messages.
        instance.producer.flush.return_value = 0

        yield instance


def test_valid_event_passes_validation(valid_event):
    result = InventoryGoodsReceivedConsumer._validate_event(valid_event)

    assert result == valid_event


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        ({"event_type": "wrong.event"}, "Unexpected event_type"),
        ({"event_version": 2}, "Unsupported event_version"),
        ({"producer": "unknown-service"}, "Unexpected producer"),
        ({"event_id": ""}, "event_id is required"),
        ({"payload": None}, "payload must be an object"),
    ],
)
def test_invalid_event_metadata_is_rejected(
    valid_event, change, expected_error
):
    event = {**valid_event, **change}

    with pytest.raises(ValueError, match=expected_error):
        InventoryGoodsReceivedConsumer._validate_event(event)


@pytest.mark.parametrize(
    ("payload_change", "expected_error"),
    [
        ({"status": "pending"}, "Receipt status must be received"),
        ({"items": []}, "payload.items must be a non-empty list"),
        (
            {"items": [{"sku_id": "SKU-000123", "quantity_received": 0}]},
            "positive integer",
        ),
        (
            {"items": [{"sku_id": "", "quantity_received": 1}]},
            "item.sku_id is required",
        ),
        (
            {"items": ["invalid-item"]},
            "Each receipt item must be an object",
        ),
    ],
)
def test_invalid_receipt_payload_is_rejected(
    valid_event, payload_change, expected_error
):
    event = {
        **valid_event,
        "payload": {**valid_event["payload"], **payload_change},
    }

    with pytest.raises(ValueError, match=expected_error):
        InventoryGoodsReceivedConsumer._validate_event(event)


def test_missing_required_payload_field_is_rejected(valid_event):
    event = {
        **valid_event,
        "payload": {
            key: value
            for key, value in valid_event["payload"].items()
            if key != "receipt_id"
        },
    }

    with pytest.raises(ValueError, match="payload.receipt_id is required"):
        InventoryGoodsReceivedConsumer._validate_event(event)


def test_valid_event_is_persisted_and_committed(
    consumer, valid_event
):
    db = MagicMock()

    with patch(
        "app.services.inventory_goods_received_consumer.SessionLocal",
        return_value=db,
    ):
        result = consumer._persist_event(valid_event)

    assert result is True
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.close.assert_called_once()

    saved_record = db.add.call_args.args[0]
    assert saved_record.event_id == valid_event["event_id"]
    assert saved_record.receipt_id == "GR-2026-000077"
    assert saved_record.po_id == "PO-2026-000123"
    assert saved_record.supplier_id == "SUP-00045"
    assert saved_record.payload == valid_event


def test_duplicate_event_is_not_persisted_twice(
    consumer, valid_event
):
    db = MagicMock()
    db.commit.side_effect = IntegrityError(
        "duplicate event", {}, Exception("duplicate key")
    )
    db.get.return_value = object()

    with patch(
        "app.services.inventory_goods_received_consumer.SessionLocal",
        return_value=db,
    ):
        result = consumer._persist_event(valid_event)

    assert result is False
    db.add.assert_called_once()
    db.rollback.assert_called_once()
    db.get.assert_called_once()
    db.close.assert_called_once()


def test_database_failure_is_propagated_and_session_closed(
    consumer, valid_event
):
    db = MagicMock()
    db.commit.side_effect = RuntimeError("database unavailable")

    with (
        patch(
            "app.services.inventory_goods_received_consumer.SessionLocal",
            return_value=db,
        ),
        pytest.raises(RuntimeError, match="database unavailable"),
    ):
        consumer._persist_event(valid_event)

    db.close.assert_called_once()


def test_invalid_event_is_sent_to_dlq(consumer):
    message = MagicMock()
    message.key.return_value = b"receipt-key"
    message.topic.return_value = "inventory.goods.received"
    message.partition.return_value = 0
    message.offset.return_value = 15
    message.value.return_value = b'{"invalid": true}'

    consumer._send_to_dlq(message, "event_id is required")

    consumer.producer.produce.assert_called_once()
    args, kwargs = consumer.producer.produce.call_args

    assert args[0] == "inventory.goods.received.dlq"
    assert kwargs["key"] == b"receipt-key"

    dlq_payload = json.loads(kwargs["value"])
    assert dlq_payload["source_topic"] == "inventory.goods.received"
    assert dlq_payload["source_partition"] == 0
    assert dlq_payload["source_offset"] == 15
    assert dlq_payload["reason"] == "event_id is required"
    assert dlq_payload["original_value"] == '{"invalid": true}'

    consumer.producer.flush.assert_called_once_with(10)
def test_id_patterns_match_the_contract():
    """If Inventory changes an ID format, this test must fail."""
    payload = load_json(GOODS_RECEIVED_CONTRACT)["properties"]["payload"]
    properties = payload["properties"]

    for field, pattern in PAYLOAD_ID_PATTERNS.items():
        assert properties[field]["pattern"] == pattern, field

    item_properties = properties["items"]["items"]["properties"]
    assert item_properties["sku_id"]["pattern"] == SKU_ID_PATTERN


def test_contract_example_passes_validation():
    event = load_json(GOODS_RECEIVED_EXAMPLE)

    assert InventoryGoodsReceivedConsumer._validate_event(event) == event


@pytest.mark.parametrize(
    ("field", "legacy_value"),
    [
        ("receipt_id", "GR1"),
        ("po_id", "PO001"),
        ("supplier_id", "SUP001"),
        ("supplier_id", "SUP-000450"),
        ("warehouse_id", "WH1"),
    ],
)
def test_non_canonical_payload_ids_are_rejected(
    valid_event, field, legacy_value
):
    event = {
        **valid_event,
        "payload": {**valid_event["payload"], field: legacy_value},
    }

    with pytest.raises(ValueError, match=re.escape(f"payload.{field}")):
        InventoryGoodsReceivedConsumer._validate_event(event)


def test_non_canonical_sku_is_rejected(valid_event):
    event = {
        **valid_event,
        "payload": {
            **valid_event["payload"],
            "items": [{"sku_id": "LAP001", "quantity_received": 1}],
        },
    }

    with pytest.raises(ValueError, match="canonical SKU ID"):
        InventoryGoodsReceivedConsumer._validate_event(event)


def test_contract_example_is_stored_and_committed(consumer, po_db):
    event = load_json(GOODS_RECEIVED_EXAMPLE)
    message = make_message(event)

    consumer._process_message(message)

    consumer.producer.produce.assert_not_called()
    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )

    with po_db() as db:
        record = db.query(InventoryGoodsReceiptEvent).one()

    assert record.event_id == event["event_id"]
    assert record.receipt_id == "GR-2026-000077"
    assert record.po_id == "PO-2026-000123"
    assert record.supplier_id == "SUP-00045"
    assert record.payload == event


def test_same_receipt_resent_with_new_event_id_is_stored_once(
    consumer, po_db
):
    first = load_json(GOODS_RECEIVED_EXAMPLE)
    resent = load_json(GOODS_RECEIVED_EXAMPLE)
    resent["event_id"] = "c1c1c1c1-0000-4000-8000-000000000002"

    consumer._process_message(make_message(first, offset=1))
    consumer._process_message(make_message(resent, offset=2))

    with po_db() as db:
        assert db.query(InventoryGoodsReceiptEvent).count() == 1

    consumer.producer.produce.assert_not_called()
    assert consumer.consumer.commit.call_count == 2


def test_conflicting_receipt_goes_to_dlq_without_retry(consumer, po_db):
    first = load_json(GOODS_RECEIVED_EXAMPLE)
    conflicting = load_json(GOODS_RECEIVED_EXAMPLE)
    conflicting["event_id"] = "c1c1c1c1-0000-4000-8000-000000000003"
    conflicting["payload"]["items"][0]["quantity_received"] = 50

    consumer._process_message(make_message(first, offset=1))

    with patch(
        "app.services.inventory_goods_received_consumer.time.sleep"
    ) as mock_sleep:
        consumer._process_message(make_message(conflicting, offset=2))

    mock_sleep.assert_not_called()
    consumer.producer.produce.assert_called_once()
    dlq_payload = json.loads(
        consumer.producer.produce.call_args.kwargs["value"]
    )
    assert "Conflicting goods receipt event" in dlq_payload["reason"]
    assert dlq_payload["source_offset"] == 2

    with po_db() as db:
        record = db.query(InventoryGoodsReceiptEvent).one()
    assert record.payload["payload"]["items"][0]["quantity_received"] == 100


def test_database_failure_is_retried_then_sent_to_dlq(consumer, valid_event):
    message = make_message(valid_event)

    with (
        patch.object(
            consumer,
            "_persist_event",
            side_effect=RuntimeError("database unavailable"),
        ) as persist,
        patch(
            "app.services.inventory_goods_received_consumer.time.sleep"
        ),
        patch(
            "app.services.inventory_goods_received_consumer.settings."
            "KAFKA_MAX_RETRIES",
            3,
        ),
    ):
        consumer._process_message(message)

    assert persist.call_count == 3
    consumer.producer.produce.assert_called_once()
    dlq_payload = json.loads(
        consumer.producer.produce.call_args.kwargs["value"]
    )
    assert dlq_payload["reason"] == "Persistence failed after 3 attempts"
    consumer.consumer.commit.assert_called_once_with(
        message=message,
        asynchronous=False,
    )


def test_database_recovering_on_retry_is_committed_without_dlq(
    consumer, valid_event
):
    message = make_message(valid_event)

    with (
        patch.object(
            consumer,
            "_persist_event",
            side_effect=[RuntimeError("database unavailable"), True],
        ) as persist,
        patch(
            "app.services.inventory_goods_received_consumer.time.sleep"
        ),
    ):
        consumer._process_message(message)

    assert persist.call_count == 2
    consumer.producer.produce.assert_not_called()
    consumer.consumer.commit.assert_called_once()


def test_failed_message_is_never_skipped_by_the_next_one(
    consumer, valid_event
):
    """Before the fix, offset 11 was committed while offset 10 was lost."""
    second = {
        **valid_event,
        "event_id": "c1c1c1c1-0000-4000-8000-000000000004",
    }
    messages = iter([make_message(valid_event, 10), make_message(second, 11)])

    def poll(_timeout):
        try:
            return next(messages)
        except StopIteration:
            consumer.stop()
            return None

    consumer.consumer.poll.side_effect = poll
    consumer.producer.flush.return_value = 1  # DLQ is down as well

    with (
        patch.object(
            consumer,
            "_persist_event",
            side_effect=RuntimeError("database unavailable"),
        ),
        patch(
            "app.services.inventory_goods_received_consumer.time.sleep"
        ),
        pytest.raises(RuntimeError, match="DLQ delivery not confirmed"),
    ):
        consumer.run()

    consumer.consumer.commit.assert_not_called()
    consumer.consumer.close.assert_called_once()


def test_unconfirmed_dlq_delivery_does_not_commit(consumer):
    consumer.producer.flush.return_value = 1
    message = make_message({"invalid": True})

    with pytest.raises(RuntimeError, match="DLQ delivery not confirmed"):
        consumer._process_message(message)

    consumer.consumer.commit.assert_not_called()


def test_dlq_delivery_error_does_not_commit(consumer):
    def produce(*_args, **kwargs):
        kwargs["on_delivery"]("broker down", None)

    consumer.producer.produce.side_effect = produce
    message = make_message({"invalid": True})

    with pytest.raises(RuntimeError, match="broker down"):
        consumer._process_message(message)

    consumer.consumer.commit.assert_not_called()


@pytest.mark.parametrize("value", [None, b"not json", b"\xff\xfe"])
def test_unreadable_message_goes_to_dlq(consumer, value):
    message = make_message(None)
    message.value.return_value = value

    consumer._process_message(message)

    consumer.producer.produce.assert_called_once()
    consumer.consumer.commit.assert_called_once()
