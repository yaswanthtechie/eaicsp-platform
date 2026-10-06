import json
import uuid
import pytest
import time

from app.core.config import settings
from datetime import UTC, datetime
from unittest.mock import MagicMock
from tests.fakes import InMemoryKafkaPublisher
from tests.conftest import seed_sales_history
from app.models.inventory import Inventory
from app.models.supplier import Supplier
from app.models.purchase_order import PurchaseOrder
from app.models.outbox import Outbox
from app.schemas.events import EventEnvelope, StockLowPayload, PurchaseOrderDraftedPayload
from app.services.outbox_service import record_event, get_pending_events
from app.services.outbox_relay import OutboxRelay
from app.services.kafka_producer import KafkaEventPublisher, KafkaPublishError
from app.services.purchase_order_service import create_draft_po_for_inventory
from app.services.inventory_service import check_and_record_low_stock


@pytest.fixture
def mock_supplier(db_session):
    supplier = Supplier(
        supplier_id="SUP-TEST-001",
        supplier_name="Test Supplier Logistics",
        sku_id="SKU-PO-DRAFT-1",
        unit_cost=25.0,
        lead_time_days=5,
    )
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


# ============================================================================
# 1. OUTBOX TABLE & ENVELOPE CONTRACT TESTS
# ============================================================================

def test_outbox_table_persists_envelope_structure(db_session):
    """
    Verify that the Outbox table stores events adhering to the standard EventEnvelope.
    """
    test_payload = {"sku_id": "SKU-ENV-1", "warehouse_id": "WH-1", "quantity": 10}
    entry = record_event(
        db=db_session,
        event_type="inventory.stock.low",
        aggregate_type="inventory",
        aggregate_id="SKU-ENV-1:WH-1",
        payload=test_payload,
        trace_id="trace-test-123",
    )
    db_session.commit()

    saved = db_session.query(Outbox).filter(Outbox.id == entry.id).first()
    assert saved is not None
    assert saved.event_type == "inventory.stock.low"
    assert saved.aggregate_type == "inventory"
    assert saved.aggregate_id == "SKU-ENV-1:WH-1"
    assert saved.status == "PENDING"
    assert saved.retry_count == 0
    assert saved.created_at is not None

    parsed_envelope = json.loads(saved.payload)
    assert parsed_envelope["event_type"] == "inventory.stock.low"
    assert parsed_envelope["producer"] == "inventory-service"
    assert parsed_envelope["event_version"] == "1.0"
    assert parsed_envelope["trace_id"] == "trace-test-123"
    assert parsed_envelope["payload"] == test_payload
    assert "event_id" in parsed_envelope
    assert "occurred_at" in parsed_envelope


# ============================================================================
# 2. HAPPY PATH EVENT EMISSION TESTS
# ============================================================================

def test_stock_low_event_emitted_on_reorder_threshold(db_session):
    """
    Verify that when an inventory item drops below reorder point,
    an 'inventory.stock.low' event is recorded in the outbox.
    """
    item = Inventory(
        sku_id="SKU-LOW-1",
        warehouse_id="WH-1",
        product_name="Low Stock Widget",
        category="Hardware",
        quantity_on_hand=5,
        lead_time_days=7,
        safety_stock=20,  # ROP will be > 5
    )
    db_session.add(item)
    db_session.commit()

    # Trigger check_and_record_low_stock
    check_and_record_low_stock(db=db_session, item=item)
    db_session.commit()

    outbox_events = (
        db_session.query(Outbox)
        .filter(Outbox.event_type == "inventory.stock.low")
        .all()
    )
    assert len(outbox_events) >= 1
    low_stock_event = outbox_events[-1]
    assert low_stock_event.aggregate_id == "SKU-LOW-1:WH-1"
    assert low_stock_event.status == "PENDING"

    payload_data = json.loads(low_stock_event.payload)["payload"]
    assert payload_data["sku_id"] == "SKU-LOW-1"
    assert payload_data["warehouse_id"] == "WH-1"
    assert payload_data["quantity_on_hand"] == 5
    assert payload_data["reorder_point"] >= 20


def test_po_drafted_event_emitted_atomically(db_session, mock_supplier):
    """
    Verify that create_draft_po_for_inventory automatically records
    an 'inventory.po.drafted' event into the outbox in the same transaction.
    """
    item = Inventory(
        sku_id="SKU-PO-DRAFT-1",
        warehouse_id="WH-CENTRAL",
        product_name="Draft PO Part",
        category="Electronics",
        quantity_on_hand=2,
        lead_time_days=5,
        safety_stock=15,
    )
    db_session.add(item)
    db_session.commit()

    # Create draft PO
    po = create_draft_po_for_inventory(db=db_session, inventory=item)
    assert po is not None

    # Verify PO exists in DB
    po_in_db = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po.po_id).first()
    assert po_in_db is not None
    assert po_in_db.status == "draft"

    # Verify outbox has inventory.po.drafted event
    outbox_event = (
        db_session.query(Outbox)
        .filter(
            Outbox.event_type == "inventory.po.drafted",
            Outbox.aggregate_id == po.po_id,
        )
        .first()
    )
    assert outbox_event is not None
    assert outbox_event.aggregate_type == "purchase_order"
    assert outbox_event.status == "PENDING"

    envelope = json.loads(outbox_event.payload)
    assert envelope["event_type"] == "inventory.po.drafted"
    assert envelope["producer"] == "inventory-service"
    po_payload = envelope["payload"]
    assert po_payload["po_id"] == po.po_id
    assert po_payload["sku_id"] == "SKU-PO-DRAFT-1"
    assert po_payload["warehouse_id"] == "WH-CENTRAL"
    assert po_payload["supplier_id"] == mock_supplier.supplier_id
    assert po_payload["status"] == "draft"
    assert po_payload["unit_cost"] == mock_supplier.unit_cost


# ============================================================================
# 3. FAILURE MODE 1: TRANSACTION ROLLBACK -> NO EVENT EMITTED
# ============================================================================

def test_failure_mode_rollback_guarantees_no_event_emitted(db_session):
    """
    Milestone 2 Requirement:
    Failure Case (1): Transaction rollback -> no event emitted.
    
    The database write and event must NEVER disagree.
    If an operation rolls back, the outbox record must be rolled back too.
    """
    po_id = f"PO-FAIL-{uuid.uuid4().hex[:8]}"

    try:
        # Simulate business write + outbox write inside an uncommitted transaction
        new_po = PurchaseOrder(
            po_id=po_id,
            sku_id="SKU-ROLLBACK",
            warehouse_id="WH-1",
            supplier_id="SUP-FAIL",
            quantity=100,
            unit_cost=10.0,
            expected_cost=1000.0,
            status="draft",
            approval_status="AUTO_APPROVED",
        )
        db_session.add(new_po)

        record_event(
            db=db_session,
            event_type="inventory.po.drafted",
            aggregate_type="purchase_order",
            aggregate_id=po_id,
            payload={"po_id": po_id, "sku_id": "SKU-ROLLBACK"},
        )

        # Simulate unexpected error before commit
        raise RuntimeError("Simulated database failure / validation abort!")

    except RuntimeError:
        db_session.rollback()

    # VERIFY: Neither the business record nor the outbox record exist!
    po_check = db_session.query(PurchaseOrder).filter(PurchaseOrder.po_id == po_id).first()
    assert po_check is None, "Purchase order must not exist after rollback"

    outbox_check = (
        db_session.query(Outbox)
        .filter(Outbox.aggregate_id == po_id)
        .first()
    )
    assert outbox_check is None, "Outbox event must NOT be emitted when transaction rolls back"


# ============================================================================
# 4. FAILURE MODE 2: KAFKA DOWN -> EVENT NOT LOST, PUBLISHED ON RECOVERY
# ============================================================================

def test_failure_mode_kafka_downtime_and_recovery(db_session):
    """
    Milestone 2 Requirement:
    Failure Case (2): Kafka down -> event not lost, stored in outbox,
    successfully published on recovery.
    """
    # 1. Store event atomically in DB
    event_id = str(uuid.uuid4())
    test_po_id = f"PO-KAFKA-DOWN-{event_id[:8]}"
    
    outbox_entry = record_event(
        db=db_session,
        event_type="inventory.po.drafted",
        aggregate_type="purchase_order",
        aggregate_id=test_po_id,
        payload={
            "po_id": test_po_id,
            "sku_id": "SKU-RECOVERY",
            "quantity": 50,
            "expected_cost": 500.0,
        },
    )
    db_session.commit()
    db_session.refresh(outbox_entry)

    assert outbox_entry.status == "PENDING"
    assert outbox_entry.retry_count == 0

    # 2. Simulate Kafka DOWN
    down_publisher = MagicMock(spec=KafkaEventPublisher)
    down_publisher.publish.side_effect = KafkaPublishError(
        "Connection to Kafka broker failed: [Errno 111] Connection refused"
    )

    relay = OutboxRelay(publisher=down_publisher)
    published_count, failed_count = relay.relay_pending_events(db=db_session)

    assert published_count == 0
    assert failed_count == 1

    # VERIFY: Event is NOT lost. It remains stored in outbox marked FAILED
    failed_record = db_session.query(Outbox).filter(Outbox.id == outbox_entry.id).first()
    assert failed_record is not None, "Outbox record must never be lost during Kafka outage"
    assert failed_record.status == "FAILED"
    assert failed_record.retry_count == 1
    assert "Connection refused" in failed_record.last_error
    assert failed_record.published_at is None

    # 3. Simulate Kafka RECOVERY
    recovered_publisher = InMemoryKafkaPublisher()
    recovery_relay = OutboxRelay(publisher=recovered_publisher)

    published_count_2, failed_count_2 = recovery_relay.relay_pending_events(db=db_session)

    assert published_count_2 >= 1
    assert failed_count_2 == 0

    # VERIFY: Event transitioned to PUBLISHED with timestamp set
    db_session.refresh(failed_record)
    assert failed_record.status == "PUBLISHED"
    assert failed_record.published_at is not None

    # VERIFY: Recovered publisher received the message
    delivered = [
        msg for msg in recovered_publisher.published_messages
        if msg["key"] == test_po_id
    ]
    assert len(delivered) == 1
    assert delivered[0]["topic"] == "inventory.po.drafted"
    parsed_msg = json.loads(delivered[0]["value"])
    assert parsed_msg["payload"]["po_id"] == test_po_id


# ============================================================================
# 5. RELAY ORDERING & IDEMPOTENCY
# ============================================================================

def test_outbox_relay_fifo_ordering_and_idempotency(db_session):
    """
    Verify that outbox events are processed in FIFO order and once published,
    subsequent relay executions do not republish them.
    """
    keys = ["KEY-1", "KEY-2", "KEY-3"]
    for k in keys:
        record_event(
            db=db_session,
            event_type="inventory.stock.low",
            aggregate_type="inventory",
            aggregate_id=k,
            payload={"key": k},
        )
    db_session.commit()

    publisher = InMemoryKafkaPublisher()
    relay = OutboxRelay(publisher=publisher)

    # First relay run
    pub_count, fail_count = relay.relay_pending_events(db=db_session)
    assert pub_count == 3
    assert fail_count == 0

    published_keys = [msg["key"] for msg in publisher.published_messages]
    assert published_keys == keys

    # Second relay run (should find 0 pending events)
    publisher.published_messages.clear()
    pub_count_2, fail_count_2 = relay.relay_pending_events(db=db_session)
    assert pub_count_2 == 0
    assert fail_count_2 == 0
    assert len(publisher.published_messages) == 0


# ============================================================================
# 6. END-TO-END HTTP API OUTBOX INTEGRATION
# ============================================================================

def test_api_create_inventory_low_stock_records_outbox(client, db_session):
    """
    Test creating an inventory item via REST API with quantity below ROP.
    Verifies that the API call commits both the inventory item and the outbox event.
    """
    from tests.conftest import seed_sales_history

    seed_sales_history("SKU-API-LOW", "WH-API-1", daily_quantity=10)

    payload = {
        "sku_id": "SKU-API-LOW",
        "product_name": "API Low Stock Test",
        "warehouse_id": "WH-API-1",
        "quantity_on_hand": 5,  # Much lower than 10 * 4 + 10 = 50 ROP
        "lead_time_days": 4,
        "safety_stock": 10,
    }

    resp = client.post("/api/v1/inventory/", json=payload)
    assert resp.status_code == 201

    outbox_entry = (
        db_session.query(Outbox)
        .filter(
            Outbox.event_type == "inventory.stock.low",
            Outbox.aggregate_id == "SKU-API-LOW:WH-API-1",
        )
        .first()
    )
    assert outbox_entry is not None
    assert outbox_entry.status == "PENDING"
    parsed = json.loads(outbox_entry.payload)
    assert parsed["event_type"] == "inventory.stock.low"
    assert parsed["payload"]["sku_id"] == "SKU-API-LOW"
    assert parsed["payload"]["quantity_on_hand"] == 5


def test_api_update_inventory_low_stock_records_outbox(client, db_session):
    """
    Test updating an inventory item via REST API so its quantity drops below ROP.
    Verifies that the update commits both the inventory decrement and the outbox event.
    """
    from tests.conftest import seed_sales_history

    seed_sales_history("SKU-API-UPD", "WH-API-2", daily_quantity=5)

    # 1. Create with sufficient stock
    create_payload = {
        "sku_id": "SKU-API-UPD",
        "product_name": "API Update Test",
        "warehouse_id": "WH-API-2",
        "quantity_on_hand": 100,  # Well above ROP
        "lead_time_days": 4,
        "safety_stock": 10,
        "unit_cost": 10.0,
    }
    resp1 = client.post("/api/v1/inventory/", json=create_payload)
    assert resp1.status_code == 201

    # 2. Update stock downward to 5 (below ROP ~ 30)
    current_version = resp1.json()["version"]
    update_payload = {
        "quantity_on_hand": 5,
        "version": current_version,
    }
    resp2 = client.put(
        "/api/v1/inventory/SKU-API-UPD/WH-API-2",
        json=update_payload,
    )
    assert resp2.status_code == 200

    outbox_entry = (
        db_session.query(Outbox)
        .filter(
            Outbox.event_type == "inventory.stock.low",
            Outbox.aggregate_id == "SKU-API-UPD:WH-API-2",
        )
        .first()
    )
    assert outbox_entry is not None
    assert outbox_entry.status == "PENDING"
    parsed = json.loads(outbox_entry.payload)
    assert parsed["payload"]["quantity_on_hand"] == 5

def test_real_producer_raises_when_broker_unreachable_and_event_is_kept(db_session):
    """
    Uses the REAL KafkaEventPublisher (no fake) pointed at a dead port.
    The event must stay in the outbox as FAILED, never PUBLISHED.
    Needs no running Kafka. Takes about 5s (the flush timeout).
    """
    record_event(
        db=db_session,
        event_type="inventory.po.drafted",
        aggregate_type="purchase_order",
        aggregate_id="PO-DEAD-BROKER",
        payload={"po_id": "PO-DEAD-BROKER"},
    )
    db_session.commit()

    relay = OutboxRelay(publisher=KafkaEventPublisher(bootstrap_servers="localhost:1"))
    published, failed = relay.relay_pending_events(db=db_session)

    assert (published, failed) == (0, 1)

    row = db_session.query(Outbox).one()
    assert row.status == "FAILED"
    assert row.published_at is None


@pytest.mark.integration
def test_outbox_relay_publishes_to_real_kafka(db_session):
    """
    End to end against the Kafka from docker-compose.dev.yml:
    outbox row -> relay -> real broker -> a real consumer reads it back.
    """
    from confluent_kafka import Consumer

    topic = "inventory.po.drafted"
    po_id = f"PO-REAL-{uuid.uuid4().hex[:8]}"

    record_event(
        db=db_session,
        event_type=topic,
        aggregate_type="purchase_order",
        aggregate_id=po_id,
        payload={"po_id": po_id},
    )
    db_session.commit()

    relay = OutboxRelay(publisher=KafkaEventPublisher())
    published, failed = relay.relay_pending_events(db=db_session)
    assert (published, failed) == (1, 0)

    consumer = Consumer(
        {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"inventory-test-{uuid.uuid4().hex}",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([topic])

    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            if msg.key() and msg.key().decode() == po_id:
                envelope = json.loads(msg.value())
                assert envelope["event_type"] == topic
                assert envelope["producer"] == "inventory-service"
                assert "occurred_at" in envelope
                assert envelope["payload"]["po_id"] == po_id
                break
        else:
            pytest.fail(f"{po_id} never arrived on topic {topic}")
    finally:
        consumer.close()


def test_sale_below_reorder_point_records_stock_low(client, db_session):
    seed_sales_history("SKU-SALE-LOW", "WH-1", daily_quantity=5)

    client.post(
        "/api/v1/inventory/",
        json={
            "sku_id": "SKU-SALE-LOW",
            "product_name": "Sale Low Item",
            "warehouse_id": "WH-1",
            "quantity_on_hand": 200,
            "lead_time_days": 4,
            "safety_stock": 10,
            "unit_cost": 5.0,
        },
    )

    # Only look at events caused by the sale.
    db_session.query(Outbox).delete()
    db_session.commit()

    resp = client.post(
        "/api/v1/inventory/decrement",
        params={"sku_id": "SKU-SALE-LOW", "warehouse_id": "WH-1", "quantity": 195},
    )
    assert resp.status_code == 200

    events = (
        db_session.query(Outbox)
        .filter(
            Outbox.event_type == "inventory.stock.low",
            Outbox.aggregate_id == "SKU-SALE-LOW:WH-1",
        )
        .all()
    )
    assert len(events) == 1
    assert json.loads(events[0].payload)["payload"]["quantity_on_hand"] == 5


def test_event_is_dead_lettered_after_max_retries(db_session, monkeypatch):
    monkeypatch.setattr(settings, "OUTBOX_MAX_RETRIES", 3)

    entry = record_event(
        db=db_session,
        event_type="inventory.stock.low",
        aggregate_type="inventory",
        aggregate_id="POISON",
        payload={"k": 1},
    )
    db_session.commit()

    relay = OutboxRelay(
        publisher=InMemoryKafkaPublisher(fail_with=KafkaPublishError("message too large"))
    )
    for _ in range(3):
        relay.relay_pending_events(db=db_session)

    db_session.refresh(entry)
    assert entry.status == "DEAD"
    assert entry.retry_count == 3
    assert get_pending_events(db_session) == []


def test_failing_events_do_not_starve_new_events(db_session):
    for i in range(3):
        record_event(
            db=db_session,
            event_type="inventory.stock.low",
            aggregate_type="inventory",
            aggregate_id=f"OLD-{i}",
            payload={"i": i},
        )
    db_session.commit()

    for row in db_session.query(Outbox).all():
        row.status = "FAILED"
        row.retry_count = 1
    db_session.commit()

    record_event(
        db=db_session,
        event_type="inventory.stock.low",
        aggregate_type="inventory",
        aggregate_id="NEW",
        payload={"new": True},
    )
    db_session.commit()

    assert get_pending_events(db_session, limit=1)[0].aggregate_id == "NEW"
