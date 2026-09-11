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
* Platform authentication and RBAC
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

When a warehouse has insufficient stock:

```text
Local Warehouse
      ↓
Check Parent Warehouse
      ↓
Stock Available?
   /        \
 Yes         No
 ↓            ↓
Transfer    Supplier
 Stock      Replenishment
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

# 3. Milestone 2 — Automatic Draft Purchase Order

When inventory falls below the reorder point, the service can generate a draft purchase order.

### Supplier Selection

Suppliers are searched for the requested SKU.

The supplier with the **lowest unit cost** is selected.

```text
SKU
 ↓
Find Suppliers
 ↓
Compare Unit Cost
 ↓
Select Lowest Cost
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

Status is initially:

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

# 5. Milestone 4 — Authentication and RBAC

The Inventory Service uses the real Platform Auth Service for authentication.

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
Role Check
  ↓
Allow / Reject
```

Requests include:

```text
Authorization: Bearer <token>
X-Caller-Service: inventory-service
```

### Authentication Responses

| Condition                | Status |
| ------------------------ | -----: |
| Missing token            |    401 |
| Invalid token            |    401 |
| Expired token            |    401 |
| Wrong role               |    403 |
| Auth service unavailable |    503 |
| Auth service timeout     |    503 |

### Role Permissions

| Operation        | Roles                                                                                                                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Bulk update      | `warehouse_manager`, `procurement_manager`                                                                               |
| Bulk upload      | `warehouse_manager`, `procurement_manager`                                                                               |
| Draft PO         | `warehouse_manager`, `procurement_manager`                                                                               |
| What-if          | `ceo`, `vp_operations`                                                                                                   |
| Valuation report | `analyst`, `warehouse_manager`, `procurement_manager`, `logistics_manager`, `compliance_officer`, `vp_operations`, `ceo` |

---

# 6. Row-Level Locking

Bulk inventory updates use database row-level locking to protect concurrent updates.

### Endpoint

```text
POST /api/v1/inventory/bulk-update
```
The service uses:
```text
SELECT ... FOR UPDATE
```
before modifying locked inventory rows.
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
The inventory `version` field is also maintained for concurrency/version tracking.
---
# 7. Bulk CSV Upload
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
Allowed roles:

```text
warehouse_manager
procurement_manager

# 8. What-If Simulation

The service provides demand simulation without permanently modifying actual inventory.
### API

POST /api/v1/inventory/what-if
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

# 9. Database Design
### Main Tables

| Table                   | Purpose                           |
| ----------------------- | --------------------------------- |
| `inventory`             | Current inventory                 |
| `sales_history`         | Historical sales                  |
| `suppliers`             | Supplier information              |
| `purchase_orders`       | Draft POs                         |
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

# 10. API Summary

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

# 11. Testing

### Run all tests

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

The goal is:

```text
0 failed

```

The README test count should be updated only from the actual final `pytest -v` output.

---

# 12. Running the Service

Activate the environment:

```powershell
.\myenv\Scripts\Activate.ps1
```

Start Inventory Service:

```powershell
uvicorn app.main:app --reload --port 8001
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

# 14. Milestone Status

| Milestone                               | Status    |
| --------------------------------------- | --------- |
| M1 — Multi-Echelon Inventory            | Completed |
| M2 — Automatic Draft PO                 | Completed |
| M3 — Inventory Valuation                | Completed |
| M4 — Authentication, RBAC & Concurrency | Completed |

## Final Coverage

The Inventory Service currently covers:

**M1:** Multi-echelon inventory and replenishment
**M2:** Demand-driven automatic draft PO
**M3:** FIFO and weighted-average valuation
**M4:** Real authentication, RBAC, row locking, bulk operations and simulation
