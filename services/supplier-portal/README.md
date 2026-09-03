# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for managing supplier-facing Purchase Orders, invoices, invoice documents, supplier operational statistics, and supplier performance scorecards.

The Supplier Portal Service is part of the **Enterprise AI Cognitive Supply Chain Platform** and integrates with the Platform Service for authentication and role-based authorization.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Features](#2-key-features)
3. [Architecture](#3-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Project Structure](#5-project-structure)
6. [Authentication and Authorization](#6-authentication-and-authorization)
7. [Purchase Order Management](#7-purchase-order-management)
8. [Invoice Management](#8-invoice-management)
9. [Invoice Document Management](#9-invoice-document-management)
10. [Supplier Statistics](#10-supplier-statistics)
11. [Supplier Performance Scorecard](#11-supplier-performance-scorecard)
12. [API Reference](#12-api-reference)
13. [HTTP Response Codes](#13-http-response-codes)
14. [Configuration](#14-configuration)
15. [Installation](#15-installation)
16. [Running the Services](#16-running-the-services)
17. [Swagger Documentation](#17-swagger-documentation)
18. [Testing](#18-testing)
19. [Business Rules](#19-business-rules)
20. [Security Controls](#20-security-controls)
21. [Storage](#21-storage)
22. [End-to-End Workflow](#22-end-to-end-workflow)
23. [Current Implementation Status](#23-current-implementation-status)
24. [Known Limitations](#24-known-limitations)
25. [Future Enhancements](#25-future-enhancements)

---

# 1. Overview

The **Supplier Portal Service** provides backend APIs for the supplier and procurement workflow.

The service currently manages four major functional areas:

```text
1. Purchase Order Management
2. Invoice Management
3. Supplier Statistics
4. Supplier Performance Scorecard
```

The overall business flow is:

```text
Purchase Order
      │
      ▼
   Draft
      │
      ▼
    Sent
      │
      ▼
Acknowledged
      │
      ▼
 Fulfilled
      │
      ▼
   Invoice
      │
      ▼
Invoice Validation
      │
      ▼
Invoice Document
      │
      ▼
Supplier Statistics
      │
      ▼
Supplier Scorecard
```

The service uses:

* **In-memory dictionaries** for Purchase Orders, invoices, and events
* **Local filesystem storage** for invoice PDF documents
* **Platform Service** for authentication and user identity verification

The implementation is structured so persistent infrastructure can be introduced in a later phase.

---

# 2. Key Features

## Purchase Orders

* Create Purchase Orders
* Retrieve all Purchase Orders
* Retrieve a Purchase Order by PO number
* Update Purchase Orders
* Delete Purchase Orders
* Supplier acknowledgement
* Controlled PO state transitions
* PO cancellation
* Illegal transition rejection
* Transition audit history
* Event retrieval
* Actor tracking
* Transition timestamps
* Expected delivery tracking
* Actual delivery tracking
* Duplicate PO protection
* Bulk Purchase Order sending

## Invoices

* Create invoices
* Retrieve invoices
* Validate invoice data
* Validate Purchase Order existence
* Validate Purchase Order status
* Validate supplier ownership
* Validate invoice line items
* Validate invoice amounts
* 5% amount tolerance
* Duplicate invoice protection
* Partial invoicing support
* Multiple invoice items
* Invoice state transitions
* Invoice disputes
* Invoice adjustments
* Compliance-officer dispute adjustment
* Invoice history

## Invoice Documents

* PDF-only upload
* Content-Type validation
* PDF signature validation
* 10 MB file-size limit
* Secure relative document paths
* Path traversal protection
* Supplier-specific document directories
* PDF download
* Orphaned invoice-file detection
* Orphaned invoice-file cleanup

## Supplier Statistics

* Purchase Order count
* On-time delivery percentage
* Average invoice cycle time
* Date normalization
* Missing delivery-data handling
* Invalid date handling
* Supplier existence validation

## Supplier Scorecard

* On-time delivery percentage
* Invoice accuracy percentage
* Dispute rate percentage
* Dispute performance
* Overall supplier score
* Performance rating
* Performance status
* Purchase Order performance details
* Invoice performance details
* Historical dispute tracking

---

# 3. Architecture

The Supplier Portal follows a layered FastAPI architecture.

```text
                       Client
                         │
                         ▼
                  FastAPI Application
                         │
                         ▼
                      Routes
                         │
            ┌────────────┼────────────┐
            │            │            │
            ▼            ▼            ▼
        Purchase      Invoice      Supplier
         Orders       Routes         Stats
            │            │            │
            └────────────┼────────────┘
                         ▼
                    Service Layer
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
       PO Store      Invoice Store   Event Store
          │              │
          │              ▼
          │        Local PDF Storage
          │
          ▼
      HTTP Response
```

Authentication is handled through the Platform Service:

```text
Client
  │
  │ Bearer Token
  ▼
Supplier Portal
  │
  │ POST /api/v1/auth/verify
  ▼
Platform Service
  │
  ▼
User Identity + Role + Supplier ID
  │
  ▼
Supplier Portal Authorization
```

---

# 4. Technology Stack

| Technology        | Purpose                         |
| ----------------- | ------------------------------- |
| Python            | Backend programming language    |
| FastAPI           | REST API framework              |
| Pydantic          | Request and response validation |
| Pydantic Settings | Environment configuration       |
| Uvicorn           | ASGI application server         |
| HTTPX             | HTTP client and FastAPI testing |
| Pytest            | Automated testing               |
| python-multipart  | Multipart file upload support   |
| pathlib           | Filesystem path handling        |
| FileResponse      | Invoice PDF downloads           |

The current dependency versions are maintained in `requirements.txt`.

---

# 5. Project Structure

The project follows this structure:

```text
supplier-portal/
│
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── auth.py
│   │   └── config.py
│   │
│   ├── routes/
│   │   ├── purchase_order.py
│   │   ├── invoice.py
│   │   └── supplier_stats_routes.py
│   │
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   ├── invoice.py
│   │   └── supplier_stats.py
│   │
│   └── services/
│       ├── purchase_order_service.py
│       ├── invoice_service.py
│       └── supplier_stats_service.py
│
├── tests/
│   ├── conftest.py
│   ├── test_purchase_order.py
│   ├── test_invoices.py
│   └── test_supplier_stats.py
│
├── uploads/
│
├── requirements.txt
├── pytest.ini
└── README.md
```

### Application Layer

`app/main.py`

Responsible for:

* Creating the FastAPI application
* Registering routers
* Defining the root endpoint

### Core Layer

`app/core/auth.py`

Responsible for:

* Bearer-token handling
* Authentication with Platform Service
* Role authorization
* Supplier identity propagation
* Request ID handling

`app/core/config.py`

Responsible for:

* Environment configuration
* Platform authentication URL
* Upload directory configuration

### Routes

Responsible for:

* HTTP endpoints
* Request handling
* Dependency injection
* HTTP response codes
* Calling service functions

### Schemas

Responsible for:

* Request validation
* Response validation
* Field constraints
* Regex validation
* Percentage boundaries

### Services

Responsible for:

* Business rules
* State machines
* Validation
* Calculations
* Document handling
* Supplier scorecard calculations

---

# 6. Authentication and Authorization

The Supplier Portal uses the **Platform Service as the authentication provider**.

The Supplier Portal does not locally decode or validate JWT tokens.

Instead, it sends the received Bearer token to:

```http
POST /api/v1/auth/verify
```

on the Platform Service.

## Authentication Flow

```text
Client
  │
  │ Authorization: Bearer <token>
  ▼
Supplier Portal
  │
  │ Verify token
  ▼
Platform Service
  │
  ├── valid
  ├── user_id
  ├── email
  ├── full_name
  ├── role
  ├── supplier_id
  └── is_active
  │
  ▼
Supplier Portal
  │
  ▼
Role / Supplier Authorization
  │
  ▼
Endpoint
```

The authentication request also sends:

```text
X-Caller-Service
X-Caller-Endpoint
X-Request-ID
```

If the client does not provide `X-Request-ID`, the Supplier Portal generates one.

## Authentication Configuration

The Platform Service URL is configured using:

```text
PLATFORM_AUTH_URL
```

Default:

```text
http://127.0.0.1:8005
```

## Authentication Errors

The Supplier Portal handles:

| Situation                          | Response |
| ---------------------------------- | -------- |
| Missing token                      | 401      |
| Invalid token                      | 401      |
| Expired token                      | 401      |
| Missing user role                  | 401      |
| Unauthorized role                  | 403      |
| Authentication timeout             | 503      |
| Authentication service unavailable | 503      |
| Invalid authentication response    | 503      |

---

## Supplier Scoping

Supplier-facing endpoints enforce supplier ownership.

For example:

```text
Authenticated Supplier:
SUP001
```

Trying to access:

```text
SUP002
```

is rejected.

```text
Supplier Token
     │
     ▼
supplier_id = SUP001
     │
     ▼
Requested Resource
supplier_id = SUP002
     │
     ▼
HTTP 403
```

This prevents one supplier from accessing another supplier's Purchase Orders, invoices, documents, or supplier performance information.

---

## Role-Based Authorization

The service supports role-based authorization through:

```python
require_roles(...)
```

Important roles include:

```text
procurement_manager
compliance_officer
supplier
```

Examples:

* Bulk PO sending requires `procurement_manager`
* Invoice adjustment requires `compliance_officer`
* Supplier-specific resources require the authenticated supplier to own the resource

---

# 7. Purchase Order Management

Purchase Orders are managed through a controlled lifecycle.

## PO Data Model

A Purchase Order contains:

```text
po_number
supplier_id
items
total_amount
status
created_at
expected_delivery
actual_delivery_date
history
```

A newly created PO starts as:

```text
draft
```

---

## PO Lifecycle

```text
             ┌─────────────┐
             │  Cancelled  │
             └─────────────┘
                ▲   ▲   ▲
                │   │   │
Draft ───────► Sent ───────► Acknowledged ───────► Fulfilled
```

The legal transitions are:

| Current State  | Allowed Transitions         |
| -------------- | --------------------------- |
| `draft`        | `sent`, `cancelled`         |
| `sent`         | `acknowledged`, `cancelled` |
| `acknowledged` | `fulfilled`, `cancelled`    |
| `fulfilled`    | None                        |
| `cancelled`    | None                        |

Terminal states:

```text
fulfilled
cancelled
```

cannot transition to another state.

---

## PO Creation

Endpoint:

```http
POST /api/v1/purchase-orders
```

The service validates:

* PO number
* Supplier ID
* Items
* Quantity
* Unit price
* Total amount
* Expected delivery
* Duplicate PO number

The calculated item total must match the submitted `total_amount`.

---

## PO Acknowledgement

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/acknowledge
```

The endpoint is supplier-scoped.

The authenticated supplier must own the Purchase Order.

The acknowledgement performs:

```text
sent
  │
  ▼
acknowledged
```

---

## PO State Transition

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/transition
```

Example:

```json
{
    "target_state": "sent",
    "actor": "admin"
}
```

The service checks the current state before performing the transition.

An illegal transition returns:

```text
400 Bad Request
```

---

## Bulk PO Send

Endpoint:

```http
POST /api/v1/purchase-orders/bulk-send
```

Authorization:

```text
procurement_manager
```

The endpoint accepts multiple PO numbers.

Example:

```json
{
    "po_numbers": [
        "PO1001",
        "PO1002",
        "PO9999"
    ]
}
```

Each Purchase Order is processed independently.

Therefore:

```text
PO1001 → Success
PO1002 → Success
PO9999 → Failure
```

A failure for one PO does not stop processing of the remaining POs.

The response contains:

```text
total
successful
failed
results
```

---

## PO Audit History

Every successful state transition creates an event containing:

```text
po_number
supplier_id
actor
from_status
to_status
timestamp
```

Events are stored separately in:

```python
po_events
```

This event store acts as the source of truth for PO transition history.

---

## PO Events

Endpoint:

```http
GET /api/v1/purchase-orders/{po_number}/events
```

The endpoint returns the Purchase Order's transition history.

Historical events are intentionally retained when a Purchase Order is deleted.

Therefore:

```text
Delete PO
   │
   ▼
PO record removed
   │
   ▼
Historical events retained
```

This preserves the audit trail.

---

## Delivery Tracking

When a PO reaches:

```text
fulfilled
```

the service records:

```text
actual_delivery_date
```

Delivery performance is determined using:

```text
actual_delivery_date <= expected_delivery
```

Therefore:

```text
Before expected date → On time
Expected date        → On time
After expected date  → Late
```

---

# 8. Invoice Management

Invoices are linked to Purchase Orders and suppliers.

An invoice can only be created when its referenced PO satisfies the required business rules.

---

## Invoice Data Model

An invoice contains:

```text
invoice_number
supplier_id
items
amount
invoice_date
status
dispute
adjustment
document_url
history
```

The invoice lookup key is:

```text
(supplier_id, invoice_number)
```

This means invoice numbers are unique within a supplier context.

---

## Invoice Lifecycle

The implemented invoice state machine is:

```text
                ┌───────────► Approved
                │
Submitted ──────┼───────────► Rejected
                │
                ▼
             Disputed
                │
          ┌─────┼─────┐
          │     │     │
          ▼     ▼     ▼
      Approved Rejected Adjusted
                         │
                     ┌───┴───┐
                     ▼       ▼
                 Approved  Rejected
```

The legal transitions are:

| Current Status | Allowed Status                     |
| -------------- | ---------------------------------- |
| `submitted`    | `approved`, `disputed`, `rejected` |
| `disputed`     | `approved`, `adjusted`, `rejected` |
| `adjusted`     | `approved`, `rejected`             |
| `approved`     | None                               |
| `rejected`     | None                               |

`approved` and `rejected` are terminal states.

---

## Invoice Creation

Endpoint:

```http
POST /api/v1/invoices
```

The service validates:

```text
Invoice number
Supplier ID
Purchase Order
Purchase Order supplier
Purchase Order status
Invoice items
Invoice quantities
Invoice unit prices
Invoice amount
Duplicate invoice
```

---

## PO Requirements for Invoices

An invoice can only reference a PO whose status is:

```text
acknowledged
fulfilled
```

Invoices cannot be created against:

```text
draft
sent
```

Therefore:

```text
Draft
  │
  └── Invoice rejected

Sent
  │
  └── Invoice rejected

Acknowledged
  │
  └── Invoice allowed

Fulfilled
  │
  └── Invoice allowed
```

---

## Invoice Supplier Validation

The invoice supplier must match the supplier associated with the Purchase Order.

For example:

```text
PO supplier = SUP001
Invoice supplier = SUP002
```

is rejected.

This prevents invoices from being associated with another supplier's Purchase Order.

---

## Invoice Line-Item Validation

Each invoice item is validated against the PO.

The service validates:

* Item exists on the PO
* Quantity is positive
* Quantity does not exceed remaining PO quantity
* Duplicate `(po_number, item_code)` lines are not allowed within one invoice
* Unit price is within the permitted tolerance
* Invoice amount matches the calculated line-item total

Rejected invoices do not consume PO quantity.

---

# 9. Invoice Document Management

Invoice documents are stored as PDF files on the local filesystem.

The upload directory is:

```text
uploads/
```

Supplier-specific directories are used:

```text
uploads/
├── SUP001/
│   ├── INV1001.pdf
│   └── INV1002.pdf
│
└── SUP002/
    └── INV2001.pdf
```

---

## PDF Upload

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint is supplier-scoped.

The authenticated supplier must own the invoice.

---

## PDF Validation

The service performs multiple checks.

### 1. Content Type

The request must use:

```text
application/pdf
```

Other types such as:

```text
image/png
text/plain
application/json
```

are rejected.

### 2. PDF Signature

The actual file contents must begin with:

```text
%PDF-
```

This prevents a non-PDF file from being accepted simply because it declares:

```text
Content-Type: application/pdf
```

### 3. Maximum File Size

Maximum supported size:

```text
10 MB
```

The actual uploaded bytes are checked to ensure the payload does not exceed the limit.

---

## Document Path and URL

The service intentionally separates the internal filesystem path from the public API URL.

Example:

```text
document_path:
SUP001/INV1001.pdf
```

This is an internal relative filesystem path.

The public URL is:

```text
/api/v1/invoices/SUP001/INV1001/document
```

Therefore:

```text
document_path
     │
     └── Internal filesystem reference

document_url
     │
     └── Public API reference
```

The absolute server filesystem path is not exposed through the API.

---

## Path Traversal Protection

The upload root is resolved:

```python
upload_root = Path(UPLOAD_DIR).resolve()
```

The final document path is also resolved:

```python
final_path = (upload_root / document_path).resolve()
```

The service then verifies that the final path remains inside the upload directory:

```python
final_path.is_relative_to(upload_root)
```

This protects against paths such as:

```text
../../some-file
```

The same protection is applied when retrieving stored documents.

---

## PDF Download

Endpoint:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The service performs:

```text
Find invoice
     │
     ▼
Check document_path
     │
     ▼
Resolve safe filesystem path
     │
     ▼
Check path is inside uploads/
     │
     ▼
Check file exists
     │
     ▼
Return FileResponse
```

The actual PDF is returned using FastAPI's file-response mechanism.

---

## Invoice Disputes

An invoice can transition from:

```text
submitted
```

to:

```text
disputed
```

A dispute requires a reason.

The dispute information records details such as:

```text
reason
actor_id
actor_name
role
timestamp
```

---

## Invoice Adjustment

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/adjust
```

Authorization:

```text
compliance_officer
```

An adjustment is allowed only for an invoice currently in:

```text
disputed
```

The adjustment can update invoice line items and recalculates the invoice amount.

The adjustment records audit information including:

```text
actor
reason
timestamp
old amount
new amount
old items
new items
```

The invoice then moves:

```text
disputed
    │
    ▼
adjusted
```

and can subsequently move to:

```text
approved
```

or:

```text
rejected
```

---

## Invoice Transition

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/transition
```

The service validates:

1. Invoice exists
2. Current status exists
3. Target status is valid
4. Current-to-target transition is allowed

Illegal transitions return:

```text
400 Bad Request
```

---

# 10. Supplier Statistics

Supplier statistics are available through:

```http
GET /api/v1/suppliers/{supplier_id}/stats
```

The endpoint provides:

```text
supplier_id
po_count
on_time_percentage
average_invoice_cycle_time
```

---

## Purchase Order Count

The PO count includes all Purchase Orders belonging to the supplier:

```text
po_count = total supplier POs
```

This includes:

```text
draft
sent
acknowledged
fulfilled
cancelled
```

---

## On-Time Delivery Percentage

The implemented business rule is:

```text
on-time percentage =
(on-time POs / total supplier POs) × 100
```

An on-time PO satisfies:

```text
actual_delivery_date <= expected_delivery
```

Example:

```text
Total POs = 3
On-time POs = 2

On-time percentage = 66.67%
```

The result is rounded to two decimal places.

Unfulfilled POs remain in the denominator.

If delivery information is incomplete, the PO does not contribute to the on-time count.

---

## Average Invoice Cycle Time

The service calculates:

```text
invoice date - PO creation date
```

Example:

```text
PO created:   August 1
Invoice date: August 4

Cycle time = 3 days
```

Negative cycle times are ignored.

Invalid date records are also ignored rather than causing the entire calculation to fail.

---

## Date Normalization

The statistics service supports:

```text
date
datetime
ISO date string
ISO datetime string
ISO datetime with Z
```

These values are normalized through a shared date-conversion helper before calculations.

---

## Supplier Not Found

A supplier is considered to exist if supplier data is present in the relevant PO or invoice stores.

If the supplier cannot be found:

```http
404 Not Found
```

is returned.

Example:

```json
{
    "detail": "Supplier 'SUP999' not found."
}
```

---

# 11. Supplier Performance Scorecard

The supplier scorecard provides a higher-level performance view.

Endpoint:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The scorecard contains:

```text
On-time delivery
Invoice accuracy
Dispute rate
Dispute performance
Overall score
Rating
Performance status
Detailed PO metrics
Detailed invoice metrics
```

---

## Scorecard Metrics

### On-Time Delivery

```text
on-time POs / total supplier POs × 100
```

Weight:

```text
40%
```

---

### Invoice Accuracy

An invoice is considered accurate when:

```text
invoice.dispute is None
```

Formula:

```text
accurate invoices / total invoices × 100
```

Weight:

```text
40%
```

---

### Dispute Rate

An invoice is considered historically disputed when:

```python
invoice.get("dispute") is not None
```

Formula:

```text
disputed invoices / total invoices × 100
```

---

### Dispute Performance

Because a high dispute rate represents poorer performance:

```text
dispute performance = 100 - dispute rate
```

Weight:

```text
20%
```

---

## Overall Score

The overall score is calculated using:

```text
40% → On-time delivery
40% → Invoice accuracy
20% → Dispute performance
```

Formula:

```text
overall score =
    (on-time delivery × 0.40)
  + (invoice accuracy × 0.40)
  + (dispute performance × 0.20)
```

Example:

```text
On-time delivery     = 75
Invoice accuracy     = 80
Dispute performance  = 90
```

Calculation:

```text
(75 × 0.40)
+ (80 × 0.40)
+ (90 × 0.20)

= 30 + 32 + 18

= 80
```

---

## Scorecard Rating

|    Score | Rating            |
| -------: | ----------------- |
|   90–100 | Excellent         |
| 75–89.99 | Good              |
| 60–74.99 | Average           |
| 40–59.99 | Needs Improvement |
| Below 40 | Poor              |

---

## Performance Status

|    Score | Status   |
| -------: | -------- |
|   75–100 | Healthy  |
| 60–74.99 | Watch    |
| 40–59.99 | At Risk  |
| Below 40 | Critical |

---

## Scorecard Details

The scorecard also provides detailed Purchase Order metrics:

```text
total
fulfilled
on_time
late
pending
cancelled
on_time_percentage
late_percentage
fulfillment_rate
average_delay_days
```

Invoice metrics include:

```text
total
accurate
inaccurate
disputed
approved
rejected
pending
accuracy_percentage
dispute_rate_percentage
approval_rate_percentage
average_cycle_time_days
```

---

## Historical Dispute Tracking

A resolved dispute remains part of the supplier's historical performance.

For example:

```text
submitted
    │
    ▼
disputed
    │
    ▼
adjusted
    │
    ▼
approved
```

The invoice remains historically disputed because the dispute information is retained.

This prevents supplier performance metrics from losing the history of previously disputed invoices.

---

## Invoice-Only Suppliers

A supplier can be recognized through invoice data even if it currently has no Purchase Orders.

The scorecard checks:

```text
Supplier exists in PO store
        OR
Supplier exists in Invoice store
```

This allows invoice-only suppliers to receive a scorecard instead of incorrectly returning `404`.

---

# 12. API Reference

All application APIs use the `/api/v1` prefix.

## Root

| Method | Endpoint | Description            |
| ------ | -------- | ---------------------- |
| GET    | `/`      | Service health/message |

---

## Purchase Order APIs

| Method | Endpoint                                          | Authentication / Role                            | Description        |
| ------ | ------------------------------------------------- | ------------------------------------------------ | ------------------ |
| POST   | `/api/v1/purchase-orders`                         | Current implementation: no route auth dependency | Create PO          |
| GET    | `/api/v1/purchase-orders`                         | Current implementation: no route auth dependency | List all POs       |
| GET    | `/api/v1/purchase-orders/{po_number}`             | Supplier scoped                                  | Get PO             |
| PUT    | `/api/v1/purchase-orders/{po_number}`             | Current implementation: no route auth dependency | Update PO          |
| DELETE | `/api/v1/purchase-orders/{po_number}`             | Current implementation: no route auth dependency | Delete PO          |
| POST   | `/api/v1/purchase-orders/{po_number}/acknowledge` | Supplier scoped                                  | Acknowledge PO     |
| POST   | `/api/v1/purchase-orders/{po_number}/transition`  | Current implementation: no route auth dependency | Transition PO      |
| GET    | `/api/v1/purchase-orders/{po_number}/events`      | Supplier scoped                                  | Retrieve PO events |
| POST   | `/api/v1/purchase-orders/bulk-send`               | `procurement_manager`                            | Bulk send POs      |

> **Note:** Authentication is implemented centrally, but not every current PO route has an authentication dependency attached. The table intentionally reflects the current implementation rather than claiming broader protection than the code currently provides.

---

## Invoice APIs

| Method | Endpoint                                                     | Authentication / Role                                       | Description             |
| ------ | ------------------------------------------------------------ | ----------------------------------------------------------- | ----------------------- |
| GET    | `/api/v1/invoices`                                           | Current implementation: no route auth dependency            | List invoices           |
| POST   | `/api/v1/invoices`                                           | Authenticated; supplier identity enforced for supplier role | Create invoice          |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}`            | Supplier scoped                                             | Get invoice             |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Supplier scoped                                             | Transition invoice      |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust`     | `compliance_officer`                                        | Adjust disputed invoice |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Supplier scoped                                             | Upload PDF              |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Supplier scoped                                             | Download PDF            |

---

## Supplier Statistics APIs

| Method | Endpoint                                    | Authentication / Scope             | Description                     |
| ------ | ------------------------------------------- | ---------------------------------- | ------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/stats`     | Supplier-scoped for supplier users | Supplier operational statistics |
| GET    | `/api/v1/suppliers/{supplier_id}/scorecard` | Supplier-scoped for supplier users | Supplier performance scorecard  |

---

## Maintenance APIs

| Method | Endpoint                                     | Description                 |
| ------ | -------------------------------------------- | --------------------------- |
| GET    | `/api/v1/maintenance/orphaned-invoice-files` | Find orphaned invoice PDFs  |
| DELETE | `/api/v1/maintenance/orphaned-invoice-files` | Purge orphaned invoice PDFs |

Optional query parameter:

```text
older_than_days
```

Default:

```text
1
```

---

# 13. HTTP Response Codes

| Status | Meaning                                                |
| -----: | ------------------------------------------------------ |
|    200 | Successful request                                     |
|    201 | Resource created                                       |
|    400 | Business-rule validation failure                       |
|    401 | Authentication required or invalid                     |
|    403 | Authenticated user is not authorized                   |
|    404 | Resource not found                                     |
|    409 | Duplicate resource                                     |
|    422 | Request/schema validation failure                      |
|    503 | Authentication service unavailable or invalid response |

---

# 14. Configuration

The service uses Pydantic Settings.

Create a `.env` file in the project root if configuration needs to be changed.

Example:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The default value is:

```text
http://127.0.0.1:8005
```

The `.env` file should not be committed to source control if it contains sensitive configuration.

---

# 15. Installation

## Step 1 — Clone/Open the Project

Open the Supplier Portal project directory in VS Code.

---

## Step 2 — Create Virtual Environment

Windows PowerShell:

```powershell
python -m venv venv
```

---

## Step 3 — Activate Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

---

## Step 4 — Install Dependencies

```powershell
pip install -r requirements.txt
```

The required packages include:

```text
FastAPI
Uvicorn
Pydantic
python-multipart
Pytest
HTTPX
```

---

# 16. Running the Services

The Supplier Portal depends on the Platform Service for authentication.

Therefore, run the services separately.

## Platform Service

Start the Platform Service on:

```text
http://127.0.0.1:8005
```

The Platform Service provides:

```http
POST /api/v1/auth/login
POST /api/v1/auth/verify
GET  /api/v1/users/me
```

---

## Supplier Portal Service

From the Supplier Portal project directory:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The Supplier Portal will run at:

```text
http://127.0.0.1:8000
```

---

## Two-Service Architecture

```text
┌─────────────────────────────┐
│      Platform Service       │
│                             │
│       Port 8005             │
│                             │
│ Authentication Provider     │
└──────────────┬──────────────┘
               │
               │ /api/v1/auth/verify
               │
               ▼
┌─────────────────────────────┐
│     Supplier Portal         │
│                             │
│       Port 8000             │
│                             │
│ PO / Invoice / Statistics   │
│ Scorecard / Documents       │
└─────────────────────────────┘
```

---

# 17. Swagger Documentation

FastAPI automatically provides interactive API documentation.

Open:

```text
http://127.0.0.1:8000/docs
```

Alternative ReDoc documentation:

```text
http://127.0.0.1:8000/redoc
```

Swagger can be used to test:

```text
Purchase Orders
PO acknowledgement
PO transitions
PO events
Bulk PO sending

Invoice creation
Invoice retrieval
Invoice transitions
Invoice disputes
Invoice adjustments

PDF upload
PDF download

Supplier statistics
Supplier scorecard

Maintenance endpoints
```

---

# 18. Testing

The project uses **Pytest** for automated testing.

Run the complete test suite:

```powershell
python -m pytest -v
```

---

## Purchase Order Tests

```powershell
python -m pytest tests/test_purchase_order.py -v
```

Tests cover:

* PO creation
* PO retrieval
* PO listing
* PO update
* PO deletion
* Duplicate PO
* PO acknowledgement
* Legal transitions
* Illegal transitions
* Cancellation
* Terminal states
* Transition history
* Event retrieval
* Actor tracking
* Timestamp tracking
* Delivery tracking
* Bulk PO sending

---

## Invoice Tests

```powershell
python -m pytest tests/test_invoices.py -v
```

Tests cover:

* Valid invoice creation
* Invoice retrieval
* Duplicate invoice
* Invalid invoice number
* Invalid supplier ID
* Missing PO
* Invalid PO status
* PO supplier mismatch
* Invoice item validation
* Quantity validation
* Unit-price tolerance
* Amount validation
* Partial invoicing
* Invoice transitions
* Disputes
* Adjustments
* PDF upload
* PDF signature validation
* Content-Type validation
* 10 MB file-size limit
* PDF download
* Missing document handling
* Path traversal protection
* Supplier scoping
* Compliance-officer adjustment

---

## Supplier Statistics and Scorecard Tests

```powershell
python -m pytest tests/test_supplier_stats.py -v
```

Tests cover:

* Supplier statistics
* Supplier not found
* PO count
* On-time delivery
* Late delivery
* Mixed delivery performance
* Unfulfilled POs
* Delivery exactly on expected date
* Missing delivery date
* Average invoice cycle time
* Date normalization
* Invalid dates
* Negative cycle times
* Scorecard calculation
* Dispute rate
* Invoice accuracy
* Dispute performance
* Overall score
* Scorecard details
* Invoice-only suppliers
* Supplier scoping
* Schema validation
* Percentage boundaries

---

## Authentication Test Configuration

The test suite uses authentication dependency overrides so business logic can be tested without requiring the real Platform Service for every test.

The test configuration provides different identities such as:

```text
Supplier SUP001
Supplier SUP002
Supplier SUP123
Compliance Officer
```

This allows supplier-scoping behaviour to be tested, including:

```text
Supplier A → Supplier A resource = Allowed
Supplier A → Supplier B resource = Forbidden
```

---

# 19. Business Rules

## Purchase Order Rules

```text
New PO → draft
```

Legal lifecycle:

```text
draft → sent
sent → acknowledged
acknowledged → fulfilled
```

Cancellation is allowed from:

```text
draft
sent
acknowledged
```

Invalid transitions return:

```text
400 Bad Request
```

---

## Invoice Rules

Invoices require an existing PO.

The PO must be:

```text
acknowledged
OR
fulfilled
```

The invoice supplier must match the PO supplier.

Duplicate invoices are prevented using:

```text
supplier_id + invoice_number
```

---

## Invoice Amount Tolerance

The configured tolerance is:

```text
TOLERANCE = 0.05
```

Therefore the permitted range is:

```text
95% <= permitted amount <= 105%
```

For a PO amount of `1000`:

```text
950  → Accepted
1000 → Accepted
1050 → Accepted

949  → Rejected
1051 → Rejected
```

---

## Rejected Invoice Quantity

Rejected invoices do not consume the Purchase Order's available quantity.

Invoices in the following states are counted when determining already-invoiced quantity:

```text
submitted
disputed
adjusted
approved
```

---

## Supplier On-Time Percentage

```text
on-time POs
---------------- × 100
total supplier POs
```

An on-time PO satisfies:

```text
actual_delivery_date <= expected_delivery
```

Unfulfilled POs remain in the denominator.

---

## Invoice Dispute Rate

```text
disputed invoices
------------------ × 100
total invoices
```

Historical dispute information is retained through the invoice's dispute data.

---

## Invoice Accuracy

```text
accurate invoices
------------------ × 100
total invoices
```

Current implementation:

```text
dispute is None     → Accurate
dispute is not None → Inaccurate
```

---

## Supplier Score

```text
40% → On-time delivery
40% → Invoice accuracy
20% → Dispute performance
```

Where:

```text
dispute performance = 100 - dispute rate
```

---

# 20. Security Controls

The service implements several security controls.

## Authentication

* Bearer token authentication
* Central authentication through Platform Service
* Authentication timeout handling
* Authentication-service failure handling
* Request ID propagation

## Authorization

* Role-based authorization
* Supplier ownership validation
* Compliance-officer authorization for invoice adjustment
* Procurement-manager authorization for bulk PO sending

## Input Validation

* PO number validation
* Supplier ID validation
* Invoice number validation
* Positive quantities
* Positive unit prices
* Positive invoice amounts
* Percentage boundaries

Allowed identifier format:

```regex
^[A-Za-z0-9_-]+$
```

---

## Document Security

Invoice documents are protected through:

* PDF Content-Type validation
* PDF signature validation
* 10 MB size limit
* Safe filename generation
* Relative filesystem paths
* Upload-root resolution
* Path traversal protection
* Supplier-specific directories
* Supplier-scoped document access

---

# 21. Storage

The current implementation intentionally uses in-memory storage.

Purchase Orders:

```python
purchase_orders = {}
```

Invoices:

```python
invoices = {}
```

PO events:

```python
po_events = {}
```

Invoice events are also maintained in memory.

Invoice documents are stored locally:

```text
uploads/
```

---

## Application Restart Behaviour

Because business data is stored in memory:

```text
Application running
      │
      ▼
PO / Invoice data exists
      │
      ▼
Application restart
      │
      ▼
In-memory data cleared
```

Invoice PDF files stored under `uploads/` are filesystem-based and therefore are not automatically cleared by an application restart.

A production deployment should replace in-memory business storage with persistent storage.

---

# 22. End-to-End Workflow

The complete business workflow is:

```text
                         Procurement
                              │
                              ▼
                     Create Purchase Order
                              │
                              ▼
                           Draft
                              │
                              ▼
                            Sent
                              │
                              ▼
                    Supplier Acknowledgement
                              │
                              ▼
                        Acknowledged
                              │
                              ▼
                          Fulfilled
                              │
                              ▼
                       Create Invoice
                              │
                 ┌────────────┼────────────┐
                 │            │            │
                 ▼            ▼            ▼
             Validate PO  Validate Items  Validate Amount
                 │            │            │
                 └────────────┼────────────┘
                              ▼
                       Invoice Submitted
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
                Approved            Disputed
                                        │
                              ┌─────────┼─────────┐
                              │         │         │
                              ▼         ▼         ▼
                           Approved  Rejected  Adjusted
                                                   │
                                             ┌─────┴─────┐
                                             ▼           ▼
                                         Approved    Rejected
                             
                              │
                              ▼
                         Upload PDF
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
              Validate Content    Validate Signature
                     │                 │
                     └────────┬────────┘
                              ▼
                        Store PDF
                              │
                              ▼
                   Supplier Statistics
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
               PO Metrics          Invoice Metrics
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    Supplier Scorecard
```

---

# 23. Current Implementation Status

| Module                              | Status                                   |
| ----------------------------------- | ---------------------------------------- |
| Purchase Order CRUD                 | Complete                                 |
| PO State Machine                    | Complete                                 |
| PO Acknowledgement                  | Complete                                 |
| PO Cancellation                     | Complete                                 |
| PO Audit Events                     | Complete                                 |
| PO Delivery Tracking                | Complete                                 |
| Bulk PO Send                        | Complete                                 |
| Invoice Creation                    | Complete                                 |
| Invoice Validation                  | Complete                                 |
| Invoice Duplicate Protection        | Complete                                 |
| Invoice Tolerance                   | Complete                                 |
| Invoice State Machine               | Complete                                 |
| Invoice Disputes                    | Complete                                 |
| Invoice Adjustments                 | Complete                                 |
| PDF Upload                          | Complete                                 |
| PDF Download                        | Complete                                 |
| PDF Signature Validation            | Complete                                 |
| File Size Validation                | Complete                                 |
| Path Traversal Protection           | Complete                                 |
| Supplier Statistics                 | Complete                                 |
| Supplier Scorecard                  | Complete                                 |
| Supplier Scoping                    | Implemented on supplier-facing endpoints |
| Platform Authentication Integration | Implemented                              |
| Automated Tests                     | Implemented                              |
| Swagger Documentation               | Available                                |

---

# 24. Known Limitations

The current implementation is primarily intended for the current development phase.

## In-Memory Business Storage

Purchase Orders, invoices, and events are stored in Python dictionaries.

This means application restarts clear business data.

---

## Local File Storage

Invoice PDFs are stored locally under:

```text
uploads/
```

Production deployments should use durable object storage.

---

## Authentication Dependency

Authentication depends on the Platform Service being available at the configured URL.

If the Platform Service is unavailable, authenticated endpoints can return:

```text
503 Service Unavailable
```

---

## Route-Level Authentication Coverage

Authentication infrastructure is implemented, but not every currently exposed route has an authentication dependency.

Before production deployment, all sensitive administrative and maintenance endpoints should be reviewed and protected appropriately.

---

## Maintenance Endpoint Authorization

The orphan-file maintenance endpoints currently do not have a role dependency attached.

For production use, these endpoints should be restricted to an appropriate administrative/service role.

---

# 25. Future Enhancements

The following improvements can be introduced in the next development phase.

## Persistence

* PostgreSQL
* SQLAlchemy ORM
* Database migrations
* Persistent audit tables

## Document Storage

* MinIO
* Amazon S3
* Object-storage lifecycle policies

## Messaging

* Kafka
* Event-driven PO and invoice events

## Caching

* Redis
* Supplier scorecard caching

## Security

* Full route-level RBAC
* Administrative authorization for maintenance APIs
* Token rotation
* Centralized security policies

## Infrastructure

* Docker
* Kubernetes
* API Gateway
* Service discovery
* Centralized configuration

## Observability

* Structured logging
* Centralized logs
* Metrics
* Distributed tracing
* Health checks
* Monitoring and alerting

## DevOps

* CI/CD pipeline
* Automated test execution
* Code quality checks
* Container image scanning
* Deployment automation

---

# Final Summary

The Supplier Portal Service provides a complete backend workflow for:

```text
Purchase Order
      ↓
PO Lifecycle
      ↓
Supplier Acknowledgement
      ↓
PO Fulfilment
      ↓
Invoice Creation
      ↓
Invoice Validation
      ↓
Invoice Dispute / Adjustment
      ↓
Invoice Approval / Rejection
      ↓
Invoice PDF Management
      ↓
Supplier Statistics
      ↓
Supplier Performance Scorecard
```

The service combines:

```text
FastAPI
Pydantic
Role-Based Authorization
Supplier Scoping
Business Validation
State Machines
Audit Events
PDF Security
Supplier KPIs
Performance Scoring
Automated Testing
```

The current implementation is suitable for the next development stage, where persistent storage, production-grade infrastructure, complete route-level authorization, object storage, observability, and deployment automation can be introduced.
