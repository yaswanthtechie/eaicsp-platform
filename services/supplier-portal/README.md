# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A FastAPI-based microservice for managing supplier purchase orders, invoices, document uploads, state transitions, transition history, and supplier performance metrics.

---

# Overview

The Supplier Portal Service enables suppliers and procurement teams to:

- Create purchase orders
- Update purchase orders
- Delete purchase orders
- Retrieve purchase orders
- Acknowledge purchase orders
- Perform controlled state transitions
- Submit invoices
- Upload invoice PDF documents
- Download invoice documents
- Track purchase-order history
- Calculate supplier statistics

This service currently uses in-memory storage and can later be extended with:

- PostgreSQL
- Kafka
- MinIO
- Redis
- Docker
- Kubernetes

---

# Technology Stack

- Python 3.14
- FastAPI
- Pydantic
- Pytest
- Uvicorn

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

- Create purchase orders
- Retrieve purchase orders
- Update purchase orders
- Delete purchase orders
- Acknowledge purchase orders
- Perform controlled state transitions
- Maintain transition history
- Store actual delivery dates

---

# Invoice Features

- Create invoices
- Upload invoice PDFs
- Download invoice PDFs
- Validate invoice amounts
- Reject duplicate invoices
- Validate purchase-order status

---

# Supplier Statistics Features

- Purchase-order count
- On-time delivery percentage
- Average invoice cycle time

---

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
| Draft | Sent, Cancelled |
| Sent | Acknowledged, Cancelled |
| Acknowledged | Fulfilled, Cancelled |
| Fulfilled | None |
| Cancelled | None |

---

# Purchase Order History

Every transition is stored.

Example:

```json
[
    {
        "actor": "procurement",
        "from_status": "draft",
        "to_status": "sent",
        "timestamp": "2026-08-01T10:00:00"
    },
    {
        "actor": "supplier",
        "from_status": "sent",
        "to_status": "acknowledged",
        "timestamp": "2026-08-01T11:00:00"
    },
    {
        "actor": "logistics",
        "from_status": "acknowledged",
        "to_status": "fulfilled",
        "timestamp": "2026-08-02T09:00:00"
    }
]
```

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

# Invoice Validation Rules

## Duplicate Invoice Validation

Duplicate invoices are rejected.

---

## Purchase Order Validation

Invoices can only be created for valid purchase orders.

---

## Invoice Amount Validation

Invoice amounts must remain within the permitted tolerance range.

---

## File Validation

Only PDF files are accepted.

```text
application/pdf
```

---

## PDF Signature Validation

Only valid PDF documents are accepted.

---

## File Size Validation

Maximum file size:

```text
10 MB
```

---

## Path Traversal Protection

Invoice filenames are sanitized before storage.

---

# API Endpoints

## Purchase Orders

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/purchase-orders` | Create purchase order |
| GET | `/api/v1/purchase-orders` | Get all purchase orders |
| GET | `/api/v1/purchase-orders/{po_number}` | Get purchase order |
| PUT | `/api/v1/purchase-orders/{po_number}` | Update purchase order |
| DELETE | `/api/v1/purchase-orders/{po_number}` | Delete purchase order |
| POST | `/api/v1/purchase-orders/{po_number}/acknowledge` | Acknowledge purchase order |
| POST | `/api/v1/purchase-orders/{po_number}/transition` | Transition purchase order |

---

## Invoices

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/invoices` | Create invoice |
| POST | `/api/v1/invoices/{invoice_number}/document` | Upload document |
| GET | `/api/v1/invoices/{invoice_number}/document` | Download document |

---

## Supplier Statistics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/suppliers/{supplier_id}/stats` | Get supplier statistics |

---

# Running the Application

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python -m uvicorn app.main:app --reload
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

# Running Tests

Run all tests:

```bash
python -m pytest -v
```

Run purchase-order tests:

```bash
python -m pytest tests/test_purchase_order.py -v
```

Run invoice tests:

```bash
python -m pytest tests/test_invoices.py -v
```

Run supplier-statistics tests:

```bash
python -m pytest tests/test_supplier_stats.py -v
```

---

# Test Coverage

## Purchase Orders

- Create purchase order
- Retrieve purchase orders
- Update purchase orders
- Delete purchase orders
- Acknowledge purchase orders
- Validate legal transitions
- Validate illegal transitions
- Verify transition history

---

## Invoices

- Create invoice
- Upload PDF
- Download PDF
- Validate invoice amount
- Reject invalid files
- Reject duplicate invoices

---

## Supplier Statistics

- Purchase-order count
- On-time delivery percentage
- Average invoice cycle time

---

# Current Storage

```python
purchase_orders = {}
invoices = {}
po_events = []
```

---

# Security

- Duplicate purchase-order protection
- Duplicate invoice protection
- State-machine validation
- File-type validation
- PDF-signature validation
- Maximum file-size validation
- Path-traversal protection

---

# Future Enhancements

- PostgreSQL integration
- SQLAlchemy ORM
- Kafka integration
- Redis integration
- MinIO integration
- JWT authentication
- Docker support
- Kubernetes deployment
- Monitoring and logging