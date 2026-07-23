# Inventory Service API

A RESTful Inventory Management API built using **FastAPI**, **SQLAlchemy**, and **SQLite**. It provides inventory CRUD operations, reorder engine, demand spike simulation, bulk CSV import, and automated inventory management features.

---

# Features

- Inventory CRUD Operations
- SQLite Database using SQLAlchemy ORM
- Automatic Reorder Point Calculation
- Low Stock Detection
- Demand Spike Simulation
- Bulk CSV Import
- Pytest Test Cases
- Swagger API Documentation

---

# Tech Stack

- Python 3.x
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- Uvicorn
- Pytest

---

# Project Structure

```text
inventory-service/
│
├── app/
│   ├── main.py
│   ├── database.py
│   │
│   ├── models/
│   │   └── inventory.py
│   │
│   ├── routes/
│   │   └── inventory.py
│   │
│   ├── schemas/
│   │   └── inventory.py
│   │
│   └── services/
│       └── inventory_service.py
│
├── tests/
│   └── test_inventory.py
│
├── sample_inventory.csv
├── requirements.txt
└── README.md
```

---

# Installation

Clone the repository

```bash
git clone <repository-url>
```

Move into the project directory

```bash
cd inventory-service
```

Create Virtual Environment

```bash
python -m venv venv
```

Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Run the Application

```bash
uvicorn app.main:app --reload
```

Application URL

```
http://127.0.0.1:8000
```

Swagger UI

```
http://127.0.0.1:8000/docs
```

ReDoc

```
http://127.0.0.1:8000/redoc
```

---

# API Endpoints

## Create Inventory Item

```
POST /api/v1/inventory/
```

## Get All Inventory

```
GET /api/v1/inventory/
```

## Get Inventory by SKU

```
GET /api/v1/inventory/{sku_id}
```

## Update Inventory

```
PUT /api/v1/inventory/{sku_id}
```

## Delete Inventory

```
DELETE /api/v1/inventory/{sku_id}
```

## Reorder Check

```
GET /api/v1/inventory/{sku_id}/reorder-check
```

Returns

```json
{
    "needs_reorder": true,
    "current_qty": 20,
    "reorder_point": 50,
    "suggested_order_qty": 30
}
```

---

## Low Stock Items

Returns all products below their reorder point.

```
GET /api/v1/inventory/low-stock
```

---

## Demand Spike Simulation

Simulates a demand spike and predicts whether reorder is required.

```
POST /api/v1/inventory/{sku_id}/simulate
```

Example Request

```json
{
    "demand_spike_percent": 30
}
```

Example Response

```json
{
    "sku_id": "SKU001",
    "current_quantity": 100,
    "new_reorder_point": 65,
    "needs_reorder": false,
    "suggested_order_qty": 0
}
```

---

## Bulk CSV Import

Import inventory records from a CSV file.

```
POST /api/v1/inventory/bulk-upload
```

Upload a CSV file using **multipart/form-data**.

---

# Reorder Point Formula

```
Reorder Point =
(Average Daily Demand × Lead Time Days)
+ Safety Stock
```

Example

```
Average Daily Demand = 10

Lead Time Days = 3

Safety Stock = 20

Reorder Point

= (10 × 3) + 20

= 50
```

---

# Sample Request

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

---

# Sample Response

```json
{
    "sku_id": "SKU001",
    "product_name": "Laptop",
    "warehouse_id": "WH001",
    "quantity_on_hand": 100,
    "reorder_point": 50,
    "avg_daily_demand": 10,
    "lead_time_days": 3,
    "safety_stock": 20
}
```

---

# Database

This project uses **SQLite** with **SQLAlchemy ORM**.

Database file:

```
inventory.db
```

---

# Testing

Run all test cases

```bash
pytest
```

Run with verbose output

```bash
pytest -v
```

---

# Dependencies

```
fastapi
uvicorn
sqlalchemy
pydantic
pytest
python-multipart
```

Install manually

```bash
pip install fastapi uvicorn sqlalchemy pydantic pytest python-multipart
```

---

# Future Enhancements

- PostgreSQL Support
- JWT Authentication
- Docker Deployment
- Pagination & Filtering
- Redis Caching
- Inventory Analytics Dashboard

---
