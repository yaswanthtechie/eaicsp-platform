# Inventory Service

## 1. Overview

The **Inventory Service** is a FastAPI-based backend microservice that manages inventory at the **SKU and warehouse level**.

The service uses historical sales data to calculate demand dynamically and uses that demand to determine reorder points and replenishment requirements.

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

The main objective is to avoid depending on manually entered demand values. Demand is derived from `SalesHistory` using the SKU and warehouse combination.

---

# 2. Main Objectives

The Inventory Service provides:

* Warehouse-level inventory management
* Dynamic demand calculation
* Rolling average demand
* Automatic reorder-point calculation
* ABC classification
* ABC-based safety-stock adjustment
* Low-stock detection
* Reorder planning
* Urgency calculation
* Warehouse transfer suggestions
* Bulk inventory updates
* CSV inventory upload
* Inventory decrement
* Concurrency protection
* Simulation and what-if analysis
* PostgreSQL persistence
* Automated pytest coverage

---

# 3. Technology Stack

| Technology              | Purpose                       |
| ----------------------- | ----------------------------- |
| Python 3.12.x           | Backend programming language  |
| FastAPI                 | REST API framework            |
| Uvicorn                 | ASGI server                   |
| SQLAlchemy              | ORM and database access       |
| PostgreSQL              | Application and test database |
| Pydantic                | Request/response validation   |
| Pytest                  | Automated testing             |
| HTTPX                   | API testing                   |
| CSV                     | Bulk inventory upload         |
| Python standard library | Utility functionality         |

---

# 4. Project Structure

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

# 5. Database

PostgreSQL is used for application data.

The main tables are:

1. `inventory`
2. `sales_history`

A separate PostgreSQL database is used for automated tests.

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

This separation prevents automated tests from modifying production data.

---

# 6. Inventory Model

The inventory record represents stock for a specific SKU in a specific warehouse.

Important fields:

| Field              | Description                     |
| ------------------ | ------------------------------- |
| `sku_id`           | Product/SKU identifier          |
| `product_name`     | Product name                    |
| `warehouse_id`     | Warehouse identifier            |
| `quantity_on_hand` | Current available quantity      |
| `avg_daily_demand` | Calculated average daily demand |
| `lead_time_days`   | Supplier lead time              |
| `safety_stock`     | Base safety stock               |

The same SKU can exist in multiple warehouses.

Example:

```text
SKU0008 | WH001
SKU0008 | WH002
SKU0008 | WH003
```

Each warehouse can have different stock and sales history.

---

# 7. Inventory Validation

Inventory creation accepts:

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

Additional unknown fields are rejected.

For example, `avg_daily_demand` is **not accepted as a manually supplied create field**.

Demand is calculated from sales history.

---

# 8. Sales History

The `sales_history` table stores historical sales information.

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

The important matching keys are:

```text
sku_id
warehouse_id
```

For example:

```text
Inventory:
SKU0008 | WH003

SalesHistory:
SKU0008 | WH003
```

This allows the service to calculate demand for that inventory record.

If the warehouse does not match, the sales history is not applicable to that inventory record.

---

# 9. Sales History Test Data

The included seed script generates synthetic sales history.

Current seed configuration:

```text
TOTAL_ITEMS = 50
TOTAL_DAYS = 30
WAREHOUSES = 5
```

Therefore the script generates:

```text
50 × 30 = 1,500 sales-history records
```

Each SKU receives a different base demand and daily variation.

Example:

```text
SKU0001 | WH001 | 2026-07-20 | 32
SKU0001 | WH001 | 2026-07-21 | 28
SKU0001 | WH001 | 2026-07-22 | 35
```

The generated quantities are positive and contain variation so that demand calculations are more realistic.

---

# 10. Average Daily Demand

Demand is calculated from `SalesHistory`.

Basic formula:

```text
Average Daily Demand =
    Total Quantity Sold / Number of Days
```

Example:

```text
Total sales = 900
Days       = 30

Average Daily Demand =
    900 / 30

Average Daily Demand = 30
```

The calculated demand is used by the inventory and reorder logic.

The service does not rely on manually supplied demand during inventory creation.

---

# 11. Rolling Average Demand

The demand service calculates demand using recent sales history.

The default demand window is:

```text
30 days
```

Conceptually:

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

The rolling demand is then used by reorder calculations.

---

# 12. Reorder Point

The reorder point is calculated using demand, lead time, and adjusted safety stock.

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

ROP =
30 × 5 + 45

ROP = 195
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

The item requires replenishment.

---

# 13. ABC Classification

The service classifies SKUs based on sales volume.

The three classifications are:

```text
A
B
C
```

The classification is based on the relative sales ranking of SKUs.

Conceptually:

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

The classification is then used to adjust safety stock.

The exact boundary behavior is covered by automated tests, including the 20% boundary.

---

# 14. Adjusted Safety Stock

Inventory contains a base:

```text
safety_stock
```

The ABC logic can adjust this value according to the SKU's ABC tier.

The adjusted safety stock is then used in the reorder-point calculation.

```text
Base Safety Stock
        |
        v
ABC Tier
        |
        v
Adjusted Safety Stock
        |
        v
Reorder Point
```

The reorder plan exposes:

```text
adjusted_safety_stock
```

so the calculated value can be inspected.

---

# 15. Low Stock Detection

An inventory item requires replenishment when:

```text
quantity_on_hand < reorder_point
```

Example:

```text
quantity_on_hand = 90
reorder_point = 304
```

Because:

```text
90 < 304
```

the item is considered low stock.

An item exactly at the reorder point does **not** require reorder:

```text
quantity_on_hand == reorder_point
```

The test suite explicitly verifies both cases:

```text
ROP
ROP - 1
```

---

# 16. Suggested Order Quantity

For a low-stock item, the suggested order quantity is based on the shortage relative to the reorder point.

Example:

```text
Reorder Point = 100
Current Quantity = 60

Suggested Order Quantity =
100 - 60

= 40
```

At exactly the reorder point:

```text
Suggested Order Quantity = 0
```

---

# 17. Urgency Score

The reorder plan calculates an urgency score for low-stock inventory.

Formula:

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
Reorder Point = 304
Quantity = 90
Average Daily Demand = 28.53

Shortage =
304 - 90
= 214

Urgency Score =
214 / 28.53
≈ 7.5
```

A higher urgency score means the inventory requires more urgent replenishment.

The reorder plan sorts low-stock entries by urgency.

---

# 18. Reorder Plan

The reorder plan combines the main inventory calculations.

The process is:

```text
1. Read Inventory
       |
2. Calculate Rolling Demand
       |
3. Classify SKU
       |
4. Calculate Adjusted Safety Stock
       |
5. Calculate Reorder Point
       |
6. Compare Quantity with ROP
       |
7. Calculate Urgency
       |
8. Find Transfer Opportunity
       |
9. Build Reorder Plan
       |
10. Sort by Urgency
```

The response contains:

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

# 19. Warehouse Transfer Suggestion

The transfer service looks for another warehouse that has excess stock of the same SKU.

A transfer can be suggested when:

1. The destination has low stock.
2. The source contains the same SKU.
3. The source is above its reorder point.
4. The source and destination warehouses are different.

Example:

```text
SKU0008

WH003:
    Quantity = 90
    ROP = 304

WH004:
    Quantity = 600
    ROP = 304
```

Destination:

```text
90 < 304
```

Therefore WH003 is low stock.

Source:

```text
600 > 304
```

Therefore WH004 has excess stock.

Possible recommendation:

```text
WH004 → WH003
```

---

# 20. Transfer Quantity

The destination shortage is:

```text
Destination Shortage =
Destination ROP - Destination Quantity
```

The source excess is:

```text
Source Excess =
Source Quantity - Source ROP
```

Transfer quantity is:

```text
min(
    Source Excess,
    Destination Shortage
)
```

Example:

```text
Destination shortage = 214
Source excess = 296

Transfer quantity =
min(296, 214)

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

# 21. When Transfer Suggestion Is Null

A null transfer suggestion is valid behavior.

For example:

```text
SKU0008 | WH003 | LOW STOCK
```

If the SKU does not exist in another warehouse, there is no possible transfer source.

Another example:

```text
WH003 | LOW STOCK
WH004 | NOT EXCESS
```

In that situation WH004 should not be used as a transfer source.

The response can therefore contain:

```json
"transfer_suggestion": null
```

This is not an error.

---

# 22. Bulk CSV Upload

The service supports inventory creation/update through CSV upload.

Example:

```csv
sku_id,product_name,warehouse_id,quantity_on_hand,lead_time_days,safety_stock
SKU0001,Product 0001,WH001,120,5,30
SKU0002,Product 0002,WH002,250,7,40
SKU0003,Product 0003,WH003,80,4,25
```

The CSV does not require `avg_daily_demand`.

The service can calculate demand from matching sales history.

Conceptually:

```text
CSV
 |
 v
SKU + Warehouse
 |
 v
Sales History
 |
 v
Demand Calculation
 |
 v
Inventory
```

CSV validation includes checks such as required columns and invalid negative quantities.

---

# 23. Existing Inventory During Bulk Upload

Inventory is identified by the SKU and warehouse combination.

```text
sku_id + warehouse_id
```

When an existing record is encountered, the upload flow should update the existing record rather than creating a duplicate inventory entry.

Demand should also be recalculated when sales history is available.

---

# 24. Bulk Update

The bulk-update operation supports multiple inventory quantity changes in one request.

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

If one update fails, the transaction should be rolled back so that earlier updates in the same operation are not partially committed.

The test suite includes a rollback test.

---

# 25. Inventory Decrement and Concurrency

Inventory can be changed by multiple requests at the same time.

Example:

```text
Initial quantity = 100

Request A:
decrement 20

Request B:
decrement 30
```

The expected final quantity is:

```text
100 - 20 - 30 = 50
```

Database row locking is used for the decrement operation when running against PostgreSQL to avoid lost updates.

The test suite includes a concurrent decrement test.

---

# 26. Simulation

The service provides simulation functionality for demand growth scenarios.

For example:

```text
Current Demand = 10
Growth = 30%
```

Simulated demand becomes approximately:

```text
10 × 1.30 = 13
```

Simulation is intended to calculate the effect of a demand change without changing the stored inventory quantity.

The test suite verifies that simulation does not modify inventory data.

The service also validates negative growth values.

---

# 27. What-If Analysis

The `what-if` endpoint provides scenario analysis using a requested demand spike.

Example:

```json
{
  "spike_percent": 30
}
```

The response provides summary information including:

```text
spike_percent
total_items
affected_items
total_suggested_order_qty
details
```

Each affected item can contain:

```text
sku_id
current_quantity
new_reorder_point
needs_reorder
suggested_order_qty
```

This allows the effect of increased demand to be evaluated without changing the stored inventory records.

---

# 28. API Endpoints

The main API base path is:

```text
/api/v1/inventory
```

## Create Inventory

```http
POST /api/v1/inventory/
```

Creates an inventory record.

---

## Get All Inventory

```http
GET /api/v1/inventory/
```

Returns inventory records.

For very large datasets, pagination and query optimization should be considered.

---

## Get Inventory by SKU and Warehouse

```http
GET /api/v1/inventory/{sku_id}/{warehouse_id}
```

Returns inventory for a specific SKU and warehouse.

---

## Update Inventory

```http
PUT /api/v1/inventory/{sku_id}/{warehouse_id}
```

Updates supported inventory fields.

---

## Delete Inventory

```http
DELETE /api/v1/inventory/{sku_id}/{warehouse_id}
```

Deletes an inventory record.

---

## Low Stock

```http
GET /api/v1/inventory/low-stock
```

Returns inventory that is below its calculated reorder point.

---

## Reorder Plan

```http
GET /api/v1/inventory/reorder-plan
```

Returns the calculated replenishment plan.

---

## Reorder Check

The test suite uses:

```http
GET /api/v1/inventory/{sku_id}/{warehouse_id}/reorder-check
```

It returns information such as:

```text
sku_id
current_qty
reorder_point
needs_reorder
suggested_order_qty
```

---

## Bulk Upload

```http
POST /api/v1/inventory/bulk-upload
```

Uploads inventory records from a CSV file.

---

## Bulk Update

```http
POST /api/v1/inventory/bulk-update
```

Updates multiple inventory records in one transaction.

---

## Decrement

```http
POST /api/v1/inventory/decrement
```

Decreases inventory quantity.

---

## Single SKU Simulation

The service supports demand-spike simulation for an inventory item.

The exact request format is exposed through Swagger and should be used as the source of truth for the currently deployed route.

---

## Global Simulation

The test suite also verifies the global simulation route:

```http
GET /api/v1/inventory/simulate?growth_percent=30
```

This returns simulated demand information without modifying stored inventory.

---

## What-If

```http
POST /api/v1/inventory/what-if
```

Runs a demand-spike scenario analysis.

---

# 29. Pydantic Schemas

The service uses Pydantic models to validate API requests and responses.

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

Validation prevents invalid values such as negative inventory quantities, negative lead times, and negative safety stock.

---

# 30. Environment Configuration

Create a `.env` file based on `.env.example`.

Example:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory

TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test
```

The two databases must be different.

```text
DATABASE_URL
    |
    v
Application Database

TEST_DATABASE_URL
    |
    v
Pytest Database
```

Never point `TEST_DATABASE_URL` to the production/application database.

---

# 31. Running the Service

Go to the Inventory Service directory:

```powershell
cd services\inventory
```

Activate the virtual environment:

```powershell
.\myenv\Scripts\activate
```

Start FastAPI:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

The API will be available at:

```text
http://127.0.0.1:8001
```

Swagger UI:

```text
http://127.0.0.1:8001/docs
```

---

# 32. Running the Sales History Seed

From the Inventory Service directory:

```powershell
python -m scripts.seed_sales_history
```

Using module execution is recommended because the script imports the application package:

```python
from app.database import ...
```

Running from the correct directory prevents errors such as:

```text
ModuleNotFoundError: No module named 'app'
```

---

# 33. Recommended Data Loading Order

For meaningful demand calculations, use this order:

```text
1. Start PostgreSQL
        |
2. Generate SalesHistory
        |
3. Create/upload Inventory
        |
4. Match SKU + Warehouse
        |
5. Calculate Demand
        |
6. Verify Inventory
        |
7. Run Low Stock
        |
8. Run Reorder Plan
        |
9. Test Transfer Suggestions
```

The important requirement is that sales history must match the inventory's:

```text
sku_id
warehouse_id
```

---

# 34. Why Average Daily Demand Can Be Zero

`avg_daily_demand` can be zero when matching sales history is unavailable.

Possible causes:

1. No sales history exists.
2. SKU does not match.
3. Warehouse does not match.
4. Sales history is outside the demand window.
5. Sales quantity is zero.
6. Inventory was created before sales history was inserted and was not recalculated.

Example:

```text
Inventory:
SKU0008 | WH003

SalesHistory:
SKU0008 | WH001
```

These are different warehouse records.

Therefore sales for `WH001` should not be used to calculate demand for `WH003`.

---

# 35. PostgreSQL Verification

After creating or uploading inventory, verify the database.

Important fields:

```text
sku_id
warehouse_id
quantity_on_hand
avg_daily_demand
lead_time_days
safety_stock
```

When matching sales history exists, verify that:

```text
avg_daily_demand > 0
```

Also verify that the calculated reorder point and reorder plan are consistent with the available sales history.

---

# 36. Transaction Handling

Database operations use transactions.

Successful operations are committed:

```text
COMMIT
```

Failed operations are rolled back:

```text
ROLLBACK
```

This is particularly important for:

* Bulk updates
* Inventory modifications
* Concurrent inventory changes

The test suite includes a bulk rollback scenario.

---

# 37. Test Database Isolation

Pytest uses `TEST_DATABASE_URL`.

The test configuration creates:

```text
test_engine
TestingSessionLocal
```

and overrides FastAPI's:

```python
get_db
```

dependency.

The test database is reset between tests.

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

The application database is not used by the tests.

---

# 38. Automated Testing

The test suite covers the main inventory business logic and API behavior.

Current test areas include:

* Inventory creation
* Inventory retrieval
* Inventory update
* Inventory deletion
* Warehouse-specific inventory
* Request validation
* Manual demand rejection
* Dynamic demand calculation
* Reorder-point calculation
* Exact reorder threshold
* One-unit-below threshold
* Reorder check
* Low-stock detection
* Reorder plan
* ABC classification
* ABC boundary behavior
* Transfer suggestions
* What-if analysis
* Simulation
* Simulation immutability
* Negative simulation validation
* Empty simulation
* Bulk update
* Bulk rollback
* 1,000-item bulk update
* Negative sales demand
* Concurrent decrement
* CSV validation

---

# 39. Test Commands

From:

```text
services/inventory
```

run:

```powershell
pytest -v
```

For a concise result:

```powershell
pytest -q
```

For coverage:

```powershell
pytest --cov=app --cov-report=term-missing
```

---

# 40. Current Test Status

The current development test suite was verified with:

```text
pytest -q
```

Result:

```text
29 passed
0 failed
```

The test suite covers the implemented inventory functionality and important edge cases.

If the test command later reports warnings or failures, the actual pytest output should be treated as the current source of truth rather than this README.

---

# 41. Important Edge Cases Tested

## Reorder threshold

At exactly the reorder point:

```text
quantity == reorder_point
```

Expected:

```text
needs_reorder = false
suggested_order_qty = 0
```

One unit below:

```text
quantity == reorder_point - 1
```

Expected:

```text
needs_reorder = true
suggested_order_qty = 1
```

---

## Negative demand

Negative sales demand is invalid.

Example:

```text
quantity_sold = -10
```

The inventory creation request is rejected when the associated sales history contains invalid negative demand.

---

## Manual demand

The API rejects manually supplied:

```text
avg_daily_demand
```

during inventory creation/update because demand is calculated from sales history.

---

## Bulk rollback

If one item in a bulk update fails, the entire transaction should be rolled back.

Example:

```text
Valid update
      |
Invalid update
      |
      v
ROLLBACK
```

The earlier valid update must not remain partially committed.

---

## ABC boundary

The test suite verifies the ABC classification boundary at the 20% ranking point.

This ensures that boundary conditions are handled consistently.

---

## Concurrent decrement

Multiple simultaneous decrement requests are tested to ensure inventory updates are not lost when PostgreSQL row locking is available.

---

# 42. Performance Testing

The service includes a bulk-update test using:

```text
1,000 inventory records
```

The test measures the time required to update all 1,000 records.

For example:

```text
1000-item bulk update: 1.0058 seconds
```

The exact execution time depends on:

* Machine performance
* PostgreSQL performance
* Network/database latency
* Python version
* Dataset state
* Environment configuration

Therefore a fixed execution time should not be treated as a permanent benchmark.

---

# 43. Large Dataset Testing

The service can be tested with larger datasets.

For example:

```text
1,000 inventory items
30 days of sales history
```

This produces:

```text
1,000 × 30
= 30,000 sales-history records
```

For 60 days:

```text
1,000 × 60
= 60,000 records
```

Large datasets are useful for evaluating demand calculation and reorder-plan performance.

---

# 44. Performance Considerations

For 1,000 inventory rows, /reorder-plan performance improved from 381.83 seconds to 0.448 seconds after query optimization.

Useful indexes may include:

```text
sku_id
warehouse_id
sale_date
```

A composite index on:

```text
sku_id + warehouse_id
```

can be useful because demand calculations commonly search sales history using both fields.

Queries that also filter by date may benefit from an index covering:

```text
sku_id
warehouse_id
sale_date
```

The actual indexes should be confirmed against the database query plans before being added.

---

# 45. Reorder Plan Optimization

For a large number of inventory records, repeatedly querying sales history for every individual inventory record can become expensive.

A less efficient pattern is:

```text
Inventory 1 → Sales Query
Inventory 2 → Sales Query
Inventory 3 → Sales Query
...
```

For large datasets, a better approach is to aggregate sales history in batches:

```text
SalesHistory
     |
     v
GROUP BY
sku_id + warehouse_id
     |
     v
Demand Results
     |
     v
Inventory Calculations
```

This reduces database round trips and can improve reorder-plan performance.

---

# 46. Example End-to-End Calculation

Consider:

```text
SKU = SKU0008
Warehouse = WH003
```

Suppose the last 30 days contain approximately:

```text
Total sales = 856
```

Average demand:

```text
856 / 30
≈ 28.53
```

Suppose:

```text
ABC Tier = B
Adjusted Safety Stock = 48
Lead Time = 9
```

Reorder point:

```text
28.53 × 9 + 48
≈ 304.77
```

Depending on the implementation's rounding/conversion rules, the stored reorder point will be an integer.

If current inventory is:

```text
90
```

then:

```text
90 < reorder point
```

The item becomes low stock.

The shortage is approximately:

```text
304 - 90
= 214
```

Urgency is approximately:

```text
214 / 28.53
≈ 7.5
```

The reorder plan then checks whether another warehouse has excess inventory for `SKU0008`.

---

# 47. Complete Business Flow

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
               Quantity < ROP ?
                    /       \
                  NO         YES
                  |           |
                  v           v
              No Reorder   Urgency
                              |
                              v
                     Search Other Warehouses
                              |
                         Same SKU?
                         /      \
                       NO        YES
                       |          |
                       v          v
                  No Transfer   Check Excess
                                   |
                              +----+----+
                              |         |
                           Excess    No Excess
                              |         |
                              v         v
                           TRANSFER   No Transfer
                              |
                              v
                        Reorder Plan
```

---

# 48. Development Issues Resolved

## Python and Dependency Compatibility

Package installation problems occurred during development because of Python/package compatibility.

The development environment was moved to a compatible Python 3.12.x setup and dependencies were installed in the virtual environment.

---

## `ModuleNotFoundError: No module named 'app'`

The sales-history script uses imports such as:

```python
from app.database import ...
```

Running the script from the wrong directory caused:

```text
ModuleNotFoundError: No module named 'app'
```

The recommended command is:

```powershell
cd services\inventory
python -m scripts.seed_sales_history
```

---

## Unrealistic Sales Data

Initial synthetic data was not suitable for realistic demand testing.

The seed script was changed to generate positive quantities with daily variation.

This provides more meaningful values for:

```text
Average Daily Demand
Reorder Point
Urgency
ABC Classification
Reorder Plan
```

---

## Empty Inventory

Inventory and sales history are separate datasets.

Sales history can be generated independently before inventory is uploaded.

For demand calculation to work correctly, the SKU and warehouse identifiers must match.

---

## Zero Average Daily Demand

If PostgreSQL contains:

```text
avg_daily_demand = 0
```

verify:

1. Matching sales history exists.
2. `sku_id` matches.
3. `warehouse_id` matches.
4. Sales dates are within the demand window.
5. Sales quantities are positive.
6. The inventory record was recalculated after sales history was inserted.

---

## Transfer Suggestion Is Null

A null transfer suggestion is expected when there is no suitable source warehouse.

Transfer logic requires:

```text
Same SKU
+
Different Warehouse
+
Destination Low Stock
+
Source Excess Stock
```

---

# 49. Verification Procedure

Before submitting the Inventory Service for review:

### Step 1 — Start PostgreSQL

Ensure PostgreSQL is running.

### Step 2 — Activate the environment

```powershell
.\myenv\Scripts\activate
```

### Step 3 — Start the application

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Step 4 — Open Swagger

```text
http://127.0.0.1:8001/docs
```

### Step 5 — Generate sales history

```powershell
python -m scripts.seed_sales_history
```

### Step 6 — Verify sales history

Confirm that records exist for the required SKU and warehouse combinations.

### Step 7 — Create or upload inventory

Use Swagger or the bulk CSV endpoint.

### Step 8 — Verify inventory

Check:

```text
sku_id
warehouse_id
quantity_on_hand
avg_daily_demand
lead_time_days
safety_stock
```

### Step 9 — Test low stock

```http
GET /api/v1/inventory/low-stock
```

### Step 10 — Test reorder plan

```http
GET /api/v1/inventory/reorder-plan
```

Verify:

```text
rolling_avg_demand
reorder_point
abc_tier
adjusted_safety_stock
urgency_score
```

### Step 11 — Test transfer

Create the same SKU in two warehouses:

```text
Destination → Low Stock
Source      → Excess Stock
```

Then verify that a transfer suggestion can be generated.

### Step 12 — Run automated tests

```powershell
pytest -q
```

### Step 13 — Run coverage

```powershell
pytest --cov=app --cov-report=term-missing
```

---

# 50. Current Development Status

| Feature                           | Status      |
| --------------------------------- | ----------- |
| Inventory CRUD                    | Implemented |
| PostgreSQL                        | Implemented |
| Warehouse-level inventory         | Implemented |
| Sales history                     | Implemented |
| Dynamic demand calculation        | Implemented |
| Rolling demand                    | Implemented |
| Automatic reorder point           | Implemented |
| ABC classification                | Implemented |
| Adjusted safety stock             | Implemented |
| Low-stock detection               | Implemented |
| Urgency calculation               | Implemented |
| Reorder plan                      | Implemented |
| Transfer suggestion               | Implemented |
| CSV bulk upload                   | Implemented |
| Bulk update                       | Implemented |
| Inventory decrement               | Implemented |
| PostgreSQL concurrency protection | Implemented |
| Simulation                        | Implemented |
| What-if analysis                  | Implemented |
| Test database isolation           | Implemented |
| Automated tests                   | Implemented |

### Test verification

```text
pytest -q

29 passed
0 failed
```

---

# 51. Known Limitations

### Transfer Suggestions

Transfer suggestions require a suitable source warehouse.

The service cannot suggest a transfer when:

* The SKU does not exist in another warehouse.
* The other warehouse is not above its reorder point.
* There is insufficient excess stock.

Therefore:

```json
"transfer_suggestion": null
```

can be a valid response.

### Large Inventory Queries

Returning very large inventory datasets from one request can become slower.

Possible future improvements include pagination and query optimization.

### Large Reorder Plans

Repeated sales-history queries can become expensive as the number of inventory records increases.

Batch aggregation can improve scalability.

---

# 52. Future Improvements

Potential improvements include:

1. Pagination for inventory listing.
2. Additional database indexes after query-plan analysis.
3. Batch sales-history aggregation.
4. Reorder-plan query optimization.
5. More transfer edge-case tests.
6. Larger load tests.
7. Structured logging.
8. Monitoring and metrics.
9. Stronger CSV validation.
10. CI/CD automated testing.
11. Additional database constraints.
12. Improved error handling.
13. Caching of expensive calculations where appropriate.
14. Integration with downstream Logistics services.

---

# 53. Summary

The Inventory Service provides a demand-driven inventory-management workflow.

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
Urgency Score
      |
      v
Reorder Plan
      |
      v
Warehouse Transfer Suggestion
```

The service supports warehouse-level inventory management, dynamic demand calculation, replenishment planning, transfer recommendations, bulk operations, simulation, concurrency protection, and automated testing.

Current automated test verification:

```text
pytest -q

28 passed

```

---

# 54. Developer Commands

Run the application:

```powershell
uvicorn app.main:app --reload 
```

Generate sales history:

```powershell
python -m scripts.seed_sales_history
```

Run tests:

```powershell
pytest -v
```

Run concise tests:

```powershell
pytest -q
```

Run coverage:

```powershell
pytest --cov=app --cov-report=term-missing
```

Swagger:

```text
http://127.0.0.1:8001/docs
```

---

## Environment Configuration

Create `.env` from `.env.example`.

Required variables:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test
```

The application database and test database **must be different databases**.
