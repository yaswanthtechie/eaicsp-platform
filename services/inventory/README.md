# Inventory Service

## 1. Overview

The Inventory Service is a FastAPI microservice for managing inventory across multiple warehouses.

### Main Features

* Multi-echelon inventory management
* Reorder point calculation
* Low-stock detection
* Warehouse-to-warehouse stock transfer
* Automatic draft purchase orders
* FIFO and weighted-average inventory valuation
* Optimistic locking and version control
* Platform authentication and fine-grained RBAC
* Row-level locking for concurrent updates
* Bulk inventory update and CSV upload
* What-if inventory simulation

### Technology Stack

| Technology  | Purpose                     |
| ----------- | --------------------------- |
| Python 3.12 | Runtime                     |
| FastAPI     | REST API                    |
| PostgreSQL  | Database                    |
| SQLAlchemy  | ORM                         |
| Pydantic    | Validation                  |
| HTTPX       | Platform Auth communication |
| Pytest      | Testing                     |

---

# 2. Milestone 1 — Multi-Echelon Inventory

The inventory network follows a warehouse hierarchy:

```text
Central Warehouse
        ↓
Regional Warehouse
        ↓
Local Warehouse
```

Each inventory record maintains:

* SKU
* Warehouse
* Product
* Category
* Quantity
* Average daily demand
* Lead time
* Safety stock
* Warehouse type
* Parent warehouse
* Version

### Reorder Point

```text
Reorder Point =
Average Daily Demand × Lead Time
+ Adjusted Safety Stock
```

### Multi-Echelon Fulfillment

When a warehouse has insufficient stock, the service checks its parent warehouse before triggering supplier replenishment.

```text
Local Warehouse
      ↓
Check Parent Warehouse
      ↓
Stock Available?
   /       \
 Yes        No
 ↓           ↓
Transfer   Supplier
 Stock     Replenishment
```

### APIs

| Method | Endpoint                                  | Purpose          |
| ------ | ----------------------------------------- | ---------------- |
| POST   | `/api/v1/inventory`                       | Create inventory |
| GET    | `/api/v1/inventory`                       | List inventory   |
| GET    | `/api/v1/inventory/reorder-plan`          | Reorder planning |
| GET    | `/api/v1/inventory/low-stock`             | Low-stock items  |
| POST   | `/api/v1/inventory/multi-echelon/fulfill` | Fulfill shortage |

---

# 3. Milestone 2 — Demand-Driven Automatic Draft Purchase Order

When inventory falls below the reorder point, the service can generate a structured draft purchase order.

### Supplier Selection

Suppliers are searched for the requested SKU.

The supplier with the lowest available unit cost is selected.

```text
SKU
 ↓
Find Suppliers
 ↓
Compare Unit Cost
 ↓
Select Supplier
 ↓
Create Draft PO
```

### Suggested Quantity

```text
Suggested Quantity =
Reorder Point - Current Quantity
```

### Expected Cost

```text
Expected Cost =
Suggested Quantity × Unit Cost
```

### Draft PO Data

A draft PO contains:

* PO ID
* SKU
* Warehouse
* Supplier
* Quantity
* Unit cost
* Expected cost
* Status

The initial status is:

```text
draft
```

### API

```text
POST /api/v1/purchase-orders/draft
```

### Allowed Roles

* `warehouse_manager`
* `procurement_manager`

### Authentication Responses

| Situation                                  |                  Response |
| ------------------------------------------ | ------------------------: |
| Authorization header missing               |        `401 Unauthorized` |
| Invalid/expired token                      |        `401 Unauthorized` |
| User authenticated but role is not allowed |           `403 Forbidden` |
| Auth service times out                     | `503 Service Unavailable` |
| Auth service is unavailable                | `503 Service Unavailable` |
| Unexpected auth-service response           | `503 Service Unavailable` |

---

# 4. Milestone 3 — Inventory Valuation

Inventory valuation supports:

1. FIFO
2. Weighted Average

## FIFO

FIFO consumes the oldest cost layers first.

Example:

```text
50 units × ₹10
50 units × ₹20
```

For 80 units:

```text
50 × ₹10 = ₹500
30 × ₹20 = ₹600

FIFO Value = ₹1,100
```

## Weighted Average

```text
50 × ₹10 = ₹500
50 × ₹20 = ₹1,000

Total Cost = ₹1,500
Total Quantity = 100

Average Cost = ₹15
```

For 80 units:

```text
80 × ₹15 = ₹1,200
```

### Report Grouping

The valuation report is grouped by:

```text
Warehouse + Category
```

### API

```text
GET /api/v1/reports/inventory-value
```

Supported methods:

```text
valuation_method=fifo
valuation_method=weighted_average
```

Example:

```text
GET /api/v1/reports/inventory-value?valuation_method=fifo
```

---

# 5. Milestone 4 — Optimistic Locking and Version Control

Inventory records maintain a `version` field for optimistic concurrency control.

### Version Flow

```text
Current Record
     ↓
Read Version
     ↓
Update With Expected Version
     ↓
Version Matches?
   /       \
 Yes        No
 ↓           ↓
Update     Reject
Record     Conflict
 ↓
Increment Version
```

For example:

```text
Current version = 1

Request A expects version = 1
Request A succeeds
New version = 2

Request B still expects version = 1
Request B is rejected
```

This prevents a stale update from overwriting a newer update.

### Version Conflict

A stale update is rejected when the supplied version does not match the current database version.

The version is incremented only after a successful update.

---

# 6. Milestone 5 — Fine-Grained Permissions and RBAC

The Inventory Service integrates with the real Platform Auth Service.

### Authentication Flow

```text
Client
  ↓
Inventory Service
  ↓
Platform Auth Service
  ↓
Validate Bearer Token
  ↓
Return User + Role
  ↓
Check Permission
  ↓
Allow / Reject
```

Requests include:

```text
Authorization: Bearer <token>
X-Caller-Service: inventory-service
```

### Authentication Responses

| Situation                                  |                  Response |
| ------------------------------------------ | ------------------------: |
| Authorization header missing               |        `401 Unauthorized` |
| Invalid/expired token                      |        `401 Unauthorized` |
| User authenticated but role is not allowed |           `403 Forbidden` |
| Auth service times out                     | `503 Service Unavailable` |
| Auth service is unavailable                | `503 Service Unavailable` |
| Unexpected auth-service response           | `503 Service Unavailable` |

### Role Permissions

| Operation          | Allowed Roles                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Bulk update        | `warehouse_manager`, `procurement_manager`                                                                               |
| Bulk upload        | `warehouse_manager`, `procurement_manager`                                                                               |
| Draft PO           | `warehouse_manager`, `procurement_manager`                                                                               |
| What-if simulation | `ceo`, `vp_operations`                                                                                                   |
| Valuation report   | `analyst`, `warehouse_manager`, `procurement_manager`, `logistics_manager`, `compliance_officer`, `vp_operations`, `ceo` |

---

# 7. Row-Level Locking

Bulk inventory updates use database row-level locking to protect concurrent updates.

### Endpoint

```text
POST /api/v1/inventory/bulk-update
```

The service uses:

```text
SELECT ... FOR UPDATE
```

before modifying inventory rows.

### Locking Flow

```text
Request 1
   ↓
Lock Row
   ↓
Update
   ↓
Commit
   ↓
Release

Request 2
   ↓
Wait for Lock
   ↓
Update
   ↓
Commit
```

Rows are locked in a consistent order using:

```text
sku_id + warehouse_id
```

This reduces deadlock risk during concurrent bulk updates.

---

# 8. Bulk CSV Upload

Inventory can be uploaded through CSV.

### API

```text
POST /api/v1/inventory/bulk-upload
```

Validation includes:

* Required fields
* SKU and warehouse
* Quantity validation
* Negative quantity rejection
* Inventory consistency
* CSV size validation

Allowed roles:

```text
warehouse_manager
procurement_manager
```

---

# 9. What-If Simulation

The service provides demand simulation without permanently modifying actual inventory.

### API

```text
POST /api/v1/inventory/what-if
```

The response includes:

* Demand growth percentage
* Total items
* Affected items
* Suggested order quantity
* Item-level details

Allowed roles:

```text
ceo
vp_operations
```

---

# 10. Database Design

### Main Tables

| Table                   | Purpose                           |
| ----------------------- | --------------------------------- |
| `inventory`             | Current inventory                 |
| `sales_history`         | Historical sales                  |
| `suppliers`             | Supplier information              |
| `purchase_orders`       | Draft purchase orders             |
| `inventory_cost_layers` | FIFO/weighted-average cost layers |

### Inventory Key

Inventory uses a composite primary key:

```text
sku_id + warehouse_id
```

This allows the same SKU to exist independently in multiple warehouses.

### Cost Layers

Cost layers store:

* SKU
* Warehouse
* Category
* Quantity received
* Remaining quantity
* Unit cost
* Received date

They support FIFO and weighted-average valuation.

---

# 11. API Summary

| Method | Endpoint                                  | Purpose                   |
| ------ | ----------------------------------------- | ------------------------- |
| POST   | `/api/v1/inventory`                       | Create inventory          |
| GET    | `/api/v1/inventory`                       | List inventory            |
| GET    | `/api/v1/inventory/reorder-plan`          | Reorder plan              |
| GET    | `/api/v1/inventory/low-stock`             | Low stock                 |
| POST   | `/api/v1/inventory/multi-echelon/fulfill` | Multi-echelon fulfillment |
| POST   | `/api/v1/inventory/bulk-update`           | Row-locked bulk update    |
| POST   | `/api/v1/inventory/bulk-upload`           | CSV upload                |
| POST   | `/api/v1/inventory/what-if`               | What-if simulation        |
| POST   | `/api/v1/purchase-orders/draft`           | Draft PO                  |
| GET    | `/api/v1/reports/inventory-value`         | Valuation report          |

---

# 12. Testing

### Run All Tests

```powershell
pytest -v
```

### HTML Coverage

```powershell
pytest --cov=app --cov-report=term-missing --cov-report=html
start htmlcov\index.html
```

### Authentication Tests

Live authentication tests require:

* Platform Auth Service running on port `8005`
* Inventory Service running on port `8001`
* Valid test tokens

Required environment variables:

```text
WAREHOUSE_MANAGER_TOKEN
PROCUREMENT_MANAGER_TOKEN
CEO_TOKEN
VP_OPERATIONS_TOKEN
EXPIRED_TOKEN
```

Run the complete suite after configuring them:

```powershell
pytest -v
```

The target is:

```text
0 failed
```

Test counts should be documented only from the actual final `pytest -v` output.

---

# 13. Running the Service

### Activate the Environment

```powershell
.\myenv\Scripts\Activate.ps1
```

### Start Inventory Service

```powershell
uvicorn app.main:app --reload --port 8001
```

### Swagger

```text
http://localhost:8001/docs
```

### Platform Auth Service

```text
http://localhost:8005
```

---

# 14. Milestone Status

| Milestone                                   | Status    |
| ------------------------------------------- | --------- |
| M1 — Multi-Echelon Inventory                | Completed |
| M2 — Demand-Driven Automatic Draft PO       | Completed |
| M3 — Inventory Valuation                    | Completed |
| M4 — Optimistic Locking and Version Control | Completed |
| M5 — Fine-Grained Permissions and RBAC      | Completed |

## Final Coverage

**M1:** Multi-echelon inventory and replenishment

**M2:** Demand-driven automatic draft PO generation

**M3:** FIFO and weighted-average inventory valuation

**M4:** Optimistic locking and version conflict detection

**M5:** Real Platform authentication, fine-grained RBAC, row-level locking, bulk operations and what-if simulation
