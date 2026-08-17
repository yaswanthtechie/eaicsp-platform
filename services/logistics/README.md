# Logistics Service

A FastAPI-based Logistics Service for managing shipments, carrier quotes, shipment status transitions, bulk quotations, reliability scoring, circuit breakers, consolidation suggestions, and ETA explanations.

---

# 1. Project Structure

```text
logistics/
│
├── app/
│   ├── __init__.py
│   │
│   ├── main.py
│   │
│   ├── routes/
│   │   └── shipment.py
│   │
│   ├── schemas/
│   │   └── shipment.py
│   │
│   ├── services/
│   │   └── shipment_service.py
│   │
│   └── carriers/
│       ├── __init__.py
│       ├── base.py
│       ├── dhl.py
│       ├── fedex.py
│       ├── ups.py
│       └── bluedart.py
│
├── tests/
│   ├── test_shipment.py
│   ├── test_quote_and_history.py
│   └── test_r4.py
│
├── .pytest_cache/
│
├── .coverage
│
├── README.md
│
└── requirements.txt
```

---

# 2. File Responsibilities

## `app/main.py`

Main FastAPI application.

Responsibilities:

* Create FastAPI application
* Register routes
* Start application configuration

---

## `app/routes/shipment.py`

Contains shipment API endpoints.

Responsibilities:

* Create shipment
* Get shipment
* Update shipment status
* Get quote
* Bulk quote
* Shipment history
* R4 endpoints

---

## `app/schemas/shipment.py`

Contains Pydantic models.

Responsibilities:

* Request validation
* Response validation
* Shipment models
* Status enum
* Carrier preferences

---

## `app/services/shipment_service.py`

Contains the main business logic.

Responsibilities:

* Shipment management
* Carrier selection
* Quote calculation
* Reliability calculation
* Bulk processing
* Circuit breaker
* Consolidation
* ETA explanation
* Shipment history

---

## `app/carriers/base.py`

Defines the common carrier structure/interface.

---

## `app/carriers/dhl.py`

DHL carrier implementation.

---

## `app/carriers/fedex.py`

FedEx carrier implementation.

FedEx also supports simulated temporary failures.

---

## `app/carriers/ups.py`

UPS carrier implementation.

---

## `app/carriers/bluedart.py`

BlueDart carrier implementation.

---

## `tests/test_shipment.py`

Tests basic shipment functionality.

---

## `tests/test_quote_and_history.py`

Tests:

* Carrier quotes
* Carrier selection
* Shipment history
* Quote functionality

---

## `tests/test_r4.py`

Tests R4 functionality:

* Bulk quote
* Async processing
* Reliability scoring
* Circuit breaker
* Consolidation
* ETA explanation
* Concurrent carrier failures
* Status transition edge cases
* Two-of-three carrier failures

---

# 3. Technology Stack

| Technology     | Purpose                     |
| -------------- | --------------------------- |
| Python         | Programming language        |
| FastAPI        | REST API framework          |
| Pydantic       | Request/response validation |
| Uvicorn        | ASGI server                 |
| AsyncIO        | Asynchronous processing     |
| HTTPX          | HTTP client                 |
| Pytest         | Testing                     |
| Pytest-Asyncio | Async tests                 |
| Tenacity       | Retry mechanism             |
---

# 4. Project Overview

The Logistics Service is responsible for handling shipment-related operations.

It provides APIs to:

* Create shipments
* Get shipment details
* Update shipment status
* Get carrier quotes
* Get bulk quotes for multiple shipments
* Compare carrier prices and delivery times
* Track carrier reliability
* Handle carrier failures
* Protect the service using circuit breakers
* Suggest shipment consolidation
* Explain ETA calculations
* Maintain shipment history

---

# 5. R1 - Basic Shipment Management

The first version provides:

* Shipment creation
* Shipment retrieval
* Shipment status management
* Shipment history
* Shipment data validation
* Valid status transitions

---

# 6. R2 - Carrier Quoting

The service supports multiple carriers.

Current carriers:

* DHL
* FedEx
* UPS
* BlueDart

The service can calculate:

* Shipping price
* Delivery time
* Carrier reliability
* Recommended carrier

---

# 7. R3 - Advanced Carrier Handling

R3 introduced:

* Carrier integration
* Carrier selection preferences
* Retry mechanism
* Carrier failure handling
* Quote APIs
* Bulk quote support
* Shipment history
* Circuit breaker foundation

---

# 8. R4 Features

R4 extends the Logistics Service with advanced functionality.

Main R4 features:

1. Real async batch quoting
2. Dynamic reliability scoring
3. Carrier failure handling
4. Independent circuit breakers
5. Consolidation suggestions
6. ETA explanation
7. Advanced R4 testing

---

# 9. R4.1 - Real Async Batch Quoting

Endpoint:

```http
POST /api/v1/shipments/bulk-quote
```

The API accepts multiple shipments in one request.

R4 requirement:

```text
20 shipments
```

Instead of processing every shipment one by one, carrier requests are executed concurrently using:

```python
asyncio.gather()
```

This improves performance.

### Sequential Processing

```text
Shipment 1 → Carrier
     ↓
Shipment 2 → Carrier
     ↓
Shipment 3 → Carrier
     ↓
Shipment 4 → Carrier
```

Each request waits for the previous request.

### Async Processing

```text
Shipment 1 ─┐
Shipment 2 ─┤
Shipment 3 ─┤──> asyncio.gather()
Shipment 4 ─┘
```

Multiple requests can run concurrently.

---

# 10. Speedup Measurement

R4 measures the difference between sequential and asynchronous processing.

Example:

```text
Sequential time : 4.80 seconds
Async time      : 1.60 seconds
Speedup          : 3.00x
```

The actual values depend on the simulated carrier response times.

The performance information is logged and returned as part of the bulk quote processing.

---

# 11. Dynamic Reliability Scoring

R4 tracks the actual simulated performance of carriers.

Example:

```text
DHL

Total shipments     : 100
On-time deliveries  : 92
Delayed deliveries  : 8

Reliability = 92 / 100
            = 0.92
```

Another example:

```text
FedEx

Total shipments     : 100
On-time deliveries  : 88
Delayed deliveries  : 12

Reliability = 88 / 100
            = 0.88
```

The reliability score is based on simulated shipment history.

---

# 12. Reliability Formula

```text
Reliability Score =
On-Time Deliveries / Total Deliveries
```

Example:

```text
On-time deliveries = 95
Total deliveries   = 100

Reliability = 95 / 100
             = 0.95
```

Higher score means better historical performance.

---

# 13. Carrier Preferences

The service supports:

* Cheapest
* Fastest
* Most Reliable

---

## Cheapest

Select the carrier with the lowest price.

Example:

```text
DHL      = ₹850
FedEx    = ₹950
UPS      = ₹900
BlueDart = ₹750
```

Selected:

```text
BlueDart
```

---

## Fastest

Select the carrier with the shortest delivery time.

Example:

```text
DHL      = 2 days
FedEx    = 3 days
UPS      = 4 days
BlueDart = 2 days
```

The service selects the fastest available option based on quote information.

---

## Most Reliable

Select the carrier with the highest reliability score.

Example:

```text
DHL      = 0.87
FedEx    = 0.92
UPS      = 0.95
BlueDart = 0.90
```

Selected:

```text
UPS
```

---

# 14. Mock Carrier Rates

The project uses simulated carrier information.

| Carrier  | Base Price | Delivery Days | Initial Reliability |
| -------- | ---------: | ------------: | ------------------: |
| DHL      |       ₹850 |             2 |                0.87 |
| FedEx    |       ₹950 |             3 |                0.92 |
| UPS      |       ₹900 |             4 |                0.95 |
| BlueDart |       ₹750 |             2 |                0.90 |

These values are used for development, simulation, and testing.

---

# 15. Carrier Failure Simulation

The project simulates carrier failures to test failure-handling logic.

For example:

```text
FedEx unavailable
```

The system should not stop the entire quotation process when one carrier fails.

Example:

```text
DHL      → Available
FedEx    → Failed
UPS      → Available
BlueDart → Available
```

The available carriers can continue processing.

---

# 16. Retry Mechanism

The project uses Tenacity for retry handling.

Example retry pattern:

```text
Attempt 1
   ↓
Wait 1 second
   ↓
Attempt 2
   ↓
Wait 2 seconds
   ↓
Attempt 3
   ↓
Success / Failure
```

Maximum attempts:

```text
3
```

Exponential wait:

```text
1 second
2 seconds
4 seconds
```

Retry helps recover from temporary failures.

---

# 17. Circuit Breaker

R4 includes a local circuit breaker.

The circuit breaker prevents repeated requests to a carrier that is continuously failing.

Each carrier has an independent circuit breaker.

---

# 18. Circuit Breaker States

## CLOSED

Normal operation.

```text
Request
   ↓
Circuit Breaker
   ↓
Carrier
   ↓
Success
```

---

## OPEN

Carrier has failed repeatedly.

```text
Request
   ↓
Circuit Breaker
   ↓
Carrier blocked
```

The service temporarily stops sending requests to that carrier.

---

## HALF-OPEN

After the recovery period, the service allows a test request.

```text
OPEN
 ↓
Recovery period
 ↓
HALF-OPEN
 ↓
Test request
```

If successful:

```text
HALF-OPEN → CLOSED
```

If failed:

```text
HALF-OPEN → OPEN
```

---

# 19. Independent Circuit Breakers

Each carrier has its own circuit breaker.

Example:

```text
DHL      → CLOSED
FedEx    → OPEN
UPS      → CLOSED
BlueDart → CLOSED
```

If FedEx fails, it should not disable DHL, UPS, or BlueDart.

---

# 20. Circuit Breaker Reset

The service supports:

```python
reset_circuit_breaker(carrier)
```

and:

```python
reset_all_circuit_breakers()
```

These are useful during testing and recovery.

---

# 21. Consolidation Suggestions

R4 supports shipment consolidation.

If two or more shipments:

* Have the same destination
* Are scheduled within 2 days

the service can suggest combining them.

Example:

```text
Shipment 101
Destination: Hyderabad
Date: 15-Aug

Shipment 102
Destination: Hyderabad
Date: 16-Aug
```

Result:

```text
Consolidation possible
```

---

# 22. Why Consolidation Is Useful

Consolidation can help reduce:

* Shipping cost
* Number of trips
* Carrier usage
* Operational overhead

Example:

```text
Shipment A → Hyderabad
Shipment B → Hyderabad
Shipment C → Hyderabad
```

Instead of three separate shipments, the system can suggest one consolidated shipment when the business rules allow it.

---

# 23. ETA Explanation

R4 includes ETA explanation functionality.

The purpose is to explain why a shipment has a particular estimated delivery time.

Example:

```text
Base transit time : 2 days
Carrier delay     : 1 day
Current status    : delayed

Estimated ETA = 3 days
```

An ETA explanation can contain:

* Carrier
* Base transit time
* Delay information
* Current shipment status
* Estimated delivery time

Example:

```text
ETA Explanation

Carrier: DHL
Base transit time: 2 days
Current status: delayed
Additional delay: 1 day
Estimated delivery: 3 days
```

---

# 24. Shipment Statuses

The service supports:

```text
pending
in_transit
delivered
delayed
cancelled
```

---

# 25. Valid Status Transitions

Allowed transitions:

```text
pending
   ↓
in_transit
   ↓
delivered
```

or:

```text
in_transit
   ↓
delayed
   ↓
in_transit
   ↓
delivered
```

Main rules:

```text
pending     → in_transit
in_transit  → delayed
in_transit  → delivered
delayed     → in_transit
delayed     → delivered
```

Invalid transitions should return an error.

---

# 26. API Endpoints

Base URL:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## Create Shipment

```http
POST /api/v1/shipments
```

Creates a new shipment.

Example:

```json
{
  "origin": "Hyderabad",
  "destination": "Bangalore",
  "weight": 10,
  "preference": "cheapest"
}
```

---

## Get Shipment

```http
GET /api/v1/shipments/{shipment_id}
```

Returns shipment details.

---

## Update Shipment Status

```http
PATCH /api/v1/shipments/{shipment_id}/status
```

Updates shipment status after validating the transition.

---

## Get Shipment History

```http
GET /api/v1/shipments/{shipment_id}/history
```

Returns shipment status history.

---

## Get Quote

```http
POST /api/v1/shipments/quote
```

Example response:

```json
{
  "carrier": "BlueDart",
  "price": 750,
  "delivery_days": 2,
  "reliability_score": 0.90
}
```

---

# 27. Bulk Quote API

Endpoint:

```http
POST /api/v1/shipments/bulk-quote
```

Purpose:

Process multiple shipment quote requests in one API call.

R4 requirement:

```text
20 shipments
```

The service processes carrier requests concurrently.

Example request:

```json
{
  "shipments": [
    {
      "origin": "Hyderabad",
      "destination": "Bangalore",
      "weight": 5
    },
    {
      "origin": "Hyderabad",
      "destination": "Chennai",
      "weight": 8
    }
  ]
}
```

Example response structure:

```json
{
  "quotes": [],
  "performance": {
    "sequential_time": 4.8,
    "async_time": 1.6,
    "speedup": 3.0
  }
}
```

---

# 28. Bulk Quote Processing Flow

```text
Client
  ↓
Bulk Quote API
  ↓
Validate shipments
  ↓
Create async tasks
  ↓
asyncio.gather()
  ↓
Query carriers concurrently
  ↓
Collect successful quotes
  ↓
Calculate performance
  ↓
Return response
```

---

# 29. Shipment History

Shipment status changes can be recorded.

Example:

```text
Shipment 101

pending
   ↓
in_transit
   ↓
delayed
   ↓
in_transit
   ↓
delivered
```

History helps track the shipment lifecycle.

---

# 30. Installing the Project

Open PowerShell.

Go to the Logistics Service folder:

```powershell
cd "C:\Users\Sowmya\OneDrive\Desktop\logistical service\eaicsp-platform\services\logistics"
```

---

# 31. Create Virtual Environment

Python 3.13 is recommended.

```powershell
py -3.13 -m venv venv
```

---

# 32. Activate Virtual Environment

PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

After activation:

```text
(venv)
```

should appear in the terminal.

---

# 33. If PowerShell Blocks Activation

Run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then:

```powershell
.\venv\Scripts\Activate.ps1
```

---

# 34. Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install project dependencies:

```powershell
pip install -r requirements.txt
```

---

# 35. Requirements

```text
fastapi==0.139.0
uvicorn[standard]==0.35.0
pydantic==2.11.7
tenacity==8.2.0
pytest==8.4.1
pytest-asyncio==1.1.0
httpx
```

---

# 36. Run the Application

From the Logistics Service directory:

```powershell
uvicorn app.main:app --reload
```

---

# 37. Open Swagger

Open:

```text
http://127.0.0.1:8000/docs
```

Swagger provides an interactive API testing interface.

---

# 38. Test Using Swagger

```text
1. Start server
2. Open /docs
3. Select API
4. Click Try it out
5. Enter request data
6. Click Execute
7. Check response
```

---

# 39. Run Tests

Use:

```powershell
python -m pytest -q
```

This is preferred because it ensures pytest runs from the active Python environment.

---

# 40. Run R4 Tests

```powershell
python -m pytest tests/test_r4.py -q
```

---

# 41. Run Individual Test Files

```powershell
python -m pytest tests/test_shipment.py -q
```

```powershell
python -m pytest tests/test_quote_and_history.py -q
```

---

# 42. Coverage

Run:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

If coverage is not installed:

```powershell
pip install coverage pytest-cov
```

Then:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

---

# 43. Git Commands

Check status:

```powershell
git status
```

Add files:

```powershell
git add .
```

Commit:

```powershell
git commit -m "Complete logistics R4 implementation"
```

Push:

```powershell
git push
```

---

# 44. GitHub Branch

Example:

```text
sowmya/round3-logistics
```

For R4, a branch can be:

```text
sowmya/round4-logistics
```

---

# 45. Complete R4 Flow

```text
Client
  |
  v
FastAPI
  |
  +----------------------+
  |                      |
  v                      v
Shipment API          Bulk Quote API
                           |
                           v
                    asyncio.gather()
                           |
              +------------+------------+
              |            |            |
              v            v            v
             DHL         FedEx         UPS
              |            |            |
              +------------+------------+
                           |
                           v
                   Quote Collection
                           |
              +------------+------------+
              |            |            |
              v            v            v
          Reliability   Circuit      Performance
            Score       Breaker        Metric
                           |
                           v
                     Final Response
```

---

# 46. R4 Architecture

```text
                    Logistics Service
                           |
             +-------------+-------------+
             |                           |
             v                           v
       Shipment Routes              Quote Routes
             |                           |
             v                           v
      Shipment Service           Async Bulk Service
             |                           |
             |                    asyncio.gather()
             |                           |
             +-------------+-------------+
                           |
                           v
                    Carrier Services
                           |
        +------------------+------------------+
        |          |          |              |
        v          v          v              v
       DHL       FedEx       UPS          BlueDart
        |          |          |              |
        +----------+----------+--------------+
                           |
                           v
                  Reliability Tracking
                           |
                           v
                    Circuit Breakers
```

---

# 47. Business Benefits

## Faster Processing

Async bulk quoting processes multiple requests concurrently.

## Better Carrier Selection

Users can select carriers based on:

* Price
* Delivery speed
* Reliability

## Better Failure Handling

Retries and circuit breakers prevent temporary carrier failures from affecting the complete system.

## Better Reliability

Actual simulated shipment history is used to calculate carrier reliability.

## Cost Optimization

Consolidation suggestions can reduce shipping costs.

## Better Visibility

Shipment history and ETA explanations provide better tracking information.

---

# 48. Adapter vs Local Carrier Approach

The project initially used a carrier adapter approach.

### Adapter Approach

```text
Logistics Service
       |
       v
Adapter Interface
   |    |    |
   v    v    v
 DHL  FedEx UPS
```

### Local Carrier Approach

```text
Logistics Service
       |
       +------ Local Carrier 1
       |
       +------ Local Carrier 2
       |
       +------ Local Carrier 3
```

The adapter approach provides a common interface between the application and different carrier integrations.

A local-carrier approach is simpler when the application is designed around a fixed set of local carriers.

---

# 49. Local Carrier Concept

Examples of Indian logistics providers include:

* Blue Dart
* Delhivery
* Ecom Express
* XpressBees
* DTDC

The current project uses mock carrier implementations for development and testing.

---

# 50. Why Carrier Failures Happen

Real carrier failures can happen because of:

* Network problems
* API timeout
* Server overload
* Maintenance
* Rate limits
* Authentication problems
* Service outages
* Invalid request data
* Temporary connectivity issues

The project simulates these situations for testing.

---

# 51. Example Complete Scenario

Customer creates:

```text
Origin:
Hyderabad

Destination:
Bangalore

Weight:
10 kg

Preference:
most_reliable
```

Carrier quotes:

```text
DHL
Price: ₹850
Days: 2
Reliability: 0.87

FedEx
Price: ₹950
Days: 3
Reliability: 0.92

UPS
Price: ₹900
Days: 4
Reliability: 0.95

BlueDart
Price: ₹750
Days: 2
Reliability: 0.90
```

For:

```text
most_reliable
```

the system selects:

```text
UPS
```

because UPS has the highest reliability score.

---

# 52. Example Cheapest Scenario

Preference:

```text
cheapest
```

Carrier prices:

```text
DHL      ₹850
FedEx    ₹950
UPS      ₹900
BlueDart ₹750
```

Selected:

```text
BlueDart
```

---

# 53. Example Failure Scenario

Suppose:

```text
FedEx → unavailable
```

The system continues:

```text
DHL      → Quote available
FedEx    → Failed
UPS      → Quote available
BlueDart → Quote available
```

---

# 54. Example Circuit Breaker Scenario

Suppose FedEx continuously fails:

```text
Failure 1
Failure 2
Failure 3
Failure 4
...
```

Circuit breaker:

```text
FedEx → OPEN
```

Other carriers continue:

```text
DHL      → Working
UPS      → Working
BlueDart → Working
```

---

# 55. Example Consolidation Scenario

```text
Shipment 1
Destination: Chennai
Date: 15-Aug

Shipment 2
Destination: Chennai
Date: 16-Aug
```

The service detects:

```text
Same destination
Date difference <= 2 days
```

Result:

```text
Consolidation suggestion available
```

---

# 56. Example ETA Explanation

```text
Shipment ID: 200

Carrier: DHL
Base transit time: 2 days
Current status: delayed
Additional delay: 1 day

Final ETA:
3 days
```

---

# 57. R4 Requirements Checklist

```text
[x] Async batch quoting
[x] POST /shipments/bulk-quote
[x] Support 20 shipments
[x] asyncio.gather()
[x] Sequential vs async performance measurement
[x] Speedup logging
[x] Dynamic reliability scoring
[x] Simulated on-time history
[x] Consolidation suggestions
[x] Same destination rule
[x] Two-day consolidation window
[x] Local circuit breaker
[x] Independent carrier circuit breakers
[x] Circuit breaker reset
[x] Concurrent carrier failure handling
[x] Status transition edge-case testing
[x] Two-of-three carrier failure testing
[x] ETA explanation
[x] R4 tests
[x] Documentation
```

---

# 58. Known Blockers / Issues
## Blocker 1- Carrier Unavailable

Example:

```text
FedEx unavailable
```

This may be an intentional simulated failure.

The system should continue using available carriers.

---

## Blocker 2- Bulk Quote Response Format

R4 bulk quote response should contain:

```text
quotes
performance
```

Example:

```json
{
  "quotes": [],
  "performance": {
    "sequential_time": 4.8,
    "async_time": 1.6,
    "speedup": 3.0
  }
}
```

---

## Blocker 3 - Circuit Breaker Reset Functions

R4 tests may require:

```python
reset_circuit_breaker(carrier)
```

and:

```python
reset_all_circuit_breakers()
```

---

## Blocker 4 - Consolidation Function

R4 tests may require:

```python
get_consolidation_suggestions()
```

The function identifies shipments with:

```text
Same destination
+
Dates within 2 days
```

---

# 59. Simple Client Explanation

> This Logistics Service manages shipment operations and selects the best available carrier based on price, delivery speed, or reliability. In R4, we improved the system to process multiple shipment quotes asynchronously, track real carrier performance, handle carrier failures using independent circuit breakers, suggest shipment consolidation, and provide ETA explanations.

---

# 60. Simple R4 Explanation

R4 mainly focuses on:

```text
Performance
Reliability
Failure Handling
Optimization
```

### Performance

```text
asyncio.gather()
```

processes multiple carrier requests concurrently.

### Reliability

Carrier reliability is calculated from simulated delivery history.

### Failure Handling

Circuit breakers isolate failing carriers.

### Optimization

Consolidation suggestions can reduce unnecessary shipments.

### Visibility

ETA explanation helps understand delivery estimates.

---

# 61. Expected Result

After completing R4, the service should be able to:

```text
Create shipments
       ↓
Generate quotes
       ↓
Compare carriers
       ↓
Track reliability
       ↓
Process bulk quotes asynchronously
       ↓
Handle carrier failures
       ↓
Open/close circuit breakers
       ↓
Suggest consolidation
       ↓
Explain ETA
       ↓
Track shipment history
```

---

# 62. Final Run Commands

Activate environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run server:

```powershell
uvicorn app.main:app --reload
```

Run all tests:

```powershell
python -m pytest -q
```

Run R4 tests:

```powershell
python -m pytest tests/test_r4.py -q
```

Run coverage:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 63. Final Project Summary

The Logistics Service is a FastAPI microservice designed to manage shipment operations and carrier selection.

The project evolved through:

```text
R1
Basic shipment management
        ↓
R2
Carrier quotes and selection
        ↓
R3
Advanced carrier handling and retries
        ↓
R4
Async bulk quoting
Dynamic reliability
Circuit breaker
Consolidation
ETA explanation
Advanced testing
```




