# Inventory Service

## 1. Project Overview

The Inventory Service is a backend microservice developed using FastAPI and PostgreSQL.

The main purpose of this service is to manage inventory at warehouse level and automatically determine when inventory needs to be replenished.

The service uses historical sales data to calculate demand dynamically and uses that demand to calculate the reorder point.

The main business flow is:

Sales History
        |
        v
Average Daily Demand
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
Warehouse Transfer Suggestion

---

# 2. Main Objective

The main objective of the Inventory Service is:

> Automatically calculate average daily demand and reorder points from sales history and identify inventory that needs replenishment.

The service should avoid depending on manually entered demand values.

For example:

If a SKU has 30 days of sales:

    Total sales = 900
    Number of days = 30

Then:

    Average Daily Demand = 900 / 30
                          = 30

The calculated demand is then used in the reorder-point calculation.

---

# 3. Technology Stack

The service is implemented using:

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- PostgreSQL
- Pydantic
- Pytest
- HTTPX
- CSV
- Python standard library

Python version used during development:

    Python 3.12.x

---

# 4. Service Responsibilities

The Inventory Service handles:

1. Inventory creation
2. Inventory retrieval
3. Inventory update
4. Inventory deletion
5. Warehouse-level inventory
6. Sales history
7. Average daily demand
8. Rolling demand calculation
9. Reorder-point calculation
10. ABC classification
11. ABC-based safety stock
12. Low-stock detection
13. Reorder planning
14. Urgency calculation
15. Warehouse transfer suggestions
16. Bulk CSV inventory upload
17. Bulk inventory update
18. Inventory decrement
19. Concurrency protection
20. Reorder checking
21. Simulation / what-if calculations
22. Automated testing

---

# 5. Project Structure

The Inventory Service is organized approximately as follows:

    services/
    └── inventory/
        |
        ├── app/
        │   ├── __init__.py
        │   ├── main.py
        │   ├── database.py
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
        └── README.md

---

# 6. Database

PostgreSQL is used as the primary database.

The service contains two important tables:

1. Inventory
2. SalesHistory

---

# 7. Inventory Table

The Inventory table stores current inventory for each SKU and warehouse.

Main fields:

    sku_id
    product_name
    warehouse_id
    quantity_on_hand
    avg_daily_demand
    lead_time_days
    safety_stock

### Field Description

| Field | Description |
|---|---|
| sku_id | Unique product identifier |
| product_name | Product name |
| warehouse_id | Warehouse identifier |
| quantity_on_hand | Current stock available |
| avg_daily_demand | Average daily sales demand |
| lead_time_days | Supplier lead time |
| safety_stock | Additional stock kept as protection |

Inventory is maintained at warehouse level.

Therefore the same SKU can exist in multiple warehouses.

Example:

    SKU0008 | WH001
    SKU0008 | WH002
    SKU0008 | WH003

Each warehouse can have a different quantity and demand.

---

# 8. Sales History Table

SalesHistory stores historical sales.

Main fields:

    sku_id
    warehouse_id
    sale_date
    quantity_sold

Example:

    SKU0001 | WH001 | 2026-07-15 | 25
    SKU0001 | WH001 | 2026-07-16 | 31
    SKU0001 | WH001 | 2026-07-17 | 28

The important matching fields are:

    sku_id
    warehouse_id

Sales history must match the inventory SKU and warehouse.

For example:

Inventory:

    SKU0008 | WH003

Sales History:

    SKU0008 | WH003

This allows demand calculation.

If the warehouse does not match, the service cannot correctly calculate demand for that inventory record.

---

# 9. Sales History Test Data

Synthetic sales history is used for development and testing.

The test dataset can contain:

    50 SKUs
    30 days

Therefore:

    50 × 30 = 1,500 records

The sales quantity is generated with variation rather than using only 0 and 1.

Example:

    SKU0001 | WH001 | Day 1  | 25
    SKU0001 | WH001 | Day 2  | 31
    SKU0001 | WH001 | Day 3  | 28
    SKU0001 | WH001 | Day 4  | 34

This produces meaningful demand calculations.

---

# 10. Average Daily Demand

Average daily demand is calculated from SalesHistory.

Formula:

    Average Daily Demand =
        Total Quantity Sold / Number of Days

Example:

    Sales for 30 days = 900

    Average Daily Demand =
        900 / 30

    Average Daily Demand = 30

The calculated value should be stored in:

    Inventory.avg_daily_demand

The purpose is to make demand data dynamic rather than manually entering it.

---

# 11. Rolling Average Demand

The demand service calculates a rolling average based on recent sales history.

Default demand window:

    30 days

The calculation process is:

    Inventory
        |
        v
    SKU + Warehouse
        |
        v
    SalesHistory
        |
        v
    Last 30 Days
        |
        v
    Calculate Average
        |
        v
    Rolling Average Demand

The rolling average is used by the reorder service.

---

# 12. Reorder Point

The reorder point is calculated dynamically.

Formula:

    Reorder Point =
        Rolling Average Demand
        × Lead Time Days
        + Adjusted Safety Stock

Example:

    Rolling Average Demand = 30
    Lead Time = 5 days
    Adjusted Safety Stock = 45

Therefore:

    Reorder Point =
        30 × 5 + 45

    Reorder Point = 195

If:

    Quantity on Hand = 100

then:

    100 < 195

The item is considered low stock.

---

# 13. ABC Classification

The service classifies SKUs into:

    A
    B
    C

ABC classification is used to determine inventory importance and adjust safety stock.

General flow:

    Sales Data
        |
        v
    ABC Classification
        |
        +---- A
        |
        +---- B
        |
        +---- C
        |
        v
    Tier Safety Stock

The reorder calculation then uses the adjusted safety stock.

---

# 14. Adjusted Safety Stock

The base safety stock comes from the Inventory table.

The ABC service adjusts the base safety stock according to the SKU tier.

Example:

    Base Safety Stock = 40
    ABC Tier = B

The ABC service calculates the adjusted safety stock.

The adjusted value is then used by:

    Reorder Point

This makes the reorder point sensitive to SKU classification.

---

# 15. Low Stock Detection

The service identifies an item as low stock when:

    quantity_on_hand < reorder_point

Example:

    Quantity on Hand = 90
    Reorder Point = 304

Because:

    90 < 304

the SKU is included in the reorder plan.

---

# 16. Urgency Score

Urgency score indicates how urgently stock needs to be replenished.

Shortage:

    shortage =
        reorder_point - quantity_on_hand

If average daily demand is greater than zero:

    urgency_score =
        shortage / average_daily_demand

Example:

    Reorder Point = 304
    Quantity = 90
    Average Daily Demand = 28.53

Shortage:

    304 - 90 = 214

Urgency:

    214 / 28.53
    ≈ 7.5

Therefore:

    urgency_score = 7.5

A higher score means greater urgency.

The reorder plan sorts items by urgency score in descending order.

---

# 17. Reorder Plan

The reorder-plan endpoint performs the following:

1. Reads inventory.
2. Calculates rolling demand.
3. Performs ABC classification.
4. Calculates adjusted safety stock.
5. Calculates reorder point.
6. Checks whether inventory is below reorder point.
7. Calculates urgency score.
8. Searches for transfer opportunities.
9. Creates reorder-plan entries.
10. Sorts the result by urgency.

Flow:

    Inventory
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
    Quantity < ROP?
        |
        +------ NO ------> Ignore
        |
        +------ YES
                  |
                  v
             Urgency Score
                  |
                  v
          Transfer Suggestion
                  |
                  v
             Reorder Plan

---

# 18. Transfer Suggestion

The transfer service identifies whether inventory can be transferred from another warehouse.

The destination warehouse must be low stock.

The source warehouse must have excess stock.

Conditions:

    1. Same SKU
    2. Different warehouse
    3. Destination below reorder point
    4. Source above its reorder point

Example:

    SKU0008

    WH003:
        Quantity = 90
        ROP = 304

    WH004:
        Quantity = 600
        ROP = 304

WH003:

    90 < 304

Therefore:

    LOW STOCK

WH004:

    600 > 304

Therefore:

    EXCESS STOCK

The service can recommend:

    WH004 → WH003

---

# 19. Transfer Quantity

Destination shortage:

    destination_shortage =
        destination_reorder_point
        - destination_quantity

Source excess:

    source_excess =
        source_quantity
        - source_reorder_point

Transfer quantity:

    transfer_quantity =
        min(
            source_excess,
            destination_shortage
        )

Example:

    Destination shortage = 214
    Source excess = 296

Therefore:

    transfer_quantity =
        min(296, 214)

    transfer_quantity = 214

Example response:

    {
        "sku_id": "SKU0008",
        "source_warehouse": "WH004",
        "destination_warehouse": "WH003",
        "transfer_quantity": 214,
        "source_excess_quantity": 296,
        "destination_shortage_quantity": 214,
        "recommendation": "TRANSFER"
    }

---

# 20. Why Transfer Suggestion Can Be Null

A transfer suggestion being null is not automatically an error.

It is expected when no suitable source warehouse exists.

Example:

    SKU0008 | WH003

If SKU0008 does not exist in another warehouse, there is nowhere to transfer stock from.

Another case:

    SKU0008 | WH003 | Low Stock
    SKU0008 | WH004 | Not Excess

In this situation WH004 cannot provide stock because it does not have enough excess inventory.

Therefore:

    transfer_suggestion = null

is valid.

---

# 21. Transfer Test Data

To test transfer logic, the same SKU must be available in multiple warehouses.

Example:

    SKU0008 | WH003 | LOW STOCK
    SKU0008 | WH004 | EXCESS STOCK

Another example:

    SKU0010 | WH002 | LOW STOCK
    SKU0010 | WH005 | EXCESS STOCK

This is required because transfer logic searches for the same SKU in another warehouse.

---

# 22. Bulk CSV Upload

The service supports uploading inventory data through CSV.

Example CSV:

    sku_id,product_name,warehouse_id,quantity_on_hand,lead_time_days,safety_stock
    SKU0001,Product 0001,WH001,120,5,30
    SKU0002,Product 0002,WH002,250,7,40
    SKU0003,Product 0003,WH003,80,4,25

The CSV does not need to manually provide average daily demand.

The service should calculate demand using SalesHistory.

Process:

    CSV Upload
        |
        v
    Read SKU
        |
        v
    Read Warehouse
        |
        v
    Find Sales History
        |
        v
    Calculate Average Daily Demand
        |
        v
    Save Inventory

---

# 23. Existing Inventory During Bulk Upload

If an inventory record already exists for the same:

    sku_id + warehouse_id

the upload operation should update the existing inventory record.

This is important because previously uploaded records may contain:

    avg_daily_demand = 0

After sales history is available, uploading/updating the inventory record should store the calculated demand.

---

# 24. Data Generation Order

For correct demand calculation, the recommended order is:

    Step 1
    Create SalesHistory

    Step 2
    Create Inventory

    Step 3
    Match SKU + Warehouse

    Step 4
    Calculate Average Daily Demand

    Step 5
    Calculate Reorder Point

    Step 6
    Run Low Stock

    Step 7
    Run Reorder Plan

    Step 8
    Test Transfer Suggestion

The important point is that SalesHistory must exist for the SKU and warehouse used by Inventory.

---

# 25. Running the Application

Go to the Inventory Service directory:

    cd services\inventory

Activate the virtual environment.

If the virtual environment is inside the inventory directory:

    .\myenv\Scripts\activate

Run FastAPI:

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

Swagger:

    http://127.0.0.1:8001/docs

---

# 26. Running Sales History Seed

From:

    services\inventory

run:

    python -m scripts.seed_sales_history

This is preferred over directly running:

    python scripts/seed_sales_history.py

because the application uses imports such as:

    from app.database import ...

Running the module from the correct project directory avoids:

    ModuleNotFoundError: No module named 'app'

---

# 27. API Endpoints

The Inventory Service exposes the following major endpoints.

## Create Inventory

    POST /api/v1/inventory/

Creates a new inventory record.

---

## Get All Inventory

    GET /api/v1/inventory/

Returns inventory records.

For large datasets, pagination or optimized queries should be considered to prevent slow responses.

---

## Get Inventory By SKU

    GET /api/v1/inventory/{sku_id}

Returns inventory for a SKU.

---

## Get Inventory By SKU and Warehouse

    GET /api/v1/inventory/{sku_id}/{warehouse_id}

Returns inventory for a specific SKU and warehouse.

---

## Update Inventory

    PUT /api/v1/inventory/{sku_id}/{warehouse_id}

Updates inventory.

---

## Delete Inventory

    DELETE /api/v1/inventory/{sku_id}/{warehouse_id}

Deletes inventory.

---

## Low Stock

    GET /api/v1/inventory/low-stock

Returns inventory items below their reorder point.

---

## Reorder Plan

    GET /api/v1/inventory/reorder-plan

Returns low-stock items with:

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

---

## Bulk Upload

    POST /api/v1/inventory/bulk-upload

Uploads inventory using CSV.

---

## Bulk Update

    PUT /api/v1/inventory/bulk-update

Updates multiple inventory records.

---

## Decrement

    POST /api/v1/inventory/decrement

Decreases inventory quantity.

Concurrency protection is applied to prevent incorrect simultaneous updates.

---

## Reorder Check

    POST /api/v1/inventory/reorder-check

Checks whether an inventory item requires replenishment.

---

## Simulate

    POST /api/v1/inventory/simulate

Simulates inventory/reorder behavior without necessarily changing stored inventory.

---

## What-If

    POST /api/v1/inventory/what-if

Used for scenario analysis.

---

# 28. PostgreSQL Data Verification

After uploading inventory, verify the database.

Check:

    sku_id
    warehouse_id
    quantity_on_hand
    avg_daily_demand
    lead_time_days
    safety_stock

The important requirement is:

    avg_daily_demand

should not remain zero when matching sales history exists.

Example expected data:

    SKU0008
    WH003
    quantity_on_hand = 90
    avg_daily_demand = 28.53
    lead_time_days = 9
    safety_stock = 40

---

# 29. Why Average Daily Demand Can Become Zero

Average daily demand can be zero when:

1. There is no SalesHistory.
2. SKU does not match.
3. Warehouse does not match.
4. Sales date is outside the selected demand window.
5. Sales quantity is actually zero.
6. Existing inventory was not updated after sales history was inserted.

Example mismatch:

    Inventory:
    SKU0008 | WH003

    SalesHistory:
    SKU0008 | WH001

These are different warehouse records.

Therefore demand for:

    SKU0008 | WH003

may be zero.

---

# 30. Concurrency

Inventory updates can happen at the same time.

Example:

    Request A:
        quantity = 100
        decrement 20

    Request B:
        quantity = 100
        decrement 30

Without proper locking, both requests may read the same original quantity.

This can cause incorrect results.

The decrement operation uses database row locking to protect the inventory row during the transaction.

Expected result:

    100 - 20 - 30 = 50

instead of an incorrect lost-update result.

---

# 31. Transaction Handling

Database operations use transactions.

If an operation succeeds:

    COMMIT

If an exception occurs:

    ROLLBACK

This prevents partially completed updates.

Bulk operations should follow the same transaction principle.

---

# 32. Test Database

Tests must not modify the production database.

A separate test database is used.

The test setup creates:

    test_engine

and overrides the FastAPI:

    get_db

dependency.

Architecture:

    Application
         |
         v
    Production Database

    Pytest
         |
         v
    Test Database

This prevents test execution from deleting or changing production inventory records.

---

# 33. Testing

The Inventory Service has been tested using Pytest.

## Test Results

Latest test execution:

    pytest -v

Result:

    19 passed
    2 warnings

All 19 test cases passed successfully.

The 2 warnings do not represent test failures.

Example:

    ===================== 19 passed, 2 warnings =====================

# 34. Test Coverage Areas

The test suite should cover:

- Inventory creation
- Inventory retrieval
- Inventory update
- Inventory deletion
- Warehouse-specific inventory
- Validation
- Low-stock calculation
- Reorder-point calculation
- Demand calculation
- ABC classification
- Safety-stock calculation
- Urgency calculation
- Reorder plan
- Transfer suggestion
- Bulk upload
- Bulk update
- Invalid input
- Database rollback
- Concurrency
- Test database isolation

---

# 35. Development Blockers

## Blocker 1: Python Version and Dependency Problems

During development there were package installation and PostgreSQL driver build issues.

The problem was related to the Python environment and package compatibility.

### Resolution

A compatible Python version was used and the virtual environment was recreated.

Dependencies were then installed again.

---

# 36. Blocker 2: `No module named app`

While running the sales-history script, the following error occurred:

    ModuleNotFoundError: No module named 'app'

### Cause

The project structure contains:

    app/
    scripts/

as separate folders.

The script imports:

    from app.database import ...

When the script was executed from the wrong directory, Python could not find the `app` package.

### Resolution

Run the command from:

    services/inventory

using:

    python -m scripts.seed_sales_history

---

# 37. Blocker 3: Sales History Contained 0 and 1 Values

The initial synthetic sales data contained values such as:

    0
    1

This was not useful for testing realistic demand calculations.

### Impact

Average daily demand became too small or zero.

This affected:

    Reorder Point
    Urgency Score
    Reorder Plan

### Resolution

Sales-history generation was changed to produce realistic positive quantities with daily variation.

---

# 38. Blocker 4: Inventory Was Empty

At one stage the Inventory table was deleted/empty.

Sales history was generated separately because the sales-history generation needed to work even when Inventory records had not yet been inserted.

The final test data approach is to generate matching sales history and then upload inventory records using matching SKU and warehouse identifiers.

---

# 39. Blocker 5: `avg_daily_demand` Was Zero in PostgreSQL

Swagger could calculate demand during a request, but PostgreSQL inventory records still showed:

    avg_daily_demand = 0

### Cause

The original bulk CSV upload created Inventory without calculating and persisting demand.

Existing inventory records were also skipped.

### Resolution

The upload flow needs to calculate demand from SalesHistory and persist it to:

    Inventory.avg_daily_demand

Existing records must also be updated rather than simply skipped.

---

# 40. Blocker 6: Reorder Plan Transfer Suggestion Was Null

Example:

    "transfer_suggestion": null

### Cause

The transfer service searches for the same SKU in another warehouse.

If only:

    SKU0008 | WH003

exists, there is no source warehouse.

### Resolution

Create test data such as:

    SKU0008 | WH003 | Low Stock
    SKU0008 | WH004 | Excess Stock

Then the service can identify:

    WH004 → WH003

as a possible transfer.

---

# 41. Blocker 7: Large Inventory Queries Were Slow

When large amounts of inventory data were loaded, the:

    GET /api/v1/inventory/

endpoint could take longer to respond.

### Cause

Returning a large number of records at once can create unnecessary database and serialization work.

Repeated demand and calculation queries can also increase processing time.

### Possible improvements

- Pagination
- Database indexes
- Batch queries
- Aggregated sales queries
- Avoid repeated ABC classification
- Avoid repeated SalesHistory queries
- Select only required columns
- Cache calculations where appropriate

---

# 42. Large Dataset Testing

For larger testing, the service can be tested with:

    1,000 inventory items

and:

    30,000 sales-history records

for:

    30 days

Calculation:

    1,000 × 30
    = 30,000 records

For 60 days:

    1,000 × 60
    = 60,000 records

This is useful for performance testing.

---

# 43. Performance Considerations

For large datasets, the following database indexes should be considered:

    sku_id

    warehouse_id

    sale_date

and especially:

    sku_id + warehouse_id

A composite index can help queries that search SalesHistory using both SKU and warehouse.

Example query pattern:

    WHERE sku_id = ?
    AND warehouse_id = ?
    AND sale_date >= ?

This is important for rolling demand calculations.

---

# 44. Potential Optimization for Reorder Plan

The reorder plan should avoid doing the same calculation repeatedly.

A naive implementation can result in:

    Inventory 1
        ↓
    Sales query

    Inventory 2
        ↓
    Sales query

    Inventory 3
        ↓
    Sales query

For thousands of inventory records, this can become expensive.

A better approach is to aggregate sales history in batches.

Conceptually:

    SalesHistory
         |
         v
    GROUP BY
        sku_id
        warehouse_id
         |
         v
    Demand Results
         |
         v
    Inventory Calculations

This reduces database round trips.

---

# 45. API Response Example

Example reorder-plan entry:

    {
        "sku_id": "SKU0008",
        "product_name": "Product 0008",
        "warehouse_id": "WH003",
        "quantity_on_hand": 90,
        "reorder_point": 304,
        "urgency_score": 7.5,
        "rolling_avg_demand": 28.53,
        "abc_tier": "B",
        "adjusted_safety_stock": 48,
        "transfer_suggestion": {
            "sku_id": "SKU0008",
            "source_warehouse": "WH004",
            "destination_warehouse": "WH003",
            "transfer_quantity": 214,
            "source_excess_quantity": 296,
            "destination_shortage_quantity": 214,
            "recommendation": "TRANSFER"
        }
    }

If no transfer source exists:

    "transfer_suggestion": null

---

# 46. End-to-End Example

Consider:

    SKU0008
    Warehouse = WH003

Sales history for 30 days:

    Total Sales = approximately 856

Average demand:

    856 / 30
    ≈ 28.53

ABC tier:

    B

Adjusted safety stock:

    48

Lead time:

    9 days

Reorder point:

    28.53 × 9 + 48
    ≈ 304

Current quantity:

    90

Low-stock check:

    90 < 304

Result:

    LOW STOCK

Shortage:

    304 - 90
    = 214

Urgency:

    214 / 28.53
    ≈ 7.5

The service then searches for another warehouse containing:

    SKU0008

If it finds:

    WH004
    Quantity > WH004 Reorder Point

then a transfer suggestion can be generated.

---

# 47. Complete Business Flow

The complete Inventory Service flow is:

    Sales History
          |
          v
    Historical Demand
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
    Compare Quantity on Hand
          |
       +--+--+
       |     |
       |     |
    Enough  Low
       |     |
       |     v
       |  Urgency Score
       |     |
       |     v
       |  Find Same SKU
       |  in Other Warehouses
       |     |
       |   +-+-+
       |   |   |
       | Excess No Excess
       |   |   |
       |   v   v
       | Transfer
       | Suggestion
       |
       v
    No Reorder


---

# 48. Test Commands

From:

    services/inventory

run:

    pytest -v

For coverage:

    pytest --cov=app --cov-report=term-missing

For the sales-history seed:

    python -m scripts.seed_sales_history

For the application:

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

Swagger:

    http://127.0.0.1:8001/docs

---

# 49. Final Verification Procedure

Before submitting the code for review:

### Step 1

Start PostgreSQL.

### Step 2

Activate the virtual environment.

### Step 3

Start FastAPI.

### Step 4

Open Swagger.

### Step 5

Verify SalesHistory.

### Step 6

Upload inventory CSV.

### Step 7

Verify PostgreSQL inventory.

Check:

    sku_id
    warehouse_id
    quantity_on_hand
    avg_daily_demand
    lead_time_days
    safety_stock

### Step 8

Run:

    GET /api/v1/inventory/low-stock

### Step 9

Run:

    GET /api/v1/inventory/reorder-plan

### Step 10

Verify:

    rolling_avg_demand > 0

    reorder_point > 0

    abc_tier is A/B/C

    urgency_score is correct

### Step 11

For transfer testing, verify:

    same SKU exists in two warehouses

and:

    destination = low stock

    source = excess stock

### Step 12

Run:

    pytest -v

### Step 13

Run:

    pytest --cov=app --cov-report=term-missing

Only after these checks should the task be marked as ready for code review.

---

# 50. Current Development Status

The Inventory Service currently covers the core requested functionality:

    Inventory CRUD                  Implemented
    PostgreSQL                      Implemented
    Warehouse support               Implemented
    Sales history                   Implemented
    Demand calculation              Implemented
    Rolling demand                  Implemented
    Automatic reorder point         Implemented
    ABC classification              Implemented
    Safety stock adjustment         Implemented
    Low-stock detection             Implemented
    Urgency score                   Implemented
    Reorder plan                    Implemented
    Transfer suggestion             Implemented
    Bulk CSV upload                 Implemented
    Bulk update                     Implemented
    Concurrency protection          Implemented
    Test database isolation         Implemented
    Automated testing               Implemented

Latest verified test status:

    19 passed
    2 warnings
    0 failed

All 19 tests passed successfully.

---

# 51. Known Limitations

## Transfer Suggestions

Transfer suggestions depend on available stock in other warehouses.

If no warehouse has excess stock, the response is:

    "transfer_suggestion": null

This is expected behavior.

## Large Data

For very large inventory datasets, returning all records from:

    GET /api/v1/inventory/

can become slow.

Pagination and optimized database queries are recommended.

## Reorder Plan Performance

The reorder plan performs multiple calculations.

For thousands of inventory records, batch demand aggregation and database indexing should be considered.

---

# 52. Future Improvements

Possible future improvements include:

1. Pagination for inventory listing.
2. Database indexes.
3. Batch sales aggregation.
4. Faster reorder-plan calculations.
5. More transfer integration tests.
6. Performance testing.
7. Load testing.
8. Structured logging.
9. Monitoring.
10. Metrics.
11. Stronger CSV validation.
12. Automated CI/CD testing.
13. Database constraints.
14. Improved error handling.
15. Caching of expensive calculations where appropriate.

---

# 53. Summary

The Inventory Service provides a data-driven inventory planning workflow.

The main purpose is to automatically determine inventory demand and replenishment requirements using sales history.

The complete process is:

    Sales History
          |
          v
    Average Daily Demand
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
    Urgency Score
          |
          v
    Reorder Plan
          |
          v
    Warehouse Transfer Suggestion

The service therefore moves inventory planning from manually maintained values toward automated, sales-history-driven calculations.

---

# 54. Developer Notes

Important commands:

    # Start service
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

    # Generate sales history
    python -m scripts.seed_sales_history

    # Run tests
    pytest -v

    # Run coverage
    pytest --cov=app --cov-report=term-missing

Swagger:

    http://127.0.0.1:8001/docs

---
