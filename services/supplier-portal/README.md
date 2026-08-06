
                  Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A FastAPI-based microservice for managing Supplier Purchase Orders and Invoices as part of the Enterprise AI Cognitive Supply Chain Platform.

---

# Overview

The Supplier Portal Service enables suppliers to:

- View Purchase Orders
- Update Purchase Order details
- Acknowledge Purchase Orders
- Perform controlled Purchase Order state transitions
- Submit Invoices
- Upload Invoice PDF documents
- Track Purchase Order transition history

This service currently uses **in-memory storage** and is designed to be extended later with databases, Kafka messaging, and object storage.

---

# Technology Stack

- Python 3.x
- FastAPI
- Pydantic
- Uvicorn
- Pytest

---

# Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Request Successful |
| 201 | Resource Created |
| 400 | Invalid Request |
| 404 | Resource Not Found |
| 409 | Duplicate Resource |
| 422 |  Unprocessable Content |

# Project Structure

```
supplier-portal/
│
├── app/
│   ├── core/
│   │   └── config.py
│   │
│   ├── routes/
│   │   ├── purchase_order.py
│   │   └── invoice.py
│   │
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   └── invoice.py
│   │
│   ├── services/
│   │   ├── purchase_order_service.py
│   │   └── invoice_service.py
│   │
│   └── main.py
│
├── tests/
│   ├── test_po.py
│   └── test_invoice.py
│
├── uploads/
│
├── requirements.txt
└── README.md
```

---

# Features

## Purchase Orders

- Create Purchase Order
- Get All Purchase Orders
- Get Purchase Order by ID
- Update Purchase Order
- Delete Purchase Order
- Purchase Order Acknowledgement
- Purchase Order State Machine
- Purchase Order Transition History

---

## Invoices

- Submit Invoice
- Upload Invoice PDF
- Store uploaded PDF locally
- Return uploaded document path

---

# Purchase Order Lifecycle

                Cancelled
               ▲
               │
Draft ──► Sent ──► Acknowledged ──► Fulfilled
   │          │            │
   └──────────┴────────────┘

Cancellation is allowed from:

- Draft
- Sent
- Acknowledged

No further transitions are allowed after:

- Fulfilled
- Cancelled

---

# State Machine

The Purchase Order status is controlled through a state machine.

Allowed transitions are:

| Current Status | Allowed Next Status |
|---------------|--------------------|
| Draft | Sent, Cancelled |
| Sent | Acknowledged, Cancelled |
| Acknowledged | Fulfilled, Cancelled |
| Fulfilled | None |
| Cancelled | None |

Any invalid transition returns:

```
400 Bad Request
```

Example:

```
Fulfilled
      │
      ▼

Draft

❌ Illegal Transition
```

---

# Purchase Order History

Every successful transition is recorded.

Example:

```json
[
    {
        "from_status": "draft",
        "to_status": "sent",
        "timestamp": "2026-07-25T10:15:22"
    },
    {
        "from_status": "sent",
        "to_status": "acknowledged",
        "timestamp": "2026-07-25T10:20:41"
    }
]
```

---

# Invoice Upload

Invoices can have an associated PDF document.

Uploaded files are stored inside:

```
uploads/
```

Example:

```
uploads/INV1001.pdf
```

The invoice response includes:

```json
{
    "document_url": "uploads/INV1001.pdf"
}
```

---

# Validation

## Purchase Orders

- Duplicate Purchase Orders are rejected.
- Invalid state transitions are rejected.
- Purchase Orders cannot bypass the state machine.

---

## Invoice Upload

The service validates:

### File Type

Only:

```
application/pdf
```

is accepted.

---

### PDF Signature

Uploaded files must contain a valid PDF signature.

Files renamed as ".pdf" but containing other content are rejected.

---

### Maximum File Size

Maximum allowed:

```
10 MB
```

---

### Path Traversal Protection

Invoice filenames are sanitized before saving to prevent writing outside the uploads directory.

---

# API Endpoints

## Purchase Orders

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/purchase-orders` | Create Purchase Order |
| GET | `/api/v1/purchase-orders` | Get All Purchase Orders |
| GET | `/api/v1/purchase-orders/{po_number}` | Get Purchase Order |
| PUT | `/api/v1/purchase-orders/{po_number}` | Update Purchase Order |
| DELETE | `/api/v1/purchase-orders/{po_number}` | Delete Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/acknowledge` | Acknowledge Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/transition` | Change Purchase Order Status |

---

## Invoices

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/invoices` | Submit Invoice |
| POST | `/api/v1/invoices/{invoice_number}/document` | Upload Invoice PDF |

---

# Running the Project

Install dependencies

```bash
pip install -r requirements.txt
```

Run the application

```bash
python -m uvicorn app.main:app --reload
```

Swagger UI

```
http://127.0.0.1:8000/docs
```



# Running Tests

Run all tests

```bash
python -m pytest
```

Run Purchase Order tests

```bash
python -m pytest tests/test_purchase_order.py
```

Run Invoice tests

```bash
python -m pytest tests/test_invoices.py
```

---

# Test Coverage

Purchase Order

- Create Purchase Order
- Get All Purchase Orders
- Get Purchase Order by ID
- Update Purchase Order
- Delete Purchase Order
- Valid Purchase Order Acknowledgement
- Valid State Transition
- Illegal State Transition
- Purchase Order History Verification

Invoice

- Create Invoice
- Upload Valid PDF
- Reject Invalid File Type
- Reject Invalid PDF Signature

# Current Storage

This project currently uses in-memory dictionaries.

```python
purchase_orders = {}
```

```python
invoices = {}
```

No database is used in the current implementation.

---
# Security

The service includes the following validations:

- Purchase Order state changes are only allowed through the state machine.
- Duplicate Purchase Orders are rejected.
- Duplicate Invoices are rejected.
- Only PDF files are accepted.
- Uploaded files must contain a valid PDF signature.
- Maximum upload size is 10 MB.
- Invoice filenames are sanitized before saving.
- Path traversal attacks are prevented.



# Future Enhancements

- PostgreSQL Integration
- SQLAlchemy ORM
- Repository Layer
- Kafka Integration
- MinIO Object Storage
- JWT Authentication
- Docker Support
- Kubernetes Deployment
- CI/CD Pipeline
- Audit Logging
- Monitoring
---





