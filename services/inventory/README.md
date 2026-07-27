# Inventory Service API

A RESTful Inventory Management API built using **FastAPI**, **SQLAlchemy ORM**, and **SQLite**.

This service provides complete inventory management features including CRUD operations, automatic reorder point calculation, low-stock detection, demand spike simulation, bulk CSV upload, and automated API testing.

---

# Features

- Inventory CRUD Operations
- SQLite Database Integration
- SQLAlchemy ORM Based Data Management
- Pydantic Schema Validation
- Automatic Reorder Point Calculation
- Low Stock Inventory Detection
- Demand Spike Simulation
- Bulk CSV Import
- Pytest API Testing
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
- Python Multipart
- Pydantic_settings

---

# Project Structure

```text
inventory-service/
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
├── inventory.db
├── requirements.txt
└── README.md
```

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
```

## Navigate Project Directory

```bash
cd inventory-service
```

## Create Virtual Environment

```bash
python -m venv venv
```

## Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```


```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Run Application

Start FastAPI server:

```bash
uvicorn app.main:app --reload
```

Application URL:

```
http://127.0.0.1:8000
```

Swagger Documentation:

```
http://127.0.0.1:8000/docs
```

ReDoc Documentation:

```
http://127.0.0.1:8000/redoc
```

---

# API Endpoints

## Create Inventory

Creates a new inventory item.

```
POST /api/v1/inventory/
```

Example Request:

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

Example Response:

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

## Get All Inventory

Returns all inventory records.

```
GET /api/v1/inventory/
```

---

## Get Inventory By SKU

Returns inventory details using SKU ID.

```
GET /api/v1/inventory/{sku_id}
```

Example:

```
GET /api/v1/inventory/SKU001
```

---

## Update Inventory

Updates existing inventory details.

```
PUT /api/v1/inventory/{sku_id}
```

---

## Delete Inventory

Deletes an inventory record.

```
DELETE /api/v1/inventory/{sku_id}
```

---

# Reorder Engine

The system automatically calculates reorder points based on inventory demand.

## Formula

```
Reorder Point =
(Average Daily Demand × Lead Time Days)
+ Safety Stock
```

Example:

```
Average Daily Demand = 10

Lead Time Days = 3

Safety Stock = 20


Reorder Point

= (10 × 3) + 20

= 50
```

When:

```
Current Quantity <= Reorder Point
```

the product requires a reorder.

---

# Reorder Check

Checks whether a product needs replenishment.

Endpoint:

```
GET /api/v1/inventory/{sku_id}/reorder-check
```

Example Response:

```json
{
    "needs_reorder": true,
    "current_qty": 20,
    "reorder_point": 50,
    "suggested_order_qty": 30
}
```

---

# Low Stock Detection

Returns products where available quantity is below the reorder point.

Endpoint:

```
GET /api/v1/inventory/low-stock
```

Example Response:

```json
[
    {
        "sku_id": "SKU001",
        "product_name": "Laptop",
        "quantity_on_hand": 20,
        "reorder_point": 50
    }
]
```

---

# Demand Spike Simulation

Simulates sudden increase in product demand.

Endpoint:

```
POST /api/v1/inventory/{sku_id}/simulate
```

Request:

```json
{
    "demand_spike_percent": 30
}
```

Example:

```
Average Daily Demand = 10

Demand Spike = 30%

New Demand

= 10 + (10 × 30/100)

= 13 units/day
```

Response:

```json
{
    "sku_id": "SKU001",
    "current_quantity": 100,
    "new_reorder_point": 59,
    "needs_reorder": false,
    "suggested_order_qty": 0
}
```

---

# Bulk CSV Upload

Uploads multiple inventory records using CSV file.

Endpoint:

```
POST /api/v1/inventory/bulk-upload
```

Content Type:

```
multipart/form-data
```

Sample CSV:

```csv
sku_id,product_name,warehouse_id,quantity_on_hand,avg_daily_demand,lead_time_days,safety_stock
SKU001,Laptop,WH001,100,10,3,20
SKU002,Mouse,WH002,50,5,2,10
```

---

# Database

Database:

```
SQLite
```

ORM:

```
SQLAlchemy
```

Database File:

```
inventory.db
```

SQLAlchemy handles:

- Database connection
- Table creation
- CRUD operations
- Query execution
- Transaction management

---

# Configuration

Application configuration is managed inside:

```
app/core/config.py
```

It contains:

- Database settings
- Application configuration
- Environment-based variables

---

# Testing

Run test cases:

```bash
pytest
```

Run with detailed output:

```bash
pytest -v
```

Test Coverage:

- Create Inventory API
- Get Inventory API
- Update Inventory API
- Delete Inventory API
- Reorder Calculation
- Low Stock Detection

---

# Requirements

```
fastapi
uvicorn
sqlalchemy
pydantic
pytest
python-multipart
```

Install manually:

```bash
pip install fastapi uvicorn sqlalchemy pydantic pytest python-multipart
```
