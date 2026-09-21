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
python -m uvicorn app.main:app --reload --port 8001
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
* Self-parent and circular hierarchy validation

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

Allowed roles:

```text
warehouse_manager
procurement_manager
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

Normal permissions:

```text
inventory:read
inventory:write
```

Special endpoint access:

| Operation   | Roles                                      |
| ----------- | ------------------------------------------ |
| Bulk update | `warehouse_manager`, `procurement_manager` |
| Bulk upload | `warehouse_manager`, `procurement_manager` |
| Draft PO    | `warehouse_manager`, `procurement_manager` |
| What-if     | `ceo`, `vp_operations`                     |

Authentication responses:

* `401` — Missing or invalid token
* `403` — Unauthorized role/permission
* `503` — Authentication service unavailable or timeout

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

## Round 6 Status

| Milestone                    | Status    |
| ---------------------------- | --------- |
| M1 — Multi-Echelon Inventory | Completed |
| M2 — Automatic Draft PO      | Completed |
| M3 — Inventory Valuation     | Completed |
| M4 — Optimistic Locking      | Completed |
| M5 — Permissions and RBAC    | Completed |
