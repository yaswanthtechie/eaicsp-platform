# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A FastAPI-based microservice for managing supplier purchase orders, invoices, document uploads, state transitions, transition history, and supplier performance metrics.


---

# 1. Overview

The Supplier Portal Service provides APIs for procurement teams and suppliers to manage the Purchase Order and Invoice lifecycle.

The service currently supports:

- Create Purchase Orders
- Retrieve all Purchase Orders
- Retrieve a Purchase Order by PO number
- Update Purchase Orders
- Delete Purchase Orders
- Acknowledge Purchase Orders
- Controlled Purchase Order state transitions
- Purchase Order transition history
- Purchase Order event retrieval
- Actual delivery date tracking
- Create invoices
- Validate invoice numbers
- Validate supplier IDs
- Validate Purchase Order existence
- Validate Purchase Order status before invoice creation
- Validate invoice amount tolerance
- Prevent duplicate invoices
- Upload invoice PDF documents
- Download invoice PDF documents
- Validate PDF content type
- Validate PDF signature
- Validate maximum PDF file size
- Protect invoice document paths from path traversal
- Calculate supplier performance statistics
- Automated API/unit testing using Pytest

---


# 2. Technology Stack

| Technology | Purpose |
|------------|---------|
| Python 3.14 | Backend programming language |
| FastAPI | REST API framework |
| Pydantic | Request and response validation |
| Uvicorn | ASGI application server |
| Pytest | Automated testing |
| HTTPX | API testing support |

---

# Response Codes

| Status Code | Description |
|------------|-------------|
| 200 | Request successful |
| 201 | Resource created |
| 400 | Invalid request |
| 404 | Resource not found |
| 409 | Duplicate resource |
| 422 | Validation error |

---

# Project Structure

```text
supplier-portal/
│
├── app/
│
│   ├── routes/
│   │   ├── purchase_order_routes.py
│   │   ├── invoice_routes.py
│   │   └── supplier_stats_routes.py
│   │
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   ├── invoice.py
│   │   └── supplier_stats.py
│   │
│   ├── services/
│   │   ├── purchase_order_service.py
│   │   ├── invoice_service.py
│   │   └── supplier_stats_service.py
│   │
│   └── main.py
│
├── tests/
│   ├── test_purchase_order.py
│   ├── test_invoices.py
│   └── test_supplier_stats.py
│
├── uploads/
│
├── requirements.txt
│
└── README.md
```

---

# Purchase Order Features

- Create Purchase Order
Get all Purchase Orders
Get Purchase Order by PO number
Update Purchase Order
Delete Purchase Order
Acknowledge Purchase Order
Transition Purchase Order status
Retrieve Purchase Order events
Maintain transition history
Track the actor responsible for a transition
Track transition timestamps
Track expected delivery date
Track actual delivery date
Validate legal state transitions
Reject illegal state transitions
Prevent duplicate Purchase Orders
---


# Invoice Features

- Create invoice
Validate invoice number
Validate supplier ID
Validate Purchase Order existence
Validate Purchase Order status
Validate invoice amount
Apply invoice amount tolerance
Prevent duplicate invoices
Upload invoice PDF
Download invoice PDF
Validate PDF content type
Validate PDF signature
Validate PDF size
Protect upload paths from traversal attacks

---

# Supplier Statistics Features

- Purchase-order count
- On-time delivery percentage
- Average invoice cycle time

---

# po and invoice flow


                     ADMIN

                        │ 

                        ▼ 

               Create Purchase Order 

                      │ 
 
                      ▼ 

              PO Status = Draft 

                     │ 

                     ▼ 

             Transition to Sent 

                     │ 

                     ▼ 

            Supplier Acknowledges PO 

                     │ 

                     ▼ 

            PO Status = Acknowledged 

                     │ 

                     ▼ 

              PO Fulfilled 

                    │ 

                    ▼ 

              Submit Invoice 

                    │ 

                    ▼ 

            Upload Invoice PDF 

                    │ 

                    ▼ 

        Invoice Stored Successfully


# Purchase Order Data


A Purchase Order contains information such as:

po_number
supplier_id
items
total_amount
status
created_at
expected_delivery
actual_delivery_date
history

Every newly created Purchase Order starts in:

 ---> draft



# Purchase Order Lifecycle

```text
                    Cancelled
                   ▲
                   │

Draft ───► Sent ───► Acknowledged ───► Fulfilled
```

---

# State Machine

| Current Status | Allowed Status |
            |---|---|
| Draft          | Sent, Cancelled |
| Sent           | Acknowledged, Cancelled |
| Acknowledged   | Fulfilled, Cancelled |
| Fulfilled      | None |
| Cancelled      | None |

---

# Purchase Order Transition API


Purchase Order state changes are performed using:

POST /api/v1/purchase-orders/{po_number}/transition

Example request:

{
    "target_state": "sent",
    "actor": "admin"
}

Example acknowledgement:

{
    "target_state": "acknowledged",
    "actor": "supplier"
}

Example fulfilment:

{
    "target_state": "fulfilled",
    "actor": "admin"
}

The actor field records who performed the state transition.



# Illegal Purchase Order Transitions


Illegal transitions return HTTP 400.

Example:

{
    "target_state": "acknowledged",
    "actor": "supplier"
}

when the current state is:

draft

will be rejected.

Example error:

Cannot go from draft to acknowledged. Allowed: sent, cancelled.

For a state with no further transitions:

Cannot go from fulfilled to draft. Allowed: none.


# Purchase Order History

Every transition is stored.

Each event contains:

- Actor
- Previous status
- New status
- Timestamp

Example:

```json
[
    {
        "actor": "harshi",
        "from_status": "draft",
        "to_status": "sent",
        "timestamp": "2026-08-01T10:00:00"
    },
    {
        "actor": "siri",
        "from_status": "sent",
        "to_status": "acknowledged",
        "timestamp": "2026-08-01T11:00:00"
    },
    {
        "actor": "dhanush",
        "from_status": "acknowledged",
        "to_status": "fulfilled",
        "timestamp": "2026-08-02T09:00:00"
    }
]
```

# Purchase Order Events Endpoint

Purchase Order transition events can be retrieved using:

GET /api/v1/purchase-orders/{po_number}/events

This endpoint returns the complete event history for the Purchase Order.

Example response:

[
    {
        "actor": "admin",
        "from_status": "draft",
        "to_status": "sent",
        "timestamp": "2026-08-06T10:00:00"
    },
    {
        "actor": "supplier",
        "from_status": "sent",
        "to_status": "acknowledged",
        "timestamp": "2026-08-06T11:00:00"
    }
]
---

# Actual Delivery Tracking

Every fulfilled purchase order stores:

```python
expected_delivery
actual_delivery_date
```

Example:

```json
{
    "expected_delivery": "2026-08-02",
    "actual_delivery_date": "2026-08-01"
}
```

---

# Supplier Statistics

## Purchase-order count

```text
po_count = total purchase orders for a supplier
```

---

## On-time delivery percentage

### Formula

```text
actual_delivery_date <= expected_delivery
```

```text
on_time_percentage =
(on_time_orders / total_orders) × 100
```

### Example

| Purchase Order | Expected Delivery | Actual Delivery | Result |
|---|---|---|---|
| PO1001 | 2026-08-02 | 2026-08-01 | On time |
| PO1002 | 2026-08-03 | 2026-08-04 | Late |

```text
(1 / 2) × 100 = 50%
```

---

## Average invoice cycle time

### Formula

```text
invoice_date - purchase_order_created_date
```

### Example

| Purchase Order Created | Invoice Created | Cycle Time |
|---|---|---|
| July 20 | July 23 | 3 days |
| July 22 | July 26 | 4 days |

```text
(3 + 4) / 2 = 3.5 days
```

---
## invoices
---------------
# Invoice Data

An Invoice contains:

invoice_number
po_number
supplier_id
amount
invoice_date
document_url

Example:

{
    "invoice_number": "INV1001",
    "po_number": "PO1001",
    "supplier_id": "SUP001",
    "amount": 50000,
    "invoice_date": "2026-08-06",
    "document_url": null
}

# Invoice Number Validation

Invoice numbers are validated using the following pattern:

^[A-Za-z0-9_-]+$

Allowed examples:

INV1001
INV-1001
INV_1001

Invalid examples include values containing unsupported characters.


#  Supplier ID Validation


Supplier IDs are also validated using:

^[A-Za-z0-9_-]+$

Allowed examples:

SUP001
SUP-001
SUP_001

This validation is performed at the Pydantic schema level.

Invalid supplier IDs are rejected before the value reaches the filesystem.

This is especially important because supplier_id is used as part of the invoice document directory path.


# Purchase Order Validation for Invoices


An invoice cannot be created if the referenced Purchase Order does not exist.

Example:

Invoice PO number → PO1001

If PO1001 does not exist, invoice creation is rejected.

Example error:

Purchase Order not found.


# Purchase Order Status Validation for Invoices


Invoices can only be created when the Purchase Order is in an appropriate state.

The currently supported invoice states are:

Acknowledged
Fulfilled

Invoices are rejected for Purchase Orders that are still:

Draft
Sent

This prevents invoices from being submitted against Purchase Orders that have not yet reached the required lifecycle stage.


# Invoice Amount Validation


Invoice amounts are checked against the Purchase Order total amount.

The service uses a named tolerance constant:

TOLERANCE = 0.05

The permitted range is calculated as:

minimum_amount = po_amount * (1 - TOLERANCE)

maximum_amount = po_amount * (1 + TOLERANCE)

Therefore, the invoice amount can be within:

95% to 105%

of the Purchase Order amount.

Example:

PO amount = 1000

Minimum = 1000 × 0.95 = 950
Maximum = 1000 × 1.05 = 1050

An invoice outside this range is rejected.

# Duplicate Invoice Validation


Duplicate invoices are rejected.

The service checks the combination of:

invoice_number
supplier_id

before creating an invoice.

This prevents the same supplier from creating the same invoice number more than once.


# Invoice PDF Upload


Invoice documents are uploaded using:

POST /api/v1/invoices/{invoice_number}/document

Only PDF documents are accepted.

The expected content type is:

application/pdf

# PDF Content Validation

The service performs multiple PDF validations.

Content-Type validation

The uploaded file must have:

application/pdf
PDF signature validation

The actual file contents must begin with:

%PDF-

This prevents a file from being accepted simply because its HTTP content type claims to be a PDF.


# Invoice PDF Size Validation


The maximum invoice document size is:

10 MB

The service validates the size both:

Before reading when file size information is available.
After reading the file contents.

This provides an additional protection against oversized uploads.


# Invoice Document Path Protection


Invoice documents are stored using the supplier ID as a directory name.

The upload root is resolved to an absolute path using:

upload_root = Path(UPLOAD_DIR).resolve()

The final document path is then resolved and checked using:

if not final_path.is_relative_to(upload_root):
    raise ValueError("Invalid file path.")

This is safer than using:

startswith()

because startswith() compares text rather than actual filesystem path structure.

The directory is created only after the final path has been confirmed to be safe.


# Invoice Document Storage
 

Invoice documents are stored under the upload directory using the supplier ID.

Conceptually:

uploads/
└── SUP001/
    └── INV1001.pdf

The resulting document path is stored in:

document_url

# Invoice Document Download


Invoice documents can be retrieved using:

GET /api/v1/invoices/{invoice_number}/document

The service verifies:

Invoice exists
Document path exists
Stored document exists on disk

If the document does not exist, the service returns an appro


# API Endpoints


Purchase Order APIs

Method          Endpoint	                                    Description
------------------------------------------------------------------------------------

POST	   /api/v1/purchase-orders	                        Create Purchase Order
GET    	   /api/v1/purchase-orders	                        Get all Purchase Orders
GET	       /api/v1/purchase-orders/{po_number}	            Get Purchase Order
PUT	       /api/v1/purchase-orders/{po_number}	            Update Purchase Order
DELETE	   /api/v1/purchase-orders/{po_number}	            Delete Purchase Order
POST	   /api/v1/purchase-orders/{po_number}/acknowledge	Acknowledge Purchase Order
POST	   /api/v1/purchase-orders/{po_number}/transition	Transition Purchase Order
GET	       /api/v1/purchase-orders/{po_number}/events	    Get Purchase Order transition 


# Invoice APIs

Method	          Endpoint	                            Description
--------------------------------------------------------------------------
GET          /api/v1/invoices                           get  by all
POST	 	 /api/v1/invoices                           Create Invoice
POST	    /api/v1/invoices/{invoice_number}/document	Upload Invoice PDF
GET	        /api/v1/invoices/{invoice_number}/document	Download Invoice PDF


# Supplier Statistics API

Method	 Endpoint	                                 Description
--------------------------------------------------------------------------
GET   	/api/v1/suppliers/{supplier_id}/stats	Get supplier statistics

# Current Storage

The service currently uses in-memory Python data structures.

Purchase Orders:

purchase_orders = {}

Invoices:

invoices = {}

Purchase Order events:

po_events = {}

Because the service currently uses in-memory storage, all data is lost when the application process is restarted.

A persistent database will be introduced in a future implementation.

# Testing

The service uses Pytest for automated testing.

The current test modules are:

tests/
├── test_purchase_order.py
├── test_invoices.py
└── test_supplier_stats.py

The tests cover:

Purchase Orders
Create Purchase Order
Retrieve Purchase Order
Retrieve all Purchase Orders
Update Purchase Order
Delete Purchase Order
Acknowledge Purchase Order
Legal state transitions
Illegal state transitions
Transition history
Purchase Order events
Actual delivery date
Invoices
Create Invoice
Duplicate invoice validation
Purchase Order validation
Purchase Order status validation
Invoice amount validation
PDF upload
Invalid file type rejection
Invalid PDF signature rejection
Maximum file size validation
Invoice document download
Supplier ID validation
Path traversal protection
Supplier Statistics
Purchase Order count
On-time delivery percentage
Average invoice cycle time


# Pytest Configuration

The service contains:

pytest.ini

with:

[pytest]
pythonpath = .
testpaths = tests

This configuration allows Pytest to correctly discover the application and test directories.

# Running Tests

Run all tests:

python -m pytest -v

Run Purchase Order tests:

python -m pytest tests/test_purchase_order.py -v

Run Invoice tests:

python -m pytest tests/test_invoices.py -v

Run Supplier Statistics tests:

python -m pytest tests/test_supplier_stats.py -v


# Test Result

The current test suite contains:

39 tests

The latest successful test run completed with:

39 passed

There is currently a Starlette/HTTPX deprecation warning related to the test client, but the test suite passes successfully.

# Installation

Create and activate a virtual environment:

python -m venv venv

Activate the virtual environment on Windows PowerShell:

.\venv\Scripts\Activate.ps1

Install the required packages:

pip install -r requirements.txt


# Running the Application

From the supplier-portal directory, run:

python -m uvicorn app.main:app --reload

The application will normally be available at:

http://127.0.0.1:8000


# Swagger Documentation

FastAPI automatically provides interactive API documentation.

Open:

http://127.0.0.1:8000/docs

Swagger can be used to test:

Purchase Order APIs
Purchase Order transitions
Purchase Order event history
Invoice APIs
Invoice document uploads
Invoice document downloads
Supplier statistics


# Security and Validation

The service contains several validation and security controls.

Purchase Order
Duplicate Purchase Order protection
State-machine validation
Illegal transition rejection
Actor tracking
Transition timestamp tracking
Invoice
Invoice number validation
Supplier ID validation
Duplicate invoice protection
Purchase Order existence validation
Purchase Order status validation
Invoice amount tolerance validation
PDF content-type validation
PDF signature validation
Maximum file size validation
Safe filename handling
Path traversal protection


# Important Implementation Details
Invoice Tolerance

The invoice tolerance is centralized using:

TOLERANCE = 0.05

The allowed invoice range is calculated as:

minimum_amount = po_amount * (1 - TOLERANCE)
maximum_amount = po_amount * (1 + TOLERANCE)

This avoids hard-coding:

0.95
1.05

throughout the implementation.

Purchase Order Events

The Purchase Order event store is the source of truth for transition history.

Events contain:

actor
from_status
to_status
timestamp
Deleted Purchase Orders

Deleting a Purchase Order does not delete its audit events.

This preserves the historical record of transitions even after the active Purchase Order has been removed.

# Future Enhancements

The current service intentionally uses in-memory storage and local file storage.

Future enhancements can include:

PostgreSQL integration
SQLAlchemy ORM
Database migrations
Kafka integration
Redis integration
MinIO object storage
JWT authentication
Role-based access control
Docker support
Kubernetes deployment
Centralized configuration
Monitoring
Logging
Distributed tracing
API Gateway integration
CI/CD pipeline
Production-grade persistent audit storage


# Current Status

The Supplier Portal Service currently provides a working FastAPI backend for Purchase Orders, Invoices, invoice document management, Purchase Order state transitions, transition history, and supplier statistics.

Current implementation includes:

Purchase Order Management
        │
        ├── Create
        ├── Read
        ├── Update
        ├── Delete
        ├── Acknowledge
        ├── State Transition
        └── Event History
                │
                ▼
Invoice Management
        │
        ├── Create Invoice
        ├── Validate Invoice
        ├── Upload PDF
        └── Download PDF
                │
                ▼
Supplier Statistics
        │
        ├── PO Count
        ├── On-Time Delivery %
        └── Average Invoice Cycle Time
                │
                ▼
Automated Testing
        │
        ├── Purchase Order Tests
        ├── Invoice Tests
        └── Supplier Statistics Tests

The service is currently ready for the next development stage, where persistent storage and infrastructure components can be introduced.