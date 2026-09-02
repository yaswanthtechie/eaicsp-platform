# Inventory Service

## 1. Overview

The **Inventory Service** is a FastAPI-based backend microservice responsible for managing inventory at the **SKU and warehouse level**.

The service calculates demand from historical sales data and uses that demand to determine reorder points, low-stock conditions, urgency, replenishment quantities, and warehouse transfer opportunities.

The service also supports bulk operations, CSV upload, simulations, what-if analysis, concurrency protection, automated testing, and integration with the shared **Platform/Auth Service**.

### Main business flow

```text
Sales History
      |
      v
Rolling Average Demand
      |
      v
ABC Classification
      |
      v
Adjusted Safety Stock
      |
      v
Reorder Point
      |
      v
Low Stock Detection
      |
      v
Urgency Calculation
      |
      v
Reorder Plan
      |
      v
Transfer Suggestion
```

### Authentication flow

```text
Client / Swagger
       |
       v
Inventory Service
       |
       | Authorization: Bearer <JWT>
       v
Platform/Auth Service
       |
       v
/ api/v1/auth/verify
       |
       v
Validate Token + User + Role
       |
       v
User information returned
       |
       v
Inventory endpoint continues
```

---

# 2. Objectives

The Inventory Service provides:

* Warehouse-level inventory management
* Inventory CRUD operations
* Historical sales tracking
* Dynamic demand calculation
* Rolling average demand
* Automatic reorder-point calculation
* ABC classification
* ABC-based safety-stock adjustment
* Low-stock detection
* Suggested order quantity
* Urgency calculation
* Reorder planning
* Warehouse transfer suggestions
* CSV bulk upload
* Bulk inventory updates
* Inventory decrement
* PostgreSQL transaction handling
* Concurrency protection
* Demand simulation
* What-if analysis
* Automated pytest coverage
* Integration with the Platform/Auth Service
* Role-based endpoint authorization
* Service-to-service authentication using HTTPX
* Request and caller-service logging

---

# 3. Technology Stack

| Technology            | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| Python 3.12.x         | Backend programming                                   |
| FastAPI               | REST API framework                                    |
| Uvicorn               | ASGI server                                           |
| SQLAlchemy            | ORM and database access                               |
| PostgreSQL            | Application database                                  |
| Pydantic              | Request/response validation                           |
| Pytest                | Automated testing                                     |
| HTTPX                 | Service-to-service HTTP communication and API testing |
| python-multipart      | File upload support                                   |
| CSV                   | Bulk inventory upload                                 |
| JWT                   | Authentication token                                  |
| Platform/Auth Service | Central authentication and role verification          |

---

# 4. Service Architecture

The project contains multiple microservices.

The Inventory Service does not independently validate the user's JWT for protected operations.

Instead, it communicates with the shared Platform/Auth Service.

```text
                    Client
                      |
                      v
              Inventory Service
                  Port 8001
                      |
                      | HTTPX
                      |
                      v
              Platform Service
                  Port 8005
                      |
                      v
              Authentication
                      |
              +-------+-------+
              |               |
          JWT valid        JWT invalid
              |               |
              v               v
        User + Role          401
              |
              v
      Inventory Authorization
              |
              v
        Requested Endpoint
```

---

# 5. Service Ports

| Service               | Port |
| --------------------- | ---: |
| Inventory Service     | 8001 |
| Platform/Auth Service | 8005 |

### Inventory

```text
http://127.0.0.1:8001
```

### Platform/Auth

```text
http://127.0.0.1:8005
```

Swagger:

```text
http://127.0.0.1:8001/docs
http://127.0.0.1:8005/docs
```

---

# 6. Project Structure

```text
services/
└── inventory/
    |
    ├── app/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── database.py
    │   │
    │   ├── core/
    │   │   ├── auth.py
    │   │   └── config.py
    │   │
    │   ├── models/
    │   │   ├── inventory.py
    │   │   └── sales_history.py
    │   │
    │   ├── schemas/
    │   │   └── inventory.py
    │   │
    │   ├── routes/
    │   │   └── inventory.py
    │   │
    │   └── services/
    │       ├── demand_service.py
    │       ├── reorder_service.py
    │       ├── abc_service.py
    │       └── transfer_service.py
    │
    ├── scripts/
    │   └── seed_sales_history.py
    │
    ├── tests/
    │   ├── conftest.py
    │   └── test_*.py
    │
    ├── requirements.txt
    ├── .env.example
    └── README.md
```

---

# 7. Database

PostgreSQL is used for application persistence.

Main tables:

```text
inventory
sales_history
```

The application database and test database are separated.

```text
Application
    |
    v
Production PostgreSQL

Pytest
    |
    v
Test PostgreSQL
```

This separation prevents automated tests from modifying application data.

---

# 8. Inventory Model

An inventory record represents stock for a particular SKU in a particular warehouse.

Important fields:

| Field              | Description                |
| ------------------ | -------------------------- |
| `sku_id`           | Product/SKU identifier     |
| `product_name`     | Product name               |
| `warehouse_id`     | Warehouse identifier       |
| `quantity_on_hand` | Current available quantity |
| `avg_daily_demand` | Calculated demand          |
| `lead_time_days`   | Supplier lead time         |
| `safety_stock`     | Base safety stock          |

The same SKU can exist in multiple warehouses.

Example:

```text
SKU0008 | WH001
SKU0008 | WH002
SKU0008 | WH003
```

These are separate inventory records because the warehouse is different.

---

# 9. Inventory Validation

Inventory creation accepts fields such as:

```text
sku_id
product_name
warehouse_id
quantity_on_hand
lead_time_days
safety_stock
```

The following values cannot be negative:

```text
quantity_on_hand >= 0
lead_time_days >= 0
safety_stock >= 0
```

Unknown fields are rejected by the request schema.

`avg_daily_demand` is not intended to be manually supplied during inventory creation.

Demand is calculated from sales history.

---

# 10. Sales History

The `sales_history` table stores historical sales.

Important fields:

```text
sku_id
warehouse_id
sale_date
quantity_sold
```

Example:

```text
SKU0001 | WH001 | 2026-08-01 | 25
SKU0001 | WH001 | 2026-08-02 | 31
SKU0001 | WH001 | 2026-08-03 | 28
```

Demand calculation uses the combination:

```text
sku_id + warehouse_id
```

Therefore:

```text
Inventory:
SKU0008 | WH003

Sales History:
SKU0008 | WH003
```

is a valid match.

But:

```text
Inventory:
SKU0008 | WH003

Sales History:
SKU0008 | WH001
```

is not a match for that inventory record.

---

# 11. Sales History Seed Data

A seed script is available for generating synthetic sales history.

The seed configuration can generate sales records for multiple SKUs, warehouses, and days.

For example:

```text
50 SKUs
30 days
```

produces:

```text
50 × 30 = 1,500 sales-history records
```

The actual number depends on the current seed configuration.

The generated data contains positive quantities and daily variation so that demand calculations are meaningful.

---

# 12. Average Daily Demand

Demand is derived from sales history rather than manually entered inventory demand.

Basic calculation:

```text
Average Daily Demand =
Total Quantity Sold / Number of Days
```

Example:

```text
Total sales = 900
Days = 30

Average Daily Demand = 900 / 30
                     = 30
```

The calculated demand is used by reorder calculations.

---

# 13. Rolling Average Demand

The demand service uses recent sales history to calculate demand.

The normal demand window is:

```text
30 days
```

Conceptual flow:

```text
Inventory
    |
    v
SKU + Warehouse
    |
    v
Sales History
    |
    v
Recent Sales
    |
    v
Rolling Average Demand
```

This demand is then used by the reorder logic.

---

# 14. Reorder Point

The reorder point uses demand, lead time, and adjusted safety stock.

Formula:

```text
Reorder Point =
    Rolling Average Demand × Lead Time Days
    + Adjusted Safety Stock
```

Example:

```text
Rolling Average Demand = 30
Lead Time = 5
Adjusted Safety Stock = 45

ROP = 30 × 5 + 45
    = 195
```

If:

```text
Quantity on Hand = 100
Reorder Point = 195
```

then:

```text
100 < 195
```

so replenishment is required.

---

# 15. ABC Classification

SKUs are classified according to their relative sales volume.

The three classifications are:

```text
A
B
C
```

Conceptual process:

```text
Sales Volume
     |
     v
Rank SKUs
     |
     +---- A
     |
     +---- B
     |
     +---- C
```

The ABC classification is used by the safety-stock logic.

Boundary behavior is covered by automated tests.

---

# 16. Adjusted Safety Stock

The inventory contains a base:

```text
safety_stock
```

The ABC classification can modify the safety-stock value.

Flow:

```text
Base Safety Stock
       |
       v
ABC Classification
       |
       v
Adjusted Safety Stock
       |
       v
Reorder Point
```

The reorder plan exposes the adjusted safety-stock value.

---

# 17. Low Stock Detection

An inventory item requires replenishment when:

```text
quantity_on_hand < reorder_point
```

Example:

```text
Quantity = 90
ROP = 304
```

Because:

```text
90 < 304
```

the item is low stock.

At exactly the reorder point:

```text
quantity_on_hand == reorder_point
```

the item does not require a reorder.

This distinction is covered by tests.

---

# 18. Suggested Order Quantity

For a low-stock item:

```text
Suggested Order Quantity =
Reorder Point - Current Quantity
```

Example:

```text
ROP = 100
Quantity = 60

Suggested Order Quantity = 40
```

At the reorder point:

```text
ROP = 100
Quantity = 100

Suggested Order Quantity = 0
```

---

# 19. Urgency Calculation

The shortage is:

```text
Shortage =
Reorder Point - Quantity on Hand
```

When demand is greater than zero:

```text
Urgency Score =
Shortage / Average Daily Demand
```

Example:

```text
ROP = 304
Quantity = 90
Average Daily Demand = 28.53

Shortage = 304 - 90
         = 214

Urgency ≈ 214 / 28.53
        ≈ 7.5
```

A higher urgency score indicates greater replenishment urgency.

The reorder plan can sort low-stock items according to urgency.

---

# 20. Reorder Plan

The reorder plan combines the major inventory calculations.

Process:

```text
Read Inventory
      |
      v
Calculate Demand
      |
      v
Classify SKU
      |
      v
Calculate Adjusted Safety Stock
      |
      v
Calculate Reorder Point
      |
      v
Check Quantity
      |
      v
Calculate Urgency
      |
      v
Find Transfer Opportunity
      |
      v
Build Reorder Plan
```

Typical response information includes:

```text
sku_id
product_name
warehouse_id
quantity_on_hand
reorder_point
urgency_score
rolling_avg_demand
abc_tier
adjusted_safety_stock
transfer_suggestion
```

---

# 21. Warehouse Transfer Suggestion

The transfer service checks whether another warehouse has excess stock for the same SKU.

A transfer requires:

1. Destination warehouse is low stock.
2. Source warehouse contains the same SKU.
3. Source warehouse is above its reorder point.
4. Source and destination warehouses are different.
5. There is sufficient excess stock.

Example:

```text
WH003
Quantity = 90
ROP = 304

WH004
Quantity = 600
ROP = 304
```

WH003 is low stock:

```text
90 < 304
```

WH004 has excess:

```text
600 > 304
```

Possible transfer:

```text
WH004 → WH003
```

---

# 22. Transfer Quantity

Destination shortage:

```text
Destination Shortage =
Destination ROP - Destination Quantity
```

Source excess:

```text
Source Excess =
Source Quantity - Source ROP
```

Transfer quantity:

```text
min(Source Excess, Destination Shortage)
```

Example:

```text
Destination shortage = 214
Source excess = 296

Transfer quantity = min(296, 214)
                  = 214
```

Example response:

```json
{
  "sku_id": "SKU0008",
  "source_warehouse": "WH004",
  "destination_warehouse": "WH003",
  "transfer_quantity": 214,
  "source_excess_quantity": 296,
  "destination_shortage_quantity": 214,
  "recommendation": "TRANSFER"
}
```

---

# 23. Null Transfer Suggestion

A null transfer suggestion is a valid business result.

For example, if no other warehouse contains the same SKU, there is no transfer source.

It can also occur when another warehouse has the SKU but does not have excess stock.

Example:

```json
"transfer_suggestion": null
```

This does not necessarily indicate an application error.

---

# 24. CSV Bulk Upload

The service supports inventory upload through CSV.

Example:

```csv
sku_id,product_name,warehouse_id,quantity_on_hand,lead_time_days,safety_stock
SKU0001,Product 0001,WH001,120,5,30
SKU0002,Product 0002,WH002,250,7,40
SKU0003,Product 0003,WH003,80,4,25
```

The CSV does not need manually calculated demand.

The service validates the input and inventory data can subsequently use matching sales history for demand calculations.

Validation includes:

* Required columns
* Data types
* Negative quantities
* Invalid inventory values
* Request schema validation

---

# 25. Existing Inventory During Bulk Upload

Inventory is identified using the SKU and warehouse combination.

```text
sku_id + warehouse_id
```

When an existing inventory record is encountered, the implementation updates the existing record instead of creating a duplicate record.

This keeps inventory unique at the SKU/warehouse level.

---

# 26. Bulk Update

Bulk update allows multiple inventory changes in a single operation.

Example:

```json
[
  {
    "sku_id": "SKU001",
    "warehouse_id": "WH001",
    "quantity_delta": -10
  },
  {
    "sku_id": "SKU002",
    "warehouse_id": "WH002",
    "quantity_delta": 20
  }
]
```

The operation is transactional.

If an update fails:

```text
Update 1 → successful
Update 2 → successful
Update 3 → failed
        |
        v
     ROLLBACK
```

Earlier successful changes in the same transaction are not partially committed.

---

# 27. Inventory Decrement and Concurrency

Inventory can receive multiple updates simultaneously.

Example:

```text
Initial quantity = 100

Request A = -20
Request B = -30
```

Expected result:

```text
100 - 20 - 30 = 50
```

PostgreSQL row locking is used where required to protect against lost updates during concurrent modifications.

The test suite includes concurrent decrement behavior.

---

# 28. Simulation

The service supports demand-growth simulation.

Example:

```text
Current Demand = 10
Growth = 30%
```

Simulated demand:

```text
10 × 1.30 = 13
```

Simulation is designed to evaluate the effect of increased demand without changing the stored inventory quantity.

The implementation also validates invalid growth values.

---

# 29. What-If Analysis

The `what-if` endpoint evaluates the effect of a demand spike.

Example request:

```json
{
  "spike_percent": 30
}
```

The response can include:

```text
spike_percent
total_items
affected_items
total_suggested_order_qty
details
```

An affected item can contain:

```text
sku_id
current_quantity
new_reorder_point
needs_reorder
suggested_order_qty
```

The scenario is calculated without modifying the stored inventory records.

---

# 30. API Endpoints

Base path:

```text
/api/v1/inventory
```

| Method | Endpoint                                                  | Purpose                   |
| ------ | --------------------------------------------------------- | ------------------------- |
| POST   | `/api/v1/inventory/`                                      | Create inventory          |
| GET    | `/api/v1/inventory/`                                      | Get inventory             |
| GET    | `/api/v1/inventory/{sku_id}/{warehouse_id}`               | Get specific inventory    |
| PUT    | `/api/v1/inventory/{sku_id}/{warehouse_id}`               | Update inventory          |
| DELETE | `/api/v1/inventory/{sku_id}/{warehouse_id}`               | Delete inventory          |
| GET    | `/api/v1/inventory/low-stock`                             | Get low-stock items       |
| GET    | `/api/v1/inventory/reorder-plan`                          | Generate reorder plan     |
| GET    | `/api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check` | Check reorder requirement |
| POST   | `/api/v1/inventory/bulk-upload`                           | Upload CSV                |
| POST   | `/api/v1/inventory/bulk-update`                           | Bulk update               |
| POST   | `/api/v1/inventory/decrement`                             | Decrement inventory       |
| GET    | `/api/v1/inventory/simulate`                              | Demand simulation         |
| POST   | `/api/v1/inventory/what-if`                               | Demand scenario analysis  |

The currently running Swagger definition should be treated as the final source of truth for exact request and response schemas.

---

# 31. Pydantic Schemas

The service uses Pydantic models for request and response validation.

Important schemas include:

```text
InventoryCreate
InventoryUpdate
InventoryResponse
ReorderCheckResponse
LowStockResponse
DemandSpikeRequest
SimulationResponse
BulkUpdateItem
TransferSuggestion
ReorderPlanEntry
WhatIfRequest
WhatIfItem
WhatIfResponse
DeleteResponse
BulkUploadResponse
```

Validation prevents invalid values such as negative inventory quantities and negative lead times.

---

# 32. Authentication Integration

The Inventory Service integrates with the shared Platform/Auth Service.

The Platform Service runs on:

```text
http://127.0.0.1:8005
```

Inventory runs on:

```text
http://127.0.0.1:8001
```

Inventory does not need to duplicate the complete authentication implementation.

Instead, it sends the JWT to:

```text
POST /api/v1/auth/verify
```

on the Platform Service.

---

# 33. Authentication Request

For a protected Inventory endpoint, the Inventory Service extracts the user's token and sends it to the Platform Service.

Conceptually:

```text
Client
  |
  | Bearer JWT
  v
Inventory
  |
  | Authorization: Bearer JWT
  | X-Caller-Service: inventory-service
  | X-Caller-Endpoint: /api/v1/inventory/bulk-update
  v
Platform /auth/verify
```

Example service-to-service request:

```python
async with httpx.AsyncClient(timeout=5.0) as client:
    response = await client.post(
        f"{settings.PLATFORM_AUTH_URL}/api/v1/auth/verify",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Caller-Service": "inventory-service",
            "X-Caller-Endpoint": request.url.path,
        },
    )
```

The endpoint value should be taken dynamically from the actual incoming Inventory request.

---

# 34. Why HTTPX Is Used

`httpx` is used because the Inventory Service needs to communicate with another microservice over HTTP.

The flow is:

```text
Inventory Service
      |
      | HTTP request
      v
Platform Service
```

HTTPX provides the client required for this service-to-service communication.

It is especially suitable here because the authentication dependency is called from an asynchronous FastAPI authentication function.

HTTPX is also used in API tests.

---

# 35. Platform Auth Verify Endpoint

The Platform Service exposes:

```http
POST /api/v1/auth/verify
```

The endpoint receives the JWT through the Authorization header.

The Platform Service:

1. Reads the token.
2. Validates the token.
3. Finds the corresponding user.
4. Loads the user's role.
5. Confirms the user is active.
6. Returns authenticated-user information.

Example response:

```json
{
  "valid": true,
  "user_id": 1,
  "email": "procurementmanager@company.com",
  "full_name": "Procurement Manager",
  "role": "procurement_manager",
  "is_active": true
}
```

---

# 36. Role-Based Authorization

The Platform Service contains roles such as:

```text
ceo
vp_operations
procurement_manager
logistics_manager
compliance_officer
warehouse_manager
analyst
supplier
```

The Inventory Service checks whether the authenticated user's role is permitted to access the requested endpoint.

The role comes from the Platform Service response rather than being trusted directly from the client request.

---

# 37. Authentication and Authorization Difference

Authentication answers:

```text
Who is this user?
```

Authorization answers:

```text
Is this user allowed to perform this operation?
```

Example:

```text
JWT
 |
 v
Authentication
 |
 v
User = procurement_manager
 |
 v
Authorization
 |
 +---- Allowed → Continue
 |
 +---- Not allowed → 403
```

---

# 38. Caller-Service Logging

The Platform Service also logs which microservice called the authentication endpoint.

Example:

```text
caller=inventory-service
```

The Inventory Service should send:

```http
X-Caller-Service: inventory-service
```

It can also send the endpoint being accessed:

```http
X-Caller-Endpoint: /api/v1/inventory/bulk-update
```

This allows Platform logs to identify the caller.

Example:

```text
caller=inventory-service
caller_endpoint=/api/v1/inventory/bulk-update
method=POST
path=/api/v1/auth/verify
status=200
```

---

# 39. Why `unknown` Was Appearing

Earlier logs showed:

```text
caller=unknown
caller_endpoint=unknown
```

This happened when the request did not contain the expected caller headers.

For example, a direct Swagger request to Platform:

```text
POST /api/v1/auth/verify
```

may not contain:

```text
X-Caller-Service
X-Caller-Endpoint
```

Therefore the Platform logging middleware has no information about the calling service.

A request coming through Inventory should include:

```http
X-Caller-Service: inventory-service
X-Caller-Endpoint: /api/v1/inventory/bulk-update
```

Then the Platform log can show:

```text
caller=inventory-service
caller_endpoint=/api/v1/inventory/bulk-update
```

---

# 40. Important Difference Between Direct and Service Calls

### Direct Platform Swagger call

```text
Swagger
   |
   v
Platform /auth/verify
```

The caller may appear as:

```text
caller=unknown
```

unless Swagger sends the caller headers.

### Inventory-protected endpoint

```text
Swagger
   |
   v
Inventory /bulk-update
   |
   v
Platform /auth/verify
```

The Platform should receive:

```text
X-Caller-Service: inventory-service
X-Caller-Endpoint: /api/v1/inventory/bulk-update
```

Therefore the log should identify Inventory.

---

# 41. Platform Logging Example

A successful Inventory authorization should produce logs similar to:

```text
Authenticated request |
user_id=1 |
role=procurement_manager |
endpoint=/api/v1/auth/verify
```

and:

```text
caller=inventory-service
caller_endpoint=/api/v1/inventory/bulk-update
method=POST
path=/api/v1/auth/verify
status=200
```

The important point is that:

```text
user_id
role
caller service
caller endpoint
```

come from different pieces of the request/authorization flow.

---

# 42. User and Role Data

The Platform Service uses role records and user records.

Example user:

```text
Email:
procurementmanager@company.com

Role:
procurement_manager
```

Another example:

```text
Email:
vpoperations@company.com

Role:
vp_operations
```

The role must exist in the Platform database and the user must reference that role correctly.

---

# 43. Seed Data

The Platform Service contains seed data for roles and users.

The role list includes:

```text
ceo
vp_operations
procurement_manager
logistics_manager
compliance_officer
warehouse_manager
analyst
supplier
```

The seed process creates missing roles and then creates users with the appropriate `role_id`.

This is important because having:

```text
"procurement_manager"
```

in `seed.py`

does not automatically mean the currently running database contains the corresponding role/user records.

The seed operation must actually be executed against the database used by the running Platform Service.

---

# 44. Procurement Manager Role Issue

One development issue occurred where:

```text
procurement_manager
```

was defined in the source code but was not correctly available to the locally running authentication flow.

The important distinction was:

```text
Source Code
    |
    | contains role definition
    v
Database
    |
    | must contain actual role/user records
    v
Authentication
```

If seed data has not been inserted into the database, the application can contain the correct role definition while authentication still fails to resolve the user's role.

---

# 45. Authentication Error Handling

The Inventory authentication dependency handles common service-to-service failures.

### Missing token

```text
401 Unauthorized
Missing authentication token
```

### Authentication service timeout

```text
503 Service Unavailable
Authentication service timed out
```

### Authentication service unavailable

```text
503 Service Unavailable
Authentication service is unavailable
```

### Invalid authentication response

The Inventory Service should treat an unexpected Platform response as an authentication-service failure rather than silently authorizing the request.

---

# 46. Environment Configuration

Inventory should contain the Platform Service URL in its environment configuration.

Example:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory

TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test

PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The application and test databases must be different.

---

# 47. Authentication Configuration

The authentication flow should use:

```text
PLATFORM_AUTH_URL
```

rather than hard-coding the Platform Service URL in route logic.

Example:

```python
f"{settings.PLATFORM_AUTH_URL}/api/v1/auth/verify"
```

This makes the service easier to run in different environments.

---

# 48. End-to-End Authentication Flow

Example: `bulk-update`

```text
1. User logs in to Platform Service
             |
             v
2. Platform generates JWT
             |
             v
3. User authorizes Inventory Swagger
             |
             v
4. User calls /bulk-update
             |
             v
5. Inventory extracts Bearer token
             |
             v
6. Inventory calls Platform /auth/verify
             |
             v
7. Platform validates JWT
             |
             v
8. Platform loads user
             |
             v
9. Platform loads user role
             |
             v
10. Platform returns user information
             |
             v
11. Inventory checks required role
             |
             v
12. Authorized request continues
```

---

# 49. Example Successful Authorization

Inventory receives:

```text
Authorization: Bearer <JWT>
```

Inventory sends:

```text
Authorization: Bearer <JWT>
X-Caller-Service: inventory-service
X-Caller-Endpoint: /api/v1/inventory/bulk-update
```

Platform validates the token and returns:

```json
{
  "valid": true,
  "user_id": 1,
  "email": "procurementmanager@company.com",
  "full_name": "Procurement Manager",
  "role": "procurement_manager",
  "is_active": true
}
```

Inventory then evaluates:

```text
role == procurement_manager
```

If permitted:

```text
Request continues
```

---

# 50. Database Isolation for Tests

The test configuration uses:

```text
TEST_DATABASE_URL
```

A separate test engine/session is used.

FastAPI's database dependency is overridden during tests.

Conceptually:

```text
pytest
   |
   v
TEST_DATABASE_URL
   |
   v
Test PostgreSQL
```

This prevents tests from accidentally modifying the application database.

---

# 51. Transaction Handling

Database operations use transactions.

Successful operations:

```text
COMMIT
```

Failed operations:

```text
ROLLBACK
```

This is especially important for:

* Bulk updates
* Inventory modifications
* Concurrent updates

---

# 52. Performance Optimization

The reorder plan originally became slow when many inventory records were processed.

A major performance problem was repeatedly querying sales history for individual inventory records.

Less efficient pattern:

```text
Inventory 1 → Sales Query
Inventory 2 → Sales Query
Inventory 3 → Sales Query
...
```

A more efficient approach is to aggregate sales history by:

```text
sku_id + warehouse_id
```

and reuse the calculated demand.

Optimized flow:

```text
Sales History
      |
      v
GROUP BY SKU + Warehouse
      |
      v
Demand Results
      |
      v
Inventory Calculations
```

This reduces unnecessary database round trips.

---

# 53. Performance Result

During development, reorder-plan performance was significantly improved for a large test dataset.

An earlier execution was approximately:

```text
381.83 seconds
```

After query optimization it was approximately:

```text
0.448 seconds
```

Actual execution time depends on:

* Machine
* PostgreSQL performance
* Dataset size
* Database indexes
* Python environment
* System load

Therefore these values are development measurements rather than permanent production benchmarks.

---

# 54. Database Index Considerations

Useful query fields include:

```text
sku_id
warehouse_id
sale_date
```

A composite index involving:

```text
sku_id + warehouse_id
```

can help queries that frequently search by SKU and warehouse.

Queries that filter by date can also benefit from an index including:

```text
sku_id
warehouse_id
sale_date
```

Indexes should be confirmed against actual PostgreSQL query plans before being added.

---

# 55. Large Dataset Testing

The service can be tested with larger datasets.

Example:

```text
1,000 inventory items
30 days of sales history
```

This can produce:

```text
1,000 × 30
= 30,000 sales-history records
```

For 60 days:

```text
1,000 × 60
= 60,000 records
```

Large datasets help evaluate:

* Demand calculation
* Reorder-plan performance
* Database query performance
* Bulk operations

---

# 56. Important Edge Cases

### Reorder threshold

At ROP:

```text
quantity == reorder_point
```

Expected:

```text
needs_reorder = false
suggested_order_qty = 0
```

One below ROP:

```text
quantity == reorder_point - 1
```

Expected:

```text
needs_reorder = true
suggested_order_qty = 1
```

### Negative demand

Negative sales quantities are invalid.

```text
quantity_sold = -10
```

should be rejected according to the implemented validation.

### Manual demand

Manually supplying `avg_daily_demand` should not replace the calculated demand logic.

### Bulk rollback

If one update fails, the complete transaction should roll back.

### Concurrent decrement

Concurrent inventory changes must not result in lost updates.

### ABC boundary

The classification boundary is covered by automated tests.

### No transfer source

A missing transfer source should return a valid null transfer suggestion rather than being treated as an application failure.

---

# 57. Problems Faced During Development

## 57.1 Python Dependency Compatibility

Dependency installation initially caused package/build compatibility problems.

The development environment was moved to Python 3.12.x and the required packages were installed in the virtual environment.

---

## 57.2 Missing `requirements.txt`

The service initially required a proper dependency file.

A `requirements.txt` was added so that the development environment could be recreated consistently.

---

## 57.3 `ModuleNotFoundError: No module named 'app'`

The sales-history seed script imports application modules such as:

```python
from app.database import ...
```

Running the script from the wrong directory caused:

```text
ModuleNotFoundError: No module named 'app'
```

The correct approach is to run it from the Inventory Service directory using module execution:

```powershell
cd services\inventory

python -m scripts.seed_sales_history
```

---

## 57.4 Average Daily Demand Showing Zero

`avg_daily_demand` was sometimes zero because matching sales history was missing.

The important matching fields are:

```text
sku_id
warehouse_id
```

If either does not match, the sales data cannot be used for that inventory record.

---

## 57.5 Sales History Deleted

When sales history was deleted and inventory remained, demand calculation no longer had historical data.

Therefore:

```text
avg_daily_demand = 0
```

can be expected until matching sales history is restored.

---

## 57.6 Production Database Used by Tests

An early test configuration risked allowing tests to interact with the application database.

This was corrected by creating:

```text
test_engine
TestingSessionLocal
```

and overriding the FastAPI `get_db` dependency.

---

## 57.7 Bulk Update Rollback

Bulk updates needed transaction-level rollback.

The implementation was corrected so that a failed update does not leave earlier updates partially committed.

---

## 57.8 Concurrency Problem

Multiple inventory decrement requests could potentially overwrite each other.

PostgreSQL row locking was used to protect the inventory row during concurrent modification.

---

## 57.9 ABC Classification Boundary

ABC classification required careful handling of ranking boundaries.

Tests were added to verify the expected boundary behavior.

---

## 57.10 What-If Response Model

A response-model mismatch caused the what-if test to fail.

The response schema and actual returned structure were aligned.

---

## 57.11 Authentication Integration

The Inventory Service originally had local authorization logic.

The requirement changed so that protected services must call the shared Platform Service.

The integration therefore became:

```text
Inventory
   |
   v
HTTPX
   |
   v
Platform /auth/verify
```

---

## 57.12 Authentication Service 503

A `503 Service Unavailable` response occurred when Inventory could not correctly communicate with the Platform authentication endpoint or received an unexpected response.

The important configuration was:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

and the Platform Service needed to be running before protected Inventory endpoints were tested.

---

## 57.13 `require_roles` Import Error

An Inventory startup error occurred:

```text
ImportError:
cannot import name 'require_roles'
from 'app.core.auth'
```

This means the route was importing a function that did not exist under that name in the current `app/core/auth.py`.

The import and authorization implementation must use the actual function defined in the current authentication module.

This error prevents Inventory from starting at all, so it must be fixed before testing authentication.

---

## 57.14 Procurement Manager Role Not Found

The role existed in the Platform source code:

```text
procurement_manager
```

but source-code presence alone does not guarantee that the database contains the required role and user relationship.

The Platform database must contain:

```text
Role:
procurement_manager
```

and the user must have the corresponding:

```text
role_id
```

---

## 57.15 `caller=unknown`

Platform logs initially showed:

```text
caller=unknown
caller_endpoint=unknown
```

The cause was that the caller headers were not being supplied.

The Inventory request to Platform should include:

```http
X-Caller-Service: inventory-service
X-Caller-Endpoint: <actual inventory endpoint>
```

After this, Platform can identify the calling service.

---

# 58. Current Authentication Logging Example

A successful Inventory authorization can appear in the Platform terminal as:

```text
Authenticated request |
user_id=1 |
role=procurement_manager |
endpoint=/api/v1/auth/verify
```

followed by:

```text
caller=inventory-service |
caller_endpoint=/api/v1/inventory/bulk-update |
method=POST |
path=/api/v1/auth/verify |
status=200
```

This confirms:

```text
User ID       → identified
Role          → identified
Caller service → identified
Caller endpoint → identified
Authentication → successful
```

---

# 59. Why Direct `/auth/verify` Can Show Unknown Caller

If `/api/v1/auth/verify` is manually called directly from Platform Swagger, the request may not originate from Inventory.

Therefore:

```text
caller=unknown
```

is expected unless the required caller headers are manually supplied.

The important test is the real service-to-service flow:

```text
Inventory endpoint
      |
      v
Inventory authentication dependency
      |
      v
Platform /auth/verify
```

---

# 60. Recommended Startup Order

Start services in this order:

```text
1. PostgreSQL
       |
       v
2. Platform/Auth Service :8005
       |
       v
3. Inventory Service :8001
       |
       v
4. Swagger
       |
       v
5. Login
       |
       v
6. Authorize Inventory
       |
       v
7. Test protected endpoint
```

The Platform Service must be available before Inventory attempts authentication.

---

# 61. Running Platform Service

From the Platform Service directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8005
Application startup complete.
```

---

# 62. Running Inventory Service

From the Inventory Service directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8001
```

If an import error occurs during startup, fix the Python import before testing the API.

---

# 63. Running Sales History Seed

From:

```text
services/inventory
```

run:

```powershell
python -m scripts.seed_sales_history
```

This ensures the `app` package can be resolved correctly.

---

# 64. Verification Procedure

### Step 1 — Start PostgreSQL

Verify PostgreSQL is running.

### Step 2 — Start Platform

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

### Step 3 — Verify Platform

Open:

```text
http://127.0.0.1:8005/docs
```

### Step 4 — Login

Use a seeded Platform user.

### Step 5 — Verify token

Use:

```http
POST /api/v1/auth/verify
```

### Step 6 — Start Inventory

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Step 7 — Open Inventory Swagger

```text
http://127.0.0.1:8001/docs
```

### Step 8 — Authorize

Use:

```text
Bearer <JWT>
```

### Step 9 — Call protected endpoint

For example:

```http
POST /api/v1/inventory/bulk-update
```

### Step 10 — Check Platform terminal

Verify that Platform logs contain:

```text
caller=inventory-service
caller_endpoint=/api/v1/inventory/bulk-update
```

and authenticated user information.

---

# 65. Database Verification

Verify inventory:

```text
sku_id
warehouse_id
quantity_on_hand
avg_daily_demand
lead_time_days
safety_stock
```

Verify sales history:

```text
sku_id
warehouse_id
sale_date
quantity_sold
```

Verify that:

```text
Inventory SKU + Warehouse
```

matches:

```text
Sales History SKU + Warehouse
```

---

# 66. Recommended Data Loading Order

```text
1. Start PostgreSQL
       |
       v
2. Generate sales history
       |
       v
3. Verify sales history
       |
       v
4. Create/upload inventory
       |
       v
5. Verify SKU + warehouse matching
       |
       v
6. Calculate demand
       |
       v
7. Test low stock
       |
       v
8. Test reorder plan
       |
       v
9. Test transfer suggestions
       |
       v
10. Test protected endpoints
```

---

# 67. Testing

Run:

```powershell
pytest -q
```

Detailed:

```powershell
pytest -v
```

Coverage:

```powershell
pytest --cov=app --cov-report=term-missing
```

The actual output from the current environment should be treated as the authoritative test result.

Do not hard-code an old test count in this README because the test suite may change.

---

# 68. Test Coverage Areas

The test suite covers the implemented functionality including:

* Inventory creation
* Inventory retrieval
* Inventory update
* Inventory deletion
* Warehouse-specific inventory
* Request validation
* Manual demand rejection
* Dynamic demand calculation
* Reorder-point calculation
* Reorder threshold
* Low-stock detection
* Reorder check
* Reorder plan
* ABC classification
* ABC boundary conditions
* Transfer suggestions
* What-if analysis
* Simulation
* Simulation immutability
* Negative simulation validation
* Empty simulation
* Bulk update
* Bulk rollback
* Large bulk update
* Negative sales demand
* Concurrent decrement
* CSV validation

Authentication integration tests should additionally verify:

* Missing token
* Invalid token
* Valid token
* Role authorization
* Platform service unavailable
* Platform service timeout
* Caller-service headers

---

# 69. Important Validation Scenarios

## Scenario 1 — Valid authentication

```text
JWT valid
User exists
User active
Role exists
Required role allowed
```

Expected:

```text
Request continues
```

## Scenario 2 — Missing token

```text
No Authorization header
```

Expected:

```text
401 Unauthorized
```

## Scenario 3 — Invalid token

```text
Invalid/expired JWT
```

Expected:

```text
401 Unauthorized
```

## Scenario 4 — Unauthorized role

```text
Valid user
Valid token
Wrong role
```

Expected:

```text
403 Forbidden
```

## Scenario 5 — Platform unavailable

```text
Inventory → Platform
        X
```

Expected:

```text
503 Service Unavailable
```

---

# 70. Why Average Demand Can Be Zero

Possible causes:

1. No sales history exists.
2. SKU does not match.
3. Warehouse does not match.
4. Sales data is outside the demand window.
5. Sales quantity is zero.
6. Demand was not recalculated after inserting sales history.

Example:

```text
Inventory:
SKU0008 | WH003

Sales History:
SKU0008 | WH001
```

The sales history belongs to another warehouse.

Therefore it should not be used for WH003.

---

# 71. End-to-End Business Example

Consider:

```text
SKU = SKU0008
Warehouse = WH003
```

Suppose:

```text
30-day sales = 856
```

Average demand:

```text
856 / 30
≈ 28.53
```

Suppose:

```text
Lead Time = 9
Adjusted Safety Stock = 48
```

Reorder point:

```text
28.53 × 9 + 48
≈ 304.77
```

The implementation converts this according to its configured integer/rounding behavior.

If:

```text
Quantity = 90
```

then the inventory is below ROP.

The service then calculates:

```text
Shortage
Urgency
Suggested Order Quantity
Transfer Opportunity
```

If another warehouse has the same SKU and excess stock, a transfer recommendation can be produced.

---

# 72. Complete Technical Flow

```text
                         Client
                           |
                           v
                    Inventory API
                           |
                    Authentication
                           |
                           v
                   Extract JWT Token
                           |
                           v
                         HTTPX
                           |
                           v
                Platform /auth/verify
                           |
                  +--------+--------+
                  |                 |
                Valid             Invalid
                  |                 |
                  v                 v
             User + Role           401
                  |
                  v
           Role Authorization
                  |
             +----+----+
             |         |
          Allowed    Denied
             |         |
             v         v
        Inventory      403
          Logic
             |
             v
       Database/PostgreSQL
             |
             v
      Business Calculation
             |
       +-----+------+------+
       |            |      |
    Demand         ABC   Transfer
       |            |      |
       +------------+------+
                    |
                    v
              Reorder Plan
                    |
                    v
                 Response
```

---

# 73. Current Development Status

| Feature                                 | Status      |
| --------------------------------------- | ----------- |
| Inventory CRUD                          | Implemented |
| PostgreSQL                              | Implemented |
| Warehouse-level inventory               | Implemented |
| Sales history                           | Implemented |
| Dynamic demand calculation              | Implemented |
| Rolling demand                          | Implemented |
| Automatic reorder point                 | Implemented |
| ABC classification                      | Implemented |
| Adjusted safety stock                   | Implemented |
| Low-stock detection                     | Implemented |
| Urgency calculation                     | Implemented |
| Reorder plan                            | Implemented |
| Transfer suggestion                     | Implemented |
| CSV bulk upload                         | Implemented |
| Bulk update                             | Implemented |
| Inventory decrement                     | Implemented |
| PostgreSQL concurrency protection       | Implemented |
| Simulation                              | Implemented |
| What-if analysis                        | Implemented |
| Test database isolation                 | Implemented |
| Automated testing                       | Implemented |
| Platform/Auth integration               | Implemented |
| HTTPX service-to-service authentication | Implemented |
| Role-based authorization                | Implemented |
| Caller-service logging                  | Implemented |

---

# 74. Known Limitations

### Transfer Suggestions

A transfer cannot be generated if there is no suitable source warehouse.

### Large Inventory Responses

Very large inventory lists may benefit from pagination.

### Large Reorder Plans

Large datasets may require further query optimization and batch aggregation.

### Authentication Dependency

Protected Inventory endpoints depend on the availability of the Platform/Auth Service.

If Platform is unavailable, Inventory cannot successfully perform centralized authentication.

---

# 75. Future Improvements

Potential improvements include:

1. Pagination for inventory listing.
2. Additional database indexes after query-plan analysis.
3. Further batch demand aggregation.
4. More load testing.
5. More authentication integration tests.
6. Request ID propagation between services.
7. Structured distributed tracing.
8. Monitoring and metrics.
9. Stronger CSV validation.
10. CI/CD test execution.
11. Additional database constraints.
12. Improved centralized error handling.
13. Caching of expensive calculations where appropriate.
14. Improved service-to-service observability.
15. Integration with downstream Logistics services.

---

# 76. Developer Commands

### Start Platform

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

### Start Inventory

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Generate sales history

```powershell
python -m scripts.seed_sales_history
```

### Run tests

```powershell
pytest -q
```

### Detailed tests

```powershell
pytest -v
```

### Coverage

```powershell
pytest --cov=app --cov-report=term-missing
```

### Inventory Swagger

```text
http://127.0.0.1:8001/docs
```

### Platform Swagger

```text
http://127.0.0.1:8005/docs
```

---

# 77. Final Summary

The Inventory Service provides a complete demand-driven inventory management workflow.

```text
Sales History
      |
      v
Rolling Demand
      |
      v
ABC Classification
      |
      v
Adjusted Safety Stock
      |
      v
Reorder Point
      |
      v
Low Stock Detection
      |
      v
Urgency Calculation
      |
      v
Reorder Plan
      |
      v
Transfer Suggestion
```

The service supports:

```text
Inventory Management
        +
Demand Calculation
        +
Reorder Planning
        +
ABC Classification
        +
Warehouse Transfers
        +
Bulk Operations
        +
Simulation
        +
Concurrency Protection
        +
PostgreSQL
        +
Automated Testing
        +
Centralized Authentication
        +
Role-Based Authorization
        +
Service-to-Service HTTPX Integration
        +
Caller-Service Logging
```

The main integration responsibility is:

```text
Inventory Service
       |
       | HTTPX
       v
Platform/Auth Service
       |
       | Verify JWT
       | Identify User
       | Identify Role
       v
Authorization Result
       |
       v
Inventory Endpoint
```

This architecture keeps authentication centralized in the Platform Service while allowing Inventory and other microservices to consume the same authentication contract.
