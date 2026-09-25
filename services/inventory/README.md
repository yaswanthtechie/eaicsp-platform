﻿# Inventory Service

FastAPI microservice for managing inventory across multiple warehouses, including multi-echelon inventory, automated purchase orders, inventory valuation, authentication, compliance checks, approval workflows, and network optimization.

## Technology

* Python 3.12
* FastAPI
* PostgreSQL
* SQLAlchemy
* Pydantic
* HTTPX
* Pytest

---

## Quick Start

From the repository root:

```powershell
cd services\inventory

.\myenv\Scripts\Activate.ps1

python -m pip install -r requirements.txt

python -m pytest -q

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

# 1. Multi-Echelon Inventory

Inventory supports a warehouse hierarchy:

```text
Central
   ↓
Regional
   ↓
Local
```

Supported functionality:

* Central → Regional → Local hierarchy
* Reorder point calculation
* Low-stock detection
* Warehouse-to-warehouse transfers
* Parent warehouse shortage fulfillment
* Self-parent validation
* Circular hierarchy validation
* Hierarchy-aware transfer suggestions

### Reorder Point

```text
Reorder Point =
Average Daily Demand × Lead Time
+ Adjusted Safety Stock
```

### Main APIs

```text
GET  /api/v1/inventory/reorder-plan
POST /api/v1/inventory/transfer
POST /api/v1/inventory/multi-echelon/fulfill
```

---

# 2. Demand-Driven Automatic Purchase Orders

When inventory reaches the reorder condition, Inventory can generate a structured draft purchase order.

The process is:

```text
Inventory
   ↓
Demand / Reorder Calculation
   ↓
Supplier Selection
   ↓
Compliance Check
   ↓
Draft Purchase Order
```

The service:

* Calculates suggested order quantity
* Selects a supplier
* Determines unit cost
* Calculates expected cost
* Creates a structured draft PO
* Prevents duplicate draft POs
* Checks supplier compliance before automatic PO creation

### Draft PO API

```text
POST /api/v1/inventory/purchase-orders/draft
```

Required permission:

```text
inventory:write
```

Draft PO generation is integrated with inventory reorder processing.

---

# 3. Inventory Valuation

Inventory supports cost-layer based valuation.

Supported methods:

```text
fifo
weighted_average
```

### API

```text
GET /api/v1/inventory/reports/inventory-value
```

Example:

```text
GET /api/v1/inventory/reports/inventory-value?valuation_method=fifo
```

### Cost Layers

The service supports:

* Opening inventory cost layers
* Purchase order cost layers
* FIFO consumption
* Weighted-average valuation
* Warehouse-level valuation
* Category-level valuation

When opening inventory has both quantity and `unit_cost`, an opening cost layer is created.

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

Physical stock movement is still allowed when cost history is incomplete. The uncovered quantity remains uncosted for valuation.

---

# 4. Optimistic Locking

Inventory records contain a `version` field.

```text
Version 1
   ↓
Successful Update
   ↓
Version 2
```

Updates use the expected version.

If the supplied version is stale, the update is rejected instead of silently overwriting newer data.

This protects inventory from concurrent stale updates.

---

# 5. Authentication and Permissions

Inventory uses the real Platform Auth Service.

```text
Client
   ↓
Inventory Service
   ↓
Platform Auth Service
   ↓
Token + Role + Permission
   ↓
Allow / Reject
```

### Permissions

```text
inventory:read
inventory:write
```

### Protected Operations

| Operation       | Access                                       |
| --------------- | -------------------------------------------- |
| Inventory read  | `inventory:read`                             |
| Inventory write | `inventory:write`                            |
| Bulk update     | `warehouse_manager` or `procurement_manager` |
| Bulk upload     | `warehouse_manager` or `procurement_manager` |
| Draft PO        | `inventory:write`                            |
| Receive PO      | `inventory:write`                            |
| What-if         | `ceo` or `vp_operations`                     |
| PO approval     | `vp_operations`                              |

Authentication requests include:

```text
Authorization: Bearer <token>
X-Caller-Service: inventory-service
X-Request-ID: <request-id>
```

### Authentication Responses

```text
401 → Missing or invalid token
403 → Insufficient role or permission
503 → Authentication service unavailable
```

---

# 6. Compliance Integration

Automatic purchase orders perform a real Compliance Service check before PO creation.

```text
Inventory
   ↓
Supplier Selection
   ↓
Compliance Service
   ↓
CLEAR / BLOCK / REVIEW
   ↓
Create or Reject PO
```

Inventory calls:

```text
POST /api/v1/compliance/internal-check
```

with:

```text
supplier_id
supplier_name
country
```

and:

```text
X-Caller-Service: inventory-service
```

### Decision Handling

| Compliance result      | Inventory behavior |
| ---------------------- | ------------------ |
| `CLEAR`                | Create draft PO    |
| `BLOCK`                | Reject PO creation |
| `REVIEW`               | Reject PO creation |
| Service unavailable    | Reject PO creation |
| Invalid/error response | Reject PO creation |

The integration uses a **fail-closed** approach because automatic PO creation creates a commercial commitment. A delayed PO is preferable to creating an automatic PO without a successful compliance decision.

---

# 7. Automated PO Approval Workflow

Purchase orders are automatically classified according to expected cost.

Configuration:

```text
PO_AUTO_APPROVAL_THRESHOLD
```

Default:

```text
1000.0
```

### Approval Rules

```text
Expected Cost <= Threshold
        ↓
     Approved
```

```text
Expected Cost > Threshold
        ↓
Pending VP Approval
```

### Approval Status

|  Expected Cost | Status                |
| -------------: | --------------------- |
| `<= threshold` | `approved`            |
|  `> threshold` | `pending_vp_approval` |

Large POs require approval from:

```text
vp_operations
```

### Approve PO

```text
POST /api/v1/inventory/purchase-orders/{po_id}/approve
```

### Receive PO

```text
POST /api/v1/inventory/purchase-orders/{po_id}/receive
```

A large PO cannot be received until VP approval is completed.

Workflow:

```text
Draft PO
   ↓
Expected Cost Check
   ↓
 ┌───────────────────────┐
 │                       │
 ≤ Threshold        > Threshold
 │                       │
 ↓                       ↓
Approved          Pending VP Approval
                         ↓
                   VP Operations
                         ↓
                      Approved
                         ↓
                      Receive
```

---

# 8. Supply-Network Optimization

Inventory provides network-level optimization across the multi-echelon warehouse hierarchy.

The optimization considers:

* Warehouse hierarchy
* Own demand
* Downstream demand
* Lead time
* Current safety stock
* Optimized safety stock
* Current inventory
* Target inventory
* Surplus quantity
* Shortage quantity

### API

```text
GET /api/v1/inventory/network-optimization
```

Example:

```text
GET /api/v1/inventory/network-optimization?days=30
```

### Example Demand Flow

```text
Central Demand  = 2/day
Regional Demand = 3/day
Local Demand    = 5/day
```

Central downstream demand:

```text
2 + 3 + 5 = 10/day
```

The service aggregates demand through the warehouse hierarchy and returns warehouse-level optimization recommendations.

### Response Information

Each warehouse result contains:

```text
sku_id
warehouse_id
warehouse_type
parent_warehouse_id
hierarchy_depth
own_daily_demand
downstream_daily_demand
current_safety_stock
optimized_safety_stock
current_quantity
target_quantity
surplus_quantity
shortage_quantity
```

Circular warehouse hierarchies are detected and rejected.

---

# 9. Forecast Contract — Contract First

Inventory now defines a versioned contract for consuming forecast data in the future.

Current contract version:

```text
v1
```

The contract contains:

```text
contract_version
sku_id
warehouse_id
forecast_date
forecast_quantity
horizon_days
generated_at
confidence
```

Example:

```json
{
    "contract_version": "v1",
    "sku_id": "SKU001",
    "warehouse_id": "WH001",
    "forecast_date": "2026-10-01",
    "forecast_quantity": 125.5,
    "horizon_days": 30,
    "generated_at": "2026-09-24T10:00:00Z",
    "confidence": 0.92
}
```

Validation includes:

* Non-negative forecast quantity
* Positive forecast horizon
* Confidence between `0` and `1`
* Required SKU and warehouse identifiers
* Supported contract version
* Rejection of unexpected fields

### Forecast Service Status

The current implementation is **contract-only**.

Inventory does **not** make an HTTP call to the Forecast Service yet.

```text
Forecast Service
      ↓
  Future API
      ↓
Forecast Contract v1
      ↓
Inventory
```

The actual Forecast Service integration will be implemented after the Forecast Service API/output contract is finalized.

---

# 10. Concurrency and Bulk Operations

Bulk updates use database row-level locking.

```text
SELECT ... FOR UPDATE
```

Rows are locked consistently using:

```text
sku_id + warehouse_id
```

This reduces the risk of concurrent updates overwriting each other.

### Bulk Upload

```text
POST /api/v1/inventory/bulk-upload
```

### Bulk Update

```text
POST /api/v1/inventory/bulk-update
```

---

# 11. What-If Simulation

Inventory supports demand-change simulations without permanently modifying inventory.

```text
POST /api/v1/inventory/what-if
```

Allowed roles:

```text
ceo
vp_operations
```

---

# Main API Reference

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
| POST   | `/api/v1/inventory/transfer`                        |
| POST   | `/api/v1/inventory/multi-echelon/fulfill`           |
| GET    | `/api/v1/inventory/network-optimization`            |
| POST   | `/api/v1/inventory/purchase-orders/draft`           |
| POST   | `/api/v1/inventory/purchase-orders/{po_id}/approve` |
| POST   | `/api/v1/inventory/purchase-orders/{po_id}/receive` |
| GET    | `/api/v1/inventory/reports/inventory-value`         |

---

# Database

Main tables:

```text
inventory
sales_history
suppliers
purchase_orders
inventory_cost_layers
```

Inventory uses:

```text
sku_id + warehouse_id
```

as the composite primary key.

---

# Testing

Run the complete test suite:

```powershell
python -m pytest -q
```

Current result:

```text
108 passed
```

### Feature-specific tests

Forecast contract:

```powershell
python -m pytest tests/test_forecast_contract.py -v
```

Network optimization:

```powershell
python -m pytest tests/test_network_optimization.py -v
```

PO approval:

```powershell
python -m pytest tests/test_purchase_order_approval.py -v
```

Coverage:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

---

# Environment Configuration

Example configuration:

```text
.env.example
```

Local configuration:

```text
.env
```

The real `.env` file must not be committed.

Important configuration:

```text
DATABASE_URL
TEST_DATABASE_URL
PLATFORM_AUTH_URL
COMPLIANCE_SERVICE_URL
PO_AUTO_APPROVAL_THRESHOLD
WAREHOUSE_MANAGER_TOKEN
PROCUREMENT_MANAGER_TOKEN
CEO_TOKEN
VP_OPERATIONS_TOKEN
EXPIRED_TOKEN
```

---

# Completion Status

## Original Inventory Milestones

| Milestone                           | Status      |
| ----------------------------------- | ----------- |
| M1 — Multi-Echelon Inventory        | ✅ Completed |
| M2 — Automatic Draft PO             | ✅ Completed |
| M3 — Inventory Valuation            | ✅ Completed |
| M4 — Optimistic Locking             | ✅ Completed |
| M5 — Permissions and Authentication | ✅ Completed |

## Round 9–11 Work

| Requirement                    | Status                 |
| ------------------------------ | ---------------------- |
| Compliance integration pattern | ✅ Completed            |
| Real Compliance Service call   | ✅ Completed            |
| Compliance failure handling    | ✅ Completed            |
| Automated PO approval workflow | ✅ Completed            |
| Value-based approval threshold | ✅ Completed            |
| VP Operations approval         | ✅ Completed            |
| Supply-network optimization    | ✅ Completed            |
| Forecast contract v1           | ✅ Completed            |
| Forecast Service HTTP wiring   | completed |
| Full test suite                | ✅ **108 passed**       |

**The Forecast Service is intentionally not wired yet. The current scope is contract-first design only.**
