# Logistics Service

A FastAPI-based Logistics Service for managing shipments, carrier quotes, shipment status transitions, bulk quotations, dynamic reliability scoring, carrier failure handling, independent circuit breakers, shipment consolidation, ETA explanations, and automated testing.

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
│   └── services/
│       ├── __init__.py
│       ├── shipment_service.py
│       │
│       └── carriers/
│           ├── __init__.py
│           ├── base.py
│           ├── dhl.py
│           ├── fedex.py
│           ├── ups.py
│           └── bluedart.py
│
├── tests/
│   ├── test_shipment.py
│   ├── test_quote_and_history.py
│   ├── test_carriers.py
│   └── test_r4.py
│
├── .coverage
├── .gitignore
├── pytest.ini
├── README.md
└── requirements.txt
```

---

# 2. File Responsibilities

## `app/main.py`

Main FastAPI application.

Responsibilities:

- Create the FastAPI application
- Register API routes
- Configure the application
- Provide the application entry point

Run the application with:

```powershell
uvicorn app.main:app --reload
```

---

## `app/routes/shipment.py`

Contains shipment API endpoints.

Responsibilities:

- Create shipment
- Get shipment
- Delete shipment
- Update shipment status
- Get shipment history
- Get carrier quotes
- Get bulk quotes
- Consolidation suggestions
- ETA explanation
- Safe API error responses

The routes layer is responsible for HTTP/API behavior.

Business logic remains in:

```text
app/services/shipment_service.py
```

---

## `app/schemas/shipment.py`

Contains Pydantic models and enums.

Responsibilities:

- Request validation
- Response validation
- Shipment models
- Quote models
- Carrier models
- Status enum
- Quote preference enum
- Tracking models
- Bulk quote models

---

## `app/services/shipment_service.py`

Contains the main business logic.

Responsibilities:

- Shipment management
- Shipment status transitions
- Carrier selection
- Quote calculation
- Carrier failure handling
- Retry handling
- Dynamic reliability scoring
- Carrier result recording
- Async bulk quoting
- Circuit breaker management
- Consolidation suggestions
- ETA explanation
- Shipment history

---

## `app/services/carriers/base.py`

Defines the common carrier interface and shared carrier functionality.

Responsibilities:

- `BaseCarrier`
- `CarrierError`
- `CarrierRate`
- `TrackingInfo`
- Retry helper
- Common carrier behavior

The service layer controls retry and circuit-breaker behavior.

---

## `app/services/carriers/dhl.py`

DHL carrier implementation.

Provides:

- Shipping quote
- Tracking information

---

## `app/services/carriers/fedex.py`

FedEx carrier implementation.

Provides:

- Shipping quote
- Tracking information
- Simulated temporary carrier failures

FedEx failure simulation is used for testing failure-handling logic.

---

## `app/services/carriers/ups.py`

UPS carrier implementation.

Provides:

- Shipping quote
- Tracking information

---

## `app/services/carriers/bluedart.py`

BlueDart carrier implementation.

Provides:

- Shipping quote
- Tracking information

---

# 3. Testing Structure

## `tests/test_shipment.py`

Tests basic shipment functionality.

Includes:

- Shipment creation
- Shipment retrieval
- Shipment deletion
- Missing shipment handling
- Status updates
- Invalid status transitions
- Shipment history
- API response codes

---

## `tests/test_quote_and_history.py`

Tests:

- Carrier quotes
- Cheapest carrier
- Fastest carrier
- Most reliable carrier
- Carrier failure warnings
- Reliability history
- Shipment history
- Quote behavior

---

## `tests/test_carriers.py`

Tests individual carrier implementations.

Includes:

- DHL rate
- FedEx rate
- UPS rate
- BlueDart rate
- Carrier tracking
- Invalid input handling
- Carrier errors

---

## `tests/test_r4.py`

Tests R4 functionality.

Includes:

- Bulk quote
- Async processing
- Reliability scoring
- Reliability history
- Carrier failure handling
- Circuit breaker
- Circuit breaker reset
- HALF_OPEN recovery
- Concurrent failures
- Two-of-three carrier failures
- Consolidation
- ETA explanation
- Status transition edge cases

---

# 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Programming language |
| FastAPI | REST API framework |
| Pydantic | Request/response validation |
| Uvicorn | ASGI server |
| asyncio | Asynchronous processing |
| HTTPX | HTTP client |
| Pytest | Testing |
| Pytest-Asyncio | Async testing |
| Tenacity | Retry mechanism |

---

# 5. Project Overview

The Logistics Service manages shipment operations and carrier selection.

The service provides APIs to:

- Create shipments
- Retrieve shipments
- Delete shipments
- Update shipment status
- Maintain shipment history
- Generate carrier quotes
- Select carriers
- Process bulk quotes
- Track carrier reliability
- Handle carrier failures
- Retry temporary failures
- Protect carriers using independent circuit breakers
- Suggest shipment consolidation
- Explain ETA calculations

---

# 6. R1 - Basic Shipment Management

R1 provides:

- Shipment creation
- Shipment retrieval
- Shipment deletion
- Shipment status management
- Shipment history
- Request validation
- Valid status transitions
- Invalid transition handling
- `404 Not Found` for missing shipments

---

# 7. R2 - Carrier Quoting

The service supports multiple carriers.

Current mock carriers:

- DHL
- FedEx
- UPS
- BlueDart

The service calculates:

- Shipping price
- Estimated delivery time
- Reliability score
- Recommended carrier

Supported preferences:

```text
cheapest
fastest
most_reliable
```

---

# 8. R3 - Advanced Carrier Handling

R3 introduced:

- Carrier integration
- Carrier selection
- Quote APIs
- Retry handling
- Carrier failure handling
- Shipment history
- Circuit breaker foundation

---

# 9. R4 - Advanced Logistics Features

R4 extends the service with:

1. Real asynchronous bulk quoting
2. Dynamic reliability scoring
3. Carrier failure handling
4. Independent circuit breakers
5. Retry and circuit-breaker coordination
6. Shipment consolidation
7. ETA explanation
8. Concurrent failure testing
9. Two-of-three carrier failure testing
10. HALF_OPEN circuit-breaker recovery
11. Advanced R4 testing

---

# 10. R4 - Async Bulk Quoting

Endpoint:

```http
POST /api/v1/shipments/bulk-quote
```

The endpoint supports a maximum of:

```text
20 shipments
```

The carrier requests are processed concurrently using:

```python
asyncio.gather()
```

---

## Sequential Processing

```text
Shipment 1
    ↓
Carrier request
    ↓
Shipment 2
    ↓
Carrier request
    ↓
Shipment 3
    ↓
Carrier request
```

Each operation waits for the previous operation.

---

## Async Processing

```text
Shipment 1 ─┐
Shipment 2 ─┤
Shipment 3 ─┤
Shipment 4 ─┤
Shipment 5 ─┘
      ↓
asyncio.gather()
      ↓
Concurrent processing
```

Multiple quote operations can run concurrently.

---

# 11. Bulk Quote Performance

R4 measures:

```text
Sequential execution time
Async execution time
Speedup
```

The values are measured during execution.

The README intentionally does not use invented values such as:

```text
sequential_time: 4.8
speedup: 3.0
```

because actual execution time depends on:

- Machine performance
- Carrier simulation
- Number of shipments
- Retry behavior
- Carrier failures
- System load

The API returns the actual measured performance information generated by the implementation.

---

# 12. Bulk Quote Response

The bulk quote response contains:

```text
quotes
performance
```

Example structure:

```json
{
  "quotes": [],
  "performance": {
    "sequential_time": 0.0,
    "async_time": 0.0,
    "speedup": 0.0
  }
}
```

The numbers above are only structural examples.

Actual values are calculated at runtime.

---

# 13. Bulk Quote Processing Flow

```text
Client
   ↓
Bulk Quote API
   ↓
Validate request
   ↓
Create async tasks
   ↓
Check circuit breaker
   ↓
Call carrier
   ↓
Retry temporary failures
   ↓
Record carrier result
   ↓
Collect successful quotes
   ↓
Collect warnings
   ↓
Calculate performance
   ↓
Return response
```

---

# 14. Dynamic Reliability Scoring

R4 tracks carrier performance using simulated delivery history.

Reliability is not randomly redrawn every application restart.

The initial carrier history is deterministic and reproducible.

Carrier results are recorded through the service logic.

The important operation is:

```python
record_carrier_result()
```

This function updates the carrier's historical result.

---

# 15. Reliability Formula

```text
Reliability Score =
On-Time Deliveries / Total Deliveries
```

Example:

```text
On-time deliveries = 95
Total deliveries   = 100

Reliability =
95 / 100

= 0.95
```

A higher score means better historical performance.

---

# 16. Reliability History

The service maintains carrier history.

Example:

```text
DHL

Total deliveries    : 100
On-time deliveries  : 92
Late deliveries     : 8

Reliability:
92 / 100 = 0.92
```

If a new delivery result is recorded, the history is updated.

Example:

```text
Previous:

92 on-time
100 total

New shipment:

On-time

New:

93 on-time
101 total

Reliability:

93 / 101
```

This makes reliability dynamic instead of generating a new random value every restart.

---

# 17. Reliability and Carrier Selection

For:

```text
most_reliable
```

the service selects the carrier with the highest current reliability score.

Example:

```text
DHL       0.87
FedEx     0.92
UPS       0.95
BlueDart  0.90
```

Selected:

```text
UPS
```

The actual score may change as delivery results are recorded.

---

# 18. Initial Mock Carrier Values

The mock carrier configuration starts with:

| Carrier | Base Price | Delivery Days | Initial Reliability |
|---|---:|---:|---:|
| DHL | ₹850 | 2 | 0.87 |
| FedEx | ₹950 | 3 | 0.92 |
| UPS | ₹900 | 4 | 0.95 |
| BlueDart | ₹750 | 2 | 0.90 |

These are starting simulation values.

The dynamic reliability system can update the historical score after simulated shipment outcomes.

---

# 19. Carrier Preferences

The service supports:

```text
cheapest
fastest
most_reliable
```

---

## Cheapest

Selects the available carrier with the lowest price.

Example:

```text
DHL       ₹850
FedEx     ₹950
UPS       ₹900
BlueDart  ₹750
```

Selected:

```text
BlueDart
```

---

## Fastest

Selects the available carrier with the shortest delivery time.

Example:

```text
DHL       2 days
FedEx     3 days
UPS       4 days
BlueDart  2 days
```

The service selects the fastest available option according to the quote data.

---

## Most Reliable

Selects the available carrier with the highest current reliability score.

---

# 20. Carrier Failure Handling

Carrier failures are intentionally simulated.

Example:

```text
DHL       → Available
FedEx     → Failed
UPS       → Available
BlueDart  → Available
```

The failure of one carrier must not stop the complete quote operation.

The service continues with the available carriers.

A warning can be returned:

```text
FedEx unavailable
```

---

# 21. Carrier Failure Warning

When a carrier fails, the service catches the carrier exception and converts it into a safe warning.

Example:

```text
FedEx unavailable
```

The service should not expose internal exception details directly to the client.

For example, raw internal messages such as:

```text
FedEx API timeout
```

should not be unnecessarily exposed through API error responses.

---

# 22. Retry Mechanism

Temporary carrier failures are retried by the service layer.

The retry mechanism uses Tenacity.

Typical retry sequence:

```text
Attempt 1
   ↓
Wait
   ↓
Attempt 2
   ↓
Wait
   ↓
Attempt 3
   ↓
Success / Failure
```

The retry policy is controlled by the logistics service.

---

# 23. Important Retry and Circuit Breaker Rule

The circuit breaker must be checked before starting retry attempts.

Correct flow:

```text
Shipment
   ↓
Check Circuit Breaker
   ↓
Is carrier OPEN?
   ├── Yes → Do not call carrier
   │
   └── No
        ↓
     Carrier call
        ↓
     Failure?
        ↓
     Retry if allowed
        ↓
     Record failure
        ↓
     Open breaker after threshold
```

The carrier adapter should not independently perform the complete retry policy.

This prevents a failing carrier from creating unnecessary retry storms during a bulk request.

---

# 24. Circuit Breaker

R4 includes a local circuit breaker for every carrier.

The purpose is to stop repeated calls to a carrier that is continuously failing.

Each carrier has an independent circuit breaker.

---

# 25. Circuit Breaker States

The service supports:

```text
CLOSED
OPEN
HALF_OPEN
```

---

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

The carrier has failed repeatedly.

```text
Request
   ↓
Circuit Breaker
   ↓
Carrier blocked
```

No new carrier calls should be made while the breaker is OPEN.

---

## HALF_OPEN

After the recovery period, the breaker permits a trial request.

```text
OPEN
 ↓
Recovery period
 ↓
HALF_OPEN
 ↓
Trial request
```

If successful:

```text
HALF_OPEN → CLOSED
```

If failed:

```text
HALF_OPEN → OPEN
```

---

# 26. Circuit Breaker Failure Threshold

The circuit breaker opens after repeated failures according to the configured failure threshold.

The exact threshold is controlled by the service implementation.

Example:

```text
Failure 1
Failure 2
Failure 3
      ↓
OPEN
```

Once OPEN, further requests are blocked until the recovery period expires.

---

# 27. Independent Circuit Breakers

Every carrier has its own breaker.

Example:

```text
DHL       → CLOSED
FedEx     → OPEN
UPS       → CLOSED
BlueDart  → CLOSED
```

If FedEx fails, the other carriers continue to operate.

---

# 28. Circuit Breaker and Bulk Quote Protection

This is an important R4 behavior.

During a 20-shipment bulk request:

```text
20 shipments
      ↓
Carrier calls
      ↓
Failure
      ↓
record_failure()
      ↓
Failure threshold reached
      ↓
Circuit OPEN
      ↓
Future calls blocked
```

The implementation avoids repeatedly retrying a carrier after its breaker has opened.

Therefore, the first bulk batch does not continue making unnecessary carrier calls after the breaker reaches OPEN.

---

# 29. Circuit Breaker Reset

The service supports:

```python
reset_circuit_breaker(carrier)
```

and:

```python
reset_all_circuit_breakers()
```

These functions are useful for:

- Automated tests
- Recovery
- Development
- Controlled simulation

---

# 30. HALF_OPEN Recovery Testing

The R4 tests verify:

```text
CLOSED
   ↓
Failures
   ↓
OPEN
   ↓
Recovery timeout
   ↓
HALF_OPEN
   ↓
Successful trial
   ↓
CLOSED
```

Failure during the trial produces:

```text
HALF_OPEN
   ↓
Failed trial
   ↓
OPEN
```

---

# 31. Consolidation Suggestions

R4 supports shipment consolidation suggestions.

The service checks for shipments that:

- Have the same destination
- Have estimated delivery dates within 2 days

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
Consolidation suggestion available
```

---

# 32. Why Consolidation Is Useful

Consolidation can help reduce:

- Shipping cost
- Number of trips
- Carrier usage
- Operational overhead

Example:

```text
Shipment A → Hyderabad
Shipment B → Hyderabad
Shipment C → Hyderabad
```

The service can suggest consolidation when the configured business rules allow it.

---

# 33. ETA Explanation

R4 provides ETA explanation functionality.

The purpose is to explain how the estimated delivery time was calculated.

Example:

```text
Base transit time : 2 days
Current status    : delayed
Additional delay  : 1 day

Estimated ETA     : 3 days
```

An ETA explanation can include:

- Carrier
- Base transit time
- Current shipment status
- Additional delay
- Estimated delivery

---

# 34. Shipment Statuses

The service supports:

```text
pending
in_transit
delivered
delayed
cancelled
```

---

# 35. Valid Status Transitions

Supported transitions include:

```text
pending
   ↓
in_transit
```

```text
in_transit
   ↓
delayed
   ↓
in_transit
   ↓
delivered
```

And:

```text
in_transit → delivered
in_transit → cancelled
delayed    → delivered
delayed    → cancelled
```

Invalid transitions are rejected.

---

# 36. Shipment Not Found

When a shipment does not exist, the API returns:

```http
404 Not Found
```

Example:

```http
GET /api/v1/shipments/9999
```

Response:

```json
{
  "detail": "Shipment not found"
}
```

The service does not return a successful `200` response for a nonexistent shipment.

---

# 37. Delete Shipment

Deleting an existing shipment returns a successful response.

Example:

```http
DELETE /api/v1/shipments/40
```

Response:

```json
{
  "message": "Shipment deleted successfully"
}
```

After deletion:

```http
GET /api/v1/shipments/40
```

returns:

```http
404 Not Found
```

---

# 38. API Endpoints

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
POST /api/v1/shipments/
```

Creates a new shipment.

Successful creation uses:

```http
201 Created
```

---

## Get Shipment

```http
GET /api/v1/shipments/{shipment_id}
```

Returns shipment details.

Missing shipment:

```http
404 Not Found
```

---

## Delete Shipment

```http
DELETE /api/v1/shipments/{shipment_id}
```

Deletes a shipment.

---

## Update Shipment Status

```http
PATCH /api/v1/shipments/{shipment_id}/status
```

Updates shipment status after validating the transition.

---

## Shipment History

```http
GET /api/v1/shipments/{shipment_id}/history
```

Returns shipment status history.

---

## Get Quote

```http
POST /api/v1/shipments/quote
```

Returns available carrier quote information and the selected carrier according to the requested preference.

---

## Bulk Quote

```http
POST /api/v1/shipments/bulk-quote
```

Processes multiple shipment quote requests concurrently.

Maximum:

```text
20 shipments
```

---

## Consolidation Suggestions

The service provides consolidation suggestions based on:

```text
Same destination
+
Delivery date difference <= 2 days
```

---

## ETA Explanation

The service provides an explanation for the calculated shipment ETA.

---

# 39. Example Quote

Example structural response:

```json
{
  "carrier": "BlueDart",
  "price": 750,
  "delivery_days": 2,
  "reliability_score": 0.90
}
```

Actual values depend on:

- Current carrier availability
- Current reliability history
- Shipment weight
- Origin
- Destination

---

# 40. Example Bulk Quote Request

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

---

# 41. Example Bulk Quote Response

```json
{
  "quotes": [],
  "performance": {
    "sequential_time": 0.0,
    "async_time": 0.0,
    "speedup": 0.0
  }
}
```

The performance numbers are generated dynamically at runtime.

---

# 42. Shipment History

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

The history provides visibility into the shipment lifecycle.

---

# 43. Installation

Open PowerShell.

Go to the Logistics Service directory:

```powershell
cd "C:\Users\Sowmya\OneDrive\Desktop\logistical service\eaicsp-platform\services\logistics"
```

---

# 44. Python Version

Python 3.13 is recommended for the current development environment.

The dependency configuration also avoids unnecessarily pinning Pydantic to a version that prevents installation on newer Python versions.

---

# 45. Create Virtual Environment

```powershell
py -3.13 -m venv venv
```

---

# 46. Activate Virtual Environment

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

# 47. If PowerShell Blocks Activation

Run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then:

```powershell
.\venv\Scripts\Activate.ps1
```

---

# 48. Install Dependencies

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

---

# 49. Requirements

Recommended `requirements.txt`:

```text
fastapi==0.139.0
uvicorn[standard]==0.35.0
pydantic>=2.11.7,<3
tenacity==8.2.0
pytest==8.4.1
pytest-asyncio==1.1.0
httpx
```

The important change is:

```text
pydantic>=2.11.7,<3
```

instead of:

```text
pydantic==2.11.7
```

This avoids unnecessarily forcing one exact Pydantic release when installing the project on newer Python versions.

---

# 50. Run the Application

From the Logistics Service directory:

```powershell
uvicorn app.main:app --reload
```

---

# 51. Open Swagger

Open:

```text
http://127.0.0.1:8000/docs
```

Swagger provides an interactive API testing interface.

---

# 52. Test Using Swagger

```text
1. Start the server
2. Open /docs
3. Select an API
4. Click Try it out
5. Enter request data
6. Click Execute
7. Check the response
```

---

# 53. Pytest Configuration

The project includes:

```text
pytest.ini
```

This keeps test discovery and pytest configuration consistent.

Example:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
```

---

# 54. Run All Tests

Use:

```powershell
python -m pytest -q
```

This is preferred because it uses pytest from the active Python environment.

Expected result after all fixes:

```text
all tests passed
```

The exact number of tests can change when additional tests are added.

---

# 55. Run R4 Tests

```powershell
python -m pytest tests/test_r4.py -q
```

---

# 56. Run Carrier Tests

```powershell
python -m pytest tests/test_carriers.py -q
```

---

# 57. Run Shipment Tests

```powershell
python -m pytest tests/test_shipment.py -q
```

---

# 58. Run Quote and History Tests

```powershell
python -m pytest tests/test_quote_and_history.py -q
```

---

# 59. Run Coverage

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

If coverage tools are not installed:

```powershell
python -m pip install coverage pytest-cov
```

Then:

```powershell
python -m pytest --cov=app --cov-report=term-missing
```

---

# 60. R4 Testing Strategy

R4 tests verify behavior under the conditions described by the requirements.

The important testing cases are:

```text
Normal carrier operation
        ↓
Carrier failure
        ↓
Retry
        ↓
Repeated failure
        ↓
Circuit breaker OPEN
        ↓
Future calls blocked
        ↓
Recovery timeout
        ↓
HALF_OPEN
        ↓
Trial request
        ↓
CLOSED / OPEN
```

This tests the actual runtime behavior rather than testing individual functions in isolation only.

---

# 61. Concurrent Carrier Failure Testing

R4 tests concurrent carrier failures.

Example:

```text
20 shipments
    ↓
Concurrent processing
    ↓
Carrier failure
    ↓
Failure recorded
    ↓
Breaker threshold reached
    ↓
Carrier OPEN
    ↓
Additional calls blocked
```

Healthy carriers continue serving quotes.

---

# 62. Two-of-Three Carrier Failure Testing

The service also tests scenarios where multiple carriers fail.

Example:

```text
DHL      → Failed
FedEx    → Failed
UPS      → Available
BlueDart → Available
```

The service should continue using the healthy carriers.

---

# 63. Carrier Reliability Test

Reliability tests verify that:

- Initial history is deterministic
- Carrier scores are reproducible
- Results are recorded
- On-time deliveries increase reliability
- Late deliveries reduce reliability
- `most_reliable` uses current history
- Restarting the service does not randomly redraw the initial scores

---

# 64. Circuit Breaker Test

The important R4 breaker test is not only:

```python
record_failure()
record_failure()
record_failure()
```

The real failure path is tested through carrier calls.

Example:

```text
Bulk request
    ↓
call_one_carrier()
    ↓
Carrier fails
    ↓
Retry
    ↓
record_failure()
    ↓
Breaker opens
    ↓
Subsequent carrier calls are blocked
```

This verifies that the retry and circuit-breaker interaction works correctly.

---

# 65. Carrier Failure Warning Test

When a carrier fails:

```text
FedEx unavailable
```

should be present in the quote warnings.

Example:

```text
DHL       → Quote
FedEx     → Failed
UPS       → Quote
BlueDart  → Quote
```

The overall quote operation continues.

---

# 66. API Error Handling

Internal exceptions should not unnecessarily be exposed directly to clients.

Instead of returning raw internal exception text such as:

```text
DatabaseError(...)
CarrierError(...)
TimeoutError(...)
```

the API should return a safe client-facing message.

Example:

```json
{
  "detail": "Unable to process shipment request"
}
```

The detailed exception can remain available in server-side logs for debugging.

---

# 67. POST Response Codes

Shipment creation uses:

```http
201 Created
```

when a new shipment is successfully created.

The service uses appropriate HTTP status codes for API behavior.

Examples:

```text
201 → Created
200 → Successful operation
400 → Invalid request
404 → Resource not found
409 → Conflict
422 → Validation error
```

---

# 68. Adapter Architecture

The project uses a common carrier interface.

Conceptually:

```text
Logistics Service
       |
       v
BaseCarrier
   /    |     \
  /     |      \
DHL   FedEx    UPS
             \
            BlueDart
```

The common interface allows the shipment service to work with different carrier implementations consistently.

---

# 69. Carrier Interface

Each carrier provides common operations such as:

```text
get_rate()
get_tracking()
```

The shipment service does not need to know the internal implementation details of each carrier.

---

# 70. Local Carrier Concept

Examples of Indian logistics providers include:

- Blue Dart
- Delhivery
- Ecom Express
- XpressBees
- DTDC

The current project uses mock carrier implementations for development and testing.

The carrier implementations simulate external logistics providers rather than making production carrier API calls.

---

# 71. Adapter vs Local Carrier Approach

## Adapter Approach

```text
Logistics Service
       |
       v
Common Carrier Interface
       |
   +---+---+---+
   |   |   |   |
   v   v   v   v
 DHL FedEx UPS BlueDart
```

Advantages:

- Common interface
- Easy carrier replacement
- Easier testing
- Different external APIs can be normalized

---

## Local Carrier Approach

```text
Logistics Service
       |
       +------ Local Carrier 1
       |
       +------ Local Carrier 2
       |
       +------ Local Carrier 3
```

This can be simpler when the system is specifically designed around a fixed set of local carriers.

---

# 72. Why Carrier Failures Happen

Real carrier integrations can fail because of:

- Network problems
- API timeout
- Server overload
- Maintenance
- Rate limits
- Authentication problems
- Service outages
- Invalid request data
- Temporary connectivity issues

The project simulates these situations to verify resilience.

---

# 73. Complete R4 Flow

```text
Client
  |
  v
FastAPI
  |
  +---------------------------+
  |                           |
  v                           v
Shipment API             Bulk Quote API
                              |
                              v
                       Validate Request
                              |
                              v
                       asyncio.gather()
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
            DHL             FedEx             UPS
             |                |                |
             +----------------+----------------+
                              |
                              v
                       Quote Collection
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
       Reliability      Circuit Breaker    Performance
          Score             State             Metrics
                              |
                              v
                       Final Response
```

---

# 74. R4 Architecture

```text
                  Logistics Service
                         |
             +-----------+-----------+
             |                       |
             v                       v
       Shipment Routes         Quote Routes
             |                       |
             v                       v
      Shipment Service       Bulk Quote Processing
                                     |
                                     v
                              asyncio.gather()
                                     |
                                     v
                              Carrier Services
                                     |
             +-----------+-----------+-----------+
             |           |           |           |
             v           v           v           v
            DHL        FedEx        UPS       BlueDart
             |           |           |           |
             +-----------+-----------+-----------+
                         |
                         v
                  Result Recording
                         |
                         v
                Reliability History
                         |
                         v
                 Circuit Breakers
```

---

# 75. Business Benefits

## Faster Processing

Async bulk quoting processes multiple requests concurrently.

---

## Better Carrier Selection

The service can select carriers based on:

- Price
- Delivery speed
- Reliability

---

## Better Failure Handling

Retry and circuit breakers reduce the impact of temporary carrier failures.

---

## Carrier Isolation

Each carrier has an independent circuit breaker.

A failing carrier does not automatically disable healthy carriers.

---

## Better Reliability

Carrier reliability is calculated from delivery history instead of being randomly regenerated on every restart.

---

## Cost Optimization

Consolidation suggestions can reduce unnecessary shipments.

---

## Better Visibility

Shipment history and ETA explanations provide better shipment visibility.

---

# 76. Example Complete Scenario

Customer requests:

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

Available carriers may provide:

```text
DHL
Price: ₹850
Days: 2

FedEx
Price: ₹950
Days: 3

UPS
Price: ₹900
Days: 4

BlueDart
Price: ₹750
Days: 2
```

The service checks the current reliability history.

For example:

```text
DHL       0.87
FedEx     0.92
UPS       0.95
BlueDart  0.90
```

The selected carrier is:

```text
UPS
```

because it has the highest current reliability score.

---

# 77. Example Cheapest Scenario

Preference:

```text
cheapest
```

Example:

```text
DHL       ₹850
FedEx     ₹950
UPS       ₹900
BlueDart  ₹750
```

Selected:

```text
BlueDart
```

---

# 78. Example Carrier Failure Scenario

Suppose:

```text
FedEx → unavailable
```

The service continues:

```text
DHL       → Quote available
FedEx     → Failed
UPS       → Quote available
BlueDart  → Quote available
```

Warnings contain:

```text
FedEx unavailable
```

The available carriers continue processing.

---

# 79. Example Circuit Breaker Scenario

Suppose FedEx continuously fails.

```text
FedEx Failure
      ↓
Retry
      ↓
Failure recorded
      ↓
Failure threshold reached
      ↓
FedEx breaker OPEN
```

After opening:

```text
FedEx → No unnecessary carrier calls
```

Healthy carriers continue:

```text
DHL       → Working
UPS       → Working
BlueDart  → Working
```

After the recovery period:

```text
OPEN
 ↓
HALF_OPEN
 ↓
Trial request
```

Successful trial:

```text
HALF_OPEN → CLOSED
```

Failed trial:

```text
HALF_OPEN → OPEN
```

---

# 80. Example Consolidation Scenario

```text
Shipment 1

Destination: Chennai
Date: 15-Aug
```

```text
Shipment 2

Destination: Chennai
Date: 16-Aug
```

The service detects:

```text
Same destination
+
Date difference <= 2 days
```

Result:

```text
Consolidation suggestion available
```

---

# 81. Example ETA Explanation

```text
Shipment ID: 200

Carrier:
DHL

Base transit time:
2 days

Current status:
delayed

Additional delay:
1 day

Estimated ETA:
3 days
```

---

# 82. R4 Requirements Checklist

```text
[x] Async batch quoting

[x] POST /api/v1/shipments/bulk-quote

[x] Maximum 20 shipments

[x] asyncio.gather()

[x] Sequential vs async performance measurement

[x] Runtime speedup calculation

[x] Dynamic reliability scoring

[x] Deterministic initial reliability history

[x] Carrier result recording

[x] Reliability updates

[x] Most reliable carrier selection

[x] Carrier failure handling

[x] Carrier warning generation

[x] Retry handling

[x] Retry coordinated with circuit breaker

[x] Independent carrier circuit breakers

[x] CLOSED state

[x] OPEN state

[x] HALF_OPEN state

[x] Recovery timer

[x] HALF_OPEN trial request

[x] Circuit breaker reset

[x] Concurrent carrier failure testing

[x] Two-of-three carrier failure testing

[x] Consolidation suggestions

[x] Same destination rule

[x] Two-day consolidation window

[x] ETA explanation

[x] Shipment history

[x] Missing shipment returns 404

[x] Deleted shipment returns 404 on subsequent GET

[x] Shipment creation returns 201

[x] Safe API error messages

[x] pytest configuration

[x] R4 tests

[x] README documentation
```

---

# 83. Resolved Review Blockers

The previously identified review blockers have been addressed.

## Blocker 01 - Python Dependency Installation

Previous issue:

```text
pydantic==2.11.7
```

could force an incompatible dependency combination on newer Python versions.

Updated requirement:

```text
pydantic>=2.11.7,<3
```

This allows a compatible Pydantic 2.x release to be selected.

---

## Blocker 02 - Reliability Scoring

Previous problem:

```text
record_carrier_result()
```

was not connected to the actual shipment/carrier result flow.

The corrected implementation records carrier outcomes through the service logic.

Reliability history is deterministic and is not randomly regenerated on every application restart.

Therefore:

```text
Carrier Result
      ↓
record_carrier_result()
      ↓
History
      ↓
Reliability Score
      ↓
Carrier Selection
```

---

## Blocker 03 - Circuit Breaker Failure Storm

Previous problem:

```text
Retry
 +
is_open() checked too late
```

could result in unnecessary carrier calls during a bulk request.

The corrected flow checks the breaker before calling the carrier and coordinates retry handling with breaker state.

```text
Check breaker
      ↓
OPEN?
 ├── Yes → Skip carrier
 |
 └── No
      ↓
Carrier call
      ↓
Failure
      ↓
Retry
      ↓
Record failure
      ↓
Threshold reached
      ↓
OPEN
      ↓
Future calls blocked
```

This prevents the same failure storm from continuing after the breaker opens.

---

# 84. Review Testing Philosophy

The important R4 behavior is tested under realistic conditions.

Instead of testing only:

```text
record_failure()
```

the tests also exercise:

```text
carrier call
    ↓
failure
    ↓
retry
    ↓
record failure
    ↓
breaker opens
    ↓
subsequent calls blocked
```

This ensures the implementation matches the actual runtime behavior required by R4.

---

# 85. Expected Test Result

Run:

```powershell
python -m pytest -q
```

The expected result is:

```text
all tests passed
```

The exact number of tests may change as the project evolves.

---

# 86. Git Commands

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
git commit -m "Fix R4 reliability and circuit breaker handling"
```

Push:

```powershell
git push
```

---

# 87. R4 Branch

Example R4 branch:

```text
sowmya/round4-logistics
```

---

# 88. Recommended Commit Sequence

For the R4 fixes, commits can be organized as:

```text
Fix Python dependency compatibility
```

```text
Implement deterministic dynamic reliability scoring
```

```text
Fix retry and circuit breaker interaction
```

```text
Improve carrier failure handling
```

```text
Add R4 failure and recovery tests
```

```text
Update logistics README
```

---

# 89. Simple Client Explanation

> This Logistics Service manages shipment operations and selects the best available carrier based on price, delivery speed, or reliability. In R4, we improved the system to process multiple shipment quotes asynchronously, track actual carrier performance, handle carrier failures using independent circuit breakers, prevent repeated calls to failing carriers, suggest shipment consolidation, and provide ETA explanations.

---

# 90. Simple R4 Explanation

R4 mainly focuses on:

```text
Performance
Reliability
Failure Handling
Optimization
Visibility
```

### Performance

```text
asyncio.gather()
```

processes multiple quote requests concurrently.

### Reliability

Carrier reliability is calculated from tracked shipment results.

### Failure Handling

Retry and independent circuit breakers protect the system from repeated carrier failures.

### Optimization

Consolidation suggestions can reduce unnecessary shipments.

### Visibility

ETA explanations and shipment history provide better shipment visibility.

---

# 91. Final R4 Flow

```text
Create Shipment
      ↓
Generate Quotes
      ↓
Compare Carriers
      ↓
Select Carrier
      ↓
Record Delivery Result
      ↓
Update Reliability
      ↓
Process Bulk Quotes
      ↓
Handle Carrier Failures
      ↓
Retry Temporary Failures
      ↓
Open Circuit Breaker When Required
      ↓
Recover Through HALF_OPEN
      ↓
Suggest Consolidation
      ↓
Explain ETA
      ↓
Track Shipment History
```

---

# 92. Final Run Commands

Activate environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
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

Run carrier tests:

```powershell
python -m pytest tests/test_carriers.py -q
```

Run shipment tests:

```powershell
python -m pytest tests/test_shipment.py -q
```

Run quote/history tests:

```powershell
python -m pytest tests/test_quote_and_history.py -q
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

# 93. Final Project Summary

The Logistics Service is a FastAPI microservice designed to manage shipment operations and carrier selection.

The project evolved through:

```text
R1
Basic Shipment Management
        ↓
R2
Carrier Quotes and Selection
        ↓
R3
Carrier Handling, Retry and Failure Management
        ↓
R4
Async Bulk Quoting
        +
Dynamic Reliability
        +
Independent Circuit Breakers
        +
Retry Protection
        +
Consolidation
        +
ETA Explanation
        +
Advanced Failure Testing
```

The final R4 implementation focuses on four major areas:

```text
Performance
    ↓
Async bulk quoting

Reliability
    ↓
Tracked carrier history

Resilience
    ↓
Retry + independent circuit breakers

Optimization
    ↓
Consolidation + carrier selection
```

The service is designed to continue operating when individual carriers fail while providing reliable carrier selection and shipment visibility.