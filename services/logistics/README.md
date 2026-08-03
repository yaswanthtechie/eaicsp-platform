# Logistics Service API

A Logistics Service API built using **Python** and **FastAPI** that allows users to create, manage, track, and quote shipments across multiple carriers.

The project demonstrates **REST API development**, **Object-Oriented Programming (OOP)** concepts, **Adapter Design Pattern**, **retry mechanisms**, **shipment tracking**, and **unit testing with Pytest**.

---

# Technologies Used

* Python
* FastAPI
* Uvicorn
* Pydantic
* Pytest
* Tenacity
* AsyncIO

---

# Project Structure


```text
logistics-service/
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
│   ├── models/
│   │
│   └── core/
│
├── tests/
│   ├── test_carriers.py
│   └── test_quotes_and_history.py
│
├── requirements.txt
│
└── README.md
```



---

# Features

* Create Shipment
* Get All Shipments
* Get Shipment By ID
* Update Shipment
* Delete Shipment
* Filter Shipment By Status
* Shipment Tracking
* Shipment History
* Shipping Quote
* Bulk Quote Endpoint
* Adapter Design Pattern
* Carrier Failure Handling
* Retry with Exponential Backoff
* Reliability Scoring
* Inheritance
* Polymorphism
* Unit Testing

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
cd logistics-service
```

---

## Create Virtual Environment

```bash
python -m venv venv
```

---

## Activate Virtual Environment

### Windows

```powershell
.\venv\Scripts\activate
```

### Linux / Mac

```bash
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

or

```bash
pip install fastapi uvicorn pytest tenacity
```

---

# Run the Application

```bash
python -m uvicorn app.main:app --reload
```

Application URL

```text
http://127.0.0.1:8000
```

Swagger Documentation

```text
http://127.0.0.1:8000/docs
```

---

# API Endpoints

## Home

```http
GET /
```

Response

```json
{
  "message": "Logistics Service is running"
}
```

---

## Create Shipment

```http
POST /api/v1/shipments/
```

Request

```json
{
  "shipment_id": 1,
  "origin": "Hyderabad",
  "destination": "Mumbai",
  "carrier": "dhl",
  "status": "pending",
  "estimated_delivery": "2026-07-30",
  "actual_delivery": null,
  "weight_kg": 25.5
}
```

---

## Get All Shipments

```http
GET /api/v1/shipments/
```

---

## Get Shipment By ID

```http
GET /api/v1/shipments/{shipment_id}
```

Example

```http
GET /api/v1/shipments/1
```

---

## Update Shipment

```http
PUT /api/v1/shipments/{shipment_id}
```

---

## Delete Shipment

```http
DELETE /api/v1/shipments/{shipment_id}
```

---

## Filter Shipment By Status

```http
GET /api/v1/shipments/?status=delayed
```

Available Status

* pending
* in_transit
* delivered
* delayed
* cancelled

---

## Shipment Tracking

```http
GET /api/v1/shipments/{shipment_id}/tracking
```

Example

```http
GET /api/v1/shipments/1/tracking
```

---

## Shipment History

```http
GET /api/v1/shipments/{shipment_id}/history
```

Example

```http
GET /api/v1/shipments/1/history
```

Sample Response

```json
[
  {
    "shipment_id": 1,
    "status": "pending",
    "timestamp": "2026-07-31T10:00:00",
    "location": "Hyderabad"
  },
  {
    "shipment_id": 1,
    "status": "in_transit",
    "timestamp": "2026-07-31T14:00:00",
    "location": "Nagpur"
  },
  {
    "shipment_id": 1,
    "status": "delivered",
    "timestamp": "2026-08-01T12:00:00",
    "location": "Mumbai"
  }
]
```

---

# Shipment Quote Endpoint

```http
POST /api/v1/shipments/quote
```

Request

```json
{
  "origin": "Hyderabad",
  "destination": "Mumbai",
  "weight_kg": 10,
  "preference": "cheapest"
}
```

Supported Preferences

* cheapest
* fastest
* most_reliable

Sample Response

```json
[
  {
    "carrier": "UPS",
    "price": 450,
    "estimated_days": 5,
    "reliability_score": 0.95
  },
  {
    "carrier": "BlueDart",
    "price": 550,
    "estimated_days": 2,
    "reliability_score": 0.90
  }
]
```

---

# Async Bulk Quote Endpoint

```http
POST /api/v1/shipments/bulk-quote
```

Request

```json
{
  "shipments": [
    {
      "origin": "Hyderabad",
      "destination": "Mumbai",
      "weight_kg": 10
    },
    {
      "origin": "Delhi",
      "destination": "Chennai",
      "weight_kg": 5
    }
  ]
}
```

The endpoint uses:

```python
asyncio.gather()
```

to query carriers in parallel.

---

# Carrier Failure Handling

Real carrier APIs can fail because of:

* Network errors
* Timeouts
* API outages
* Invalid responses

To handle failures, the project uses **Tenacity**.

### Retry Strategy

* Attempt 1 → Immediate
* Attempt 2 → Wait 1 second
* Attempt 3 → Wait 2 seconds
* Final Attempt → Wait 4 seconds

### Exponential Backoff Flow

```text
Carrier Request
      │
      ▼
Attempt 1
      │
      ├── Success
      │
      └── Failure
              │
              ▼
           Wait 1s
              │
              ▼
          Attempt 2
              │
              └── Failure
                      │
                      ▼
                   Wait 2s
                      │
                      ▼
                  Attempt 3
                      │
                      ├── Success
                      └── Failure
                              │
                              ▼
                       Fallback Response
```

---

## Graceful Fallback

If all retries fail, the service does not crash.

Example Response

```json
{
  "rates": [
    {
      "carrier": "UPS",
      "price": 450
    },
    {
      "carrier": "BlueDart",
      "price": 550
    }
  ],
  "warnings": [
    "FedEx unavailable"
  ]
}
```

---

## Mock Failure Simulation

The FedEx adapter intentionally fails approximately 30% of the time.

Purpose:

* Verify retry mechanism
* Test resilience
* Validate fallback behavior

Even when FedEx fails, the API still returns useful results.

---

# Smart Quote Selection

The quote endpoint supports multiple preferences.

### Cheapest

Returns the lowest-cost carrier.

### Fastest

Returns the carrier with the smallest delivery time.

### Most Reliable

Returns the carrier with the highest weighted score.

Example Formula

```python
score = (
    reliability_score * 100
    - price * 0.01
    - estimated_days
)
```

Higher score = Better recommendation.

---

# Shipment Status Enum

```python
from enum import Enum

class Status(str, Enum):

    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"
    delayed = "delayed"
    cancelled = "cancelled"
```

---

# Legal Shipment Status Transitions

Allowed

```text
pending → in_transit
in_transit → delivered
```

Flow

```text
pending
   │
   ▼
in_transit
   │
   ▼
delivered
```

Invalid

```text
delivered → pending
delivered → in_transit
```

Response

```json
{
  "detail": "Invalid status transition"
}
```

HTTP Status

```text
400 Bad Request
```

---

# Carriers

Supported Carriers

* DHL
* FedEx
* UPS
* BlueDart

Common Methods

```python
get_rate()
get_tracking()
```

---

# Adapter Design Pattern

```text
              CarrierAdapter
                     │
     ┌───────────────┼───────────────┐
     │               │               │
 DHLAdapter     FedExAdapter     UPSAdapter
                                     │
                               BlueDartAdapter
```

Benefits

* Common interface
* Easy maintenance
* Easy carrier integration
* Scalable architecture

---

# OOP Concepts Used

## Abstraction

```python
from abc import ABC, abstractmethod

class CarrierAdapter(ABC):

    @abstractmethod
    def get_rate(self):
        pass

    @abstractmethod
    def get_tracking(self):
        pass
```

---

## Inheritance

```python
class DHLAdapter(CarrierAdapter):
    pass

class FedExAdapter(CarrierAdapter):
    pass

class UPSAdapter(CarrierAdapter):
    pass

class BlueDartAdapter(CarrierAdapter):
    pass
```

---

## Polymorphism

All carrier classes implement:

```python
get_rate()

get_tracking()
```

Same method names, different implementations.

---

# Project Flow

```text
Client
   │
   ▼
FastAPI Route
   │
   ▼
Pydantic Validation
   │
   ▼
Shipment Service
   │
   ▼
Carrier Adapter
   │
   ▼
Response
```

---

# Tracking Flow

```text
Client
      │
      ▼
Shipment ID
      │
      ▼
Find Shipment
      │
      ▼
Check Carrier
      │
      ├── DHL
      ├── FedEx
      ├── UPS
      └── BlueDart
      │
      ▼
get_tracking()
      │
      ▼
Tracking Response
```

---

# Quote Flow

```text
Client
      │
      ▼
Origin
Destination
Weight
Preference
      │
      ▼
get_quotes()
      │
      ├── DHL
      ├── FedEx
      ├── UPS
      └── BlueDart
      │
      ▼
Score / Sort Results
      │
      ▼
Return Response
```

---

# Bulk Quote Flow

```text
Client
      │
      ▼
Bulk Quote Request
      │
      ▼
asyncio.gather()
      │
      ├── DHL
      ├── FedEx
      ├── UPS
      └── BlueDart
      │
      ▼
Combine Results
      │
      ▼
Return Response
```

---

# Running Tests

Run:

```bash
python -m pytest -q
```

Example Output

```text
=========================
12 passed
=========================
```

---

# Definition of Done

✔ Carrier retry mechanism implemented

✔ Exponential backoff using Tenacity

✔ Graceful fallback without crashes

✔ Warning messages for failed carriers

✔ 30% mock carrier failure simulation

✔ Smart quote selection

✔ Reliability scoring

✔ Shipment tracking history

✔ Legal status transition validation

✔ Async bulk quote endpoint

✔ All tests passing

---

# Author

Developed using Python, FastAPI, OOP concepts, Adapter Design Pattern, Retry Mechanisms, and Unit Testing to demonstrate production-style logistics service architecture.
