# Inventory Service

Enterprise AI-Powered Supply Chain Platform - Inventory Management Service.

A FastAPI-based inventory service that manages stock levels, warehouse inventory, reorder calculations, bulk updates, CSV uploads, and inventory simulations.

---

# Features

## Inventory Management
- Create inventory items
- Get inventory by SKU and warehouse
- Update inventory details
- Delete inventory items
- Support multiple warehouses for the same SKU

## Reorder Engine
- Automatic reorder point calculation:

```
reorder_point = (avg_daily_demand × lead_time_days) + safety_stock
```

- Reorder check API
- Suggested order quantity calculation
- Low stock identification
- Warehouse-wise reorder planning

## Inventory Simulation
- Demand spike simulation
- What-if inventory analysis

## Bulk Operations
- Bulk CSV inventory upload
- Bulk inventory updates
- Transaction-based rollback on failures
- Row-level locking for concurrent updates

## Testing Safety
- Dedicated test database support
- Production database is never used during testing
- Database session override for tests

---

# Tech Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- Pytest
- Uvicorn

---

# Project Structure

```
inventory/
│
├── app/
│   ├── main.py
│   ├── database.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── models/
│   │   └── inventory.py
│   │
│   ├── schemas/
│   │   └── inventory.py
│   │
│   ├── routes/
│   │   └── inventory.py
│   │
│   └── services/
│       └── inventory_service.py
│
├── tests/
│   ├── conftest.py
│   └── test_inventory.py
│
├── requirements.txt
├── pytest.ini
└── README.md
```

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
```

Navigate to inventory service:

```bash
cd services/inventory
```

Create virtual environment:

```bash
python -m venv venv
```

Activate virtual environment:

Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Configuration

Create a `.env` file:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/inventory

TEST_DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/inventory_test
```

## Database Configuration

The application uses:

- `DATABASE_URL` → Application database
- `TEST_DATABASE_URL` → Test database

Tests always run on the test database.

Production database is never used by the test suite.

---

# Running Application

Start FastAPI server:

```bash
uvicorn app.main:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

Swagger documentation:

```
http://127.0.0.1:8000/docs
```

---

# API Endpoints

## Create Inventory

```
POST /api/v1/inventory
```

Example:

```json
{
  "sku_id": "SKU101",
  "product_name": "Laptop",
  "warehouse_id": "WH001",
  "quantity_on_hand": 100,
  "avg_daily_demand": 5,
  "lead_time_days": 4,
  "safety_stock": 10
}
```

---

## Get Inventory

```
GET /api/v1/inventory/{sku_id}/{warehouse_id}
```

---

## Update Inventory

```
PUT /api/v1/inventory/{sku_id}/{warehouse_id}
```

---

## Delete Inventory

```
DELETE /api/v1/inventory/{sku_id}/{warehouse_id}
```

---

## Reorder Check

```
GET /api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check
```

Response:

```json
{
  "current_qty": 20,
  "reorder_point": 30,
  "needs_reorder": true,
  "suggested_order_qty": 10
}
```

---

## Low Stock Items

```
GET /api/v1/inventory/low-stock
```

---

## Reorder Plan

```
GET /api/v1/inventory/reorder-plan
```

---

## Demand Spike Simulation

```
POST /api/v1/inventory/{sku_id}/{warehouse_id}/simulate
```

---

## What-If Simulation

```
POST /api/v1/inventory/what-if
```

---

## Bulk CSV Upload

```
POST /api/v1/inventory/bulk-upload
```

Supported CSV fields:

```
sku_id
product_name
warehouse_id
quantity_on_hand
avg_daily_demand
lead_time_days
safety_stock
```

---

## Bulk Inventory Update

```
POST /api/v1/inventory/bulk-update
```

Features:

- Transaction support
- Rollback on failure
- Row locking
- Deadlock prevention using sorted locking order

---

# Running Tests

Run all tests:

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Generate HTML coverage report:

```bash
pytest --cov=app --cov-report=html
```

Open:

```
htmlcov/index.html
```

---

# Test Results

Current test execution:

```
13 passed
```

Coverage:

```
74%
```

Test cases include:

- Create inventory
- Get inventory
- Reorder calculation
- Low stock detection
- Multi warehouse inventory
- Reorder planning
- Demand simulation
- What-if analysis
- Delete inventory
- Bulk update rollback
- Concurrent inventory decrement

---

# Recent Updates

## Database Safety Fix

- Added separate test database engine.
- Updated `tests/conftest.py`.
- Tests no longer connect to production database.
- Added dependency override for database sessions.

## Bulk Update Improvements

- Added transaction rollback verification.
- Added row-level locking using SQLAlchemy `with_for_update()`.
- Added SKU and warehouse sorting before locking to avoid deadlocks.

## Concurrency Testing Improvements

- Added multi-thread inventory decrement testing.
- Verified concurrent requests complete successfully.
- Verified final inventory quantity after updates.

## Configuration Improvements

- Added `TEST_DATABASE_URL`.
- Removed test dependency on production database configuration.

---

# Known Warnings

Current warnings:

```
FastAPI on_event is deprecated
```

These warnings do not affect application functionality.

Future improvement:

- Replace startup events with FastAPI lifespan handlers.

---

