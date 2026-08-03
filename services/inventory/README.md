# Inventory Service API

A RESTful Inventory Management API built using **FastAPI**, **SQLAlchemy ORM**, and **SQLite**.

This service provides complete inventory management features including CRUD operations, automatic reorder point calculation, low-stock detection, demand spike simulation, bulk CSV upload, dedicated response models, and automated API testing.
The default configuration uses PostgreSQL; adjust `DATABASE_URL` in `.env`.

---

# Features

* Inventory CRUD Operations
* SQLite Database Integration
* SQLAlchemy ORM
* Pydantic Request & Response Validation
* Automatic Reorder Point Calculation
* Low Stock Inventory Detection
* Demand Spike Simulation
* Bulk CSV Import
* Duplicate SKU Validation
* Response Models for All Endpoints
* Pytest API Testing
* Swagger API Documentation

---

# Tech Stack

* Python 3.x
* FastAPI
* SQLAlchemy
* SQLite
* Pydantic
* Uvicorn
* Pytest
* Python Multipart
* Pydantic Settings

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
* PostgreSQL
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

## Navigate to Project Directory

```bash
cd inventory-service
├── requirements.txt
├── README.md

## Create Virtual Environment

```bash
python -m venv venv
```

## Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Run the Application

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

Application URL

```
http://127.0.0.1:8000
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

ReDoc Documentation

```
http://127.0.0.1:8000/redoc
```

---

## PostgreSQL setup (local development)

Create the Postgres databases used by the service and tests. Adjust user/password/host as needed.

```bash
# create a test and dev database (example using default postgres user)
psql -c "CREATE DATABASE inventory;"
psql -c "CREATE DATABASE inventory_test;"
```

If you need a dedicated DB user, create one and grant privileges:

```bash
psql -c "CREATE USER inventory_user WITH PASSWORD 'secretpass';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE inventory TO inventory_user;"
psql -c "GRANT ALL PRIVILEGES ON DATABASE inventory_test TO inventory_user;"
```

Then set your `.env` accordingly (example):

```dotenv
DATABASE_URL=postgresql+psycopg://inventory_user:secretpass@localhost:5432/inventory
TEST_DATABASE_URL=postgresql+psycopg://inventory_user:secretpass@localhost:5432/inventory_test
```


# Response Models

The API uses dedicated Pydantic response models for all endpoints.

| Endpoint                                       | Response Model          |
| ---------------------------------------------- | ----------------------- |
| POST `/api/v1/inventory/`                      | InventoryResponse       |
| GET `/api/v1/inventory/`                       | list[InventoryResponse] |
| GET `/api/v1/inventory/{sku_id}`               | InventoryResponse       |
| PUT `/api/v1/inventory/{sku_id}`               | InventoryResponse       |
| DELETE `/api/v1/inventory/{sku_id}`            | DeleteResponse          |
| GET `/api/v1/inventory/low-stock`              | list[LowStockResponse]  |
| GET `/api/v1/inventory/{sku_id}/reorder-check` | ReorderCheckResponse    |
| POST `/api/v1/inventory/{sku_id}/simulate`     | SimulationResponse      |
| POST `/api/v1/inventory/bulk-upload`           | BulkUploadResponse      |

---

# API Endpoints

## Create Inventory

Creates a new inventory item.

```
POST /api/v1/inventory/
```

### Example Request

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

### Example Response

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

### Duplicate SKU

If a SKU already exists, the API returns:

**Status Code:** `409 Conflict`

```json
{
    "detail": "SKU already exists"
}
```

---

## Get All Inventory

```
GET /api/v1/inventory/
```

Returns all inventory records.

---

## Get Inventory By SKU

```
GET /api/v1/inventory/{sku_id}
```

Returns inventory details for the specified SKU.

---

## Update Inventory

```
PUT /api/v1/inventory/{sku_id}
```

Updates an existing inventory record.

---

## Delete Inventory

```
DELETE /api/v1/inventory/{sku_id}
```

Example Response

```json
{
    "message": "Inventory deleted successfully"
}
```

---

# Reorder Engine

The reorder point is calculated automatically.

## Formula

```
Reorder Point =
(Average Daily Demand × Lead Time Days)
+ Safety Stock
```

### Example

```
Average Daily Demand = 10

Lead Time Days = 3

Safety Stock = 20

Reorder Point

= (10 × 3) + 20

= 50
```

When

```
Current Quantity <= Reorder Point
```

the inventory item requires replenishment.

---

# Suggested Order Quantity

Formula

```
Suggested Order Quantity =
Reorder Point - Current Quantity
```

Example

```
Current Quantity = 20

Reorder Point = 50

Suggested Order Quantity

= 50 - 20

= 30
```

If the calculated value is negative, the API returns **0**.

---

# Reorder Check

```
GET /api/v1/inventory/{sku_id}/reorder-check
```

Example Response

```json
{
    "sku_id": "SKU001",
    "current_qty": 20,
    "reorder_point": 50,
    "needs_reorder": true,
    "suggested_order_qty": 30
}
```
---

# Low Stock Detection

Returns all inventory items where the available quantity is less than or equal to the reorder point.

### Endpoint

```text
GET /api/v1/inventory/low-stock
```

### Example Response

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

Simulates an increase in product demand and calculates a new reorder point.

### Endpoint

```text
POST /api/v1/inventory/{sku_id}/simulate
```

### Example Request

```json
{
    "demand_spike_percent": 30
}
```

### Example Calculation

```text
Average Daily Demand = 10

Demand Spike = 30%

New Average Daily Demand

= 10 + (10 × 30 / 100)

= 13 units/day

New Reorder Point

= (13 × 3) + 20

= 59
```

### Example Response

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

Upload multiple inventory records using a CSV file.

### Endpoint

```text
POST /api/v1/inventory/bulk-upload
```

### Content Type

```text
multipart/form-data
```

### Sample CSV

```csv
sku_id,product_name,warehouse_id,quantity_on_hand,avg_daily_demand,lead_time_days,safety_stock
SKU001,Laptop,WH001,100,10,3,20
SKU002,Mouse,WH002,50,5,2,10
```

### Success Response

```json
{
    "message": "CSV uploaded successfully",
    "total_records": 2
}
```

---

# Database

Database used:

```text
SQLite
```

ORM:

```text
SQLAlchemy
```

Database file:

```text
inventory.db
```

SQLAlchemy is responsible for:

* Database connection
* Table creation
* CRUD operations
* Query execution
* Transaction management

---

# Configuration

Application configuration is located in:

```text
app/core/config.py
```

Configuration includes:

* Database URL
* Environment variables
* Application settings

---

# Error Responses

## Duplicate SKU

**Status Code:** `409 Conflict`

```json
{
    "detail": "SKU already exists"
}
```

---

## Inventory Not Found

**Status Code:** `404 Not Found`

```json
{
    "detail": "Inventory not found"
}
```

---

## Invalid CSV File

**Status Code:** `400 Bad Request`

```json
{
    "detail": "Only CSV files are allowed"
}
```

---

# Testing

Run all test cases:

```bash
pytest
```

Run with detailed output:

```bash
pytest -v
```

### Current Test Result

```text
11 passed
```

### Test Coverage

* Create Inventory API
* Get Inventory API
* Get All Inventory API
* Update Inventory API
* Delete Inventory API
* Low Stock Detection
* Reorder Calculation
* Reorder Above Threshold
* Reorder Below Threshold
* Reorder At Threshold (`quantity == reorder_point`)
* Duplicate SKU Handling (409 Conflict)
* Suggested Order Quantity Validation
* Demand Spike Simulation

---

# Requirements

```text
fastapi
uvicorn
sqlalchemy
pydantic
pydantic-settings
python-multipart
pytest
```

Install manually:

```bash
pip install fastapi uvicorn sqlalchemy pydantic pydantic-settings python-multipart pytest
```

---





---

# Conclusion

This Inventory Service demonstrates a production-style REST API built with FastAPI and SQLAlchemy. It supports complete inventory management through CRUD operations, automatic reorder calculations, low-stock detection, demand spike simulation, CSV bulk upload, comprehensive response models, and automated testing with Pytest.
