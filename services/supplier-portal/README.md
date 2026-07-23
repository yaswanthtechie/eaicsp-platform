# Supplier Portal Service

## Overview

The Supplier Portal Service is a backend API built using **FastAPI** that allows suppliers to interact with Purchase Orders (POs) and Invoices.

This project is developed in stages:

- **Wednesday:** Purchase Order CRUD APIs
- **Thursday:** Purchase Order Acknowledgment & Invoice Submission
- **Friday:** Invoice PDF Upload

> **Note**
>
> - No database is used in this phase.
> - Data is stored in Python in-memory dictionaries.
> - Kafka and MinIO are not used yet.



# Project Goal

This service simulates how suppliers receive Purchase Orders from buyers.

A supplier can:

- View Purchase Orders
- Acknowledge a Purchase Order
- Submit an Invoice
- Upload Invoice PDF

---

# Purchase Order Flow

```
Buyer

   │

Create Purchase Order

   │

Status = draft

   │

Send Purchase Order

   │

Status = sent

   │

Supplier Acknowledges

   │

Status = acknowledged

   │

Supplier Delivers Goods

   │

Status = fulfilled
```

---

# Invoice Flow

```
Supplier

    │

Submit Invoice

    │

Invoice Created

    │

Upload PDF

    │

PDF Stored

    │

Invoice Updated
```

---
PO ---POST

{
  "po_number": "PO1001",
  "supplier_id": "SUP001",
  "items": [
    "Laptop",
    "Mouse"
  ],
  "total_amount": 50000,
  "status": "sent",
  "created_at": "2026-07-19T13:38:05.111Z",
  "expected_delivery": "2026-07-25"
}















# Wednesday Tasks

## 1. Create Purchase Order Schema

Purchase Order contains:

| Field | Description |
|--------|-------------|
| po_number | Purchase Order Number |
| supplier_id | Supplier Identifier |
| items | List of ordered products |
| total_amount | Total Purchase Order Amount |
| status | Current PO Status |
| created_at | PO Creation Date |
| expected_delivery | Expected Delivery Date |

---

## Purchase Order Status

Allowed values:

```
draft
sent
acknowledged
fulfilled
cancelled
```

These values are implemented using an Enum.

---

## Invoice Schema

Invoice contains:

| Field | Description |
|--------|-------------|
| invoice_number | Invoice Number |
| po_number | Purchase Order Number |
| supplier_id | Supplier Identifier |
| amount | Invoice Amount |
| submitted_at | Submission Date |
| status | Invoice Status |
| document_url | Uploaded PDF Path |

---

## CRUD APIs

### Create Purchase Order

```
POST /api/v1/purchase-orders
```

Creates a new Purchase Order.

---

### Get All Purchase Orders

```
GET /api/v1/purchase-orders
```

Returns all Purchase Orders.

---

### Get Purchase Order

```
GET /api/v1/purchase-orders/{po_number}
```

Returns a single Purchase Order.

---

### Update Purchase Order

```
PUT /api/v1/purchase-orders/{po_number}
```

Updates an existing Purchase Order.

---

### Delete Purchase Order

```
DELETE /api/v1/purchase-orders/{po_number}
```

Deletes a Purchase Order.

---

# Thursday Tasks

## Purchase Order Acknowledgment

Endpoint:

```
POST /api/v1/purchase-orders/{po_number}/acknowledge
```

Purpose:

The supplier confirms that the Purchase Order has been received.

Current status:

```
sent
```

changes to

```
acknowledged
```

Example:

Before:

```
PO1001

Status = sent
```

After:

```
PO1001

Status = acknowledged
```

---

## Submit Invoice

Endpoint

```
POST /api/v1/invoices
```

Example Request

```json
{
    "invoice_number":"INV1001",
    "po_number":"PO1001",
    "supplier_id":"SUP001",
    "amount":50000
}
```

This creates an invoice linked to a Purchase Order.

---

# Friday Tasks

## Upload Invoice PDF

Endpoint

```
POST /api/v1/invoices/{invoice_number}/document
```

Purpose

Upload the invoice PDF after the invoice is created.

The uploaded file is saved inside

```
uploads/
```

Example

Before

```
document_url = null
```

After upload

```
document_url = uploads/INV1001.pdf
```

---

## Validation Rules

### File Type

Only

```
application/pdf
```

is accepted.

Rejected:

```
jpg
png
docx
xlsx
```

---

### File Size

Maximum file size:

```
10 MB
```

If exceeded:

```
400 Bad Request
```

---

# In-Memory Storage

Since no database is used, data is stored in dictionaries.

Purchase Orders

```python
purchase_orders = {}
```

Invoices

```python
invoices = {}
```

Example

```python
purchase_orders = {
    "PO1001": {
        ...
    }
}
```

---

# Tests

## Test Purchase Order Acknowledgment

Given

```
Status = sent
```

When

```
POST /purchase-orders/PO1001/acknowledge
```

Then

```
Status = acknowledged
```

Expected Response

```
200 OK
```

---

## Test Invalid File Upload

Upload

```
invoice.jpg
```

Expected

```
400 Bad Request
```

Message

```
Only PDF files are allowed
```

---

# API Summary

| Method | Endpoint | Purpose |
|----------|-----------------------------------------------|---------------------------|
| POST | /purchase-orders | Create Purchase Order |
| GET | /purchase-orders | Get All Purchase Orders |
| GET | /purchase-orders/{po_number} | Get Purchase Order |
| PUT | /purchase-orders/{po_number} | Update Purchase Order |
| DELETE | /purchase-orders/{po_number} | Delete Purchase Order |
| POST | /purchase-orders/{po_number}/acknowledge | Acknowledge Purchase Order |
| POST | /invoices | Submit Invoice |
| POST | /invoices/{invoice_number}/document | Upload Invoice PDF |

---

# Future Enhancements

- PostgreSQL Database
- SQLAlchemy Models
- Kafka Integration
- MinIO File Storage
- Authentication & Authorization
- Supplier Dashboard
- Audit Logs