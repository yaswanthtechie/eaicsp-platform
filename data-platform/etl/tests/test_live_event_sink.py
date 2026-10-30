import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from live_event_sink import ClickHouseEventSink, validate_event


def goods_event():
    return {
        "event_id": "123e4567-e89b-42d3-a456-426614174000",
        "event_type": "inventory.goods.received",
        "event_version": 1,
        "occurred_at": "2026-10-15T14:15:00Z",
        "producer": "inventory-service",
        "payload": {
            "receipt_id": "GR-2026-000077",
            "po_id": "PO-2026-000123",
            "supplier_id": "SUP-00045",
            "warehouse_id": "WH-BLR-01",
            "received_at": "2026-10-15T14:15:00Z",
            "status": "received",
            "items": [{"sku_id": "SKU-000123", "quantity_received": 100}],
        },
    }


def eta_event():
    return {
        "event_id": "123e4567-e89b-42d3-a456-426614174001",
        "event_type": "eta.shipment.predicted",
        "event_version": 1,
        "occurred_at": "2026-10-15T06:31:04Z",
        "producer": "eta-prediction",
        "payload": {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 5.2,
            "confidence_low": 4.1,
            "confidence_high": 7.3,
            "model_version": "eta_pipeline/3",
            "predicted_at": "2026-10-15T06:31:04Z",
        },
    }


class FakeMessage:
    def __init__(self, event, topic="inventory.goods.received"):
        self.raw = json.dumps(event).encode()
        self._topic = topic

    def value(self):
        return self.raw

    def topic(self):
        return self._topic

    def partition(self):
        return 0

    def offset(self):
        return 4


class FakeConsumer:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class FakeFuture:
    def get(self, timeout=None):
        return SimpleNamespace()


class FakeProducer:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, topic, **kwargs):
        if self.fail:
            raise RuntimeError("DLQ unavailable")
        self.sent.append((topic, kwargs))
        return FakeFuture()


class FakeClient:
    def __init__(self, fail_table=None):
        self.tables = {}
        self.fail_table = fail_table

    def command(self, sql):
        pass

    def query(self, sql, parameters=None):
        event_id = (parameters or {}).get("event_id")
        rows = self.tables.get("analytics.dashboard_event_sink_processed", [])
        found = any(row[0] == event_id for row in rows)
        return SimpleNamespace(result_rows=[(event_id,)] if found else [])

    def insert(self, table, rows, column_names):
        if table == self.fail_table:
            raise RuntimeError("ClickHouse unavailable")
        self.tables.setdefault(table, []).extend(rows)

    def close(self):
        pass


def make_sink(fail_table=None, dlq_fail=False):
    consumer = FakeConsumer()
    producer = FakeProducer(fail=dlq_fail)
    client = FakeClient(fail_table=fail_table)
    return ClickHouseEventSink(consumer, producer, client), consumer, producer, client


def test_valid_contract_events():
    assert validate_event(goods_event())["event_type"] == "inventory.goods.received"
    assert validate_event(eta_event())["event_type"] == "eta.shipment.predicted"


def test_rejects_invalid_goods_quantity():
    event = goods_event()
    event["payload"]["items"][0]["quantity_received"] = 0
    with pytest.raises(ValueError):
        validate_event(event)


def test_goods_event_writes_lines_and_commits():
    sink, consumer, _, client = make_sink()
    assert sink.process_message(FakeMessage(goods_event())) == "processed"
    assert len(client.tables["analytics.goods_receipt_lines"]) == 1
    assert len(client.tables["analytics.dashboard_event_sink_processed"]) == 1
    assert consumer.commits == 1


def test_duplicate_event_id_is_not_written_twice():
    sink, consumer, _, client = make_sink()
    message = FakeMessage(goods_event())
    assert sink.process_message(message) == "processed"
    assert sink.process_message(message) == "duplicate"
    assert len(client.tables["analytics.goods_receipt_lines"]) == 1
    assert consumer.commits == 2


def test_eta_event_writes_prediction_and_commits():
    sink, consumer, _, client = make_sink()
    assert sink.process_message(
        FakeMessage(eta_event(), topic="eta.shipment.predicted")
    ) == "processed"
    assert len(client.tables["analytics.shipment_eta_predictions"]) == 1
    assert consumer.commits == 1


def test_invalid_event_goes_to_dlq_before_commit():
    sink, consumer, producer, _ = make_sink()
    event = goods_event()
    event["payload"]["items"] = []
    result = sink.process_message(FakeMessage(event))
    assert result == "dead_letter"
    assert producer.sent[0][0] == "inventory.goods.received.dlq"
    assert consumer.commits == 1


def test_clickhouse_failure_does_not_commit():
    sink, consumer, _, _ = make_sink(fail_table="analytics.goods_receipt_lines")
    with pytest.raises(RuntimeError, match="ClickHouse unavailable"):
        sink.process_message(FakeMessage(goods_event()))
    assert consumer.commits == 0


def test_dlq_failure_does_not_commit():
    sink, consumer, _, _ = make_sink(dlq_fail=True)
    event = goods_event()
    event["payload"]["items"] = []
    with pytest.raises(RuntimeError, match="DLQ unavailable"):
        sink.process_message(FakeMessage(event))
    assert consumer.commits == 0
