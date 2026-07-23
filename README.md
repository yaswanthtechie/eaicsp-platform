# Logistics Service

A simple FastAPI-based logistics service for managing shipments and tracking shipments through different carrier adapters.

The project supports shipment CRUD operations, shipment status filtering, and a carrier adapter pattern for DHL, FedEx, and UPS.

---

## Features

- Create a shipment
- Get all shipments
- Get a shipment by ID
- Update a shipment
- Delete a shipment
- Filter shipments by status
- Shipment status validation using Enum
- Carrier adapter pattern
- DHL tracking adapter
- FedEx tracking adapter
- UPS tracking adapter
- Mock tracking data
- Automated tests using Pytest
- Interactive API documentation using Swagger UI

---
install
     Python
     FastAPI
     Uvicorn
     Pydantic
     Pytest
     Adapter Design Pattern
# Project Structure

```text
logistical service/
│
├── venv/
│
├── app/
│   ├── __init__.py
│   │
│   ├── main.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   └── shipment.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── shipment.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── shipment_service.py
│   │   │
│   │   └── carriers/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── dhl.py
│   │       ├── fedex.py
│   │       └── ups.py
│   │
│   ├── models/
│   │   └── __init__.py
│   │
│   └── core/
│       ├── __init__.py
│       └── config.py
│
├── tests/
│   ├── __init__.py
│   └── test_carriers.py
│
├── requirements.txt
│
└── README.md