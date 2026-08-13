# Logistics Service

## Project Overview

The Logistics Service is a FastAPI-based application that manages shipments, carrier quotes, shipment tracking, shipment history, retry and backoff, bulk quote processing, dynamic reliability scoring, shipment consolidation, circuit breaker handling, and ETA explanation.

The service is designed to continue processing shipments even when one or more carriers are temporarily unavailable.

---

# Technologies Used

* Python 3.13
* FastAPI
* Pydantic
* Asyncio
* Pytest
* Tenacity
* HTTPX
* Coverage
* Adapter Pattern

---

# Project Structure

```text
logistics/
│
├── app/
│   ├── main.py
│   │
│   ├── routes/
│   │   └── shipment.py
│   │
│   ├── schemas/
│   │   └── shipment.py
│   │
│   ├── services/
│   │   ├── shipment_service.py
│   │   │
│   │   └── carriers/
│   │       ├── base.py
│   │       ├── dhl.py
│   │       ├── fedex.py
│   │       ├── ups.py
│   │       └── bluedart.py
│   │
│   └── core/
│       └── config.py
│
├── tests/
│   ├── test_carriers.py
│   ├── test_quote_and_history.py
│   └── test_r4.py
│
├── requirements.txt
├── README.md
└── .coverage
```

---

# Supported Carriers

The service currently supports:

* DHL
* FedEx
* UPS
* BlueDart

The carrier implementations use the Adapter Pattern so different carrier implementations can be handled through a common interface.

---

# Shipment Management

## Shipment CRUD

### Endpoints

```text
POST   /api/v1/shipments
GET    /api/v1/shipments
GET    /api/v1/shipments/{id}
PUT    /api/v1/shipments/{id}
DELETE /api/v1/shipments/{id}
```

### Create Shipment Example

```json
{
  "shipment_id": 1,
  "origin": "Hyderabad",
  "destination": "Mumbai",
  "carrier": "dhl",
  "status": "pending",
  "weight_kg": 10
}
```

---

# Shipment Status

Supported statuses:

```text
pending
in_transit
delivered
delayed
cancelled
```

---

# Status Transition Rules

## Allowed

```text
pending → in_transit

in_transit → delayed
in_transit → delivered

delayed → in_transit
delayed → delivered
```

## Not Allowed

```text
delivered → pending
delivered → in_transit
cancelled → delivered
```

Invalid transitions return a validation error.

---

#  Quote and Tracking

## Quote API

### Endpoint

```text
POST /api/v1/shipments/quote
```

### Preferences

```text
cheapest
fastest
most_reliable
```

---

## Cheapest Quote

Selects the carrier with the lowest price.

Example:

```text
BlueDart = ₹750
DHL      = ₹850
UPS      = ₹900

Selected = BlueDart
```

---

## Fastest Quote

Selects the carrier with the lowest estimated delivery time.

Example:

```text
BlueDart = 2 days
DHL      = 2 days
UPS      = 4 days
```

---

## Most Reliable Quote

Selects the carrier with the highest reliability score.

The reliability score is dynamically calculated in R4.

---

# Carrier Rate Example

```text
DHL
Price: ₹850
Estimated Days: 2

FedEx
Price: ₹950
Estimated Days: 3

UPS
Price: ₹900
Estimated Days: 4

BlueDart
Price: ₹750
Estimated Days: 2
```

---

# Quote Output

```json
{
  "rates": [
    {
      "carrier": "bluedart",
      "price": 750,
      "estimated_days": 2
    },
    {
      "carrier": "dhl",
      "price": 850,
      "estimated_days": 2
    }
  ]
}
```

---

# Tracking API

### Endpoint

```text
GET /api/v1/shipments/{id}/tracking
```

### Example Output

```json
{
  "tracking_number": "1",
  "carrier": "dhl",
  "status": "in_transit",
  "location": "In Transit"
}
```

---

#  Retry and Shipment History

## Retry Logic

Carrier requests use Tenacity retry logic.

### Retry Attempts

```text
3 attempts
```

### Backoff

```text
1 second
2 seconds
4 seconds
```

### Purpose

* Handle temporary carrier failures
* Handle timeout problems
* Improve reliability
* Give failed carrier requests another chance

---

# Retry Flow

```text
Carrier Request
      |
      v
   Failure?
    /   \
  Yes    No
   |      |
 Retry   Success
   |
 Retry 2
   |
 Retry 3
   |
Final Failure
```

---

# FedEx Failure Simulation

FedEx can randomly simulate a carrier failure.

Example:

```python
if random.random() < 0.3:
    raise CarrierError()
```

Purpose:

* Test retry logic
* Test failure handling
* Test warnings
* Test circuit breaker

---

# Shipment History

### Endpoint

```text
GET /api/v1/shipments/{id}/history
```

History stores:

* Status
* Timestamp
* Location

### Example

```json
[
  {
    "status": "pending",
    "location": "Hyderabad"
  },
  {
    "status": "in_transit",
    "location": "In Transit"
  }
]
```

---

#  Advanced Logistics Features

R4 focuses on:

* Performance
* Concurrent processing
* Dynamic reliability
* Consolidation
* Circuit breaker
* Carrier failure handling
* ETA explanation

---

# Async Bulk Quote

### Endpoint

```text
POST /api/v1/shipments/bulk-quote
```

The endpoint supports:

```text
20 shipments
```

The quote requests are processed concurrently using:

```python
asyncio.gather()
```

---

## Sequential Processing

Without async processing:

```text
Shipment 1 → Quote
Shipment 2 → Quote
Shipment 3 → Quote
Shipment 4 → Quote
...
Shipment 20 → Quote
```

Each operation waits for the previous operation.

---

## Parallel Processing

With `asyncio.gather()`:

```text
Shipment 1 ─┐
Shipment 2 ─┤
Shipment 3 ─┤
Shipment 4 ─┤
Shipment 5 ─┤
     ...    ├──→ asyncio.gather()
Shipment 20 ┘
```

Multiple requests can execute concurrently.

---

## Example Output

```json
{
  "quotes": 20,
  "shipment_count": 20,
  "parallel_time": 0.50,
  "sequential_time": 2.10,
  "speedup": 4.20
}
```

---

## Benefits

* Faster quote processing
* Better performance
* Concurrent carrier requests
* Suitable for multiple shipments

---

# R4.2 - Dynamic Reliability Score

Previously the reliability score was static.

Example:

```python
reliability_score = 0.95
```

This does not represent actual carrier performance.

---

## New Reliability Formula

```text
Reliability Score =
On-Time Deliveries / Total Deliveries
```

---

## Example

```text
On-Time Deliveries = 8
Total Deliveries   = 10

Reliability Score = 8 / 10

Reliability Score = 0.80
```

---

## Benefits

* Uses actual carrier history
* More realistic reliability
* Better carrier ranking
* Improves `most_reliable` selection

---

# Shipment Consolidation

The service checks whether shipments can be combined.

## Rule

Consolidation is suggested when:

```text
2 or more shipments
AND
Same destination
AND
Within 2 days
```

---

## Example

```text
Shipment 1
Destination: Mumbai
Date: 15-Aug

Shipment 2
Destination: Mumbai
Date: 16-Aug
```

Suggestion:

```text
Combine shipments to save cost
```

---

## Example Output

```json
{
  "destination": "Mumbai",
  "message": "Combine shipments to save cost"
}
```

---

## Benefits

* Reduced transportation cost
* Better vehicle utilization
* Fewer individual shipments
* Improved logistics efficiency

---

# Circuit Breaker

The circuit breaker prevents continuous requests to a carrier that is repeatedly failing.

---

## Circuit States

```text
CLOSED
   |
   | repeated failures
   v
OPEN
```

---

## Example

```text
DHL Request 1 → Failure
DHL Request 2 → Failure
DHL Request 3 → Failure

Circuit → OPEN
```

When the circuit is open, additional requests to that carrier are prevented.

---

## Example Warning

```json
{
  "warning": "DHL circuit is OPEN"
}
```

---

## Benefits

* Prevents repeated calls to failed carriers
* Reduces unnecessary retries
* Improves response time
* Protects the application
* Improves system stability

---

# Circuit Breaker Testing

Circuit breaker tests cover:

```text
Carrier available
Carrier fails once
Carrier fails multiple times
Circuit opens
Circuit reset
Multiple carriers failing
```

Testing helper functions:

```python
reset_circuit_breaker()
reset_all_circuit_breakers()
```

These functions make sure circuit state does not leak from one test to another.

---

# ETA Explain

### Endpoint

```text
GET /api/v1/shipments/{id}/eta-explain
```

The endpoint explains why the shipment has a particular ETA.

---

## Example Output

```json
{
  "shipment_id": 1,
  "carrier": "dhl",
  "estimated_days": 2,
  "reason": [
    "Carrier baseline 2 days",
    "Normal weather",
    "Medium distance"
  ]
}
```

---

## Benefits

* Easy to understand ETA
* Better transparency
* Helps users understand delivery estimation
* Useful for debugging ETA decisions

---

# Carrier Failure Handling

The system is designed to continue processing when one or more carriers fail.

---

# Scenario 1 - One Carrier Down

```text
DHL      → DOWN
FedEx    → UP
UPS      → UP
BlueDart → UP
```

Expected:

```text
DHL warning returned

FedEx quote available
UPS quote available
BlueDart quote available
```

The entire quote operation should not fail because one carrier is unavailable.

---

# Scenario 2 - Two Carriers Down

```text
DHL      → DOWN
FedEx    → DOWN
UPS      → UP
BlueDart → UP
```

Expected:

```text
DHL unavailable
FedEx unavailable

UPS quote available
BlueDart quote available
```

---

# Scenario 3 - All Carriers Available

```text
DHL      → UP
FedEx    → UP
UPS      → UP
BlueDart → UP
```

Expected:

```text
All carrier quotes returned
No carrier failure warnings
```

---

# Concurrent Carrier Failure Test

Example:

```text
DHL      → DOWN
FedEx    → DOWN
UPS      → UP
BlueDart → UP
```

Expected:

```json
[
  "DHL unavailable",
  "FedEx unavailable"
]
```

while successful carriers continue returning quotes.

---

# Adapter Pattern

The carrier implementations use a common interface.

```text
                 Carrier Interface
                        |
          +-------------+-------------+
          |             |             |
         DHL          FedEx          UPS
                                      |
                                   BlueDart
```

The application can communicate with all carriers through a common interface.

---

# Testing

Run all tests using:

```powershell
python -m pytest -q
```

---

# Shipment Tests

Tests include:

* Create shipment
* Get shipment
* Update shipment
* Delete shipment
* Status validation
* Invalid status transitions

---

# Quote Tests

Tests include:

* Cheapest quote
* Fastest quote
* Most reliable quote
* Carrier failure handling
* Multiple carrier failures

---

# History Tests

Tests include:

* History creation
* Status event creation
* Event ordering
* Tracking history

---

# Tests

Tests include:

* Bulk quote
* Async execution
* Parallel speedup
* Dynamic reliability
* Consolidation suggestion
* Circuit breaker
* Circuit breaker reset
* Carrier failure handling
* Two-carrier failure
* Transition edge cases
* ETA explanation

---

# Important Test Scenarios

## Bulk Quote Test

```text
20 shipments
      |
      v
asyncio.gather()
      |
      v
Concurrent processing
      |
      v
Bulk quote result
```

---

## Two Carrier Failure Test

```text
DHL      → DOWN
FedEx    → DOWN
UPS      → UP
BlueDart → UP
```

Expected:

```text
Warnings for DHL and FedEx

Quotes from UPS and BlueDart
```

---

## Invalid Transition Test

Example:

```text
delivered → pending
```

Expected:

```text
Validation Error
```

---

## Circuit Breaker Test

```text
Failure
Failure
Failure
   |
   v
Circuit OPEN
```

Expected:

```text
Further calls are blocked
```

---

# Blockers Faced

# Blocker 1 - Circuit Breaker Test Failure

### Problem

The circuit breaker state remained open between tests.

One test could affect another test.

### Cause

The circuit breaker stores state.

### Fix

Added reset helper functions:

```python
reset_circuit_breaker()
reset_all_circuit_breakers()
```

This allows tests to start with a clean circuit state.

---

# Blocker 2 - Reliability Score Test Failure

### Problem

The reliability calculation expected a dictionary but sometimes received a boolean.

Example:

```python
True
```

instead of:

```python
{
    "on_time": True
}
```

This produced an error similar to:

```text
bool object has no attribute get
```

### Fix

The implementation was changed to handle both:

```text
True
False
```

and:

```python
{
    "on_time": True
}
```

This made reliability calculation more robust.

---

# Blocker 3 - FedEx Warning Name

### Problem

Expected:

```text
FedEx unavailable
```

but received:

```text
Fedex unavailable
```

### Cause

The carrier name was generated using normal capitalization.

### Fix

Added custom carrier display names:

```text
DHL
FedEx
UPS
BlueDart
```

This keeps carrier names consistent in warnings and API responses.

---

# Blocker 4 - Multiple Carrier Failures

### Problem

When multiple carriers fail during async processing, one exception should not stop all other carrier requests.

Example:

```text
DHL      → Failure
FedEx    → Failure
UPS      → Success
BlueDart → Success
```

### Expected

```text
DHL warning
FedEx warning

UPS quote
BlueDart quote
```

The bulk quote processing must handle each carrier failure independently.

---

# Environment Setup

## Create Virtual Environment

Use Python 3.13:

```powershell
py -3.13 -m venv venv
```

---

## Activate Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

After activation:

```text
(venv) PS C:\Users\Sowmya\OneDrive\Desktop\logistical service\eaicsp-platform\services\logistics>
```

---

## Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

---

# Run Application

Start the FastAPI server:

```powershell
python -m uvicorn app.main:app --reload
```

---

# Swagger Documentation

After starting the server, open:

```text
http://127.0.0.1:8000/docs
```

Swagger can be used to test all API endpoints.

---

# Run Tests

```powershell
python -m pytest -q
```

---

# Run Coverage

```powershell
coverage run -m pytest
```

Then:

```powershell
coverage report
```

---

# Git Branch

Current R4 development branch:

```text
sowmya/round3-logistics
```

---

# R1 Completion

```text
✓ Shipment CRUD
✓ Shipment status
✓ Status transition validation
```

---

# R2 Completion

```text
✓ Quote API
✓ Cheapest quote
✓ Fastest quote
✓ Most reliable quote
✓ Tracking API
```

---

# R3 Completion

```text
✓ Retry logic
✓ Tenacity retry
✓ Exponential backoff
✓ Shipment history
✓ FedEx failure simulation
```

---

# R4 Completion

```text
✓ Async bulk quote
✓ 20 shipment support
✓ asyncio.gather()
✓ Parallel speedup measurement
✓ Dynamic reliability score
✓ Consolidation suggestion
✓ Circuit breaker
✓ Circuit breaker reset
✓ Concurrent carrier failure handling
✓ Two-carrier failure handling
✓ Transition edge-case testing
✓ ETA explain endpoint
```

---

# Current Status

The project has reached the main R4 implementation and testing stage.

The completed flow is:

```text
R1
Shipment Management
      ↓
R2
Quotes + Tracking
      ↓
R3
Retry + History
      ↓
R4
Async Bulk Quote
      ↓
Dynamic Reliability
      ↓
Consolidation
      ↓
Circuit Breaker
      ↓
Carrier Failure Handling
      ↓
ETA Explanation
```

# Final Testing Checklist

```text
[ ] Virtual environment created
[ ] Virtual environment activated
[ ] Requirements installed
[ ] FastAPI server starts
[ ] Swagger opens
[ ] Shipment CRUD works
[ ] Quote API works
[ ] Tracking works
[ ] Shipment history works
[ ] Retry works
[ ] Bulk quote accepts 20 shipments
[ ] asyncio.gather() is used
[ ] Parallel execution works
[ ] Speedup is measured
[ ] Dynamic reliability works
[ ] Consolidation suggestion works
[ ] Circuit breaker opens after failures
[ ] Circuit breaker reset works
[ ] One carrier failure is handled
[ ] Two carrier failures are handled
[ ] Invalid status transitions are rejected
[ ] ETA explanation works
[ ] All tests pass
```


# Final Summary

The Logistics Service has evolved from a basic shipment management API into an advanced logistics service.

The completed functionality includes:

```text
Shipment Management
        +
Carrier Quotes
        +
Tracking
        +
Retry and Backoff
        +
Shipment History
        +
Async Bulk Quotes
        +
Dynamic Reliability
        +
Shipment Consolidation
        +
Circuit Breaker
        +
Carrier Failure Handling
        +
ETA Explanation
```

The current stopping point is:

```text
R4 IMPLEMENTATION
        +
R4 TESTING
        +
R4 DOCUMENTATION
```

