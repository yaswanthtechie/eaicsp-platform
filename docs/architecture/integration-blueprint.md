# EAICSP Integration Blueprint (v1)
### Owner: Team Lead. Round 15 builds against this document. Changes go through a PR to this file.

This is the single reference for **who owns which data, how services and models call each other, and what the database layout is.** It follows Section 3 (architecture) and Section 6 (database architecture and API design) of the client proposal, plus our key decisions (REST between services instead of gRPC; basic OAuth2/JWT security).

---

## 1. The five rules

1. **One owner per entity.** Only the owning service writes it. Everyone else refers to it by ID, and learns about changes from events.
2. **One ID format everywhere** (Section 2). No service invents its own IDs for shared entities.
3. **Each service owns its own schema.** One PostgreSQL instance, one schema per service, no queries into another service's schema.
4. **Sync calls (REST) only when the caller needs an answer now.** Everything else goes over Kafka events.
5. **Contract first.** Every endpoint and event used by another service has a contract file in `contracts/` before anyone builds against it. Consumers build against the contract and a mock, then switch to the real thing.

---

## 2. Canonical IDs and master data

| Entity | ID format | Example | Owner service | Source of truth |
|---|---|---|---|---|
| Product / SKU | `SKU-` + 6 digits | `SKU-000123` | Inventory | `inventory.products` |
| Warehouse | `WH-` + city's 3-letter IATA airport code + 2 digits | `WH-BLR-01` | Inventory | `inventory.warehouses` |
| Supplier | `SUP-` + 5 digits | `SUP-00045` | Supplier Portal | `supplier_portal.suppliers` |
| Purchase order | `PO-` + year + 6 digits | `PO-2026-000123` | Inventory (create, approve) then Supplier Portal (supplier-facing lifecycle) | see Flow B |
| Shipment | `SHP-` + year + 6 digits | `SHP-2026-000077` | Supplier Portal (dispatch) | `supplier_portal.shipments` |
| User | UUID | | Platform | `platform.users` |
| Event | UUID v4 | | Producer | envelope `event_id` |

The six seed warehouses are `WH-BLR-01`, `WH-BOM-01` (Mumbai), `WH-CCU-01` (Kolkata),
  `WH-DEL-01`, `WH-HYD-01`, `WH-MAA-01` (Chennai). New warehouses use the IATA code of
  their city (e.g. Pune → `WH-PNQ-01`). Sanctions test suppliers: `SUP-00007`, `SUP-00023`, `SUP-00045`.
  This goes just above the paragraph that starts with "One shared seed dataset". Save the file.

**One shared seed dataset** (`data-platform/seed/`, owned by Vivek) generates all master data with these IDs: 500 SKUs, 6 warehouses, 60 suppliers (a few with names on sanctions lists), 2 years of daily sales. Every service and model loads from it. No more per-person mock data for shared entities.

---

## 3. Database layout (per proposal Section 6.1)

| Store | What lives there | Owner(s) |
|---|---|---|
| **PostgreSQL 16**, schema per service | `inventory`: products, warehouses, inventory_ledger, purchase_orders, po_lines, goods_receipts, outbox, processed_events<br>`supplier_portal`: suppliers, supplier_users, po_mirror, po_acknowledgements, shipments, invoices, match_results, outbox, processed_events<br>`compliance`: screenings, cases, case_events, customs_checks, sanctions_entities<br>`platform`: users, roles, permissions, api_keys, auth_audit<br>`logistics`: carriers, routes (team lead) | Each service, Alembic migrations in its own folder |
| **ClickHouse 24** | `demand_forecast_history`, `kpi_metrics`, `inventory_snapshots`, `transport_performance`, `sales_fact` marts | Vivek (tables and views); Uday writes forecasts |
| **MongoDB 7** | `news_signals`, `risk_assessments`, `supplier_documents` metadata | Mahendhar (PM) |
| **Redis 7.2** | `forecast_cache`, `live_kpis`, auth/session state | Uday (forecast cache), Mahendhar (live KPIs), Rahul (auth) |
| **InfluxDB 2.7** | `temperature_readings`, `equipment_metrics` | Kalyani |
| **MinIO** | `supplier-docs`, `ml-models`, `generated-reports` | Rashida (docs), Ajith (models) |

`supplier_portal.po_mirror` is a **read copy** of POs built from `inventory.po.approved` events. Inventory remains the owner of PO creation and approval.

---

## 4. Synchronous calls (REST, through the gateway in production)

| Caller | Called | Endpoint | Why sync | If it fails |
|---|---|---|---|---|
| Inventory | Forecast serving (Ajith, Uday's model) | `GET /api/v1/demand/forecast/{sku_id}?horizon=30` | Reorder needs the number now | Fall back to 28-day moving average, mark recommendation `forecast_source=fallback` |
| Inventory, Supplier Portal | Compliance | `POST /api/v1/compliance/internal-check` (exists) | Must not act on an unscreened supplier | As already documented by each service (R9-11) |
| Supplier Portal | Supplier Risk (Mahendhar PM) | `GET /api/v1/suppliers/{supplier_id}/risk-score` | Show risk during onboarding | Show "risk unavailable", don't block (Round 16) |
| All services | Platform | `/verify` (exists) | Auth | Reject (fail closed) |
| Dashboard | Gateway BFF (Mahendhar AM) | `GET /api/v1/analytics/kpis`, `WS /api/v1/analytics/kpis/real-time` | UI | Dashboard shows last snapshot (PWA) |

Paths match proposal Section 6.3 where the proposal names one.

---

## 5. Event catalog (Kafka, standard envelope, schemas in `contracts/events/`)

| Event | Producer | Consumers | Status |
|---|---|---|---|
| `inventory.po.approved` | Inventory | Supplier Portal | 🆕 Round 15 |
| `inventory.goods.received` | Inventory | Supplier Portal (3-way match) | 🆕 Round 15 |
| `inventory.stock.low` | Inventory | Gateway BFF | exists, new consumer |
| `supplierportal.po.acknowledged` | Supplier Portal | Inventory | 🆕 Round 15 |
| `supplierportal.shipment.dispatched` | Supplier Portal | ETA model service | 🆕 Round 15 |
| `eta.shipment.predicted` | ETA (Harish) | Supplier Portal, Gateway BFF | 🆕 Round 15 |
| `forecast.batch.completed` | Forecasting (Uday) | Gateway BFF | 🆕 Round 15 |
| `compliance.supplier.status_changed` | Compliance | Inventory, Supplier Portal | exists |
| `supplierrisk.score.changed` | Supplier Risk | Gateway BFF | exists, new consumer |
| `iot.anomaly.detected` | Anomaly (Kalyani) | Gateway BFF | exists, new consumer |
| `data.pipeline.completed` | ETL (Vivek) | Gateway BFF | exists, new consumer |

Every consumer: own consumer group, idempotent by `event_id`, offset committed after the DB write, dead-letter topic for bad messages (the Round 14 pattern).

---

## 6. The three end-to-end flows for Round 15

### Flow A: Forecast to purchase order
```
seed sales history (Vivek)
  -> Uday trains ensemble on canonical SKUs, registers "Production" model in MLflow
  -> Ajith serves it: GET /api/v1/demand/forecast/{sku_id}
  -> Balaji: GET /api/v1/inventory/optimization/recommendations
       (calls forecast, computes reorder qty, uses seed stock levels)
  -> draft PO -> compliance internal-check -> approve (procurement_manager)
  -> event inventory.po.approved
```

### Flow B: PO to supplier to goods receipt
```
inventory.po.approved
  -> Rashida: PO appears for the supplier (REST/GraphQL)
  -> supplier acknowledges -> event supplierportal.po.acknowledged -> Balaji marks PO acknowledged
  -> supplier dispatches -> event supplierportal.shipment.dispatched
  -> Harish: ETA model predicts -> event eta.shipment.predicted -> Rashida stores ETA on shipment
  -> warehouse receives: POST /api/v1/inventory/goods-receipts (warehouse_manager)
  -> stock updated -> event inventory.goods.received
  -> Rashida: 3-way match (PO vs receipt vs invoice)
```

### Flow C: Live control tower (dashboard on real data)
```
inventory.stock.low, iot.anomaly.detected, supplierrisk.score.changed,
eta.shipment.predicted, forecast.batch.completed, data.pipeline.completed
  -> Mahendhar BFF consumes -> WS /api/v1/analytics/kpis/real-time
  -> Chandhu: live alerts panel
Vivek: KPI views in ClickHouse (fill rate, stockouts, open POs, on-time delivery)
  -> Mahendhar: GET /api/v1/analytics/kpis
  -> Chandhu: KPI widgets on real data
```

**Demo target, Friday 23/10:** run `make up && make seed`, then drive Flow A and B from Swagger, and watch Flow C update the dashboard live.

---

## 7. Shared environment

`infra/docker-compose.yml` (owned by Ajith) brings up every store above plus every service, with health checks. One Postgres init script creates one schema and one user per service. `make up`, `make seed`, `make e2e`.

Per-person `docker-compose.dev.yml` files keep working for solo work.

---

## 8. What is deliberately NOT in Round 15

- Logistics route optimization (team lead, later round).
- IoT ingestion via MQTT (Kalyani's simulator publishes straight to Kafka for now).
- Supplier Portal UI on real data (UI parked; Flow B is demoed via API).
- Kubernetes for the full stack (Ajith's single-service K8s stays as a reference).
