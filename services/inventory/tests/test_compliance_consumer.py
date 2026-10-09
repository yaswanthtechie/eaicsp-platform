from datetime import UTC, datetime, timedelta
import json
import threading
from unittest.mock import MagicMock
import pytest
from sqlalchemy.exc import OperationalError

from app.models.compliance_event import ProcessedEvent, SupplierComplianceState
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.services.compliance_consumer import (
    ComplianceConsumerWorker,
    DeadLetterPublishError,
    InvalidMessageError,
    classify_compliance_status,
    process_compliance_event,
)
from tests.fakes import FakeKafkaConsumer, FakeKafkaMessage, InMemoryKafkaPublisher


def supplier_name_for(supplier_id: str) -> str:
    return f"Supplier {supplier_id}"


def seed_supplier(db_session, supplier_id: str, name: str | None = None) -> None:
    if db_session.get(Supplier, supplier_id) is None:
        db_session.add(Supplier(
            supplier_id=supplier_id,
            supplier_name=name or supplier_name_for(supplier_id),
            sku_id=f"SKU-{supplier_id}",
            unit_cost=10.0,
            lead_time_days=3,
        ))
        db_session.commit()


def make_event(
    event_id: str = "evt-test-1",
    supplier_id: str = "SUP-TEST-1",
    new_status: str = "BLOCK",
    old_status: str = "CLEAR",
    reason: str = "Sanctions match detected",
    occurred_at: str | None = None,
    event_version=1,
    matched_list: list[str] | None = None,
) -> dict:
    """Exactly the shape published by services/compliance (no supplier_id)."""
    return {
        "event_id": event_id,
        "event_type": "compliance.supplier.status_changed",
        "event_version": event_version,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "producer": "compliance-service",
        "payload": {
            "supplier_name": supplier_name_for(supplier_id),
            "country": "India",
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": matched_list or ["OFAC"],
            "reason": reason,
            "screening_run_id": "run-test-1",
        },
    }


def seed_po(
    db_session,
    po_id: str,
    supplier_id: str,
    status: str = "draft",
    approval_status: str = "pending_vp_approval",
    hold_reason: str | None = None,
    hold_source: str | None = None,
) -> PurchaseOrder:
    seed_supplier(db_session, supplier_id)
    po = PurchaseOrder(
        po_id=po_id,
        sku_id=f"SKU-{po_id}",
        warehouse_id="WH-1",
        supplier_id=supplier_id,
        quantity=10,
        unit_cost=15.0,
        expected_cost=150.0,
        status=status,
        approval_status=approval_status,
        hold_reason=hold_reason,
        hold_source=hold_source or ("compliance" if status == "on_hold" else None),
    )
    db_session.add(po)
    db_session.commit()
    db_session.refresh(po)
    return po


def _run_until_drained(worker, consumer):
    """Run the real loop until the fake consumer has nothing left to deliver."""
    stop = threading.Event()
    original_poll = consumer.poll

    def poll(timeout):
        m = original_poll(timeout)
        if m is None:
            stop.set()
        return m

    consumer.poll = poll
    worker.run_worker_loop(poll_timeout=0, stop_event=stop)


# ============================================================================
# 1. STATUS CLASSIFICATION & BASIC PO ACTIONS (HOLD & RELEASE)
# ============================================================================

def test_classify_compliance_status():
    assert classify_compliance_status("BLOCK") == "BLOCKED"
    assert classify_compliance_status("blocked") == "BLOCKED"
    assert classify_compliance_status("CONFIRMED") == "BLOCKED"

    assert classify_compliance_status("REVIEW") == "NEEDS_REVIEW"
    assert classify_compliance_status("needs review") == "NEEDS_REVIEW"
    assert classify_compliance_status("needs_review") == "NEEDS_REVIEW"
    assert classify_compliance_status("under_review") == "NEEDS_REVIEW"
    assert classify_compliance_status("open") == "NEEDS_REVIEW"

    assert classify_compliance_status("CLEAR") == "CLEARED"
    assert classify_compliance_status("cleared") == "CLEARED"

    assert classify_compliance_status("UNKNOWN_STATUS") is None
    assert classify_compliance_status("") is None


def test_po_held_when_supplier_blocked(db_session):
    """
    When supplier moves to blocked: every open draft PO for that supplier
    must be put on hold with the reason recorded.
    """
    po1 = seed_po(db_session, "PO-BLK-1", "SUP-BLK-1", status="draft")
    po2 = seed_po(db_session, "PO-BLK-2", "SUP-BLK-1", status="draft")
    po_other = seed_po(db_session, "PO-OTHER", "SUP-OTHER", status="draft")
    po_received = seed_po(db_session, "PO-RCV", "SUP-BLK-1", status="received")

    event = make_event(
        event_id="EVT-BLK-1",
        supplier_id="SUP-BLK-1",
        new_status="BLOCK",
        reason="OFAC SDN match",
    )

    result = process_compliance_event(db_session, event)
    assert result.status == "PROCESSED"
    assert set(result.affected_pos) == {"PO-BLK-1", "PO-BLK-2"}

    # Refresh records
    db_session.refresh(po1)
    db_session.refresh(po2)
    db_session.refresh(po_other)
    db_session.refresh(po_received)

    assert po1.status == "on_hold"
    assert po1.hold_reason == "OFAC SDN match"
    assert po1.hold_source == "compliance"

    assert po2.status == "on_hold"
    assert po2.hold_reason == "OFAC SDN match"
    assert po2.hold_source == "compliance"

    # Other supplier untouched
    assert po_other.status == "draft"
    assert po_other.hold_reason is None

    # Received PO untouched
    assert po_received.status == "received"
    assert po_received.hold_reason is None


def test_po_held_when_supplier_needs_review(db_session):
    """
    When supplier moves to 'needs review': draft POs put on hold.
    """
    po = seed_po(db_session, "PO-REV-1", "SUP-REV-1", status="draft")

    event = make_event(
        event_id="EVT-REV-1",
        supplier_id="SUP-REV-1",
        new_status="needs review",
        reason="Fuzzy match on PEP list",
    )

    result = process_compliance_event(db_session, event)
    assert result.status == "PROCESSED"

    db_session.refresh(po)
    assert po.status == "on_hold"
    assert po.hold_reason == "Fuzzy match on PEP list"
    assert po.hold_source == "compliance"


def test_po_released_to_draft_when_supplier_cleared(db_session):
    """
    When supplier cleared again: held POs with hold_source='compliance' are released back to draft.
    """
    po1 = seed_po(db_session, "PO-CLR-1", "SUP-CLR-1", status="on_hold", hold_reason="Previous sanction", hold_source="compliance")
    po2 = seed_po(db_session, "PO-CLR-2", "SUP-CLR-1", status="on_hold", hold_reason="Previous sanction", hold_source="compliance")

    event = make_event(
        event_id="EVT-CLR-1",
        supplier_id="SUP-CLR-1",
        new_status="CLEAR",
        reason="False positive cleared by compliance officer",
    )

    result = process_compliance_event(db_session, event)
    assert result.status == "PROCESSED"
    assert set(result.affected_pos) == {"PO-CLR-1", "PO-CLR-2"}

    db_session.refresh(po1)
    db_session.refresh(po2)

    assert po1.status == "draft"
    assert po1.hold_reason is None
    assert po1.hold_source is None

    assert po2.status == "draft"
    assert po2.hold_reason is None
    assert po2.hold_source is None


# ============================================================================
# 2. IDEMPOTENCY: DUPLICATE EVENTS DO NOT CHANGE STATE
# ============================================================================

def test_duplicate_event_is_idempotent_and_stores_event_id(db_session):
    """
    Idempotent: the same event delivered twice must not change anything the second time.
    Store processed event_ids.
    """
    po = seed_po(db_session, "PO-IDEMP", "SUP-IDEMP", status="draft")

    event = make_event(
        event_id="EVT-IDEMP-99",
        supplier_id="SUP-IDEMP",
        new_status="BLOCK",
        reason="First delivery",
    )

    # First delivery
    res1 = process_compliance_event(db_session, event)
    assert res1.status == "PROCESSED"

    db_session.refresh(po)
    assert po.status == "on_hold"
    assert po.hold_reason == "First delivery"

    # Verify event_id is recorded in processed_events table
    saved_event = db_session.query(ProcessedEvent).filter(ProcessedEvent.event_id == "EVT-IDEMP-99").first()
    assert saved_event is not None
    assert saved_event.status == "PROCESSED"

    # Modify hold reason manually to verify second delivery does not touch it
    po.hold_reason = "Modified by human"
    db_session.commit()

    # Second delivery with the same event_id
    res2 = process_compliance_event(db_session, event)
    assert res2.status == "DUPLICATE"
    assert res2.affected_pos == []

    # State in database remains untouched
    db_session.refresh(po)
    assert po.status == "on_hold"
    assert po.hold_reason == "Modified by human"


# ============================================================================
# 3. COMMIT OFFSET ONLY AFTER DB WRITE SUCCEEDS & CRASH-BEFORE-COMMIT SAFETY
# ============================================================================

def test_crash_before_commit_is_safe_on_restart(db_session):
    po = seed_po(db_session, "PO-CRASH", "SUP-CRASH", status="draft")
    msg = FakeKafkaMessage(json.dumps(make_event(event_id="EVT-CRASH-1", supplier_id="SUP-CRASH")))
    consumer = FakeKafkaConsumer([msg])
    worker = ComplianceConsumerWorker(consumer=consumer, dlq_publisher=InMemoryKafkaPublisher(),
                                      db_session_factory=lambda: db_session)

    # The process dies between the DB commit and the Kafka commit.
    consumer.commit = MagicMock(side_effect=RuntimeError("process killed before offset commit"))
    with pytest.raises(RuntimeError, match="killed"):
        worker.handle_kafka_message(db=db_session, msg=msg)
    db_session.refresh(po)
    assert po.status == "on_hold"                       # the DB write happened
    del consumer.commit                                 # "restart": real commit behaviour again

    # Kafka redelivers the uncommitted message; idempotency makes it a no-op.
    result = worker.handle_kafka_message(db=db_session, msg=msg)
    assert result.status == "DUPLICATE"
    assert consumer.committed_messages == [msg]
    assert db_session.query(ProcessedEvent).filter_by(event_id="EVT-CRASH-1").count() == 1


def test_offset_not_committed_if_database_write_fails(db_session):
    """
    If the database write fails or raises an error, offset must NEVER be committed.
    """
    event = make_event(event_id="EVT-FAIL-1", supplier_id="SUP-FAIL", new_status="BLOCK")
    msg = FakeKafkaMessage(json.dumps(event))
    consumer = FakeKafkaConsumer([msg])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    # Simulate DB failure by passing a mock db that raises on query
    failing_db = MagicMock()
    failing_db.query.side_effect = RuntimeError("DB Connection Lost")

    with pytest.raises(RuntimeError, match="DB Connection Lost"):
        worker.handle_kafka_message(db=failing_db, msg=msg)

    # Offset was NOT committed
    assert len(consumer.committed_messages) == 0
    # Did not go to DLQ (transient DB error must be retried, not DLQ'd)
    assert len(dlq_pub.published_messages) == 0


# ============================================================================
# 4. OUT-OF-ORDER EVENTS: CLEARED ARRIVES BEFORE OLDER BLOCKED
# ============================================================================

def test_out_of_order_events_cleared_before_older_blocked_does_not_block(db_session):
    """
    Out-of-order events: if "cleared" arrives before an older "blocked",
    don't end up blocked. Use occurred_at to decide.
    """
    po = seed_po(db_session, "PO-ORDER-1", "SUP-ORDER-1", status="on_hold", hold_reason="Under investigation", hold_source="compliance")

    t_earlier = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    t_later = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    # Newer event: Supplier was CLEARED at t_later (1 hour ago)
    evt_cleared = make_event(
        event_id="EVT-CLEARED-NEWER",
        supplier_id="SUP-ORDER-1",
        new_status="CLEAR",
        occurred_at=t_later,
        reason="Cleared after thorough review",
    )

    res_clear = process_compliance_event(db_session, evt_cleared)
    assert res_clear.status == "PROCESSED"

    db_session.refresh(po)
    assert po.status == "draft"
    assert po.hold_reason is None

    # Supplier compliance state recorded at t_later
    state = db_session.query(SupplierComplianceState).filter_by(supplier_id="SUP-ORDER-1").first()
    assert state is not None
    assert state.last_status == "CLEAR"

    # Older event: Arrives out-of-order! Supplier was BLOCKED at t_earlier (2 hours ago)
    evt_blocked_older = make_event(
        event_id="EVT-BLOCKED-OLDER",
        supplier_id="SUP-ORDER-1",
        new_status="BLOCK",
        occurred_at=t_earlier,
        reason="Initial sanctions hit",
    )

    res_blocked = process_compliance_event(db_session, evt_blocked_older)
    assert res_blocked.status == "OUT_OF_ORDER"

    # CRITICAL: PO MUST NOT END UP BLOCKED!
    db_session.refresh(po)
    assert po.status == "draft"
    assert po.hold_reason is None

    # Supplier state remains CLEAR
    db_session.refresh(state)
    assert state.last_status == "CLEAR"


# ============================================================================
# 5. BAD MESSAGES ROUTED TO DLQ & CONSUMER KEEPS RUNNING
# ============================================================================

def test_bad_messages_unparseable_json_goes_to_dlq_with_reason(db_session):
    """
    Bad messages: unparseable JSON goes to a dead-letter topic with reason.
    Offset is committed so consumer moves forward.
    """
    bad_msg = FakeKafkaMessage(b"{invalid-json-payload-corrupted", partition=1, offset=42)
    consumer = FakeKafkaConsumer([bad_msg])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    res = worker.handle_kafka_message(db_session, bad_msg)
    assert res.status == "DLQ"

    # DLQ message published
    assert len(dlq_pub.published_messages) == 1
    dlq_entry = dlq_pub.published_messages[0]
    assert dlq_entry["topic"] == "compliance.supplier.status_changed.dlq"

    dlq_body = json.loads(dlq_entry["value"])
    assert "Unparseable JSON" in dlq_body["error"]
    assert dlq_body["consumer_group"] == "inventory-service"
    assert dlq_body["partition"] == 1
    assert dlq_body["offset"] == 42

    # Offset was committed so poison pill is cleared
    assert len(consumer.committed_messages) == 1


def test_bad_messages_unknown_event_version_goes_to_dlq(db_session):
    """
    Bad messages: unknown event_version (e.g. 2 or "1.0") goes to DLQ with reason.
    Both integer 2 and string "1.0" must be rejected.
    """
    # 1. Test event_version=2
    event2 = make_event(event_id="EVT-VER-2", event_version=2)
    bad_msg2 = FakeKafkaMessage(json.dumps(event2))
    consumer2 = FakeKafkaConsumer([bad_msg2])
    dlq_pub2 = InMemoryKafkaPublisher()

    worker2 = ComplianceConsumerWorker(
        consumer=consumer2,
        dlq_publisher=dlq_pub2,
        db_session_factory=lambda: db_session,
    )

    res2 = worker2.handle_kafka_message(db_session, bad_msg2)
    assert res2.status == "DLQ"
    assert len(dlq_pub2.published_messages) == 1
    dlq_body2 = json.loads(dlq_pub2.published_messages[0]["value"])
    assert "Unknown or unsupported event_version: 2" in dlq_body2["error"]
    assert len(consumer2.committed_messages) == 1

    # 2. Test event_version="1.0"
    event_str = make_event(event_id="EVT-VER-STR", event_version="1.0")
    bad_msg_str = FakeKafkaMessage(json.dumps(event_str))
    consumer_str = FakeKafkaConsumer([bad_msg_str])
    dlq_pub_str = InMemoryKafkaPublisher()

    worker_str = ComplianceConsumerWorker(
        consumer=consumer_str,
        dlq_publisher=dlq_pub_str,
        db_session_factory=lambda: db_session,
    )

    res_str = worker_str.handle_kafka_message(db_session, bad_msg_str)
    assert res_str.status == "DLQ"
    assert len(dlq_pub_str.published_messages) == 1
    dlq_body_str = json.loads(dlq_pub_str.published_messages[0]["value"])
    assert "Unknown or unsupported event_version: '1.0'" in dlq_body_str["error"]
    assert len(consumer_str.committed_messages) == 1


def test_bad_messages_missing_required_fields_goes_to_dlq(db_session):
    """
    Missing required fields in envelope or payload goes to DLQ with reason.
    """
    event = {
        "event_id": "EVT-NO-SUPP",
        "event_type": "compliance.supplier.status_changed",
        "event_version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "new_status": "BLOCK"
        }
    }
    msg = FakeKafkaMessage(json.dumps(event))
    consumer = FakeKafkaConsumer([msg])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    res = worker.handle_kafka_message(db_session, msg)
    assert res.status == "DLQ"

    assert len(dlq_pub.published_messages) == 1
    dlq_body = json.loads(dlq_pub.published_messages[0]["value"])
    assert "Missing 'supplier_name' (and no 'supplier_id')" in dlq_body["error"]


def test_consumer_keeps_running_through_bad_message(db_session):
    """
    Definition of done: One bad message must never stop the consumer.
    Consumer processes bad message (routes to DLQ) and keeps running,
    successfully processing the subsequent valid message.
    """
    po = seed_po(db_session, "PO-SURVIVE", "SUP-SURVIVE", status="draft")

    msg_bad = FakeKafkaMessage(b"corrupted-poison-pill-message", offset=101)
    msg_good = FakeKafkaMessage(
        json.dumps(make_event(
            event_id="EVT-GOOD-102",
            supplier_id="SUP-SURVIVE",
            new_status="BLOCK",
            reason="Confirmed Block",
        )),
        offset=102,
    )

    consumer = FakeKafkaConsumer([msg_bad, msg_good])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    # Run loop over both messages
    processed = worker.run_worker_loop(max_messages=2)
    assert processed == 2

    # 1. Bad message was routed to DLQ and committed
    assert len(dlq_pub.published_messages) == 1
    assert "Unparseable JSON" in dlq_pub.published_messages[0]["value"]

    # 2. Good message was processed and committed
    from tests.conftest import TestingSessionLocal
    verify_session = TestingSessionLocal()
    try:
        po_updated = verify_session.query(PurchaseOrder).filter_by(po_id="PO-SURVIVE").first()
        assert po_updated is not None
        assert po_updated.status == "on_hold"
        assert po_updated.hold_reason == "Confirmed Block"
        assert po_updated.hold_source == "compliance"
    finally:
        verify_session.close()

    # Both offsets committed
    assert len(consumer.committed_messages) == 2


# ============================================================================
# 6. BUSINESS LOGIC & ENDPOINTS FOR HELD PURCHASE ORDERS
# ============================================================================

def test_cannot_approve_or_receive_po_when_on_hold(db_session):
    """
    Business rule: When a PO is on hold, it cannot be approved or received.
    """
    from app.services.purchase_order_service import approve_purchase_order, receive_purchase_order

    po = seed_po(db_session, "PO-HOLD-LOCK", "SUP-HOLD", status="on_hold", hold_reason="Compliance investigation")

    with pytest.raises(ValueError, match="Cannot approve purchase order: PO is on hold"):
        approve_purchase_order(db=db_session, po_id=po.po_id)

    with pytest.raises(ValueError, match="Cannot receive purchase order: PO is on hold"):
        receive_purchase_order(db=db_session, po_id=po.po_id)


def test_get_and_list_purchase_order_endpoints(client, db_session):
    """
    API test: GET /api/v1/inventory/purchase-orders and GET /{po_id} return
    PO details including hold_reason when on hold.
    """
    seed_po(db_session, "PO-EP-1", "SUP-EP-1", status="on_hold", hold_reason="Sanctions review")
    seed_po(db_session, "PO-EP-2", "SUP-EP-1", status="draft")

    # 1. Get by ID
    resp = client.get("/api/v1/inventory/purchase-orders/PO-EP-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["po_id"] == "PO-EP-1"
    assert data["status"] == "on_hold"
    assert data["hold_reason"] == "Sanctions review"

    # 2. List with filter
    resp_filtered = client.get("/api/v1/inventory/purchase-orders?status=on_hold")
    assert resp_filtered.status_code == 200
    items = resp_filtered.json()
    assert len(items) >= 1
    assert all(item["status"] == "on_hold" for item in items)


# ============================================================================
# 7. NEW TESTS REQUESTED BY TL (ITEM 6)
# ============================================================================

def test_real_producer_event_holds_pos(db_session):
    seed_po(db_session, "PO-REAL", "SUP001")
    seed_supplier(db_session, "SUP001", name="supplier sup001 ")
    event = {   # copied from build_supplier_status_changed_event() in services/compliance
        "event_id": "real-1", "event_type": "compliance.supplier.status_changed", "event_version": 1,
        "occurred_at": datetime.now(UTC).isoformat(), "producer": "compliance-service",
        "payload": {"supplier_name": "supplier sup001 ", "country": "India", "old_status": "CLEAR",
                    "new_status": "BLOCK", "matched_list": ["OFAC"],
                    "reason": "Strong compliance match found", "screening_run_id": "run-123"},
    }
    result = process_compliance_event(db_session, event)
    assert result.status == "PROCESSED"
    assert db_session.get(PurchaseOrder, "PO-REAL").status == "on_hold"


def test_transient_db_error_is_retried_not_skipped(db_session, monkeypatch):
    import app.services.compliance_consumer as cc
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    seed_po(db_session, "PO-T1", "SUP-T1")
    seed_po(db_session, "PO-T2", "SUP-T2")
    m1 = FakeKafkaMessage(json.dumps(make_event(event_id="E1", supplier_id="SUP-T1")), offset=1)
    m2 = FakeKafkaMessage(json.dumps(make_event(event_id="E2", supplier_id="SUP-T2")), offset=2)
    consumer = FakeKafkaConsumer([m1, m2])
    worker = ComplianceConsumerWorker(consumer=consumer, dlq_publisher=InMemoryKafkaPublisher(),
                                      db_session_factory=lambda: db_session)

    real = cc.process_compliance_event
    failed = []

    def flaky(db, event_data):
        if event_data["event_id"] == "E1" and not failed:
            failed.append(True)
            raise OperationalError("UPDATE purchase_orders", {}, Exception("deadlock detected"))
        return real(db=db, event_data=event_data)

    monkeypatch.setattr(cc, "process_compliance_event", flaky)

    _run_until_drained(worker, consumer)

    assert consumer.seeks == [(0, 1)]
    assert [m.offset() for m in consumer.committed_messages] == [1, 2]
    db_session.expire_all()
    assert db_session.get(PurchaseOrder, "PO-T1").status == "on_hold"   # E1 was NOT lost


def test_dlq_down_does_not_commit_and_retries(db_session, monkeypatch):
    import app.services.compliance_consumer as cc
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)

    class FlakyDLQ(InMemoryKafkaPublisher):
        calls = 0
        def publish(self, topic, key, value):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("broker unavailable")
            return super().publish(topic, key, value)

    bad = FakeKafkaMessage(b"garbage", offset=5)
    consumer = FakeKafkaConsumer([bad])
    dlq = FlakyDLQ()
    worker = ComplianceConsumerWorker(consumer=consumer, dlq_publisher=dlq,
                                      db_session_factory=lambda: db_session)

    with pytest.raises(DeadLetterPublishError):          # first attempt: nothing committed
        worker.handle_kafka_message(db_session, bad)
    assert consumer.committed_messages == []

    _run_until_drained(worker, consumer)                  # retry succeeds
    assert len(dlq.published_messages) == 1
    assert consumer.committed_messages == [bad]


def test_future_occurred_at_is_rejected(db_session):
    future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    with pytest.raises(InvalidMessageError, match="future"):
        process_compliance_event(db_session, make_event(event_id="E-FUT", occurred_at=future))


def test_ambiguous_supplier_name_goes_to_dlq(db_session):
    seed_supplier(db_session, "SUP-A", name="Same Name")
    seed_supplier(db_session, "SUP-B", name="Same Name")
    event = make_event(event_id="E-AMB")
    event["payload"]["supplier_name"] = "Same Name"
    with pytest.raises(InvalidMessageError, match="Ambiguous"):
        process_compliance_event(db_session, event)


def test_unknown_supplier_is_recorded_and_not_retried(db_session):
    event = make_event(event_id="E-UNK", supplier_id="NOT-IN-INVENTORY")
    assert process_compliance_event(db_session, event).status == "UNKNOWN_SUPPLIER"
    assert process_compliance_event(db_session, event).status == "DUPLICATE"


def test_simulate_endpoint_is_gone(client):
    response = client.post("/api/v1/inventory/purchase-orders/compliance-events/simulate",
                           json={"supplier_id": "SUP001", "new_status": "CLEAR"})
    assert response.status_code in (404, 405)
