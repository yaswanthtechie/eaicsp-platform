from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import pytest

from app.models.compliance_event import ProcessedEvent
from app.models.purchase_order import PurchaseOrder
from app.services.po_acknowledged_consumer import (
    InvalidMessageError,
    POAcknowledgedConsumerWorker,
    process_po_acknowledged_event,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_PATH = (
    REPO_ROOT
    / "contracts"
    / "events"
    / "examples"
    / "supplierportal.po.acknowledged.v1.json"
)


class MockKafkaMessage:
    def __init__(self, value_dict_or_str, topic="supplierportal.po.acknowledged", partition=0, offset=1):
        if isinstance(value_dict_or_str, dict):
            self._value = json.dumps(value_dict_or_str).encode("utf-8")
        elif isinstance(value_dict_or_str, str):
            self._value = value_dict_or_str.encode("utf-8")
        else:
            self._value = value_dict_or_str
        self._topic = topic
        self._partition = partition
        self._offset = offset

    def value(self):
        return self._value

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


class MockConsumer:
    def __init__(self):
        self.committed = []

    def commit(self, message=None, asynchronous=False):
        self.committed.append(message)


class MockDLQPublisher:
    def __init__(self):
        self.published = []

    def publish(self, topic, key, value):
        self.published.append({"topic": topic, "key": key, "value": value})
        return True


@pytest.fixture
def example_event():
    assert EXAMPLE_PATH.exists(), f"Example event file missing at {EXAMPLE_PATH}"
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def seed_po(db_session, example_event):
    po_id = example_event["payload"]["po_number"]
    supplier_id = example_event["payload"]["supplier_id"]

    po = PurchaseOrder(
        po_id=po_id,
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        supplier_id=supplier_id,
        quantity=100,
        unit_cost=250.0,
        expected_cost=25000.0,
        status="draft",
        approval_status="approved",
    )
    db_session.add(po)
    db_session.commit()
    return po


def test_process_rashida_example_event(db_session, example_event, seed_po):
    """
    Consumer processes Rashida's official example event:
    contracts/events/examples/supplierportal.po.acknowledged.v1.json
    - PO status transitions to 'acknowledged'.
    - ProcessedEvent record is persisted for idempotency.
    """
    result = process_po_acknowledged_event(db_session, example_event)

    assert result.status == "PROCESSED"
    assert result.affected_po == seed_po.po_id

    # PO updated in database
    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == seed_po.po_id).first()
    assert po.status == "acknowledged"

    # Idempotency record created
    processed = (
        db_session.query(ProcessedEvent)
        .filter(ProcessedEvent.event_id == example_event["event_id"])
        .first()
    )
    assert processed is not None
    assert processed.status == "PROCESSED"
    assert processed.event_type == "supplierportal.po.acknowledged"
    assert processed.supplier_id == seed_po.supplier_id


def test_consumer_idempotency_duplicate_event(db_session, example_event, seed_po):
    """
    Delivering the same event_id twice produces DUPLICATE result and leaves PO untouched.
    """
    # 1. First delivery
    res1 = process_po_acknowledged_event(db_session, example_event)
    assert res1.status == "PROCESSED"

    # 2. Duplicate delivery
    res2 = process_po_acknowledged_event(db_session, example_event)
    assert res2.status == "DUPLICATE"
    assert "already processed" in res2.details.lower()

    # ProcessedEvent count is exactly 1
    count = (
        db_session.query(ProcessedEvent)
        .filter(ProcessedEvent.event_id == example_event["event_id"])
        .count()
    )
    assert count == 1


def test_consumer_po_not_found_handled_gracefully(db_session, example_event):
    """
    An acknowledgement event for a non-existent PO records SKIPPED_PO_NOT_FOUND
    without crashing.
    """
    # Ensure PO does not exist
    po_id = example_event["payload"]["po_number"]
    db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).delete()
    db_session.commit()

    result = process_po_acknowledged_event(db_session, example_event)
    assert result.status == "PO_NOT_FOUND"

    processed = (
        db_session.query(ProcessedEvent)
        .filter(ProcessedEvent.event_id == example_event["event_id"])
        .first()
    )
    assert processed is not None
    assert processed.status == "SKIPPED_PO_NOT_FOUND"


def test_consumer_does_not_revert_received_po(db_session, example_event, seed_po):
    """
    If PO is already 'received' or 'partially_received', late arrival of
    po.acknowledged does not regress status back to 'acknowledged'.
    """
    seed_po.status = "received"
    db_session.commit()

    result = process_po_acknowledged_event(db_session, example_event)
    assert result.status == "PROCESSED"

    po = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == seed_po.po_id).first()
    assert po.status == "received"


def test_consumer_rejects_invalid_event_envelope(db_session, example_event):
    """Malformed envelope raises InvalidMessageError."""
    bad_type = dict(example_event, event_type="wrong.type")
    with pytest.raises(InvalidMessageError):
        process_po_acknowledged_event(db_session, bad_type)

    bad_version = dict(example_event, event_version=99)
    with pytest.raises(InvalidMessageError):
        process_po_acknowledged_event(db_session, bad_version)

    no_id = dict(example_event, event_id="")
    with pytest.raises(InvalidMessageError):
        process_po_acknowledged_event(db_session, no_id)


def test_consumer_rejects_future_skew(db_session, example_event):
    """Events with occurred_at far in the future are rejected."""
    future_time = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    bad_time = dict(example_event, occurred_at=future_time)
    with pytest.raises(InvalidMessageError):
        process_po_acknowledged_event(db_session, bad_time)


def test_worker_end_to_end_success(db_session, example_event, seed_po):
    """
    POAcknowledgedConsumerWorker processes message, commits Kafka offset on success.
    """
    consumer = MockConsumer()
    dlq = MockDLQPublisher()
    worker = POAcknowledgedConsumerWorker(consumer=consumer, dlq_publisher=dlq)

    msg = MockKafkaMessage(example_event)
    result = worker.handle_kafka_message(db_session, msg)

    assert result.status == "PROCESSED"
    assert len(consumer.committed) == 1
    assert len(dlq.published) == 0


def test_worker_routes_unparseable_json_to_dlq(db_session):
    """
    Unparseable JSON goes to DLQ and commits Kafka offset to avoid stalling.
    """
    consumer = MockConsumer()
    dlq = MockDLQPublisher()
    worker = POAcknowledgedConsumerWorker(consumer=consumer, dlq_publisher=dlq)

    msg = MockKafkaMessage("not-json-at-all")
    result = worker.handle_kafka_message(db_session, msg)

    assert result.status == "DLQ"
    assert len(dlq.published) == 1
    assert len(consumer.committed) == 1


def test_ack_for_unapproved_po_is_ignored(db_session, example_event, seed_po):
    seed_po.approval_status = "pending_vp_approval"
    db_session.commit()
    result = process_po_acknowledged_event(db_session, example_event)
    assert result.status == "SKIPPED_INVALID_STATE"
    db_session.refresh(seed_po)
    assert seed_po.status == "draft"


def test_ack_for_on_hold_po_keeps_the_hold(db_session, example_event, seed_po):
    seed_po.status = "on_hold"
    seed_po.hold_reason = "Supplier under review"
    seed_po.hold_source = "compliance"
    db_session.commit()
    result = process_po_acknowledged_event(db_session, example_event)
    assert result.status == "SKIPPED_INVALID_STATE"
    db_session.refresh(seed_po)
    assert seed_po.status == "on_hold"


def test_ack_from_other_supplier_is_rejected(db_session, example_event, seed_po):
    bad = json.loads(json.dumps(example_event))
    bad["payload"]["supplier_id"] = "SUP-99999"
    with pytest.raises(InvalidMessageError, match="does not own"):
        process_po_acknowledged_event(db_session, bad)
    db_session.refresh(seed_po)
    assert seed_po.status == "draft"


def test_ack_with_non_canonical_po_number_is_rejected(db_session, example_event):
    bad = json.loads(json.dumps(example_event))
    bad["payload"]["po_number"] = "PO-123"  # noncanonical-ok
    with pytest.raises(InvalidMessageError):
        process_po_acknowledged_event(db_session, bad)


