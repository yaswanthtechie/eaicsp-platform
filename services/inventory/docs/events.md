# Inventory Service — Event Contract Specification

## Overview

The **Inventory Service** utilizes the **Transactional Outbox Pattern** to publish domain events to Apache Kafka. This pattern guarantees **dual-write consistency**: the database mutation and the outbound event are committed in the same database transaction. The database state and published events will **never disagree**.

---

## Architecture: Transactional Outbox & Relay

```
+-----------------------------------------------------------------------------------+
|                            INVENTORY SERVICE BOUNDARY                            |
|                                                                                   |
|  +------------------------+                                                       |
|  | Business Mutation      |                                                       |
|  | (Inventory / Draft PO) |                                                       |
|  +-----------+------------+                                                       |
|              |                                                                    |
|              v [Same ACID Transaction]                                            |
|  +-------------------------------------------------------+                        |
|  |                   PostgreSQL Database                 |                        |
|  |  +--------------------+       +--------------------+  |                        |
|  |  | Business Tables    |       | Outbox Table       |  |                        |
|  |  | (inventory,        |       | (id, event_type,   |  |                        |
|  |  |  purchase_orders)  |       |  payload, status)  |  |                        |
|  |  +--------------------+       +---------+----------+  |                        |
|  +-----------------------------------------|-------------+                        |
|                                            |                                      |
|                                            v (Polls PENDING/FAILED)               |
|                                  +-------------------+                            |
|                                  |   Outbox Relay    |                            |
|                                  +---------+---------+                            |
+--------------------------------------------|--------------------------------------+
                                             |
                                             v (At-Least-Once Delivery)
                                   +-------------------+
                                   |   Apache Kafka    |
                                   |  (Broker Cluster) |
                                   +---------+---------+
                                             |
                      +----------------------+----------------------+
                      |                                             |
                      v                                             v
          `inventory.stock.low`                         `inventory.po.drafted`
     (Downstream: Procurement/Replenishment)      (Downstream: Compliance/Approvals)
```

---

## Guarantees & Failure Semantics

1. **Atomic Dual-Write**: If a transaction aborts or rolls back in the database, the outbox record is rolled back simultaneously. No phantom event will ever be published.
2. **Kafka Outage Resilience**: If Kafka is unreachable, events remain securely persisted in the PostgreSQL `outbox` table (marked as `FAILED` with retry metadata). When Kafka recovers, the `OutboxRelay` delivers all pending events.
3. **Delivery Semantics**: **At-Least-Once Delivery**. Downstream consumers should be idempotent, utilizing the `event_id` in the envelope for deduplication.
4. **Ordering**: Events for the same aggregate partition on the aggregate key and are published in FIFO order.

---

## Standard Event Envelope

Every event emitted by the Inventory Service is wrapped in a standard `EventEnvelope`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `event_id` | `string` (UUIDv4) | Unique event identifier for tracing and idempotency deduplication |
| `event_type` | `string` | The topic / event classification |
| `source` | `string` | Originating microservice (`"inventory-service"`) |
| `timestamp` | `string` (ISO8601 UTC) | Timestamp when the event was created |
| `version` | `string` | Envelope version schema (`"1.0"`) |
| `trace_id` | `string` (Optional) | Distributed trace identifier |
| `payload` | `object` | Domain-specific event body |

---

## Topic 1: `inventory.stock.low`

### Description
Published whenever inventory on hand drops below the calculated Reorder Point (ROP) during creation, stock decrement, or bulk updates.

### Routing Key
* Kafka Partition Key: `{sku_id}:{warehouse_id}` (e.g. `SKU-001:WH-001`)

### Payload Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `sku_id` | `string` | SKU identifier |
| `warehouse_id` | `string` | Warehouse identifier |
| `quantity_on_hand` | `integer` | Current stock level after update |
| `reorder_point` | `integer` | Calculated reorder point threshold |
| `safety_stock` | `integer` | Configured/adjusted safety stock level |
| `avg_daily_demand` | `float` | Rolling average daily demand |

### Example Event
```json
{
  "event_id": "b9c51ff8-45e0-40e1-95eb-3fa5bf237075",
  "event_type": "inventory.stock.low",
  "producer": "inventory-service",
  "occurred_at": "2026-09-30T12:00:00.000000Z",
  "event_version": "1.0",
  "trace_id": "trace-8891-xyz",
  "payload": {
    "sku_id": "SKU-LOW-1",
    "warehouse_id": "WH-1",
    "quantity_on_hand": 5,
    "reorder_point": 25,
    "safety_stock": 10,
    "avg_daily_demand": 3.75
  }
}
```

---

## Topic 2: `inventory.po.drafted`

### Description
Published whenever an automatic draft Purchase Order is generated in response to low stock.

### Routing Key
* Kafka Partition Key: `{po_id}` (e.g. `PO-20260930-123456`)

### Payload Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `po_id` | `string` | Unique Purchase Order identifier |
| `sku_id` | `string` | SKU identifier to replenish |
| `warehouse_id` | `string` | Destination warehouse identifier |
| `supplier_id` | `string` | Selected supplier identifier |
| `quantity` | `integer` | Reorder order quantity |
| `unit_cost` | `float` | Unit cost agreed with supplier |
| `expected_cost` | `float` | Total expected cost (`quantity * unit_cost`) |
| `status` | `string` | Purchase order status (`"draft"`) |
| `approval_status` | `string` | Approval status (`"AUTO_APPROVED"` or `"PENDING_APPROVAL"`) |
| `created_at` | `string` (ISO8601 UTC) | Purchase order timestamp |

### Example Event
```json
{
  "event_id": "d4a77e8a-2114-41d9-95a9-f5978daec532",
  "event_type": "inventory.po.drafted",
  "producer": "inventory-service",
  "occurred_at": "2026-09-30T12:05:00.000000Z",
  "event_version": "1.0",
  "trace_id": null,
  "payload": {
    "po_id": "PO-20260930-001",
    "sku_id": "SKU-PO-DRAFT-1",
    "warehouse_id": "WH-CENTRAL",
    "supplier_id": "SUP-TEST-001",
    "quantity": 23,
    "unit_cost": 25.0,
    "expected_cost": 575.0,
    "status": "draft",
    "approval_status": "AUTO_APPROVED",
    "created_at": "2026-09-30T12:05:00.000000Z"
  }
}
```

---

## Database Outbox Schema Reference

Created and tracked via Alembic migration `002_create_outbox_table`:

```sql
CREATE TABLE outbox (
    id VARCHAR PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    aggregate_type VARCHAR NOT NULL,
    aggregate_id VARCHAR NOT NULL,
    payload TEXT NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP NOT NULL,
    published_at TIMESTAMP
);

CREATE INDEX ix_outbox_event_type ON outbox (event_type);
CREATE INDEX ix_outbox_aggregate_id ON outbox (aggregate_id);
CREATE INDEX ix_outbox_status ON outbox (status);
CREATE INDEX ix_outbox_created_at ON outbox (created_at);
```
