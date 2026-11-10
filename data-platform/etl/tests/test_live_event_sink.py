import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from live_event_sink import ClickHouseEventSink, validate_event

EXAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "events" / "examples"


def _example(name):
    return json.loads((EXAMPLES / f"{name}.v1.json").read_text(encoding="utf-8"))


def goods_event():
    return _example("inventory.goods.received")


def eta_event():
    return _example("eta.shipment.predicted")


class FakeMessage:
    def __init__(self, event, topic="inventory.goods.received"):
        self.value = json.dumps(event).encode()
        self.topic = topic
        self.partition = 0
        self.offset = 4


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


class TransportClient(FakeClient):
    def __init__(self, dispatched_at):
        super().__init__()
        self.row = (
            "SHP-2026-000077", "PO-2026-000123", "SUP-00045", "WH-BLR-01",
            "BlueDart", dispatched_at, None, None, None, None, dispatched_at,
        )

    def query(self, sql, parameters=None):
        if "transport_performance" in sql:
            return SimpleNamespace(result_rows=[self.row])
        return super().query(sql, parameters)


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


def test_rejects_goods_event_without_received_by():
    event = goods_event()
    del event["payload"]["received_by"]
    with pytest.raises(ValueError, match="received_by"):
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


def test_predicted_eta_counts_from_dispatched_at():
    dispatched_at = datetime(2026, 10, 14, 6, 0)
    client = TransportClient(dispatched_at)
    sink = ClickHouseEventSink(FakeConsumer(), FakeProducer(), client)

    sink.process_message(
        FakeMessage(eta_event(), topic="eta.shipment.predicted")
    )

    (row,) = client.tables["analytics.transport_performance"]
    assert row[6] == dispatched_at + timedelta(days=5.2)


def test_eta_without_transport_row_is_logged(caplog):
    sink, _, _, client = make_sink()
    with caplog.at_level("WARNING"):
        result = sink.process_message(
            FakeMessage(eta_event(), topic="eta.shipment.predicted")
        )
    assert result == "processed"
    assert "analytics.transport_performance" not in client.tables
    assert "No transport_performance row" in caplog.text


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
