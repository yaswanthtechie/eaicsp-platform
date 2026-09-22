﻿# Inventory Service

FastAPI microservice for managing inventory across multiple warehouses.

## Technology

* Python 3.12
* FastAPI
* PostgreSQL
* SQLAlchemy
* Pydantic
* HTTPX
* Pytest

## Quick Start

```powershell
cd services\inventory
.\myenv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Swagger:

```text
http://localhost:8001/docs
```

Platform Auth Service:

```text
http://localhost:8005
```

---

## Milestone 1 — Multi-Echelon Inventory

Supports:

* Central → Regional → Local warehouse hierarchy
* Reorder point calculation
* Low-stock detection
* Warehouse-to-warehouse transfers
* Parent warehouse shortage fulfillment
* Self-parent validation
* Circular hierarchy validation

Reorder point:

```text
Reorder Point =
Average Daily Demand × Lead Time
+ Adjusted Safety Stock
```

Main API:

```text
POST /api/v1/inventory/multi-echelon/fulfill
```

---

## Milestone 2 — Automatic Draft Purchase Orders

When inventory falls below the reorder point:

* Calculates suggested quantity
* Selects the lowest-cost supplier
* Calculates expected cost
* Creates a structured draft PO
* Prevents duplicate draft POs

Draft PO:

```text
POST /api/v1/inventory/purchase-orders/draft
```

Draft PO generation is triggered when inventory reaches the reorder condition during:

* Inventory creation
* Inventory update
* Bulk inventory operations
* Stock decrement

Required permission:

```text
inventory:write
```

Receive PO:

```text
POST /api/v1/inventory/purchase-orders/{po_id}/receive
```

Receiving a PO:

* Increases inventory
* Creates a cost layer using the PO unit cost
* Increments inventory version
* Changes status to `received`

---

## Milestone 3 — Inventory Valuation

Supports:

* FIFO valuation
* Weighted-average valuation
* Cost-layer tracking
* Cost-layer consumption during stock movement
* Warehouse and category reporting

API:

```text
GET /api/v1/inventory/reports/inventory-value
```

Example:

```text
GET /api/v1/inventory/reports/inventory-value?valuation_method=fifo
```

Supported methods:

```text
fifo
weighted_average
```

### Opening Inventory Cost

Inventory creation supports an optional `unit_cost` field.

When `quantity_on_hand` is greater than zero and `unit_cost` is provided, an opening cost layer is created for the inventory.

Example:

```json
{
    "sku_id": "SKU001",
    "product_name": "Example Product",
    "warehouse_id": "WH001",
    "category": "Electronics",
    "quantity_on_hand": 40,
    "lead_time_days": 5,
    "safety_stock": 10,
    "warehouse_type": "local",
    "unit_cost": 12.50
}
```

If `unit_cost` is omitted and no previous cost exists for the SKU and warehouse, the physical inventory can still be created and moved. However, the uncosted quantity is not included in inventory valuation until cost information becomes available.

---

## Stock Decrement and Cost History

Stock can still be physically decremented when cost-layer history is missing or only partially covers the quantity.

Available cost layers are consumed when possible.

If the available cost layers do not cover the entire decrement:

* Physical inventory quantity is still reduced.
* Available cost layers are consumed.
* The uncovered quantity remains uncosted for valuation.
* A warning is logged for incomplete cost history.

Missing cost history affects valuation accuracy but does not prevent physical inventory movement.

Stock decrement API:

```text
POST /api/v1/inventory/decrement
```

---

## Milestone 4 — Optimistic Locking

Each inventory record contains a `version`.

```text
Version 1
   ↓
Successful Update
   ↓
Version 2
```

If an update uses an old version, the service rejects the request with a conflict instead of overwriting newer data.

This prevents stale updates from silently overwriting newer inventory changes.

---

## Milestone 5 — Permissions and Authentication

Inventory uses the real Platform Auth Service.

```text
Client
  ↓
Inventory Service
  ↓
Platform Auth Service
  ↓
Token + Role + Permissions
  ↓
Allow / Reject
```

The inventory service calls the real authentication verification endpoint.

Normal permissions:

```text
inventory:read
inventory:write
```

### Protected Operations

| Operation                  | Required access                              |
| -------------------------- | -------------------------------------------- |
| Inventory read operations  | `inventory:read`                             |
| Inventory write operations | `inventory:write`                            |
| Bulk update                | `warehouse_manager` or `procurement_manager` |
| Bulk upload                | `warehouse_manager` or `procurement_manager` |
| Draft PO                   | `inventory:write`                            |
| Receive PO                 | `inventory:write`                            |
| What-if                    | `ceo` or `vp_operations`                     |

Authentication responses:

* `401` — Missing or invalid token
* `403` — Insufficient role or permission
* `503` — Authentication service unavailable, timeout, or unexpected authentication-service failure

Authentication requests include:

```text
Authorization: Bearer <token>
X-Caller-Service: inventory-service
X-Request-ID: <request-id>
```

---

## Concurrency and Bulk Operations

Bulk updates use database row-level locking:

```text
SELECT ... FOR UPDATE
```

Rows are locked consistently using:

```text
sku_id + warehouse_id
```

This helps prevent concurrent updates from overwriting each other.

Bulk CSV upload:

```text
POST /api/v1/inventory/bulk-upload
```

Bulk update:

```text
POST /api/v1/inventory/bulk-update
```

---

## What-If Simulation

Simulates demand changes without permanently modifying inventory.

```text
POST /api/v1/inventory/what-if
```

Allowed roles:

```text
ceo
vp_operations
```

---

## Main APIs

| Method | Endpoint                                            |
| ------ | --------------------------------------------------- |
| POST   | `/api/v1/inventory`                                 |
| GET    | `/api/v1/inventory`                                 |
| GET    | `/api/v1/inventory/{sku_id}/{warehouse_id}`         |
| PUT    | `/api/v1/inventory/{sku_id}/{warehouse_id}`         |
| DELETE | `/api/v1/inventory/{sku_id}/{warehouse_id}`         |
| GET    | `/api/v1/inventory/reorder-plan`                    |
| GET    | `/api/v1/inventory/low-stock`                       |
| POST   | `/api/v1/inventory/decrement`                       |
| POST   | `/api/v1/inventory/bulk-upload`                     |
| POST   | `/api/v1/inventory/bulk-update`                     |
| POST   | `/api/v1/inventory/what-if`                         |
| POST   | `/api/v1/inventory/multi-echelon/fulfill`           |
| POST   | `/api/v1/inventory/purchase-orders/draft`           |
| POST   | `/api/v1/inventory/purchase-orders/{po_id}/receive` |
| GET    | `/api/v1/inventory/reports/inventory-value`         |

---

## Inventory Creation

The `POST /api/v1/inventory` endpoint accepts the following fields:

| Field                 | Description                                   |
| --------------------- | --------------------------------------------- |
| `sku_id`              | Product/SKU identifier                        |
| `product_name`        | Product name                                  |
| `warehouse_id`        | Warehouse identifier                          |
| `category`            | Inventory category                            |
| `quantity_on_hand`    | Current physical stock                        |
| `lead_time_days`      | Supplier/replenishment lead time              |
| `safety_stock`        | Safety-stock quantity                         |
| `warehouse_type`      | `central`, `regional`, or `local`             |
| `parent_warehouse_id` | Parent warehouse in the hierarchy             |
| `unit_cost`           | Optional opening unit cost used for valuation |

`unit_cost` is optional.

When positive opening stock is created with `unit_cost`, the service creates the corresponding opening inventory cost layer.

---

## Database

Main tables:

* `inventory`
* `sales_history`
* `suppliers`
* `purchase_orders`
* `inventory_cost_layers`

Inventory uses:

```text
sku_id + warehouse_id
```

as the composite primary key.

---

## Testing

Run all tests:

```powershell
python -m pytest -v
```

Run regression tests:

```powershell
python -m pytest tests/test_regressions.py -v
```

Run inventory tests:

```powershell
python -m pytest tests/test_inventory.py -v
```

Coverage:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

Authentication tests use:

```text
WAREHOUSE_MANAGER_TOKEN
PROCUREMENT_MANAGER_TOKEN
CEO_TOKEN
VP_OPERATIONS_TOKEN
EXPIRED_TOKEN
```

---

## Environment Configuration

The inventory service uses environment variables for database and authentication configuration.

Example configuration is provided in:

```text
.env.example
```

The actual local configuration should be stored in:

```text
.env
```

The real `.env` file must not be committed to the repository.

Important configuration includes:

```text
DATABASE_URL
TEST_DATABASE_URL
PLATFORM_AUTH_URL
WAREHOUSE_MANAGER_TOKEN
PROCUREMENT_MANAGER_TOKEN
CEO_TOKEN
VP_OPERATIONS_TOKEN
EXPIRED_TOKEN
```

---

## Round 6 Status

| Milestone                           | Status    |
| ----------------------------------- | --------- |
| M1 — Multi-Echelon Inventory        | Completed |
| M2 — Automatic Draft PO             | Completed |
| M3 — Inventory Valuation            | Completed |
| M4 — Optimistic Locking             | Completed |
| M5 — Permissions and Authentication | Completed |
