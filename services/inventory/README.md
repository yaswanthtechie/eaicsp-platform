# Inventory Service

FastAPI microservice for multi-echelon inventory management, automated purchase orders, FIFO valuation, compliance checks, approval workflows, and network optimization.

## Technology Stack

- **Runtime & Framework:** Python 3.11+, FastAPI, Pydantic v2
- **Persistence:** PostgreSQL, SQLAlchemy, Psycopg2
- **Testing & HTTP:** Pytest, HTTPX, Coverage

---

## Quick Start

From `services/inventory`:

```powershell
.\myenv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- **Swagger UI:** `http://localhost:8001/docs`
- **Platform Auth Service:** `http://localhost:8005`
- **Compliance Service:** `http://localhost:8003`

---

## 1. Multi-Echelon Inventory

Supports hierarchical distribution across warehouse tiers: **Central → Regional → Local**.

- **Reorder Point:** $\text{ROP} = (\text{Avg Daily Demand} \times \text{Lead Time}) + \text{Safety Stock}$
- **Core Features:** Low-stock detection, circular hierarchy validation, parent warehouse shortage fulfillment, and cross-warehouse stock transfers.
- **Key Endpoints:** `GET /api/v1/inventory/reorder-plan`, `POST /api/v1/inventory/transfer`, `POST /api/v1/inventory/multi-echelon/fulfill`

---

## 2. Demand-Driven Automatic Purchase Orders

When stock falls below the reorder point, a structured draft purchase order is generated for the lowest-cost compliant supplier:
- Calculates suggested order quantity and expected purchase cost.
- Checks supplier compliance before PO creation and prevents duplicate draft POs.
- **Manual Draft Endpoint:** `POST /api/v1/inventory/purchase-orders/draft` (Permission: `inventory:write`).

---

## 3. Inventory Valuation

Supports cost-layer based inventory valuation using FIFO and weighted average:
- Inbound stock received against purchase orders creates new FIFO cost layers.
- Outbound stock movements consume cost layers in FIFO sequence.
- **Valuation Endpoint:** `GET /api/v1/inventory/reports/inventory-value?method=fifo`

---

## 4. Optimistic Locking

Inventory records track an integer `version` column. Concurrent updates validate that the provided version matches the database version before committing, returning `409 Conflict` on version mismatch to prevent lost updates.

---

## 5. Authentication & Permissions

Integrates with Platform Auth Service (`http://localhost:8005`) for role-based access control:
- **Permissions:** `inventory:read`, `inventory:write`
- **Roles:** `warehouse_manager`, `procurement_manager`, `ceo`, `vp_operations`
- Service calls require `Authorization: Bearer <token>` and `X-Caller-Service: inventory-service`.

---

## 6. Compliance Integration

Automatic and manual draft purchase orders perform screening checks with the Compliance Service.

### Decision Handling

| Compliance Result | Automatic PO (Stock Movements) | Manual `POST /purchase-orders/draft` |
|---|---|---|
| `CLEAR` | Draft PO created | 201 Created, draft PO returned |
| `BLOCK` / `REVIEW` | Skipped, warning logged with decision & supplier | 409 Conflict with decision and reason |
| Service Unavailable | Skipped, warning logged, retried on next movement | 503 Service Unavailable |
| Invalid / Error Response | Skipped, warning logged, retried on next movement | 502 Bad Gateway |

**Failure Mode:** Fail closed on the PO, never on physical stock movements. Physical stock operations (sales, decrements, bulk uploads) always succeed and commit. Skipped reorders leave warning logs for manual follow-up.

**Known Gap:** `/api/v1/compliance/internal-check` is not yet exposed by the Compliance Service (which currently exposes `/screen`). Until implemented, automatic POs are safely skipped with visible warnings.

---

## 7. Automated PO Approval Workflow

Purchase orders are classified according to expected cost against `PO_AUTO_APPROVAL_THRESHOLD` (default: `1000.0`):
- **$\le 1000.0$:** Automatically approved (`approval_status = "approved"`).
- **$> 1000.0$:** Marked `approval_status = "pending_vp_approval"`.
- **Approve Endpoint:** `POST /api/v1/inventory/purchase-orders/{po_id}/approve` (Role: `vp_operations`). Approving a non-existent PO returns `404 Not Found`.
- **Receive Endpoint:** `POST /api/v1/inventory/purchase-orders/{po_id}/receive`. Pending POs cannot be received until VP approval is granted.

---

## 8. Supply-Network Optimization

Calculates network-level safety-stock recommendations across the multi-echelon hierarchy without modifying physical quantities.

### Safety-Stock Formula
```text
safety stock = max(baseline_safety_stock, ceil(z × σ_pooled × √lead_time))
target       = safety stock + ceil(downstream_demand × lead_time)
```
- $\sigma_{\text{pooled}} = \sqrt{\sum \sigma_i^2}$: Variances add across locations, providing risk-pooling benefits upstream.
- $z$: Set via `NETWORK_SERVICE_LEVEL_Z` (default `1.65` $\approx$ 95% cycle service level).
- Baseline configured `safety_stock` acts as an enforced floor.
- **Endpoint:** `GET /api/v1/inventory/network-optimization?days=30`

---

## 9. Forecast Contract — Contract First

Versioned contract v1 aligned to the Forecast Service's output:
- **Shape:** Monthly `{date, predicted, lower, upper}` points, `interval_level`, `model_version`, and `generated_at`.
- **Tolerant Reader:** `extra="ignore"` ensures additional fields (such as `latency_ms`) are ignored without breaking Inventory.

### Contract Gaps to Agree with Forecast Owner

| Field | Forecast Service Today | Why Inventory Needs It |
|---|---|---|
| `sku_id`, `warehouse_id` | Accepted in request, but forecast is aggregate | Reorder points are per SKU and warehouse |
| `generated_at` | Not returned | Stale forecasts must fall back to history |
| `interval_level` | Not returned | Required to convert prediction bands to standard deviation |
| `granularity`, `contract_version` | Not returned | Explicit units and contract versioning |

### Forecast Consumption Adapter (`forecast_adapter.py`)
1. Only use forecast if SKU and warehouse match.
2. Only use fresh forecast (`age <= FORECAST_MAX_AGE_DAYS`, default 35 days).
3. Only use forecast covering the target date.
4. Otherwise, fall back to historical rolling average demand and record fallback reason.

---

## 10. Database & Migration

- **Primary Models:** `Inventory` (composite key: `sku_id` + `warehouse_id`), `SalesHistory`, `Supplier`, `PurchaseOrder`, `InventoryCostLayer`.

### Upgrading an Existing Database (Round 10)
SQLAlchemy `create_all()` does not add columns to existing tables. For pre-Round-10 databases, run the one-off migration:
```powershell
python -m scripts.migrate_add_approval_status
```
Adds `approval_status` (VARCHAR NOT NULL DEFAULT 'approved') so existing draft POs remain receivable.

---

## 11. Testing

Run the test suite from `services/inventory`:
```powershell
python -m pytest -q
```
**Current Result: 162 passed, 13 skipped** (175 total collected)

*(The 13 skipped tests in `test_auth_integration.py` require the live Platform Auth service on port 8005. All mock, unit, and business-logic integration tests pass 100%).*

---

## 12. Main API Reference

| Method | Endpoint | Description | Access / Role |
|---|---|---|---|
| `GET` | `/api/v1/inventory` | List all inventory items | `inventory:read` |
| `POST` | `/api/v1/inventory` | Create new inventory item | `inventory:write` |
| `POST` | `/api/v1/inventory/decrement` | Decrement stock & FIFO layers | `inventory:write` |
| `GET` | `/api/v1/inventory/reorder-plan` | View SKU reorder status | `inventory:read` |
| `POST` | `/api/v1/inventory/transfer` | Warehouse-to-warehouse transfer | `inventory:write` |
| `GET` | `/api/v1/inventory/network-optimization` | Network safety-stock calculation | `inventory:read` |
| `POST` | `/api/v1/inventory/purchase-orders/draft` | Create draft purchase order | `inventory:write` |
| `POST` | `/api/v1/inventory/purchase-orders/{id}/approve` | Approve draft purchase order | `vp_operations` |
| `POST` | `/api/v1/inventory/purchase-orders/{id}/receive` | Receive approved purchase order | `inventory:write` |
| `POST` | `/api/v1/inventory/what-if` | Run demand-spike simulation | `ceo` / `vp_operations` |
| `GET` | `/api/v1/inventory/reports/inventory-value` | Inventory valuation report (FIFO) | `inventory:read` |

---

## 13. Completion Status

### Original Milestones
| Milestone | Status |
|---|---|
| M1 — Multi-Echelon Inventory | Completed |
| M2 — Automatic Draft PO | Completed |
| M3 — Inventory Valuation | Completed |
| M4 — Optimistic Locking | Completed |
| M5 — Permissions and Authentication | Completed |

### Round 9–11 Work
| Requirement | Status |
|---|---|
| Compliance integration pattern | Completed |
| Compliance failure handling | Completed (fail closed on PO, never on stock movement) |
| Real Compliance Service call | Partial (Client ready; `/internal-check` not yet in Compliance) |
| Automated PO approval workflow | Completed (threshold, VP approval, missing PO 404) |
| Supply-network optimization | Completed ($z \cdot \sigma \cdot \sqrt{L}$ with risk pooling) |
| Forecast contract v1 | Completed (schema + adapter matching forecast output) |
| Forecast Service HTTP wiring | Not started (contract-first by design) |
| Full test suite | 162 passed, 13 skipped |
