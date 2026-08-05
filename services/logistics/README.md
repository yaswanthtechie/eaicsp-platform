# 🚚 Logistics Service API

A FastAPI-based Logistics Management System for managing shipments, tracking delivery status, comparing carrier rates, and integrating multiple delivery providers.

The project follows clean architecture principles and uses the **Adapter Design Pattern** for carrier integration.

## Features

- Shipment creation and management
- Shipment status tracking
- Shipment history
- Carrier quote comparison
- Cheapest, fastest, and reliable carrier selection
- Retry mechanism for failed carrier requests
- Async bulk quote processing
- Automated Pytest testing


# 📌 Project Description

The Logistics Service API provides backend services for delivery management.

Users can:

- Create shipments
- View shipment details
- Update shipment status
- Delete shipments
- Track shipment history
- Generate carrier quotations
- Select carriers based on:
  - Lowest price
  - Fast delivery
  - Reliability score


# ✨ Main Features

## Shipment Management

Supported operations:

✔ Create shipment  
✔ Get all shipments  
✔ Get shipment by ID  
✔ Update status  
✔ Delete shipment  


## Tracking System

Every shipment stores tracking events.

Tracking information:

- Shipment ID
- Status
- Location
- Timestamp


## Carrier Integration

Supported carriers:

- DHL
- FedEx
- UPS
- BlueDart


## Quote Management

Provides:

- Cheapest carrier
- Fastest carrier
- Most reliable carrier


## Reliability Features

- Automatic retry handling
- Carrier failure management
- Warning responses instead of application failure


## Performance

Uses:

- asyncio
- Non-blocking execution
- Parallel quote processing


# 🛠 Technology Stack


| Technology | Purpose |
|------------|---------|
| Python | Programming Language |
| FastAPI | REST API Framework |
| Pydantic | Data Validation |
| Uvicorn | ASGI Server |
| Tenacity | Retry Handling |
| Asyncio | Async Processing |
| Pytest | Testing |



# 🏗 System Architecture

             Client
                |
                |
          FastAPI Routes
                |
                |
      Shipment Service Layer
                |
   ----------------------------
   |            |             |
   Shipment Quote History
Management System Tracking
|
|
Carrier Adapter Layer
|

| | | |
DHL FedEx UPS BlueDart


# 📂 Project Structure

logistics/

│
├── app/
│
│ ├── main.py
│ ├── routes/
│ │ └── shipments.py
│ │
│ ├── schemas/
│ │ └── shipment.py
│ │
│ └── services/
│ ├── shipment_service.py
│ │
│ └── carriers/
│ ├── base.py
│ ├── dhl.py
│ ├── fedex.py
│ ├── ups.py
│ └── bluedart.py
│
├── tests/
│ ├── test_carriers.py
│ └── test_quote_and_history.py
│
├── requirements.txt
└── README.md



# 📁 Folder Explanation


## main.py

Responsible for:

- Creating FastAPI application
- Registering routes
- Running API


## routes/shipments.py

Contains shipment endpoints.

Examples:


POST /shipments

GET /shipments

PUT /shipments/{id}

DELETE /shipments/{id}



## schemas/shipment.py

Contains Pydantic models:

- ShipmentCreate
- ShipmentEvent
- CarrierRate
- QuoteRequest
- QuoteResponse


Responsibilities:

- Request validation
- Response formatting


## services/shipment_service.py

Contains business logic.

Handles:

- Shipment storage
- Status validation
- History creation
- Quote generation
- Carrier sorting
- Bulk processing


## services/carriers/

Contains carrier adapters:


base.py
dhl.py
fedex.py
ups.py
bluedart.py


Each carrier follows the same interface.


# ⚙ Installation


## Clone Repository


```bash
git clone <repository-url>

Move into project:

cd logistics
Create Virtual Environment

Windows:

python -m venv venv

Activate:

venv\Scripts\activate

Linux/Mac:

source venv/bin/activate
Install Dependencies
pip install -r requirements.txt
▶ Run Application
uvicorn app.main:app --reload

Application:

http://127.0.0.1:8000
📖 API Documentation

Swagger:

http://127.0.0.1:8000/docs

ReDoc:

http://127.0.0.1:8000/redoc
🚚 Shipment APIs

Base URL:

/api/v1/shipments

Create Shipment

Endpoint:

POST /api/v1/shipments


Request:

{
 "shipment_id":100,
 "origin":"Hyderabad",
 "destination":"Mumbai",
 "carrier":"dhl",
 "status":"pending",
 "estimated_delivery":"2027-01-01",
 "weight_kg":12.5
}


Response:

{
 "shipment_id":100,
 "status":"pending"
}
# Get All Shipments


Endpoint:


GET /api/v1/shipments



Returns all available shipments.


---

# Get Shipment By ID


Endpoint:


GET /api/v1/shipments/{shipment_id}



Example:


GET /api/v1/shipments/100



---

# Update Shipment Status


Endpoint:


PUT /api/v1/shipments/{shipment_id}



The system checks whether the status change is valid before updating.


---

# Delete Shipment


Endpoint:


DELETE /api/v1/shipments/{shipment_id}



Deletes:

- Shipment information
- Shipment history



# 📍 Shipment History


Endpoint:


GET /api/v1/shipments/{shipment_id}/history



Response:

```json
[
 {
  "shipment_id":100,
  "status":"pending",
  "location":"Hyderabad"
 },
 {
  "shipment_id":100,
  "status":"in_transit",
  "location":"Mumbai"
 }
]
Shipment Status Flow

Allowed status transitions:

pending
   |
   v
in_transit
   |
   +----------------+
   |                |
   v                v
delayed        delivered
   |
   v
in_transit


Invalid transition:

delivered → pending

Response:

400 Bad Request
💰 Carrier Quote System

The quote system collects delivery prices from all carriers and selects the best option based on user preference.

Quote API

Endpoint:

POST /api/v1/shipments/quote

Request:

{
 "origin":"Hyderabad",
 "destination":"Mumbai",
 "weight_kg":10,
 "preference":"cheapest"
}


Response:

{
 "rates":[
  {
   "carrier":"bluedart",
   "price":750,
   "estimated_days":2,
   "reliability_score":0.90
  }
 ],
 "warnings":[]
}

Quote Selection Methods
1. Cheapest Carrier

Selects carrier with minimum price.

Sorting:

price ascending

Example:

BlueDart

Price: 750
2. Fastest Carrier

Selects carrier with minimum delivery time.

Sorting:

estimated_days ascending

Example:

DHL

Delivery: 2 days
3. Most Reliable Carrier

Uses reliability calculation:

score =

(reliability × 100)
-
(price × 0.01)
-
delivery_days


Example:

UPS

Reliability: 0.95

🚛 Carrier Integration

The project uses the Adapter Design Pattern.

Architecture:

             Carrier Adapter

                    |
     --------------------------------
     |              |       |       |
    DHL           FedEx    UPS   BlueDart


Shipment service communicates with the adapter instead of directly communicating with carriers.

Flow:

Shipment Service

        |

Carrier Interface

        |

Carrier Implementation
Why Adapter Pattern?
Loose Coupling

Business logic does not depend on individual carrier classes.

Easy Expansion

New carriers can be added easily.

Example:

amazon.py

without modifying existing shipment logic.

Independent Carrier Logic

Each carrier manages:

Rate calculation
Tracking information
API communication
Carrier Adapter Interface

File:

base.py

Contains common methods:

get_rate()

get_tracking()


Every carrier implements these methods.

📦 Carrier Details
DHL
Price: 850

Delivery Time: 2 days

Reliability: 0.87

FedEx
Price: 950

Delivery Time: 3 days

Reliability: 0.92


FedEx simulates temporary failures.

Failure chance:

30%
UPS
Price: 900

Delivery Time: 4 days

Reliability: 0.95

BlueDart
Price: 750

Delivery Time: 2 days

Reliability: 0.90

🔁 Retry Mechanism

Carrier APIs may fail because of:

Network issues
Timeout
Temporary service problems

The project uses:

Tenacity Library
Retry Configuration

Maximum attempts:

3 retries

Retry delay:

Attempt 1 → 1 second

Attempt 2 → 2 seconds

Attempt 3 → 4 seconds


Flow:

Request Carrier Rate

        |

Check Response

        |

Failure?

        |

Retry Request

        |

Return Result

Error Handling

Carrier failure does not stop the complete quote process.

Example:

If FedEx fails:

{
 "warnings":[
    "FedEx unavailable"
 ]
}
# ⚡ Bulk Quote Processing


The system supports multiple quote requests at the same time using asynchronous processing.


Technology:


asyncio.gather()



Example:



Request 1 → Hyderabad to Mumbai

Request 2 → Delhi to Chennai

Request 3 → Pune to Bangalore



Traditional processing:



Request 1
(wait)

Request 2
(wait)

Request 3



Async processing:



Request 1
Request 2
Request 3

Together



Benefits:

- Faster response time
- Better performance
- Handles multiple users



# 🧪 Testing


Testing Framework:


Pytest



Run tests:


```bash
python -m pytest -v
Code Coverage

Run coverage:

coverage run -m pytest

coverage report -m


Example:

TOTAL

Coverage: 95%+

Test Cases Covered
Carrier Tests

File:

test_carriers.py

Covered:

✔ DHL rate calculation
✔ DHL tracking
✔ FedEx rate calculation
✔ FedEx tracking
✔ UPS rate calculation
✔ UPS tracking
✔ BlueDart rate calculation
✔ BlueDart tracking
✔ Retry handling

Shipment Tests

File:

test_quote_and_history.py

Covered:

✔ Create shipment

✔ Get shipment details

✔ Delete shipment

✔ Shipment history

✔ Valid status transition

✔ Invalid status transition

✔ Quote sorting

✔ Carrier failure handling

✔ Bulk quote processing

🏛 Business Logic Flow

Complete request flow:

Client

 |

API Endpoint

 |

Shipment Route

 |

Shipment Service

 |

Carrier Adapter

 |

Carrier Provider

 |

Response

💾 Current Storage

The current implementation uses:

In-memory Dictionary Storage

Example:

shipments = {}

shipment_events = {}


Advantages:

Simple implementation
Fast execution
Easy testing

Future versions can use:

PostgreSQL
MySQL
MongoDB
🚀 Future Enhancements
Database Integration

Replace memory storage with:

PostgreSQL
MySQL
Authentication

Add:

JWT Authentication
User roles
API security
Redis Cache

Use Redis for:

Carrier quote caching
Faster response time
Real Carrier APIs

Integrate:

DHL API
FedEx API
UPS API
Background Workers

Use:

Celery
RabbitMQ

For:

Notifications
Tracking updates
📚 Technology Explanation
FastAPI

Used for:

REST API creation
Request handling
Automatic API documentation
Pydantic

Used for:

Request validation
Schema management
Tenacity

Used for:

Retry failed carrier requests
Handling temporary errors
Asyncio

Used for:

Parallel quote processing
Non-blocking execution
Pytest

Used for:

Automated testing
Code reliability
Adapter Pattern

Used for:

Carrier integration
Maintainable architecture
👨‍💻 Author
FastAPI Logistics Service Project

Built using:

Python
FastAPI
Pydantic
Asyncio
Tenacity
Pytest

