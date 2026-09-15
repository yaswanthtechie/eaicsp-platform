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

## Status & Known Gaps

The current Supplier Portal implementation includes authentication, role-based authorization, supplier-level scoping, Purchase Order and invoice workflows, document validation, supplier statistics, supplier scorecards, and automated security testing.

The major current implementation limitations are:

* Purchase Orders, invoices, and audit events use **in-memory storage** and are not persistent across service restarts.
* Invoice PDF documents use **local filesystem storage**.
* Authentication depends on the availability of the **Platform Service**.
* The current implementation is suitable for development and functional validation; production deployment requires persistent storage and additional operational hardening.

For the detailed list of limitations and future production considerations, see [Known Limitations](#24-known-limitations).

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
        Orders       Routes          Stats

           │            │            │

           └────────────┼────────────┘

                        ▼

                   Service Layer

                        │

          ┌─────────────┼─────────────┐

          │             │             │

          ▼             ▼             ▼

       PO Store     Invoice Store   Event Store

          │             │

          │             ▼

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

The Supplier Portal Service follows a layered FastAPI architecture separating application configuration, authentication, API routes, validation schemas, business logic, and automated tests.

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

│   ├── test_auth.py

│   ├── test_requires_auth.py

│   └── test_supplier_stats.py

│

├── uploads/

│

├── .env.example

├── requirements.txt

├── pytest.ini

└── README.md
```

### Application Layer

`app/main.py`

Responsible for:

* Creating and configuring the FastAPI application

* Registering application routers

* Defining the root endpoint

* Initializing the application entry point

### Core Layer

`app/core/auth.py`

Responsible for:

* Bearer-token extraction and handling

* Authentication with the Platform Service

* Role-based authorization

* Authenticated user identity propagation

* Supplier identity propagation

* Supplier-level access control

* Request ID generation and propagation

* Authentication error handling

`app/core/config.py`

Responsible for:

* Environment-based configuration

* Platform authentication service URL

* Upload directory configuration

* Application configuration values

### Routes

The route layer is responsible for:

* Defining HTTP endpoints

* Processing incoming requests

* Dependency injection

* Authentication and authorization dependencies

* Supplier ownership and scoping checks

* HTTP status-code handling

* Calling the appropriate service-layer functions

### Schemas

The schema layer is responsible for:

* Request validation

* Response validation

* Field constraints

* Regex validation

* Percentage and numeric boundaries

* API data-model definitions

### Services

The service layer is responsible for:

* Business rules

* Purchase-order lifecycle state transitions

* Invoice lifecycle state transitions

* Business validation

* Supplier performance calculations

* Supplier scorecard calculations

* Invoice and purchase-order processing

* Document handling

### Tests

The `tests/` directory contains automated test coverage for:

* Purchase-order APIs and lifecycle operations

* Invoice APIs and lifecycle operations

* Authentication and Platform Service integration

* Role-based authorization

* Supplier-level data scoping

* Cross-supplier access rejection

* Supplier statistics

* Supplier scorecards

* Validation and business rules

* Authentication-required endpoint protection

### R5 Authentication and Supplier Scoping

Round 5 extends the application with authentication, role-based authorization, and supplier-level data isolation across supplier-facing endpoints.

The route layer obtains the authenticated user through the Platform Service authentication dependency and applies the appropriate access-control rules before returning protected resources.

The primary R5 security principle is:

```text
A valid supplier token does not provide unrestricted supplier access.

The authenticated supplier must own the requested resource.
```

For example:

```text
Supplier A

supplier_id = SUP001

       │

       │ requests

       ▼

Supplier B resource

supplier_id = SUP002

       │

       ▼

HTTP 403 Forbidden
```

Supplier users are therefore restricted to resources belonging to their authenticated `supplier_id`.

Internal authorized roles may access supplier data according to their assigned permissions and role-based access rules.

Supplier identities without a valid `supplier_id` are rejected from supplier-scoped operations with `HTTP 403 Forbidden`.

Unknown supplier resources return `HTTP 404 Not Found`, while authenticated suppliers attempting to access another supplier's existing resource return `HTTP 403 Forbidden`.

This separation ensures that authentication establishes **who the caller is**, while supplier scoping determines **which supplier data the caller is authorized to access**.

---

# 6. Authentication and Authorization

The Supplier Portal uses the **Platform Service as the authentication provider**.

The Supplier Portal does not locally decode or validate JWT tokens. Instead, it forwards the received Bearer token to the Platform Service for validation.

The authentication endpoint used by the Supplier Portal is:

```http
POST /api/v1/auth/verify
```

## Authentication Flow

```text
Client

   │

   │ Authorization: Bearer <token>

   ▼

Supplier Portal

   │

   │ Verify token with Platform Service

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

Authentication

   │

   ▼

Role Authorization

   │

   ▼

Supplier Ownership Check

   │

   ▼

Endpoint / Resource
```

The Platform Service provides the authenticated supplier's `supplier_id` as part of the `/api/v1/auth/verify` response.

The authentication request also includes the following headers:

```text
X-Caller-Service

X-Caller-Endpoint

X-Request-ID
```

If the client does not provide an `X-Request-ID`, the Supplier Portal generates a request ID before calling the Platform Service.

## Authentication Configuration

The Platform Service URL is configured using the following environment variable:

```text
PLATFORM_AUTH_URL
```

The default development value is:

```text
http://127.0.0.1:8005
```

### Starting the Platform Service

The Platform Service can be started locally using:

```powershell
python -m uvicorn app.main:app --reload --port 8005
```

The Supplier Portal can then communicate with the Platform Service using the configured `PLATFORM_AUTH_URL`.

## Authentication Errors

The Supplier Portal handles authentication and authorization failures as follows:

| Situation                            | Response |
| ------------------------------------ | -------: |
| Missing token                        |      401 |
| Invalid token                        |      401 |
| Expired token                        |      401 |
| Missing user role                    |      401 |
| Unauthorized role                    |      403 |
| Supplier identity missing            |      403 |
| Supplier resource ownership mismatch |      403 |
| Authentication timeout               |      503 |
| Authentication service unavailable   |      503 |
| Invalid authentication response      |      503 |

## Supplier Scoping

Supplier-facing endpoints enforce **supplier ownership** in addition to authentication.

A valid supplier token identifies the authenticated supplier through the `supplier_id` returned by the Platform Service.

For example:

```text
Authenticated Supplier

        │

        ▼

supplier_id = SUP001

        │

        ▼

Requested Resource

supplier_id = SUP002

        │

        ▼

HTTP 403 Forbidden
```

A supplier authenticated as `SUP001` cannot access a resource owned by `SUP002`.

This prevents one supplier from accessing another supplier's:

* Purchase Orders

* Purchase Order events

* Invoices

* Invoice documents

* Supplier statistics

* Supplier scorecards

A supplier user without a valid `supplier_id` is also rejected from supplier-scoped resources:

```text
Supplier Role

     │

     ▼

supplier_id missing

     │

     ▼

HTTP 403 Forbidden
```

## Supplier List Filtering

Collection endpoints are also protected by authentication and supplier-level filtering.

The following endpoints require authentication:

```http
GET /api/v1/purchase-orders

GET /api/v1/invoices
```

When the authenticated user has the `supplier` role, the Supplier Portal returns only records belonging to that supplier.

Internal authorized users can access the broader collection according to their assigned role.

### Purchase Order List Scoping

```text
Supplier SUP001

      │

      ▼

GET /api/v1/purchase-orders

      │

      ▼

Only SUP001 Purchase Orders
```

### Invoice List Scoping

```text
Supplier SUP001

      │

      ▼

GET /api/v1/invoices

      │

      ▼

Only SUP001 Invoices
```

This ensures that authenticated supplier users cannot retrieve another supplier's records through collection endpoints.

## Role-Based Authorization

The Supplier Portal supports role-based authorization through:

```python
require_roles(...)
```

Important roles include:

```text
procurement_manager

compliance_officer

supplier
```

Examples of role-based restrictions include:

* Purchase Order creation requires `procurement_manager`

* Purchase Order transition requires `procurement_manager`

* Bulk Purchase Order sending requires `procurement_manager`

* Invoice adjustment requires `compliance_officer`

* Supplier-specific resources require the authenticated supplier to own the resource

* Supplier collection endpoints return only the authenticated supplier's resources

Role authorization and supplier ownership are **separate security checks**.

```text
Authentication

      │

      ▼

Role Authorization

      │

      ▼

Supplier Ownership

      │

      ▼

Resource Access
```

A valid token therefore does not automatically grant access to every resource.

## Round 5 Security Requirement

The primary Round 5 security requirement is:

```text
A valid supplier token does not provide unrestricted supplier access.
```

The authenticated supplier must own the requested supplier-scoped resource.

Examples:

```text
SUP001 token → SUP001 PO          → Allowed

SUP001 token → SUP002 PO          → 403 Forbidden

SUP001 token → SUP001 Invoice     → Allowed

SUP001 token → SUP002 Invoice     → 403 Forbidden

SUP001 token → SUP001 Scorecard   → Allowed

SUP001 token → SUP002 Scorecard   → 403 Forbidden
```

The same ownership principle applies to supplier-scoped Purchase Order events, invoice documents, statistics, and other supplier resources.

Supplier-level authorization is enforced at the API layer and covered by automated Round 5 tests, including:

* Supplier cannot view another supplier's Purchase Order

* Supplier cannot acknowledge another supplier's Purchase Order

* Supplier cannot view another supplier's Invoice

* Supplier cannot access another supplier's Scorecard

* Supplier cannot access another supplier's Statistics

* Supplier token without `supplier_id` is rejected

* Supplier collection endpoints return only the authenticated supplier's resources

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

Authorization:

```text
procurement_manager
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

## PO List

Endpoint:

```http
GET /api/v1/purchase-orders
```

The endpoint requires authentication.

For supplier users, the response is filtered using the authenticated `supplier_id`.

```text
Supplier SUP001

      │

      ▼

Authenticated request

      │

      ▼

Filter supplier_id = SUP001

      │

      ▼

Only SUP001 Purchase Orders
```

Internal authorized users can access the broader Purchase Order collection according to their role.

---

## Get PO

Endpoint:

```http
GET /api/v1/purchase-orders/{po_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the Purchase Order.

Internal authorized users can view Purchase Orders across suppliers according to their role.

A supplier attempting to access another supplier's Purchase Order receives:

```text
403 Forbidden
```

---

## PO Update

Endpoint:

```http
PUT /api/v1/purchase-orders/{po_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the requested Purchase Order.

A supplier cannot update another supplier's Purchase Order.

---

## PO Delete

Endpoint:

```http
DELETE /api/v1/purchase-orders/{po_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the requested Purchase Order.

Supplier ownership is checked before the Purchase Order is deleted.

Historical PO events remain retained after deletion.

---

## PO Acknowledgement

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/acknowledge
```

The endpoint is supplier-scoped and is restricted to the owning supplier.

The authenticated supplier must own the Purchase Order.

The acknowledgement performs:

```text
sent

 │

 ▼

acknowledged
```

A supplier attempting to acknowledge another supplier's Purchase Order is rejected with:

```text
403 Forbidden
```

---

## PO State Transition

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/transition
```

Authorization:

```text
procurement_manager
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

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the Purchase Order or its retained event history.

Internal authorized users can view Purchase Order event history across suppliers according to their role.

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

The endpoint requires authentication.

For supplier users, the authenticated `supplier_id` must match the invoice supplier.

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

## Invoice List

Endpoint:

```http
GET /api/v1/invoices
```

The endpoint requires authentication.

For supplier users, only invoices belonging to the authenticated supplier are returned.

For internal authorized users, the broader invoice collection can be returned according to the user's role.

Example:

```text
Supplier SUP001

      │

      ▼

GET /api/v1/invoices

      │

      ▼

Only SUP001 invoices
```

A supplier cannot use the collection endpoint to discover another supplier's invoices.

---

## Get Invoice

Endpoint:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the requested invoice.

Internal authorized users can view invoices across suppliers according to their role.

A supplier attempting to access another supplier's invoice receives:

```text
403 Forbidden
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

R5 additionally ensures that the authenticated supplier identity must match the supplier being acted upon.

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

A supplier cannot upload a document to another supplier's invoice.

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

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the invoice.

Internal authorized users can access invoice documents according to their role and authorization rules.

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

The endpoint is supplier-scoped for supplier users.

The authenticated supplier must own the invoice.

Internal roles are handled according to the endpoint's role authorization rules.

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

The endpoint requires authentication.

For supplier users, the authenticated `supplier_id` must match the requested `supplier_id`.

The endpoint provides:

```text
supplier_id

po_count

on_time_percentage

average_invoice_cycle_time
```

---

## Supplier-Level Access Control

Supplier statistics are protected by supplier ownership.

Example:

```text
Authenticated supplier:

SUP001
```

Request:

```text
/suppliers/SUP001/stats
```

Result:

```text
Allowed
```

Request:

```text
/suppliers/SUP002/stats
```

Result:

```text
403 Forbidden
```

A supplier user without a `supplier_id` receives:

```text
403 Forbidden
```

Internal authorized users can access supplier statistics for other suppliers according to their role.

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

### R5 404 vs 403 Behavior

For supplier statistics and scorecards, the service first determines whether the requested supplier exists and then performs the supplier ownership check.

Therefore:

```text
Known supplier + wrong supplier token

        ↓

403 Forbidden
```

while:

```text
Unknown supplier

        ↓

404 Not Found
```

This distinction is intentional.

The behavior provides a clear separation between:

```text
Resource does not exist

        ↓

404 Not Found
```

and:

```text
Resource exists

+

Authenticated supplier does not own it

        ↓

403 Forbidden
```

Because the resource-existence check occurs before the supplier ownership check, an unauthorized supplier may be able to distinguish whether a requested `supplier_id` exists based on the HTTP status code.

This is a deliberate behavior of the current implementation. If future production security requirements require preventing supplier-existence enumeration, the authorization flow can be changed to perform the ownership check before resource lookup or return a uniform response for both cases.


# 11. Supplier Performance Scorecard

The Supplier Performance Scorecard provides a higher-level view of supplier performance.

Endpoint:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The endpoint requires authentication.

Supplier users can access only their own scorecard.

Internal authorized users can access supplier scorecards according to their assigned role permissions.

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
On-time delivery    = 75
Invoice accuracy    = 80
Dispute performance = 90
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

Protected application endpoints authenticate users through the Platform Service authentication provider.

Supplier-facing endpoints additionally enforce supplier-level ownership and data scoping.

Authentication, role authorization, and supplier ownership are enforced independently according to the endpoint's access-control requirements.

---

## Root

| Method | Endpoint | Authentication / Role | Description            |
| ------ | -------- | --------------------- | ---------------------- |
| GET    | `/`      | Public                | Service health/message |

---

## Purchase Order APIs

| Method | Endpoint                                          | Authentication / Role | Description                    |
| ------ | ------------------------------------------------- | --------------------- | ------------------------------ |
| POST   | `/api/v1/purchase-orders`                         | `procurement_manager` | Create Purchase Order          |
| GET    | `/api/v1/purchase-orders`                         | Authenticated         | List Purchase Orders           |
| GET    | `/api/v1/purchase-orders/{po_number}`             | Authenticated         | Get Purchase Order             |
| PUT    | `/api/v1/purchase-orders/{po_number}`             | Authenticated         | Update Purchase Order          |
| DELETE | `/api/v1/purchase-orders/{po_number}`             | Authenticated         | Delete Purchase Order          |
| POST   | `/api/v1/purchase-orders/{po_number}/acknowledge` | Owning supplier       | Acknowledge Purchase Order     |
| POST   | `/api/v1/purchase-orders/{po_number}/transition`  | `procurement_manager` | Transition Purchase Order      |
| GET    | `/api/v1/purchase-orders/{po_number}/events`      | Authenticated         | Retrieve Purchase Order events |
| POST   | `/api/v1/purchase-orders/bulk-send`               | `procurement_manager` | Bulk send Purchase Orders      |

For supplier users, ownership is enforced on supplier-facing PO operations.

Internal authorized users access Purchase Orders according to their assigned role permissions.

### Purchase Order Supplier Scoping

For supplier users, the following Purchase Order endpoints require the authenticated supplier to own the requested Purchase Order:

```text
GET    /api/v1/purchase-orders/{po_number}
PUT    /api/v1/purchase-orders/{po_number}
DELETE /api/v1/purchase-orders/{po_number}
POST   /api/v1/purchase-orders/{po_number}/acknowledge
GET    /api/v1/purchase-orders/{po_number}/events
```

Example:

```text
Authenticated Supplier

        │

        ▼

supplier_id = SUP001

        │

        ▼

Requested Purchase Order
supplier_id = SUP002

        │

        ▼

HTTP 403 Forbidden
```

The Purchase Order collection endpoint is also supplier-scoped for supplier users:

```http
GET /api/v1/purchase-orders
```

For supplier users, only Purchase Orders belonging to the authenticated supplier are returned.

```text
Supplier SUP001
      │
      ▼
GET /api/v1/purchase-orders
      │
      ▼
Only SUP001 Purchase Orders
```

Internal authenticated users access the collection according to their assigned role permissions.

---

## Invoice APIs

| Method | Endpoint                                                     | Authentication / Role | Description             |
| ------ | ------------------------------------------------------------ | --------------------- | ----------------------- |
| GET    | `/api/v1/invoices`                                           | Authenticated         | List invoices           |
| POST   | `/api/v1/invoices`                                           | Authenticated         | Create invoice          |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}`            | Authenticated         | Get invoice             |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Owning supplier       | Transition invoice      |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust`     | `compliance_officer`  | Adjust disputed invoice |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Owning supplier       | Upload invoice PDF      |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Authenticated         | Download invoice PDF    |

For supplier users, invoice ownership is enforced.

Internal authorized users can access invoices according to their assigned role permissions.

### Invoice Collection Scoping

The invoice collection endpoint requires authentication:

```http
GET /api/v1/invoices
```

For supplier users:

```text
Supplier SUP001

      │

      ▼

GET /api/v1/invoices

      │

      ▼

Only SUP001 invoices
```

The API filters the returned collection using the authenticated supplier's `supplier_id`.

Therefore, a valid supplier token cannot be used to retrieve invoices belonging to another supplier.

Internal authenticated users can access the broader invoice collection according to their assigned role permissions.

---

## Supplier Statistics APIs

| Method | Endpoint                                    | Authentication / Scope | Description                     |
| ------ | ------------------------------------------- | ---------------------- | ------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/stats`     | Authenticated          | Supplier operational statistics |
| GET    | `/api/v1/suppliers/{supplier_id}/scorecard` | Authenticated          | Supplier performance scorecard  |

For supplier users, the authenticated `supplier_id` must match the requested `supplier_id`.

```text
Authenticated supplier_id
        │
        ▼
Requested supplier_id
        │
        ├── Same
        │     │
        │     ▼
        │   Allowed
        │
        └── Different
              │
              ▼
        403 Forbidden
```

### Supplier Not Found Behavior

If the requested supplier does not exist, the API returns:

```text
404 Not Found
```

If the supplier exists but the authenticated supplier does not own that supplier's data, the API returns:

```text
403 Forbidden
```

The distinction is intentional:

```text
Unknown supplier
      │
      ▼
404 Not Found


Existing supplier
+
Wrong supplier ownership
      │
      ▼
403 Forbidden
```

Internal authenticated users may access supplier statistics and scorecards according to their assigned role permissions.

Supplier users without a valid `supplier_id` are rejected from supplier-scoped statistics and scorecard access:

```text
Supplier role
      │
      ▼
supplier_id missing
      │
      ▼
403 Forbidden
```

---

## Maintenance APIs

Maintenance endpoints perform administrative operations on invoice files and require authentication and administrative authorization.

| Method | Endpoint                                     | Authentication / Role | Description                 |
| ------ | -------------------------------------------- | --------------------- | --------------------------- |
| GET    | `/api/v1/maintenance/orphaned-invoice-files` | `compliance_officer`  | Find orphaned invoice PDFs  |
| DELETE | `/api/v1/maintenance/orphaned-invoice-files` | `compliance_officer`  | Purge orphaned invoice PDFs |

Optional query parameter:

```text
older_than_days
```

Default:

```text
1
```

These endpoints are administrative operations and are not intended for anonymous or supplier access.

The intended access model is:

```text
Authenticated User
       │
       ▼
compliance_officer role?
       │
   ┌───┴───┐
   │       │
  Yes      No
   │       │
   ▼       ▼
Allowed   403 Forbidden
```

---

## R5 API Security Summary

The final R5 protected API model is:

| Resource                  | Supplier Access | Internal Role Access             |
| ------------------------- | --------------- | -------------------------------- |
| Own PO                    | Allowed         | According to role                |
| Other supplier PO         | `403 Forbidden` | According to role                |
| Own invoice               | Allowed         | According to role                |
| Other supplier invoice    | `403 Forbidden` | According to role                |
| Own invoice document      | Allowed         | According to role                |
| Other supplier document   | `403 Forbidden` | According to role                |
| Own statistics            | Allowed         | According to role                |
| Other supplier statistics | `403 Forbidden` | According to role                |
| Own scorecard             | Allowed         | According to role                |
| Other supplier scorecard  | `403 Forbidden` | According to role                |
| Missing supplier identity | `403 Forbidden` | Not applicable to internal roles |

The R5 security model therefore provides:

```text
Authentication

      +

Role Authorization

      +

Supplier Data Isolation
```

A successful token verification alone is not sufficient for supplier access.

The authenticated supplier identity must also match the supplier that owns the requested supplier-scoped resource.

---

## R5 Security Principle

The most important security property of the Supplier Portal is:

```text
Valid authentication ≠ unrestricted authorization
```

Authentication establishes:

```text
Who is the user?
```

Authorization establishes:

```text
What role does the user have?
```

Supplier scoping establishes:

```text
Which supplier's data can this supplier access?
```

The complete access-control sequence is:

```text
Bearer Token
      │
      ▼
Platform Service Verification
      │
      ▼
Authenticated User
      │
      ▼
Role Authorization
      │
      ▼
Supplier Ownership Check
      │
      ▼
Resource Access
```

For supplier users, the ownership check verifies that the authenticated `supplier_id` matches the supplier associated with the requested resource.

For internal authorized users, access is determined by the user's assigned role and the authorization rules implemented for the endpoint.

This security model prevents cross-supplier data access while preserving authorized access for internal platform roles.

---

## Round 5 Definition of Done

The Supplier Portal R5 authorization requirement is satisfied when:

```text
Valid supplier authentication

        │

        ▼

Correct supplier identity

        │

        ▼

Correct resource ownership

        │

        ▼

Resource access allowed
```

Cross-supplier access must be rejected:

```text
SUP001 token
      │
      ▼
SUP002 resource
      │
      ▼
403 Forbidden
```

The R5 implementation is covered by automated tests for:

* Cross-supplier Purchase Order access
* Cross-supplier Purchase Order acknowledgement
* Cross-supplier Purchase Order events
* Cross-supplier invoice access
* Cross-supplier invoice document access
* Cross-supplier supplier statistics access
* Cross-supplier supplier scorecard access
* Supplier users without `supplier_id`
* Supplier Purchase Order list filtering
* Supplier invoice list filtering
* Internal-role access to authorized resources

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

The Supplier Portal uses Pydantic Settings for configuration.

Create a `.env` file in the project root when configuration needs to be changed.

Example:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The default Platform authentication URL is:

```text
http://127.0.0.1:8005
```

### Environment Template

The project provides:

```text
.env.example
```

The `.env.example` file contains:

```env
# Platform Service (authentication provider)
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

To create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

The `.env` file should not be committed to source control if it contains sensitive configuration.

The Supplier Portal uses the Platform Service as its centralized authentication provider.

---

# 15. Installation

## Step 1 — Clone/Open the Project

Open the Supplier Portal project directory in VS Code.

Example project location:

```text
services/supplier-portal/
```

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

`python-multipart` is required for invoice PDF upload handling.

---

## Step 5 — Configure Environment

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

The local configuration should contain:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The Platform Service must be available at this address when running authenticated Supplier Portal endpoints.

---

# 16. Running the Services

The Supplier Portal depends on the Platform Service for authentication.

Therefore, the services must be run separately.

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

The Platform Service authentication response provides the authenticated user identity, including:

```text
user_id
email
full_name
role
supplier_id
is_active
```

The Supplier Portal uses the returned `supplier_id` for supplier-level authorization.

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
│      Supplier Portal        │
│                             │
│       Port 8000             │
│                             │
│ PO / Invoice / Statistics   │
│ Scorecard / Documents       │
└─────────────────────────────┘
```

Authentication flow:

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
Authenticated User
  │
  ├── user_id
  ├── role
  ├── supplier_id
  └── is_active
  │
  ▼
Supplier Portal Authorization
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

Protected endpoints require a valid bearer token.

---

# 18. Testing

The Supplier Portal uses Pytest for automated testing.

The test suite covers:

* Core business logic
* Purchase Order lifecycle
* Invoice lifecycle
* Supplier statistics and scorecards
* Authentication
* Role-based authorization
* Supplier-level resource ownership
* Collection-level supplier filtering
* Document security
* Round 5 supplier-scoping requirements
* Authentication-required endpoint protection

Run the complete test suite with:

```powershell
python -m pytest -v
```

The test suite uses `python -m pytest` so that the tests run using the active Python environment.

---

## Purchase Order Tests

Run the Purchase Order test suite:

```powershell
python -m pytest tests/test_purchase_order.py -v
```

The Purchase Order tests cover:

* PO creation
* PO retrieval
* PO listing
* PO update
* PO deletion
* Duplicate PO handling
* PO acknowledgement
* Legal state transitions
* Illegal state transitions
* Cancellation
* Terminal states
* Transition history
* Event retrieval
* Actor tracking
* Timestamp tracking
* Delivery tracking
* Bulk PO sending

### R5 Authorization and Supplier-Scoping Tests

The Purchase Order tests additionally validate:

* Supplier can access its own Purchase Order
* Supplier cannot access another supplier's Purchase Order
* Supplier can acknowledge its own Purchase Order
* Supplier cannot acknowledge another supplier's Purchase Order
* Supplier can view its own Purchase Order events
* Supplier cannot view another supplier's Purchase Order events
* Supplier can view only its own Purchase Orders through the PO list endpoint
* Supplier cannot retrieve another supplier's Purchase Orders through the PO list endpoint
* Supplier can update its own Purchase Order
* Supplier cannot update another supplier's Purchase Order
* Supplier can delete its own Purchase Order
* Supplier cannot delete another supplier's Purchase Order
* Supplier cannot perform procurement-manager-only PO transitions
* Supplier cannot perform procurement-manager-only bulk PO sending
* Unauthorized roles are rejected
* Supplier ownership is validated using the authenticated `supplier_id`

The PO scoping rule is:

```text
Authenticated Supplier
        │
        ▼
supplier_id = SUP001
        │
        ▼
Requested PO
        │
        ├── supplier_id = SUP001 → Allowed
        │
        └── supplier_id = SUP002 → 403 Forbidden
```

---

## Invoice Tests

Run the Invoice test suite:

```powershell
python -m pytest tests/test_invoices.py -v
```

The Invoice tests cover:

* Valid invoice creation
* Invoice retrieval
* Invoice listing
* Duplicate invoice protection
* Invalid invoice number
* Invalid supplier ID
* Missing Purchase Order
* Invalid Purchase Order status
* Purchase Order supplier mismatch
* Invoice item validation
* Quantity validation
* Unit-price tolerance
* Invoice amount validation
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
* Compliance-officer authorization

### R5 Authorization and Supplier-Scoping Tests

The Invoice tests additionally validate:

* Supplier can access its own invoice
* Supplier cannot access another supplier's invoice
* Supplier can view only its own invoices through the invoice list endpoint
* Supplier cannot retrieve another supplier's invoices through the invoice list endpoint
* Supplier cannot transition another supplier's invoice
* Supplier cannot upload a document for another supplier's invoice
* Supplier cannot download another supplier's invoice document
* Supplier cannot create an invoice for another supplier
* Supplier cannot perform compliance-only invoice adjustment
* Compliance officer can perform authorized invoice adjustment
* Authenticated supplier identity is matched against invoice `supplier_id`
* Supplier ownership is enforced for supplier-facing invoice endpoints

The invoice scoping rule is:

```text
Authenticated Supplier
        │
        ▼
supplier_id = SUP001
        │
        ▼
Requested Invoice
        │
        ├── supplier_id = SUP001 → Allowed
        │
        └── supplier_id = SUP002 → 403 Forbidden
```

The invoice collection endpoint is also tested for supplier-level filtering.

```text
Supplier SUP001
       │
       ▼
GET /api/v1/invoices
       │
       ▼
Only SUP001 invoices returned
```

---

## Supplier Statistics and Scorecard Tests

Run the Supplier Statistics and Scorecard test suite:

```powershell
python -m pytest tests/test_supplier_stats.py -v
```

The tests cover:

* Supplier statistics
* Supplier not found
* Purchase Order count
* On-time delivery
* Late delivery
* Mixed delivery performance
* Unfulfilled Purchase Orders
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

### R5 Authorization and Supplier-Scoping Tests

The tests validate:

* Supplier can access its own statistics
* Supplier cannot access another supplier's statistics
* Supplier can access its own scorecard
* Supplier cannot access another supplier's scorecard
* Second supplier can access its own statistics
* Second supplier cannot access another supplier's statistics
* Supplier token without `supplier_id` is rejected
* Unknown supplier statistics request returns `404`
* Unknown supplier scorecard request returns `404`
* Authorized internal roles can access other suppliers' statistics
* Authorized internal roles can access other suppliers' scorecards
* Supplier ownership is validated using authenticated `supplier_id`

The expected behavior is:

```text
Known supplier
+
Matching supplier_id
        │
        ▼
Allowed


Known supplier
+
Different supplier_id
        │
        ▼
403 Forbidden


Supplier role
+
Missing supplier_id
        │
        ▼
403 Forbidden


Unknown supplier
        │
        ▼
404 Not Found
```

The distinction between `403` and `404` is intentional.

A known supplier requested by the wrong authenticated supplier results in `403 Forbidden`, while a supplier that does not exist results in `404 Not Found`.

---

## Authentication and Authorization Tests

Run the authentication test suite:

```powershell
python -m pytest tests/test_auth.py -v
```

The authentication and authorization tests validate the authentication path between the Supplier Portal and Platform Service.

Tests cover:

* Valid access-token verification
* Missing authentication token
* Invalid authentication token
* Expired authentication token
* Authentication service unavailable
* Authentication service timeout
* Unexpected authentication-service response
* Invalid authentication-service JSON response
* Authentication response with `valid = false`
* Missing `user_id` from authentication response
* Missing user role
* Supplier identity returned by Platform Service
* `supplier_id` propagation
* `X-Request-ID` generation and forwarding
* Allowed role authorization
* Unauthorized role rejection
* Procurement-manager role authorization
* Role-based access control
* Authentication failure handling

The authentication flow is:

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

Authenticated User

   │

   ├── user_id
   ├── email
   ├── full_name
   ├── role
   ├── supplier_id
   └── is_active

   │

   ▼

Supplier Portal Authorization
```

Authentication establishes the identity of the caller.

Authorization then determines whether the caller's role and supplier identity allow access to the requested resource.

---

## Authentication-Required Endpoint Tests

The project includes:

```text
tests/test_requires_auth.py
```

This test module verifies that protected endpoints cannot be accessed without authentication.

The test removes the authentication dependency override used by the normal test suite and executes the real authentication dependency.

The protected routes are discovered automatically from the Supplier Portal API routers rather than maintaining a hardcoded list of endpoint URLs.

Currently, the test discovers and validates:

```text
20 protected endpoint/method combinations
```

Run these tests with:

```powershell
python -m pytest tests/test_requires_auth.py -v
```

Expected result:

```text
20 passed
```

The test confirms that every discovered protected endpoint rejects a request without an `Authorization` header.

Expected unauthenticated responses are:

```text
401 Unauthorized
```

or:

```text
403 Forbidden
```

This test protects against accidentally removing authentication dependencies from protected routes.

---

## R5 Supplier-Scoping Validation

Round 5 specifically validates that authentication alone does not provide unrestricted supplier access.

The core security rule is:

```text
A valid supplier token does not provide unrestricted supplier access.

The authenticated supplier must own the requested resource.
```

### Own Resource

```text
Supplier A Token

       │

       │ supplier_id = SUP001

       ▼

Requested Resource

       │

       │ supplier_id = SUP001

       ▼

Access Allowed
```

### Other Supplier Resource

```text
Supplier A Token

       │

       │ supplier_id = SUP001

       ▼

Requested Resource

       │

       │ supplier_id = SUP002

       ▼

403 Forbidden
```

The R5 test suite validates supplier ownership across:

```text
Purchase Orders
PO Acknowledgement
PO Events
PO Updates
PO Deletions
Purchase Order Listing
Invoices
Invoice Listing
Invoice Transitions
Invoice Documents
Supplier Statistics
Supplier Scorecards
```

It also validates:

```text
Supplier without supplier_id → 403 Forbidden

Supplier accessing another supplier's resource
                              → 403 Forbidden

Unauthorized role             → 403 Forbidden

Missing token                 → 401 Unauthorized

Invalid token                 → 401 Unauthorized

Authentication service failure
                              → 503 Service Unavailable
```

---

## R5 Supplier-Scoping Matrix

The expected access behavior is:

| Request                                            | Expected Result           |
| -------------------------------------------------- | ------------------------- |
| Supplier → Own PO                                  | Allowed                   |
| Supplier → Other supplier PO                       | `403 Forbidden`           |
| Supplier → Own invoice                             | Allowed                   |
| Supplier → Other supplier invoice                  | `403 Forbidden`           |
| Supplier → Own invoice document                    | Allowed                   |
| Supplier → Other supplier document                 | `403 Forbidden`           |
| Supplier → Own statistics                          | Allowed                   |
| Supplier → Other supplier statistics               | `403 Forbidden`           |
| Supplier → Own scorecard                           | Allowed                   |
| Supplier → Other supplier scorecard                | `403 Forbidden`           |
| Supplier without `supplier_id` → Supplier resource | `403 Forbidden`           |
| Internal authorized role → Other supplier data     | Allowed according to role |

The R5 test suite therefore validates both:

```text
Resource-Level Ownership

            +

Collection-Level Filtering
```

---

## Authentication Test Configuration

The normal test suite uses authentication dependency overrides for isolated authorization and business-logic testing.

This allows individual tests to simulate different authenticated identities without requiring the real Platform Service for every unit or API test.

Test identities include:

```text
Supplier SUP001

Supplier SUP002

Procurement Manager

Compliance Officer

Supplier without supplier_id
```

These identities allow the test suite to validate:

```text
Supplier A → Supplier A resource
            → Allowed

Supplier A → Supplier B resource
            → 403 Forbidden

Supplier without supplier_id
            → Supplier resource
            → 403 Forbidden

Supplier → Compliance-only endpoint
         → 403 Forbidden

Supplier → Procurement-only endpoint
         → 403 Forbidden

Compliance Officer
         → Authorized invoice adjustment
         → Allowed

Procurement Manager
         → Authorized Purchase Order operation
         → Allowed
```

Multiple supplier identities are used so cross-supplier access can be tested explicitly.

---

## R5 Test Coverage Summary

The Round 5 test strategy validates four separate security layers:

```text
Authentication
      │
      ▼
Role-Based Authorization
      │
      ▼
Supplier Ownership / Scoping
      │
      ▼
Collection-Level Filtering
```

This is combined with the existing business-rule and validation test coverage:

```text
Authentication

       +

Authorization

       +

Supplier Scoping

       +

Collection Filtering

       +

Business Rules

       +

Input Validation

       +

Document Security
```

The R5 tests therefore verify the key requirement:

```text
A supplier can access only resources belonging
to its authenticated supplier_id.
```

Cross-supplier access is explicitly tested and must return:

```text
HTTP 403 Forbidden
```

for existing resources owned by another supplier.

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

### Purchase Order Authorization Rules

Purchase Order creation is restricted to:

```text
procurement_manager
```

For supplier users, requested Purchase Orders must belong to the authenticated supplier.

Therefore:

```text
Supplier SUP001 → PO SUP001 = Allowed

Supplier SUP001 → PO SUP002 = 403 Forbidden
```

PO collection access is also supplier-scoped for supplier users:

```text
Supplier SUP001 → GET /purchase-orders
                ↓
Only SUP001 Purchase Orders returned
```

Internal authorized users can access Purchase Orders according to their assigned role permissions.

For read operations such as retrieving a Purchase Order or its events, internal authorized users are not restricted by supplier ownership.

Supplier ownership checks apply specifically to supplier users.

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

### Invoice Authorization Rules

Supplier users must be authenticated before accessing supplier-facing invoice resources.

For supplier users:

```text
Authenticated supplier_id

        =

Invoice supplier_id
```

must be true.

If they do not match:

```text
403 Forbidden
```

Invoice collection access is also filtered by supplier:

```text
Supplier SUP001

      │

      ▼

GET /api/v1/invoices

      │

      ▼

Only SUP001 invoices returned
```

Internal authorized users can access invoice data according to their assigned role permissions.

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

## Supplier Access-Control Rule

Supplier-level authorization is applied in addition to authentication.

The security rule is:

```text
Authentication

      +

Role Authorization

      +

Supplier Ownership
```

A valid token alone does not authorize a supplier to access another supplier's resources.

Internal authorized users are governed by their assigned role permissions.

---

# 20. Security Controls

The service implements several security controls.

## Authentication

* Bearer token authentication
* Central authentication through Platform Service
* Authentication timeout handling
* Authentication-service failure handling
* Request ID propagation
* Authentication response validation
* Supplier identity retrieval through `supplier_id`

## Authorization

* Role-based authorization
* Supplier ownership validation
* Supplier-level collection filtering
* Compliance-officer authorization for invoice adjustment
* Procurement-manager authorization for PO creation
* Procurement-manager authorization for PO transition
* Procurement-manager authorization for bulk PO sending
* Supplier identity validation using authenticated `supplier_id`

## Supplier Data Isolation

R5 introduces explicit supplier-level data isolation.

Supplier users can access only resources belonging to their authenticated supplier.

Internal authorized users can access supplier resources according to their assigned role permissions.

Protected resource categories include:

* Purchase Orders
* Purchase Order events
* Invoices
* Invoice documents
* Supplier statistics
* Supplier scorecards

Cross-supplier access by supplier users is rejected with:

```text
403 Forbidden
```

A supplier without a valid `supplier_id` is also rejected from supplier-scoped resources:

```text
403 Forbidden
```

Collection endpoints are filtered so that supplier users do not receive other suppliers' records.

---

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
                    Supplier Authentication
                             │
                             ▼
                    Supplier Ownership Check
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
               ┌─────────────┼─────────────┐
               │             │             │
               ▼             ▼             ▼
          Validate PO   Validate Items   Validate Amount
               │             │             │
               └─────────────┼─────────────┘
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
                   ┌─────────┴─────────┐
                   ▼                   ▼
              Validate Content    Validate Signature
                   │                   │
                   └─────────┬─────────┘
                             ▼
                         Store PDF
                             │
                             ▼
                    Supplier Statistics
                             │
                   ┌─────────┴─────────┐
                   ▼                   ▼
                PO Metrics       Invoice Metrics
                   │                   │
                   └─────────┬─────────┘
                             ▼
                    Supplier Scorecard
```

R5 authorization applies to the supplier-facing portions of this workflow.

For example:

```text
Supplier SUP001

      │

      ▼

Authenticated through Platform Service

      │

      ▼

supplier_id = SUP001

      │

      ▼

Requested resource supplier_id = SUP001

      │

      ▼

Allowed
```

Whereas:

```text
Supplier SUP001

      │

      ▼

Requested resource supplier_id = SUP002

      │

      ▼

403 Forbidden
```

---

# 23. Current Implementation Status

| Module                                 | Status    |
| -------------------------------------- | --------- |
| Purchase Order CRUD                    | Complete  |
| PO State Machine                       | Complete  |
| PO Acknowledgement                     | Complete  |
| PO Cancellation                        | Complete  |
| PO Audit Events                        | Complete  |
| PO Delivery Tracking                   | Complete  |
| Bulk PO Send                           | Complete  |
| Invoice Creation                       | Complete  |
| Invoice Validation                     | Complete  |
| Invoice Duplicate Protection           | Complete  |
| Invoice Tolerance                      | Complete  |
| Invoice State Machine                  | Complete  |
| Invoice Disputes                       | Complete  |
| Invoice Adjustments                    | Complete  |
| PDF Upload                             | Complete  |
| PDF Download                           | Complete  |
| PDF Signature Validation               | Complete  |
| File Size Validation                   | Complete  |
| Path Traversal Protection              | Complete  |
| Supplier Statistics                    | Complete  |
| Supplier Scorecard                     | Complete  |
| Supplier Authentication                | Complete  |
| Supplier Scoping                       | Complete  |
| Supplier Collection Filtering          | Complete  |
| Role-Based Authorization               | Complete  |
| Cross-Supplier Access Protection       | Complete  |
| Missing Supplier Identity Protection   | Complete  |
| Platform Authentication Integration    | Complete  |
| Authentication-Required Endpoint Tests | Complete  |
| Automated Tests                        | Complete  |
| R5 Supplier-Scoping Tests              | Complete  |
| Swagger Documentation                  | Available |

### Authentication-Required Endpoint Coverage

Authentication-required endpoint coverage is implemented in:

```text
tests/test_requires_auth.py
```

The test automatically discovers protected API routes from the Supplier Portal routers.

Currently, it validates:

```text
20 protected endpoint/method combinations
```

The test confirms that protected endpoints reject requests without authentication.

Run:

```powershell
python -m pytest tests/test_requires_auth.py -v
```

---

## R5 Completion Status

Round 5 supplier authentication, role authorization, and supplier-level data-scoping requirements have been implemented and covered by automated tests.

The implemented security model ensures:

```text
Valid supplier token

      ≠

Unrestricted supplier access
```

Instead, access follows this sequence:

```text
Valid Token

     │

     ▼

Platform Service Verification

     │

     ▼

Authenticated Identity

     │

     ▼

Role Check

     │

     ▼

supplier_id Ownership Check

     │

     ▼

Resource Access
```

For supplier users, the authenticated `supplier_id` must match the supplier associated with the requested supplier-scoped resource.

Cross-supplier access attempts are rejected with:

```text
403 Forbidden
```

Supplier users without a valid `supplier_id` are rejected from supplier-scoped resources with:

```text
403 Forbidden
```

Supplier collection endpoints are also protected by authentication and return only records belonging to the authenticated supplier.

Internal authorized users can access supplier data according to their assigned role permissions.

Unknown supplier resources return:

```text
404 Not Found
```

while an authenticated supplier attempting to access an existing resource belonging to another supplier receives:

```text
403 Forbidden
```

This distinction is intentional and provides clear separation between resource existence and supplier authorization.

The implemented R5 security controls satisfy the supplier data-isolation requirement.

---

# 24. Known Limitations

The current implementation is primarily designed for the development and testing phase.

The core authentication, role-based authorization, and supplier-level data-scoping requirements have been implemented and tested.

The remaining limitations are primarily related to production persistence, durable file storage, service availability, and operational hardening.

---

## In-Memory Business Storage

Purchase Orders, invoices, and related business events are currently stored in Python in-memory data structures.

As a result, application restarts clear the stored business data.

```text
Application Restart

       │

       ▼

In-Memory Data Cleared

       │

       ▼

Purchase Orders / Invoices / Events Lost
```

This storage model is suitable for development and automated testing but is not suitable for durable production business data.

A production deployment should use persistent database storage.

---

## Local File Storage

Invoice PDF documents are currently stored locally under:

```text
uploads/
```

Local file storage is suitable for the current development environment but does not provide the durability, scalability, and availability expected from production deployments.

A production implementation should use durable object or document storage.

Recommended production capabilities include:

* Durable document storage
* Appropriate access controls
* Backup and recovery
* Encryption at rest
* Retention management
* Scalable storage

---

## Authentication Dependency

Authentication depends on the Platform Service being available at the configured authentication URL.

The Supplier Portal sends authentication requests to the Platform Service for token verification.

If the Platform Service is unavailable or authentication verification times out, protected endpoints can return:

```text
503 Service Unavailable
```

This dependency is intentional because the Platform Service is the centralized authentication provider for the microservice architecture.

Production deployments should therefore provide appropriate service availability, monitoring, timeout handling, and operational recovery mechanisms for the Platform Service.

---

## Administrative and Maintenance Endpoint Hardening

Core supplier-facing authentication, role-based authorization, and supplier-level data scoping are implemented as part of the R5 security model.

Supplier-facing resources are protected using:

```text
Authentication

      +

Role Authorization

      +

Supplier Ownership
```

The protected supplier-facing areas include:

* Purchase Orders
* Purchase Order events
* Invoices
* Invoice documents
* Supplier statistics
* Supplier scorecards
* Supplier collection endpoints

Supplier users can access only resources belonging to their authenticated `supplier_id`.

Administrative maintenance operations require separate administrative authorization and remain restricted from supplier users and anonymous callers.

The maintenance endpoints are:

```text
GET    /api/v1/maintenance/orphaned-invoice-files

DELETE /api/v1/maintenance/orphaned-invoice-files
```

These operations should remain restricted to the designated administrative role:

```text
compliance_officer
```

They should never be exposed as anonymous endpoints because they inspect or modify server-side invoice files.

---

## Production Persistence

The current in-memory storage and local-file storage model is suitable for development and testing but is not sufficient for durable production operation.

A production implementation should introduce:

* Persistent database storage
* Transaction management
* Database-backed Purchase Order records
* Database-backed invoice records
* Persistent event and audit history
* Durable supplier records
* Durable document/object storage
* Backup and recovery procedures

The production persistence architecture should preserve the existing authorization model so that moving from in-memory storage to persistent storage does not weaken supplier-level data isolation.

---

## Production Operational Hardening

Before production deployment, the service should additionally be evaluated for:

* Centralized logging and monitoring
* Health and readiness checks
* Database connection management
* Distributed request tracing
* Secure secret management
* TLS configuration
* Rate limiting where appropriate
* Backup and recovery procedures
* File-storage lifecycle management
* Authentication-service availability monitoring

These are production-readiness considerations and do not change the implemented R5 supplier-scoping security model.

---

## R5 Security Status

The following R5 security requirements are implemented:

```text
Platform Service Authentication

            │

            ▼

Role-Based Authorization

            │

            ▼

Supplier Ownership Validation

            │

            ▼

Collection-Level Supplier Filtering

            │

            ▼

Protected Resource Access
```

The key R5 security requirement is therefore satisfied:

```text
A valid supplier token does not provide unrestricted supplier access.
```

A supplier authenticated as `SUP001` cannot access supplier-scoped resources belonging to `SUP002`.

Cross-supplier access is rejected with:

```text
403 Forbidden
```

The implemented R5 model also protects supplier collection endpoints from returning other suppliers' records.

The remaining limitations described in this section are primarily related to:

```text
Production Persistence

Durable File Storage

Authentication Service Availability

Operational Hardening
```

rather than the core R5 supplier-scoping requirement.
