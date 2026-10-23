import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.inventory_goods_received_consumer import (
    InventoryGoodsReceivedConsumer,
)


@pytest.fixture
def valid_event():
    return {
        "event_id": "b7c8d9e0-f1a2-4b3c-8d5e-6f7a8b9c0d1e",
        "event_type": "inventory.goods.received",
        "event_version": 1,
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
