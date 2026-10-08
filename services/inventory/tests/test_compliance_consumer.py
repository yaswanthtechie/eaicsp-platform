from datetime import UTC, datetime, timedelta
import json
import pytest
from unittest.mock import MagicMock

from app.models.compliance_event import ProcessedEvent, SupplierComplianceState
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier
from app.services.compliance_consumer import (
    ComplianceConsumerWorker,
    InvalidMessageError,
    classify_compliance_status,
    process_compliance_event,
)
from tests.fakes import FakeKafkaConsumer, FakeKafkaMessage, InMemoryKafkaPublisher


def make_event(
    event_id: str = "evt-test-1",
    supplier_id: str = "SUP-TEST-1",
    new_status: str = "BLOCK",
    old_status: str = "CLEAR",
    reason: str = "Sanctions match detected",
    occurred_at: str | None = None,
    event_version: str = "1.0",
    matched_list: list[str] | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "event_type": "compliance.supplier.status_changed",
        "producer": "compliance-service",
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "event_version": event_version,
        "trace_id": "trace-test-123",
        "payload": {
            "supplier_id": supplier_id,
            "old_status": old_status,
            "new_status": new_status,
            "matched_list": matched_list or ["OFAC"],
            "reason": reason,
        },
    }


def seed_po(
    db_session,
    po_id: str,
    supplier_id: str,
    status: str = "draft",
    approval_status: str = "pending_vp_approval",
    hold_reason: str | None = None,
) -> PurchaseOrder:
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
    )
    db_session.add(po)
    db_session.commit()
    db_session.refresh(po)
    return po


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

    assert po2.status == "on_hold"
    assert po2.hold_reason == "OFAC SDN match"

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


def test_po_released_to_draft_when_supplier_cleared(db_session):
    """
    When supplier cleared again: held POs are released back to draft (not auto-sent).
    """
    po1 = seed_po(db_session, "PO-CLR-1", "SUP-CLR-1", status="on_hold", hold_reason="Previous sanction")
    po2 = seed_po(db_session, "PO-CLR-2", "SUP-CLR-1", status="on_hold", hold_reason="Previous sanction")

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

    assert po2.status == "draft"
    assert po2.hold_reason is None


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
    """
    Commit the offset only after the database write succeeds. If your service
    crashes between the two, the event is processed again on restart, and
    idempotency makes that safe. Test this.
    """
    po = seed_po(db_session, "PO-CRASH", "SUP-CRASH", status="draft")

    event = make_event(
        event_id="EVT-CRASH-1",
        supplier_id="SUP-CRASH",
        new_status="BLOCK",
        reason="Sanction flagged",
    )
    raw_json = json.dumps(event)

    msg = FakeKafkaMessage(raw_json)
    consumer = FakeKafkaConsumer([msg])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    # 1. Attempt 1: DB write succeeds, but service crashes before commit
    with pytest.raises(RuntimeError, match="Simulated service crash"):
        worker.handle_kafka_message(
            db=db_session,
            msg=msg,
            simulate_crash_before_commit=True,
        )

    # Offset was NOT committed because of the crash!
    assert len(consumer.committed_messages) == 0

    # But database write did succeed and wrote event_id to processed_events
    db_session.refresh(po)
    assert po.status == "on_hold"
    assert db_session.query(ProcessedEvent).filter_by(event_id="EVT-CRASH-1").first() is not None

    # 2. Service restarts: Kafka delivers the uncommitted message again
    res2 = worker.handle_kafka_message(
        db=db_session,
        msg=msg,
        simulate_crash_before_commit=False,
    )

    # Idempotency makes it safe: identified as duplicate
    assert res2.status == "DUPLICATE"

    # Now offset IS committed cleanly!
    assert len(consumer.committed_messages) == 1
    assert consumer.committed_messages[0] == msg


def test_offset_not_committed_if_database_write_fails():
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

    # Simulate DB failure by passing a mock db that raises on commit
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
    po = seed_po(db_session, "PO-ORDER-1", "SUP-ORDER-1", status="on_hold", hold_reason="Under investigation")

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
    Bad messages: unknown event_version (e.g. 2.0) goes to DLQ with reason.
    """
    event = make_event(event_id="EVT-VER-99", event_version="2.0")
    bad_msg = FakeKafkaMessage(json.dumps(event))
    consumer = FakeKafkaConsumer([bad_msg])
    dlq_pub = InMemoryKafkaPublisher()

    worker = ComplianceConsumerWorker(
        consumer=consumer,
        dlq_publisher=dlq_pub,
        db_session_factory=lambda: db_session,
    )

    res = worker.handle_kafka_message(db_session, bad_msg)
    assert res.status == "DLQ"

    assert len(dlq_pub.published_messages) == 1
    dlq_body = json.loads(dlq_pub.published_messages[0]["value"])
    assert "Unknown or unsupported event_version: '2.0'" in dlq_body["error"]

    assert len(consumer.committed_messages) == 1


def test_bad_messages_missing_required_fields_goes_to_dlq(db_session):
    """
    Missing required fields in envelope or payload goes to DLQ with reason.
    """
    # Missing supplier_id in payload
    event = {
        "event_id": "EVT-NO-SUPP",
        "event_type": "compliance.supplier.status_changed",
        "event_version": "1.0",
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
    assert "Missing or invalid 'supplier_id'" in dlq_body["error"]


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
