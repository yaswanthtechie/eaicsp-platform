# Inventory Service

FastAPI inventory service backed by PostgreSQL. Inventory is tracked per
`(sku_id, warehouse_id)`, so the same SKU can have independent quantities in
multiple warehouses.

## Features

- Warehouse-aware inventory CRUD
- Automatic reorder-point calculation and low-stock detection
- Reorder plan ranked across all warehouses
- Transactional bulk quantity updates
- PostgreSQL row locking for concurrent decrements
- Demand-spike what-if analysis
- Legacy single-SKU route compatibility
- CSV inventory upload

## Requirements

- Python 3.10+
- PostgreSQL 14+

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Configuration

Create a local `.env` file in this directory. It is ignored by Git and must
not be committed.

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/inventory
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/inventory_test
```

`TEST_DATABASE_URL` must point to a separate disposable database. The test
suite drops and recreates its tables before and after every test.

For a fresh PostgreSQL database, the application creates the `inventory` table
at startup. If you are migrating an existing database, create and review a
schema migration before deployment because the inventory identity is now the
composite key `(sku_id, warehouse_id)`.

## Run the service

From `services/inventory`:

```powershell
uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Reorder logic

```text
reorder_point = (avg_daily_demand * lead_time_days) + safety_stock
```

An item needs reorder when:

```text
quantity_on_hand <= reorder_point
```

The reorder plan uses this priority score and sorts higher values first:

```text
urgency_score = (reorder_point - quantity_on_hand) / avg_daily_demand
```

## API

Base path: `/api/v1/inventory`

### Create inventory

```http
POST /api/v1/inventory
```

```json
{
  "sku_id": "SKU001",
  "product_name": "Laptop",
  "warehouse_id": "WH001",
  "quantity_on_hand": 100,
  "avg_daily_demand": 10,
  "lead_time_days": 3,
  "safety_stock": 20
}
```

The same SKU may be created in another warehouse. Creating the same
`sku_id` and `warehouse_id` pair again returns `409 Conflict`.

### Read, update, and delete inventory

Use the warehouse-specific paths when a SKU exists in multiple warehouses:

```http
GET    /api/v1/inventory/{sku_id}/{warehouse_id}
PUT    /api/v1/inventory/{sku_id}/{warehouse_id}
DELETE /api/v1/inventory/{sku_id}/{warehouse_id}
```

The earlier single-SKU routes remain supported for an SKU held in exactly one
warehouse:

```http
GET    /api/v1/inventory/{sku_id}
PUT    /api/v1/inventory/{sku_id}
DELETE /api/v1/inventory/{sku_id}
```

For a multi-warehouse SKU, preserve the original URL style by supplying a
query parameter:

```http
GET /api/v1/inventory/SKU001?warehouse_id=WH001
```

Without `warehouse_id`, an ambiguous single-SKU request returns `409 Conflict`
instead of guessing the warehouse.

### Reorder endpoints

```http
GET /api/v1/inventory/reorder-plan
GET /api/v1/inventory/low-stock
GET /api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check
```

The legacy reorder-check endpoint is also supported:

```http
GET /api/v1/inventory/{sku_id}/reorder-check?warehouse_id=WH001
```

### Bulk update

```http
POST /api/v1/inventory/bulk-update
```

The request body is a JSON list. Each item identifies one warehouse row and
changes its quantity using `quantity_delta`.

```json
[
  {
    "sku_id": "SKU001",
    "warehouse_id": "WH001",
    "quantity_delta": -5
  },
  {
    "sku_id": "SKU002",
    "warehouse_id": "WH002",
    "quantity_delta": 20
  }
]
```

### CSV bulk upload

```http
POST /api/v1/inventory/bulk-upload
```

Upload the CSV file as multipart/form-data with field name `file`.
Each row should contain inventory fields such as `sku_id`, `product_name`,
`warehouse_id`, `quantity_on_hand`, `avg_daily_demand`, `lead_time_days`, and
`safety_stock`.

All changes run in one database transaction. If one row is missing or a
decrement would make stock negative, the whole request is rolled back.

On PostgreSQL, the service locks target rows with `SELECT ... FOR UPDATE` in a
stable order. Concurrent decrements therefore serialize and cannot overwrite
each other.

### What-if demand spike

```http
POST /api/v1/inventory/what-if
```

```json
{
  "spike_percent": 50
}
```

This does not change inventory. It returns warehouse rows that would be at or
below their recalculated reorder point if demand increased by the given
percentage.

### Legacy per-SKU simulation

```http
POST /api/v1/inventory/{sku_id}/simulate?warehouse_id=WH001
```

```json
{
  "demand_spike_percent": 50
}
```

### CSV upload

```http
POST /api/v1/inventory/bulk-upload
Content-Type: multipart/form-data
```

Required CSV headers:

```text
sku_id,product_name,warehouse_id,quantity_on_hand,avg_daily_demand,lead_time_days,safety_stock
```

## Validation and errors

| Condition | Status |
| --- | ---: |
| Invalid request values | 422 |
| Inventory row not found | 404 |
| Duplicate SKU/warehouse pair | 409 |
| Ambiguous SKU without warehouse ID | 409 |
| Missing bulk row or insufficient stock | 409 |
| Invalid CSV upload | 400 |

## Tests

Run all tests:

```powershell
pytest -q
```

The suite runs against `TEST_DATABASE_URL` and currently contains 16 tests:

- 11 regression tests for the original API behavior
- reorder-point edge cases: exactly at, one below, and one above
- multi-warehouse reorder-plan ordering
- transactional bulk rollback
- ten concurrent decrements with no lost updates
- what-if demand-spike analysis

## Project structure

```text
services/inventory/
├── app/
│   ├── core/config.py
│   ├── models/inventory.py
│   ├── routes/inventory.py
│   ├── schemas/inventory.py
│   ├── services/inventory_service.py
│   ├── database.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_inventory.py
│   └── test_legacy_inventory.py
├── requirements.txt
└── README.md
```
