# Logistics Service API

A simple Logistics Service API built using **Python** and **FastAPI**.

This project allows users to create, update, delete, and track shipments. It also provides shipping quotes from multiple carriers using the **Adapter Design Pattern**.

---

# Technologies Used

- Python
- FastAPI
- Uvicorn
- Pydantic
- Pytest

---

# Project Structure

```text
logistical service/
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
│   └── test_carriers.py
│
├── requirements.txt
│
└── README.md
```

---

# Features

- Create Shipment
- Get All Shipments
- Get Shipment by ID
- Update Shipment
- Delete Shipment
- Filter Shipment by Status
- Shipment Tracking
- Shipping Quote
- Adapter Design Pattern
- Inheritance
- Polymorphism
- Unit Testing

---

# Installation

## Clone the Project

```bash
git clone <repository-url>
```

---

## Create Virtual Environment

```bash
python -m venv venv
```

---

## Activate Virtual Environment

Windows

```powershell
.\venv\Scripts\activate
```

---

## Install Packages

```bash
python -m pip install fastapi uvicorn pytest
```

---

# Run the Project

```bash
python -m uvicorn app.main:app --reload
```

Application URL

```
http://127.0.0.1:8000
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

---

# API Endpoints

## Home

```
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

```
POST /api/v1/shipments/
```

Sample Request

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

```
GET /api/v1/shipments/
```

---

## Get Shipment By ID

```
GET /api/v1/shipments/{shipment_id}
```

Example

```
GET /api/v1/shipments/1
```

---

## Update Shipment

```
PUT /api/v1/shipments/{shipment_id}
```

---

## Delete Shipment

```
DELETE /api/v1/shipments/{shipment_id}
```

---

## Filter Shipment by Status

```
GET /api/v1/shipments/?status=delayed
```

Available Status

- pending
- in_transit
- delivered
- delayed
- cancelled

---

## Shipment Tracking

```
GET /api/v1/shipments/{shipment_id}/tracking
```

Example

```
GET /api/v1/shipments/1/tracking
```

---

## Shipment Quote

```
POST /api/v1/shipments/quote
```

Parameters

```
origin
destination
weight_kg
```

Example

```
origin = Hyderabad
destination = Mumbai
weight_kg = 25.5
```

Sample Response

```json
[
    {
        "carrier": "UPS",
        "price": 450,
        "estimated_days": 5
    },
    {
        "carrier": "BlueDart",
        "price": 550,
        "estimated_days": 2
    },
    {
        "carrier": "FedEx",
        "price": 650,
        "estimated_days": 3
    },
    {
        "carrier": "DHL",
        "price": 850,
        "estimated_days": 2
    }
]
```

---

# Shipment Status Enum

```python
class Status(str, Enum):

    pending = "pending"
    in_transit = "in_transit"
    delivered = "delivered"
    delayed = "delayed"
    cancelled = "cancelled"
```

---

# Carriers

This project supports four carriers.

- DHL
- FedEx
- UPS
- BlueDart

Each carrier implements the same methods.

```
get_rate()

get_tracking()
```

---

# Adapter Design Pattern

```
              CarrierAdapter
                     │
     ┌───────────────┼───────────────┐
     │               │               │
 DHLAdapter     FedExAdapter     UPSAdapter
                     │
               BlueDartAdapter
```

The Adapter Pattern allows all carriers to use the same interface.

If a real carrier API is added later, only that adapter file needs to be updated.

---

# OOP Concepts Used

## Abstraction

```python
class CarrierAdapter(ABC):

    @abstractmethod
    def get_rate():
        pass

    @abstractmethod
    def get_tracking():
        pass
```

---

## Inheritance

```python
class DHLAdapter(CarrierAdapter)
```

```python
class FedExAdapter(CarrierAdapter)
```

```python
class UPSAdapter(CarrierAdapter)
```

```python
class BlueDartAdapter(CarrierAdapter)
```

Each carrier inherits from `CarrierAdapter`.

---

## Polymorphism

All carrier classes implement the same methods.

```
get_rate()

get_tracking()
```

The method name is the same, but each carrier returns its own data.

---

# Project Flow

```
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

```
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

```
Client
      │
      ▼
Origin
Destination
Weight
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
Sort by Price
      │
      ▼
Return Response
```

---

# Running Tests

Run the following command.

```bash
python -m pytest
```

Example Output

```
=============================
8 passed
=============================
```

---



