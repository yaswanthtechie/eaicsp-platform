# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for managing supplier-facing Purchase Orders, invoices, invoice documents, supplier operational statistics, supplier performance scorecards, supplier onboarding, and the procure-to-pay workflow.

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
12. [Procure-to-Pay Lifecycle](#12-procure-to-pay-lifecycle)
13. [Three-Way Match](#13-three-way-match)
14. [Supplier Onboarding](#14-supplier-onboarding)
15. [API Reference](#15-api-reference)
16. [HTTP Response Codes](#16-http-response-codes)
17. [Configuration](#17-configuration)
18. [Installation](#18-installation)
19. [Running the Services](#19-running-the-services)
20. [Swagger Documentation](#20-swagger-documentation)
21. [Testing](#21-testing)
22. [Business Rules](#22-business-rules)
23. [Security Controls](#23-security-controls)
24. [Storage](#24-storage)
25. [End-to-End Workflow](#25-end-to-end-workflow)
26. [Current Implementation Status](#26-current-implementation-status)
27. [Known Limitations](#27-known-limitations)
28. [Future Enhancements](#28-future-enhancements)

---

# 1. Overview

The **Supplier Portal Service** provides backend APIs for supplier and procurement workflows.

The service manages the following major functional areas:

```text
1. Purchase Order Management
2. Procure-to-Pay Processing
3. Shipment Notice Management
4. Goods Receipt Management
5. Invoice Management
6. Three-Way Match Processing
7. Payment Approval Workflow
8. Supplier Onboarding
9. Supplier Statistics
10. Supplier Performance Scorecard
11. Invoice Document Management
12. Authentication, Authorization, and Supplier Scoping
```

The implemented procure-to-pay flow is:

```text
Purchase Order
      │
      ▼
Acknowledgement
      │
      ▼
Shipment Notice
      │
      ▼
Goods Receipt
      │
      ▼
Invoice
      │
      ▼
Three-Way Match
      │
      ├── Matched
      │
      └── Discrepancy
              │
              ▼
         Human Review
              │
              ▼
       Payment Approval
```

Three-way matching compares:

```text
Purchase Order
      +
Goods Receipt
      +
Invoice
      │
      ▼
Match Result
      │
      ├── Matched
      │
      └── Discrepancy
            ├── Quantity Difference
            └── Price Difference
```

Discrepancies are identified by the matching process and are not automatically treated as approved transactions.

Supplier onboarding is implemented as a separate supplier lifecycle:

```text
Registration
      │
      ▼
Document Collection
      │
      ▼
Mock Verification
      │
      ▼
Approval
      │
      ▼
Active
```

A supplier must be **registered and active** before a Purchase Order can be created for that supplier.

Supplier-level authorization introduced in Round 5 remains enforced throughout supplier-facing workflows.

---

## Existing Status & Known Gaps

The current Supplier Portal implementation includes:

* Platform Service authentication
* Role-based authorization
* Supplier-level resource scoping
* Purchase Order management
* Purchase Order lifecycle management
* Shipment notices
* Goods Receipt processing
* Invoice processing
* Three-way matching
* Quantity and price discrepancy detection
* Human-review handling for discrepancies
* Payment approval workflow states
* Supplier onboarding
* Active-supplier enforcement during PO creation
* Supplier statistics
* Supplier performance scorecards
* Invoice document security
* Automated business-rule testing
* Supplier isolation and cross-supplier security testing

The five reviewer-identified functional issues were addressed:

```text
1. Three-way match discrepancy reachability       → Fixed
2. Scorecard invoice metrics                      → Fixed
3. Supplier ID existence leak                     → Fixed
4. Supplier onboarding enforcement                → Fixed
5. Future-due PO handling in on-time metrics      → Fixed
```

The remaining limitations are primarily related to persistence, infrastructure, and future workflow enhancements.

Current infrastructure limitations include:

* Purchase Orders, invoices, P2P records, onboarding data, and audit events use in-memory storage.
* In-memory business data is not persistent across service restarts.
* Invoice PDF documents use local filesystem storage.
* Authentication depends on the availability of the Platform Service.
* Production deployment requires persistent storage and additional operational hardening.

The current implementation is suitable for development, functional validation, API testing, and workflow verification. Production deployment requires additional infrastructure and operational controls.

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
* Supplier onboarding validation during PO creation
* Active supplier enforcement

## Invoices

* Create invoices
* Retrieve invoices
* Validate invoice data
* Validate Purchase Order existence
* Validate Purchase Order status
* Validate supplier ownership
* Validate invoice line items
* Validate invoice amounts
* Duplicate invoice protection
* Partial invoice creation support
* Multiple invoice items
* Invoice state transitions
* Invoice disputes
* Invoice adjustments
* Compliance-officer dispute adjustment
* Invoice history
* Invoice/P2P integration
* Price discrepancy support for three-way matching
* Quantity discrepancy support for three-way matching

> The invoice service does not block a price difference merely because it exceeds the three-way-match tolerance. Price differences must be allowed to reach the matching stage so that the matching process can identify and flag the discrepancy.

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
* Invoice performance metrics
* Date normalization
* Missing delivery-data handling
* Invalid date handling
* Supplier existence validation
* Future-due PO exclusion from on-time calculations
* Past-due unfulfilled PO handling

The on-time delivery denominator uses a common delivery-eligibility rule:

```text
Fulfilled PO
      → Eligible

Past-due unfulfilled PO
      → Eligible and counted as late

Future-due unfulfilled PO
      → Not eligible

Cancelled PO
      → Not eligible

PO without expected delivery date
      → Not eligible
```

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
* Invoice cycle-time calculation
* Monthly performance trend
* Supplier-scoped scorecard access

Invoice-related scorecard calculations use the `po_number` stored on invoice line items.

## Procure-to-Pay

* Complete PO-to-payment workflow
* PO acknowledgement
* Shipment notice processing
* Goods Receipt processing
* Partial/short Goods Receipt support
* P2P state transitions
* Invoice integration with P2P state
* Three-way PO/Receipt/Invoice matching
* Quantity discrepancy detection
* Price discrepancy detection
* Human-review handling for discrepancies
* Payment approval workflow
* Out-of-order transition rejection

## Supplier Onboarding

* Supplier registration
* Supplier document collection
* Mock supplier verification
* Supplier approval workflow
* Supplier activation
* Supplier-scoped onboarding access
* Onboarding lifecycle state management
* Active supplier validation before PO creation

## Three-Way Match

* Purchase Order matching
* Goods Receipt matching
* Invoice matching
* Quantity validation
* Price validation
* Match/discrepancy determination
* Quantity discrepancy detection
* Price discrepancy detection
* Human-review handling for discrepancies
* Prevention of automatic approval when a discrepancy exists

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
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
     Purchase           Invoice         Supplier
      Orders             Routes           Routes
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    Authentication /
                    Authorization
                           │
                           ▼
                     Service Layer
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       PO Store       Invoice Store    Supplier Stores
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                    P2P State Management
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
      Shipment       Goods Receipt       Invoice
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    Three-Way Match
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
               Matched         Discrepancy
                                    │
                                    ▼
                              Human Review
                                    │
                                    ▼
                            Payment Approval
```

Authentication is handled through the Platform Service:

```text
Client
  │
  │ Bearer Token
  ▼
Supplier Portal
  │
  │ Token Verification Request
  ▼
Platform Service
  │
  ▼
User Identity
+ Role
+ Supplier ID
+ Active Status
  │
  ▼
Supplier Portal Authorization
  │
  ▼
Resource Access
```

## Procure-to-Pay Architecture

The Supplier Portal extends the existing layered architecture with a dedicated procure-to-pay workflow layer.

```text
                         Client
                           │
                           ▼
                   FastAPI Application
                           │
                           ▼
                         Routes
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       PO Routes      Invoice Routes   Supplier Routes
          │                │                │
          ▼                ▼                ▼
       PO Service      Invoice Service   Supplier Services
          │                │                │
          └────────────────┼────────────────┘
                           │
                           ▼
                  P2P State Management
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       Shipment       Goods Receipt       Invoice
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    Three-Way Match
                           │
                  ┌────────┴────────┐
                  │                 │
                  ▼                 ▼
               Matched         Discrepancy
                                    │
                                    ▼
                              Human Review
                                    │
                                    ▼
                            Payment Approval
```

The P2P state machine is separate from the existing Purchase Order lifecycle state machine.

### Purchase Order Lifecycle

The Purchase Order lifecycle represents the business status of the Purchase Order itself:

```text
draft
  │
  ▼
sent
  │
  ▼
acknowledged
  │
  ▼
fulfilled
```

Cancellation is available through the legal PO transition rules.

### P2P State Machine

The P2P state machine represents the Purchase Order's progress through the procure-to-pay process:

```text
acknowledged
      │
      ▼
shipped
      │
      ▼
received
      │
      ▼
invoiced
      │
      ▼
matched / discrepancy
      │
      ▼
payment_approved
```

These state models serve different purposes and must not be treated as the same state machine.

### Layer Responsibilities

```text
Routes
   │
   ▼
Authentication / Authorization
   │
   ▼
Business Services
   │
   ▼
P2P State Management
   │
   ▼
In-Memory Business Stores
```

The P2P workflow reuses the existing Purchase Order and Invoice business objects rather than creating an unrelated parallel PO/invoice system.

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
│   │   ├── shipment.py
│   │   ├── goods_receipt.py
│   │   ├── invoice.py
│   │   ├── three_way_match.py
│   │   ├── supplier_onboarding.py
│   │   └── supplier_stats_routes.py
│   │
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   ├── shipment.py
│   │   ├── goods_receipt.py
│   │   ├── invoice.py
│   │   ├── three_way_match.py
│   │   ├── supplier_onboarding.py
│   │   └── supplier_stats.py
│   │
│   └── services/
│       ├── purchase_order_service.py
│       ├── shipment_service.py
│       ├── goods_receipt_service.py
│       ├── invoice_service.py
│       ├── three_way_match_service.py
│       ├── supplier_onboarding_service.py
│       ├── supplier_stats_service.py
│       └── po_p2p_state_machine.py
│
├── tests/
│   ├── conftest.py
│   ├── test_purchase_order.py
│   ├── test_invoices.py
│   ├── test_auth.py
│   ├── test_requires_auth.py
│   ├── test_supplier_stats.py
│   ├── test_shipment.py
│   ├── test_goods_receipt.py
│   ├── test_three_way_match.py
│   └── test_supplier_onboarding.py
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
* Exposing the Supplier Portal API modules

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
* Handling Platform Service timeout, unavailable, and invalid authentication responses

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
* Resource existence validation
* Calling the appropriate service-layer functions

The Supplier Portal currently exposes routes for:

* Purchase-order management
* Shipment notices
* Goods receipts
* Invoice management and invoice documents
* Three-way matching and payment approval
* Supplier onboarding
* Supplier statistics and performance scorecards

For supplier-scoped detail endpoints, ownership authorization is performed before exposing resource existence to the supplier caller. This prevents a supplier from distinguishing another supplier's existing resource from a missing resource through different response statuses.

### Schemas

The schema layer is responsible for:

* Request validation
* Response validation
* Field constraints
* Regex validation
* Percentage and numeric boundaries
* Purchase-order data models
* Shipment data models
* Goods-receipt data models
* Invoice data models
* Three-way-match data models
* Supplier-onboarding data models
* Supplier-statistics and scorecard data models

### Services

The service layer is responsible for:

* Business rules and validation
* Purchase-order processing
* Purchase-order lifecycle state transitions
* Procure-to-pay state transitions
* Shipment processing
* Goods-receipt processing
* Invoice processing
* Invoice lifecycle state transitions
* Three-way matching
* Discrepancy detection and resolution
* Payment-approval processing
* Supplier onboarding workflow
* Supplier activation checks
* Supplier performance calculations
* Supplier scorecard calculations
* Invoice and purchase-order processing
* Invoice document handling
* Supplier-scoped business operations

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

The Platform Service provides the authenticated supplier's `supplier_id` as part of the authentication response.

The authentication request also includes:

```text
X-Caller-Service
X-Caller-Endpoint
X-Request-ID
```

If the client does not provide an `X-Request-ID`, the Supplier Portal generates a request ID before calling the Platform Service.

## Authentication Configuration

The Platform Service URL is configured using:

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

The Supplier Portal communicates with the Platform Service using the configured `PLATFORM_AUTH_URL`.

## Authentication Errors

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

This applies to supplier-scoped resources such as:

* Purchase Orders
* Purchase Order events
* Invoices
* Invoice documents
* Supplier statistics
* Supplier scorecards
* Shipments
* Goods Receipts
* Three-way match records
* Supplier onboarding records

A supplier user without a valid `supplier_id` is rejected from supplier-scoped resources:

```text
Supplier Role
     │
     ▼
supplier_id missing
     │
     ▼
HTTP 403 Forbidden
```

For affected supplier-scoped detail endpoints, authorization is checked before resource existence is revealed. This avoids leaking whether another supplier's resource ID exists.

## Supplier List Filtering

Collection endpoints are protected by authentication and supplier-level filtering.

The following endpoints require authentication:

```http
GET /api/v1/purchase-orders
GET /api/v1/invoices
```

When the authenticated user has the `supplier` role, the Supplier Portal returns only records belonging to that supplier.

Internal authorized users can access broader data according to the current role-based access implementation.

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

This ensures authenticated supplier users cannot retrieve another supplier's records through collection endpoints.

## Role-Based Authorization

The Supplier Portal supports role-based authorization through:

```python
require_roles(...)
```

Important roles include:

```text
procurement_manager
compliance_officer
warehouse_manager
supplier
```

Examples of role-based restrictions include:

* Purchase Order creation requires `procurement_manager`
* Purchase Order transition requires `procurement_manager`
* Bulk Purchase Order sending requires `procurement_manager`
* Invoice adjustment requires `compliance_officer`
* Goods Receipt creation requires `warehouse_manager`
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
SUP001 token → SUP001 PO         → Allowed
SUP001 token → SUP002 PO         → 403 Forbidden

SUP001 token → SUP001 Invoice    → Allowed
SUP001 token → SUP002 Invoice    → 403 Forbidden

SUP001 token → SUP001 Scorecard  → Allowed
SUP001 token → SUP002 Scorecard  → 403 Forbidden
```

The same ownership principle applies to supplier-scoped Purchase Order events, invoice documents, statistics, shipments, goods receipts, three-way matches, and onboarding resources.

Supplier-level authorization is enforced at the API layer and covered by automated tests, including:

* Supplier cannot view another supplier's Purchase Order
* Supplier cannot acknowledge another supplier's Purchase Order
* Supplier cannot view another supplier's Invoice
* Supplier cannot access another supplier's Scorecard
* Supplier cannot access another supplier's Statistics
* Supplier token without `supplier_id` is rejected
* Supplier collection endpoints return only the authenticated supplier's resources
* Supplier detail endpoints do not reveal another supplier's resource existence through different missing/existing responses

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

## PO Lifecycle

```text
             ┌─────────────┐
             │  Cancelled  │
             └─────────────┘
                  ▲
                  │
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

## PO Creation

Endpoint:

```http
POST /api/v1/purchase-orders
```

Authorization:

```text
procurement_manager
```

Before creating a Purchase Order, the service verifies that the referenced supplier exists and has completed onboarding with:

```text
status = active
```

Therefore:

```text
Unregistered Supplier
        │
        ▼
PO Creation
        │
        ▼
Rejected

Pending/Inactive Supplier
        │
        ▼
PO Creation
        │
        ▼
Rejected

Active Supplier
        │
        ▼
PO Creation
        │
        ▼
Allowed
```

This prevents Purchase Orders from being created for suppliers that have not completed the required onboarding lifecycle.

The service validates:

* PO number
* Supplier ID
* Supplier onboarding/active status
* Items
* Quantity
* Unit price
* Total amount
* Expected delivery
* Duplicate PO number

The calculated item total must match the submitted `total_amount`.

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

Internal authorized users can access the broader Purchase Order collection according to the current role-based access implementation.

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

## PO Update

Endpoint:

```http
PUT /api/v1/purchase-orders/{po_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the requested Purchase Order.

A supplier cannot update another supplier's Purchase Order.

## PO Delete

Endpoint:

```http
DELETE /api/v1/purchase-orders/{po_number}
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the requested Purchase Order.

Supplier ownership is checked before the Purchase Order is deleted.

Historical PO events remain retained after deletion.

## PO Acknowledgement

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/acknowledge
```

The endpoint is supplier-scoped and restricted to the owning supplier.

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

The service validates the current state before performing the transition.

The authenticated user's identity is used for transition auditing rather than trusting the actor value supplied by the request body.

An illegal transition returns:

```text
400 Bad Request
```

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

## Delivery Tracking

When a PO reaches:

```text
fulfilled
```

the service records:

```text
actual_delivery_date
```

Delivery performance uses:

```text
actual_delivery_date <= expected_delivery
```

Therefore:

```text
Before expected date → On time
Expected date        → On time
After expected date  → Late
```

For supplier statistics and scorecards, future-due unfulfilled POs are excluded from the on-time denominator, while past-due unfulfilled POs are treated as late.

---

# 8. Invoice Management

Invoices are linked to Purchase Orders and suppliers.

An invoice can only be created when its referenced PO satisfies the required business rules.

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

Invoice line items contain the PO reference used by supplier performance calculations and matching.

The invoice lookup key is:

```text
(supplier_id, invoice_number)
```

This means invoice numbers are unique within a supplier context.

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

Invoice price differences are allowed to reach the three-way matching stage. The matching process is responsible for determining whether the price difference is within tolerance or represents a discrepancy.

## Invoice List

Endpoint:

```http
GET /api/v1/invoices
```

The endpoint requires authentication.

For supplier users, only invoices belonging to the authenticated supplier are returned.

For internal authorized users, the broader invoice collection can be returned according to the current role-based access implementation.

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

Supplier authorization is evaluated before exposing whether another supplier's invoice exists.

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

The P2P invoice integration additionally requires the Purchase Order to have reached the appropriate P2P `received` state before the P2P invoice transition is performed.

## Invoice Supplier Validation

The invoice supplier must match the supplier associated with the Purchase Order.

For example:

```text
PO supplier      = SUP001
Invoice supplier = SUP002
```

is rejected.

This prevents invoices from being associated with another supplier's Purchase Order.

R5 additionally ensures that the authenticated supplier identity must match the supplier being acted upon.

## Invoice Line-Item Validation

Each invoice item is validated against the Purchase Order.

The service validates:

* Item exists on the PO
* Quantity is positive
* Quantity does not exceed remaining PO quantity
* Duplicate `(po_number, item_code)` lines are not allowed within one invoice
* Invoice amount matches the calculated line-item total

Invoice quantity and price differences that are valid from an invoice-data perspective are allowed to reach the three-way match process.

The three-way match applies the configured tolerance when comparing invoice prices against Purchase Order prices.

This separation is intentional:

```text
Invoice Creation
      │
      ▼
Validate invoice structure and quantities
      │
      ▼
Invoice accepted
      │
      ▼
Three-Way Match
      │
      ├── Within tolerance → Matched
      │
      └── Outside tolerance → Price Discrepancy
```

Rejected invoices do not consume PO quantity.

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

Invoice documents are stored using a supplier-specific path so that invoice files remain associated with the supplier that owns the invoice.

---

## PDF Upload

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint is authenticated and supplier-scoped.

For supplier users, the authenticated `supplier_id` must match the supplier associated with the invoice.

A supplier cannot upload a document to another supplier's invoice.

---

## PDF Validation

The service performs multiple validation checks before storing an invoice document.

### 1. Content Type

The request must use:

```text
application/pdf
```

Other content types such as:

```text
image/png
text/plain
application/json
```

are rejected.

### 2. PDF Signature

The uploaded file contents must begin with:

```text
%PDF-
```

This prevents a non-PDF file from being accepted simply because the request declares:

```text
Content-Type: application/pdf
```

### 3. Maximum File Size

The maximum supported PDF size is:

```text
10 MB
```

The actual uploaded bytes are checked to ensure the payload does not exceed the configured limit.

---

## Document Path and URL

The service intentionally separates the internal filesystem path from the public API URL.

Example internal document path:

```text
SUP001/INV1001.pdf
```

This is an internal relative filesystem reference.

The public API endpoint is:

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

The upload root is resolved before filesystem operations:

```python
upload_root = Path(UPLOAD_DIR).resolve()
```

The final document path is also resolved:

```python
final_path = (upload_root / document_path).resolve()
```

The service verifies that the resolved document path remains inside the configured upload directory:

```python
final_path.is_relative_to(upload_root)
```

This prevents path traversal attempts such as:

```text
../../some-file
```

The same safe-path validation is applied when retrieving stored documents.

---

## PDF Download

Endpoint:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint requires authentication.

For supplier users, the authenticated supplier must own the invoice.

Internal authorized users can access invoice documents according to the endpoint's role authorization rules.

The document retrieval flow is:

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
Verify path is inside uploads/
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

The dispute information records audit details such as:

```text
reason
actor_id
actor_name
role
timestamp
```

Historical dispute information is retained so that a previously disputed invoice remains identifiable as historically disputed even after subsequent adjustment or approval.

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

An adjustment is allowed only when the invoice is currently:

```text
disputed
```

The adjustment can update invoice line items and recalculates the invoice amount.

Audit information includes details such as:

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

and can subsequently move to an appropriate final invoice state such as:

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

The endpoint requires authentication and applies the appropriate role and supplier-scope rules.

For supplier users, the authenticated supplier must own the invoice.

The service validates:

1. Invoice existence
2. Current invoice status
3. Target status
4. Whether the current-to-target transition is valid

Illegal invoice transitions are rejected with:

```text
400 Bad Request
```

Invoice lifecycle management remains separate from the P2P state machine.

The invoice lifecycle represents invoice processing:

```text
submitted
    │
    ├── disputed
    │      │
    │      └── adjusted
    │
    ├── approved
    │
    └── rejected
```

The P2P state machine represents the broader transaction processing stage.

---

# 10. Supplier Statistics

Supplier operational statistics are available through:

```http
GET /api/v1/suppliers/{supplier_id}/stats
```

The endpoint requires authentication.

For supplier users, the authenticated `supplier_id` must match the requested `supplier_id`.

The endpoint provides statistics including:

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

A supplier user without a `supplier_id` is rejected from supplier-scoped statistics access:

```text
403 Forbidden
```

Internal authorized users can access supplier statistics according to their assigned role permissions.

---

## Purchase Order Count

The PO count includes all Purchase Orders belonging to the supplier:

```text
po_count = total supplier POs
```

This includes Purchase Orders in states such as:

```text
draft
sent
acknowledged
fulfilled
cancelled
```

---

## Delivery Eligibility and On-Time Percentage

Supplier delivery statistics use a common delivery-eligibility rule shared with the supplier scorecard and monthly trend calculations.

A Purchase Order is eligible for delivery-performance calculation when:

```text
fulfilled
```

or when:

```text
expected delivery date has passed
```

Cancelled POs are excluded.

Future-due unfulfilled POs are excluded because they are not yet eligible to be considered late.

The implemented rule is conceptually:

```text
Cancelled
    │
    └── Excluded

Fulfilled
    │
    └── Eligible

Unfulfilled + future due date
    │
    └── Excluded

Unfulfilled + past due date
    │
    └── Eligible and counted as late
```

For eligible Purchase Orders:

```text
on-time percentage =
(on-time eligible POs / eligible POs) × 100
```

A fulfilled PO is considered on time when its actual delivery is on or before the expected delivery date.

Past-due unfulfilled POs are counted as misses.

Future-due unfulfilled POs do not count as misses because their delivery deadline has not yet passed.

The result is rounded to two decimal places.

Example:

```text
Eligible POs = 3
On-time POs = 2

On-time percentage = 66.67%
```

This delivery-eligibility rule is intentionally shared by:

```text
Supplier Statistics
        +
Supplier Scorecard
        +
Supplier Monthly Trend
```

so that the same business definition is used consistently.

---

## Average Invoice Cycle Time

The service calculates invoice cycle time using the relationship between the invoice date and the associated Purchase Order creation date.

Conceptually:

```text
invoice cycle time =
invoice date - PO creation date
```

Invoice Purchase Order references are taken from the invoice line items' `po_number` values.

For example:

```text
PO created:   August 1
Invoice date: August 4

Cycle time = 3 days
```

Negative cycle times are ignored.

Invalid or unusable date records are ignored rather than causing the entire supplier statistic calculation to fail.

---

## Invoice PO Reference Handling

Invoice records store the related Purchase Order reference at the invoice-item level.

The statistics service therefore extracts Purchase Order numbers from:

```text
invoice.items[].po_number
```

The service also supports the legacy/top-level `po_number` value when present.

This allows invoice cycle-time and trend calculations to correctly associate invoices with their Purchase Orders.

---

## Date Normalization

The statistics service supports common date representations including:

```text
date
datetime
ISO date string
ISO datetime string
ISO datetime with Z
```

These values are normalized through the shared date-conversion logic before calculations are performed.

---

## Supplier Not Found

A supplier can be identified from the supplier-related data maintained by the Supplier Portal, including relevant Purchase Order and invoice records.

If the requested supplier cannot be found for a supplier-statistics operation, the service returns:

```http
404 Not Found
```

Example:

```json
{
  "detail": "Supplier 'SUP999' not found."
}
```

---

## R5 403 vs 404 Security Behavior

Supplier-scoped detail and analytics endpoints were updated so that supplier ownership is checked before exposing resource-existence information where the endpoint supports that security model.

For a supplier user:

```text
Authenticated supplier
        │
        ▼
Requested supplier_id
        │
        ▼
Ownership check
        │
   ┌────┴────┐
   │         │
 Owner     Not owner
   │         │
   ▼         ▼
Continue   403 Forbidden
```

This prevents an unauthorized supplier from learning whether another supplier's protected resource exists merely from a different response status.

The same security principle is applied across the affected supplier-scoped detail endpoints.

For internal authorized users, resource lookup and access behavior follows the endpoint's internal authorization rules.

The implemented security objective is:

```text
Unauthorized supplier
        │
        ▼
No cross-supplier resource disclosure
```

---

# 11. Supplier Performance Scorecard

The Supplier Performance Scorecard provides a higher-level view of supplier performance.

Endpoint:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The endpoint requires authentication.

Supplier users can access only their own scorecard.

Internal authorized users can access supplier scorecards according to their assigned role permissions.

The scorecard contains performance information including:

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

The scorecard uses the same delivery-eligibility rule as supplier statistics.

Eligible Purchase Orders are:

```text
Fulfilled POs
+
Past-due unfulfilled POs
```

The following are excluded:

```text
Cancelled POs
+
Future-due unfulfilled POs
```

The percentage is calculated from eligible Purchase Orders.

Weight:

```text
40%
```

---

### Invoice Accuracy

Invoice accuracy is calculated from the supplier's invoice history.

An invoice without a recorded dispute is treated as accurate for the implemented scorecard calculation.

Conceptually:

```text
invoice accuracy =
accurate invoices / total invoices × 100
```

Weight:

```text
40%
```

Historical dispute information is retained, so a previously disputed invoice continues to contribute to the supplier's historical dispute metrics even if it is later adjusted or approved.

---

### Dispute Rate

An invoice is historically disputed when:

```python
invoice.get("dispute") is not None
```

The dispute rate is:

```text
disputed invoices / total invoices × 100
```

---

### Dispute Performance

Because the implemented scorecard treats a higher dispute rate as lower performance:

```text
dispute performance = 100 - dispute rate
```

Weight:

```text
20%
```

---

## Overall Score

The implemented scorecard combines:

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

The implementation maps the calculated score into the configured rating bands:

|    Score | Rating            |
| -------: | ----------------- |
|   90–100 | Excellent         |
| 75–89.99 | Good              |
| 60–74.99 | Average           |
| 40–59.99 | Needs Improvement |
| Below 40 | Poor              |

---

## Performance Status

The implementation also exposes a performance status based on score:

|    Score | Status   |
| -------: | -------- |
|   75–100 | Healthy  |
| 60–74.99 | Watch    |
| 40–59.99 | At Risk  |
| Below 40 | Critical |

---

## Scorecard Details

The scorecard provides detailed Purchase Order metrics including:

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

Invoice cycle-time calculations use the Purchase Order references stored in:

```text
invoice.items[].po_number
```

This ensures invoice metrics correctly associate invoice records with their related Purchase Orders.

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

The invoice remains historically disputed because its dispute information is retained.

This prevents supplier performance metrics from losing the history of previously disputed invoices.

---

## Invoice-Only Suppliers

A supplier can be identified through invoice data even if it currently has no Purchase Orders.

The scorecard can recognize a supplier from relevant supplier data maintained by the service, including:

```text
Purchase Order data
        OR
Invoice data
```

This prevents an invoice-only supplier from incorrectly receiving a `404 Not Found` solely because the supplier currently has no Purchase Orders.

---

## Supplier Performance Analytics

Supplier performance analytics are implemented through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The scorecard provides:

```text
On-time delivery percentage
Invoice accuracy percentage
Dispute rate
Dispute performance
Overall supplier score
Performance rating
Performance status
Purchase Order performance details
Invoice performance details
```

Supplier-scoped access remains enforced:

```text
Supplier SUP001
      │
      ▼
SUP001 scorecard
      │
      ▼
Allowed
```

while:

```text
Supplier SUP001
      │
      ▼
SUP002 scorecard
      │
      ▼
403 Forbidden
```

The scorecard therefore combines operational Purchase Order metrics, invoice metrics, dispute history, and supplier-scoped authorization.

---

# 12. Procure-to-Pay Lifecycle

The Supplier Portal implements a procure-to-pay workflow connecting:

```text
Purchase Order
      ↓
Acknowledgement
      ↓
Shipment
      ↓
Goods Receipt
      ↓
Invoice
      ↓
Three-Way Match
      ↓
Payment Approval
```

The workflow is implemented using explicit P2P state transitions rather than treating each step as an unrelated record operation.

---

## P2P Flow

```text
Purchase Order
      │
      ▼
Acknowledged
      │
      ▼
Shipped
      │
      ▼
Received
      │
      ▼
Invoiced
      │
      ▼
Matched / Discrepancy
      │
      ▼
Payment Approved
```

A discrepancy is routed for human review instead of automatically progressing to payment approval.

---

## P2P State Machine

The P2P state machine is implemented separately from the legacy Purchase Order lifecycle.

The P2P states represent the processing stage of the transaction:

```text
acknowledged
      ↓
shipped
      ↓
received
      ↓
invoiced
      ↓
matched / discrepancy
      ↓
payment_approved
```

The transition logic validates the current state before allowing a transition.

Examples:

```text
acknowledged → shipped
shipped      → received
received     → invoiced
```

are valid transitions.

Invalid transitions are rejected.

The P2P state machine does not allow a transaction to skip required processing stages.

---

## Purchase Order and P2P State Are Separate

The Supplier Portal maintains two related but distinct concepts:

```text
Purchase Order Lifecycle
        +
P2P Processing State
```

The Purchase Order lifecycle manages Purchase Order business status such as:

```text
draft
sent
acknowledged
fulfilled
cancelled
```

The P2P state machine manages transaction processing:

```text
acknowledged
shipped
received
invoiced
matched / discrepancy
payment_approved
```

This separation allows the existing Purchase Order lifecycle to remain intact while the new P2P workflow controls end-to-end transaction progression.

---

## Shipment Notice

After a Purchase Order has been acknowledged, the supplier can progress the P2P transaction through shipment processing.

The shipment stage represents notification that the ordered goods have been shipped.

```text
acknowledged
      │
      ▼
shipped
```

Shipment processing validates the related Purchase Order and supplier context before advancing the P2P state.

---

## Goods Receipt

Goods Receipt represents the receiving of shipped goods.

A Goods Receipt contains information such as:

```text
receipt_id
po_number
supplier_id
receipt_date
warehouse
received_by
items
status
created_at
created_by
```

Goods Receipt validation includes:

```text
Purchase Order existence
Supplier ownership
Item code validation
Received quantity validation
Duplicate item detection
Receipt information validation
```

The expected P2P transition is:

```text
shipped
   │
   ▼
received
```

Invalid state transitions are rejected.

---

## Partial Goods Receipt

The Goods Receipt implementation supports partial delivery.

A receipt can contain only part of the Purchase Order quantity.

For example:

```text
PO quantity       = 100
Received quantity = 40
```

is allowed when the received quantity is valid.

The implementation also allows PO items to be omitted from a partial receipt.

Each received item must satisfy:

```text
quantity > 0
```

and:

```text
received quantity <= PO quantity
```

Extra PO items are rejected, and duplicate item codes within a receipt are rejected.

This allows real-world partial shipment and receiving scenarios to reach the three-way matching stage.

---

## Invoice Integration

Invoice processing is integrated with the P2P state machine.

A P2P invoice requires the related transaction to have reached:

```text
received
```

before progressing to:

```text
invoiced
```

The existing Invoice lifecycle remains separate:

```text
submitted
    │
    ├── approved
    ├── rejected
    └── disputed
           │
           └── adjusted
```

Therefore:

```text
P2P State Machine
        +
Invoice Lifecycle
```

work together without replacing each other.

Invalid or duplicate invoice submissions do not advance the P2P state.

---

## Payment Approval

After invoice processing and three-way matching, a successfully matched transaction can progress toward:

```text
payment_approved
```

A discrepancy does not automatically progress to payment approval.

The control flow is:

```text
Three-Way Match
      │
      ├── No discrepancy
      │       │
      │       ▼
      │  Payment Approval
      │
      └── Discrepancy
              │
              ▼
         Human Review
```

This prevents quantity or price mismatches from being automatically approved for payment.

---

## P2P State Integrity

The P2P workflow maintains state integrity by:

* Validating the current P2P state before transition
* Allowing only legal state transitions
* Preventing invalid duplicate processing
* Validating Purchase Order ownership
* Validating related business records
* Requiring the appropriate supplier context
* Requiring an appropriate Goods Receipt before P2P invoicing
* Preventing invalid invoice submissions from advancing the state
* Routing match discrepancies for human review

---

## Active Supplier Requirement

Supplier onboarding is connected to Purchase Order creation.

A Purchase Order cannot be created for a supplier that is:

```text
Unregistered
```

or:

```text
Not active
```

The supplier must complete onboarding and reach:

```text
active
```

before Purchase Order creation is allowed.

Conceptually:

```text
Supplier Registration
        ↓
Documents
        ↓
Verification
        ↓
Approval
        ↓
Active
        ↓
PO Creation Allowed
```

This provides an actual enforcement point between the onboarding workflow and P2P business operations.

---

# 13. Three-Way Match

The Supplier Portal implements automated three-way matching between:

```text
Purchase Order
        +
Goods Receipt
        +
Invoice
```

The purpose of the match is to determine whether the invoice agrees with what was ordered and what was actually received.

The matching process can identify quantity and price discrepancies and flag them for human review.

---

## Three-Way Match Flow

```text
Purchase Order
      │
      ├── Ordered Quantity
      ├── Item Code
      └── Unit Price
      │
      ▼
Goods Receipt
      │
      ├── Received Quantity
      └── Item Code
      │
      ▼
Invoice
      │
      ├── Invoiced Quantity
      ├── Item Code
      └── Unit Price
      │
      ▼
Three-Way Match
      │
 ┌────┴─────────────┐
 │                  │
 ▼                  ▼
Matched        Discrepancy
 │                  │
 ▼                  ▼
Continue        Human Review
to Payment
Approval
```

---

## Quantity Matching

The matching process validates quantities across:

```text
Purchase Order
Goods Receipt
Invoice
```

A deliberate quantity mismatch is identified as a discrepancy.

Example:

```text
PO quantity       = 100
Received quantity = 90
Invoice quantity  = 100
```

Result:

```text
Quantity discrepancy
        │
        ▼
Human Review
```

Because Goods Receipt now supports partial receiving, short receipts can reach the matching stage and be evaluated by the three-way match logic.

---

## Price Matching

Invoice creation no longer blocks a valid invoice merely because its unit price differs from the Purchase Order price.

This allows a price discrepancy to reach the three-way matching stage.

Example:

```text
PO unit price       = 100
Invoice unit price  = 120
```

Result:

```text
Price discrepancy
        │
        ▼
Human Review
```

The implemented three-way matching logic uses the configured price tolerance when determining whether the price difference is acceptable.

The tolerance is therefore a **matching rule**, not an invoice-creation rejection rule.

---

## Match Result

A successful match indicates that the relevant Purchase Order, Goods Receipt, and Invoice information satisfies the implemented matching rules.

Conceptually:

```text
Purchase Order
      │
      ├── Item matches
      ├── Quantity matches
      └── Unit price matches within tolerance
      │
      ▼
Goods Receipt
      │
      └── Received data satisfies matching rules
      │
      ▼
Invoice
      │
      └── Invoice data satisfies matching rules
      │
      ▼
Matched
      │
      ▼
Payment Approval
```

---

## Discrepancy Handling

The three-way match does not automatically approve transactions containing discrepancies.

Supported discrepancy categories include:

```text
Quantity mismatch
Price mismatch
```

The intended control is:

```text
Discrepancy detected
        │
        ▼
Human review required
        │
        ▼
No automatic payment approval
```

The matching system identifies the exception while keeping the final business decision under controlled human review.

---

## P2P Integration

The three-way match operates after:

```text
Acknowledged
      ↓
Shipped
      ↓
Received
      ↓
Invoiced
```

and before:

```text
Payment Approved
```

The resulting control flow is:

```text
Purchase Order
      ↓
Goods Receipt
      ↓
Invoice
      ↓
Three-Way Match
      │
 ┌────┴──────────────┐
 │                   │
 ▼                   ▼
Matched         Discrepancy
 │                   │
 ▼                   ▼
Payment          Human Review
Approval
```

---

## Real-Flow Discrepancy Support

The implementation supports discrepancy scenarios through the real API flow.

### Quantity discrepancy

A partial Goods Receipt can be created first, allowing a short-receipt scenario to reach matching.

Example:

```text
PO quantity       = 100
Goods Receipt     = 90
Invoice quantity  = 100
```

The match can flag the quantity discrepancy.

### Price discrepancy

Invoice creation allows a price difference to reach matching.

Example:

```text
PO unit price      = 100
Invoice unit price = 120
```

The three-way match can then flag the price discrepancy.

This prevents invoice validation from hiding the discrepancy before the matching process has an opportunity to evaluate it.

---

# 14. Supplier Onboarding

The Supplier Portal implements a supplier onboarding workflow for registering and activating suppliers.

The onboarding workflow is:

```text
Registration
      │
      ▼
Document Collection
      │
      ▼
Mock Verification
      │
      ▼
Approval
      │
      ▼
Active
```

---

## Onboarding Lifecycle

Each stage represents a separate business step:

```text
registration
      ↓
documents
      ↓
verification
      ↓
approval
      ↓
active
```

The onboarding service validates the current stage before allowing the supplier to progress.

---

## Registration

The workflow begins when a supplier is registered.

The registration stage establishes the supplier onboarding record before verification and approval.

A supplier that has only been registered is not considered active.

---

## Document Collection

Required supplier documentation is collected as part of onboarding.

Document collection does not itself activate the supplier.

```text
Registration
      │
      ▼
Documents Collected
      │
      ▼
Verification
```

---

## Mock Verification

The current implementation uses mock verification logic for development and functional validation.

The verification stage represents the point at which supplier information and collected documents are checked before approval.

```text
Document Collection
      │
      ▼
Mock Verification
```

---

## Approval

After successful verification, the supplier can progress through the approval stage.

```text
Verified
   │
   ▼
Approved
```

---

## Active Supplier

An approved supplier reaches the active state:

```text
Approved
   │
   ▼
Active
```

The onboarding service exposes an active-supplier check that is used by Purchase Order creation.

Therefore:

```text
Active supplier
      │
      ▼
PO creation allowed
```

while:

```text
Unregistered / inactive supplier
      │
      ▼
PO creation rejected
```

This makes onboarding enforcement part of the actual business flow rather than documentation-only behavior.

---

## Supplier Scoping

Supplier onboarding follows the same supplier-level security principles established in Round 5.

Authentication, role authorization, and supplier ownership are separate controls:

```text
Authentication
      │
      ▼
Role Authorization
      │
      ▼
Supplier Ownership / Scope
      │
      ▼
Onboarding Resource Access
```

Supplier users cannot access another supplier's onboarding resources.

---

## Onboarding Workflow Integrity

The workflow validates the current onboarding stage before advancing.

The intended lifecycle is:

```text
registration
      ↓
documents
      ↓
verification
      ↓
approval
      ↓
active
```

Invalid progression is rejected rather than silently changing the supplier's onboarding state.

---

## Onboarding and P2P Integration

The onboarding workflow is connected to the P2P process through the active-supplier requirement.

The business dependency is:

```text
Supplier
   │
   ▼
Onboarding
   │
   ▼
Active
   │
   ▼
Purchase Order Creation
   │
   ▼
P2P Processing
```

A supplier that has not completed onboarding cannot be used for new Purchase Order creation.

---

# 15. API Reference

All application APIs use the `/api/v1` prefix unless otherwise noted.

Protected application endpoints authenticate users through the Platform Service.

Supplier-facing endpoints additionally enforce supplier-level ownership and data scoping.

Authentication, role authorization, supplier ownership, and business-state validation are enforced according to each endpoint's requirements.

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

For supplier users, supplier ownership is enforced on supplier-facing Purchase Order operations.

Internal authorized users access Purchase Orders according to their assigned role permissions.

### Purchase Order Supplier Scoping

For supplier users, ownership is enforced on detail operations including:

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
403 Forbidden
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

| Method | Endpoint                                                     | Authentication / Role                           | Description             |
| ------ | ------------------------------------------------------------ | ----------------------------------------------- | ----------------------- |
| GET    | `/api/v1/invoices`                                           | Authenticated                                   | List invoices           |
| POST   | `/api/v1/invoices`                                           | Authenticated                                   | Create invoice          |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}`            | Authenticated                                   | Get invoice             |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Authenticated / endpoint-specific authorization | Transition invoice      |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust`     | `compliance_officer`                            | Adjust disputed invoice |
| POST   | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Owning supplier                                 | Upload invoice PDF      |
| GET    | `/api/v1/invoices/{supplier_id}/{invoice_number}/document`   | Authenticated                                   | Download invoice PDF    |

For supplier users, invoice ownership is enforced.

Internal authorized users can access invoices according to the endpoint's role authorization rules.

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

The collection is filtered using the authenticated supplier's `supplier_id`.

Therefore, a supplier token cannot be used to retrieve another supplier's invoice collection.

---

## Invoice Document APIs

Invoice documents are managed through:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

and:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The upload operation validates:

```text
Authentication
Supplier ownership
Content type
PDF signature
Maximum file size
Safe filesystem path
```

The download operation validates:

```text
Authentication
Supplier ownership where applicable
Stored document path
Path traversal protection
File existence
```

---

## Procure-to-Pay APIs

The Supplier Portal exposes P2P operations covering:

| Stage            | Purpose                                                            |
| ---------------- | ------------------------------------------------------------------ |
| Shipment         | Progress an acknowledged P2P transaction to shipped                |
| Goods Receipt    | Record received goods and progress the P2P state                   |
| Invoice          | Submit an invoice after the required receipt state                 |
| Three-Way Match  | Compare PO, receipt, and invoice data                              |
| Payment Approval | Progress successfully matched transactions toward payment approval |

P2P operations require the appropriate authentication, role authorization, supplier ownership, and current-state validation.

Supplier-facing operations follow the R5 security principle:

```text
Authenticated supplier
        │
        ▼
Authenticated supplier_id
        │
        ▼
Related resource supplier_id
        │
        ├── Same → Allowed
        │
        └── Different → 403 Forbidden
```

Invalid P2P state transitions are rejected and do not partially advance the workflow.

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

Supplier users without a valid `supplier_id` are rejected:

```text
403 Forbidden
```

Internal authenticated users access supplier statistics and scorecards according to their assigned role permissions.

---

## Supplier Onboarding APIs

The Supplier Portal provides onboarding operations for:

```text
Supplier registration
Document collection
Verification
Approval
Activation
Status
History
```

Supplier onboarding detail operations are supplier-scoped.

The onboarding service also exposes the active-supplier state internally so that business operations such as Purchase Order creation can enforce onboarding completion.

---

## Shipment APIs

Shipment processing is part of the P2P state machine.

The shipment operation progresses:

```text
acknowledged
      ↓
shipped
```

Shipment operations validate:

```text
Authentication
Supplier ownership
Purchase Order relationship
Current P2P state
Shipment information
```

Invalid state transitions are rejected.

---

## Goods Receipt APIs

Goods Receipt processing progresses:

```text
shipped
    ↓
received
```

Goods Receipt validation includes:

```text
Purchase Order existence
Supplier ownership
Item validation
Quantity validation
Duplicate item validation
Partial receipt support
```

A partial receipt can contain fewer quantities than the original Purchase Order.

---

## Three-Way Match APIs

Three-way matching compares:

```text
Purchase Order
+
Goods Receipt
+
Invoice
```

The matching process checks relevant:

```text
Item codes
Quantities
Unit prices
```

Supported discrepancy categories include:

```text
Quantity mismatch
Price mismatch
```

Discrepancies are flagged for human review and do not automatically result in payment approval.

---

## Maintenance APIs

Maintenance endpoints perform administrative operations on invoice files.

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

These endpoints require authentication and administrative authorization and are not intended for anonymous or supplier access.

---

## R5 API Security Summary

The protected API model is:

| Resource                  | Supplier Access | Internal Role Access                              |
| ------------------------- | --------------- | ------------------------------------------------- |
| Own PO                    | Allowed         | According to role                                 |
| Other supplier PO         | `403 Forbidden` | According to role                                 |
| Own invoice               | Allowed         | According to role                                 |
| Other supplier invoice    | `403 Forbidden` | According to role                                 |
| Own invoice document      | Allowed         | According to role                                 |
| Other supplier document   | `403 Forbidden` | According to role                                 |
| Own statistics            | Allowed         | According to role                                 |
| Other supplier statistics | `403 Forbidden` | According to role                                 |
| Own scorecard             | Allowed         | According to role                                 |
| Other supplier scorecard  | `403 Forbidden` | According to role                                 |
| Missing supplier identity | `403 Forbidden` | Not applicable to supplier-scoped supplier access |

The R5 security model therefore combines:

```text
Authentication
      +
Role Authorization
      +
Supplier Data Isolation
```

A successful token verification alone is not sufficient for supplier access.

The authenticated supplier identity must match the supplier associated with the requested supplier-scoped resource.

---

## R5 Security Principle

The core security principle is:

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

Automated tests cover areas including:

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
* Supplier-scoped detail endpoint access-control behavior

---

# 16. HTTP Response Codes

| Status | Meaning                                                                          |
| -----: | -------------------------------------------------------------------------------- |
|    200 | Successful request                                                               |
|    201 | Resource created                                                                 |
|    400 | Business-rule validation failure                                                 |
|    401 | Authentication required, invalid, or expired                                     |
|    403 | Authenticated user is not authorized or supplier scope does not match            |
|    404 | Resource not found when the endpoint's access model permits existence disclosure |
|    409 | Duplicate resource                                                               |
|    422 | Request/schema validation failure                                                |
|    503 | Platform authentication service unavailable or returned an unusable response     |

For protected supplier-scoped resources, the implementation also applies ownership checks before resource lookup on affected detail endpoints to avoid cross-supplier existence disclosure.

---

# 17. Configuration

The Supplier Portal uses Pydantic Settings for configuration.

Create a `.env` file in the project root when local configuration needs to be changed.

Example:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The default Platform authentication URL is:

```text
http://127.0.0.1:8005
```

---

## Environment Template

The project provides:

```text
.env.example
```

The example configuration contains:

```env
# Platform Service (authentication provider)

PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

To create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

The `.env` file should not be committed to source control when it contains sensitive or environment-specific configuration.

The Supplier Portal uses the Platform Service as its centralized authentication provider.

---

# 18. Installation

## Step 1 — Open the Project

Open the Supplier Portal project directory in VS Code.

Example:

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

The project uses dependencies including:

```text
FastAPI
Uvicorn
Pydantic
python-multipart
Pytest
HTTPX
```

`python-multipart` is required for multipart invoice PDF upload handling.

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

# 19. Running the Services

The Supplier Portal depends on the Platform Service for authentication.

Therefore, the services run separately.

---

## Platform Service

Start the Platform Service on:

```text
http://127.0.0.1:8005
```

The Platform Service provides authentication operations including:

```http
POST /api/v1/auth/login
POST /api/v1/auth/verify
GET  /api/v1/users/me
```

The authentication response provides authenticated user information such as:

```text
user_id
email
full_name
role
supplier_id
is_active
```

The Supplier Portal does not independently decode the authentication token.

Instead, it delegates token verification to the Platform Service and uses the returned identity and role information for authorization and supplier scoping.

---

## Supplier Portal Service

From the Supplier Portal project directory:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The Supplier Portal runs at:

```text
http://127.0.0.1:8000
```

The root endpoint can be used to confirm that the service is running:

```http
GET /
```

---

## Two-Service Architecture

```text
┌─────────────────────────────┐
│      Platform Service       │
│                             │
│        Port 8005            │
│                             │
│   Authentication Provider   │
└──────────────┬──────────────┘
               │
               │ /api/v1/auth/verify
               │
               ▼
┌─────────────────────────────┐
│      Supplier Portal        │
│                             │
│        Port 8000            │
│                             │
│ PO / Invoice / P2P          │
│ Statistics / Scorecard      │
│ Documents / Onboarding      │
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
  ├── email
  ├── role
  ├── supplier_id
  └── is_active
  │
  ▼
Supplier Portal Authorization
  │
  ├── Role Check
  │
  ├── Supplier Ownership Check
  │
  └── Business Rule Validation
```

The Supplier Portal therefore follows the architecture:

```text
Platform Service
       │
       │ Authentication
       ▼
Supplier Portal
       │
       ├── Role Authorization
       ├── Supplier Scoping
       ├── Business Validation
       ├── P2P State Management
       └── Supplier Operations
```

The Supplier Portal does not replace the Platform Service authentication mechanism. It consumes the authenticated identity provided by the Platform Service and applies endpoint-specific authorization and supplier-scoping rules.
# 20. Swagger Documentation

FastAPI automatically provides interactive API documentation.

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Alternative ReDoc documentation:

```text
http://127.0.0.1:8000/redoc
```

Swagger can be used to inspect and test supported API operations, including:

```text
Purchase Orders
PO acknowledgement
PO transitions
PO events
Bulk PO sending
Shipment notices
Goods Receipts
Invoice creation
Invoice retrieval
Invoice transitions
Invoice disputes
Invoice adjustments
Invoice document upload
Invoice document download
Supplier onboarding
Supplier statistics
Supplier scorecard
Three-way matching
Payment approval
Maintenance endpoints
```

Protected endpoints require a valid bearer token.

---

# 21. Testing

The Supplier Portal uses **Pytest** for automated testing.

The test suite covers:

* Core business logic
* Purchase Order lifecycle
* P2P state transitions
* Shipment processing
* Goods Receipt processing
* Invoice lifecycle
* Three-way matching
* Quantity discrepancy detection
* Price discrepancy detection
* Supplier onboarding
* Supplier statistics and scorecards
* Authentication
* Role-based authorization
* Supplier-level resource ownership
* Collection-level supplier filtering
* Invoice document security
* Authentication-required endpoint protection
* Round 5 supplier-scoping requirements
* Rounds 6–8 functional milestones

Run the complete test suite with:

```powershell
python -m pytest -v
```

The test suite uses `python -m pytest` so that tests execute using the active Python environment.

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
* Active supplier enforcement
* Unregistered supplier rejection
* Inactive supplier rejection

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

Purchase Order creation additionally requires the referenced supplier to be registered and in the `active` onboarding state.

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
* Unit-price validation
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

Invoice creation does **not** reject price differences solely because they exceed the three-way-match tolerance.

The configured `5%` tolerance is used by the **three-way matching process** to identify price discrepancies.

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

The invoice collection endpoint is also tested for supplier-level filtering:

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

## Procure-to-Pay and Milestone Testing

The test suite validates the implemented procure-to-pay and supplier workflow milestones.

### P2P Workflow Tests

The P2P tests validate:

* P2P state initialization
* Valid P2P transitions
* Invalid P2P transitions
* Shipment progression
* Goods Receipt creation
* Partial Goods Receipt support
* Goods Receipt validation
* Purchase Order existence validation
* Supplier ownership validation
* Item validation
* Quantity validation
* Duplicate Goods Receipt item protection
* Extra item rejection
* Invoice submission after the required receipt state
* Invoice submission advancing the P2P workflow
* Invalid invoice submission not advancing P2P state
* Duplicate invoice protection
* Three-way match processing
* Quantity discrepancy detection
* Price discrepancy detection
* Discrepancy routing for human review
* Prevention of automatic payment approval for discrepancies
* Payment approval progression after successful matching

The P2P state sequence is:

```text
acknowledged
      ↓
shipped
      ↓
received
      ↓
invoiced
      ↓
matched / discrepancy
      ↓
payment_approved
```

---

### Supplier Onboarding Tests

The onboarding workflow tests validate:

* Supplier registration
* Document collection
* Mock verification
* Approval
* Activation
* Valid onboarding state transitions
* Invalid onboarding transitions
* Supplier-level authorization
* Cross-supplier access protection
* Active-supplier enforcement for Purchase Order creation

The onboarding lifecycle is:

```text
registration
      ↓
documents
      ↓
verification
      ↓
approval
      ↓
active
```

A supplier must reach the `active` state before a Purchase Order can be created for that supplier.

---

### Three-Way Match Tests

The three-way matching tests validate both successful matching and discrepancy scenarios.

The matching process compares:

```text
Purchase Order
      +
Goods Receipt
      +
Invoice
```

The discrepancy tests cover:

```text
Quantity mismatch
       OR
Price mismatch
       │
       ▼
Discrepancy detected
       │
       ▼
Human review required
       │
       ▼
No automatic payment approval
```

The mismatch tests are exercised through the supported API flow so that quantity and price discrepancies can reach the matching layer without being rejected prematurely by invoice creation or Goods Receipt validation.

Partial Goods Receipts are supported, which allows a received quantity to be lower than the original PO quantity.

The matching implementation uses the configured price tolerance when determining whether invoice price differences constitute discrepancies.

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
* Future-due Purchase Orders
* Past-due unfulfilled Purchase Orders
* Delivery exactly on expected date
* Missing delivery date
* Average invoice cycle time
* Invoice line-level `po_number` handling
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
* Monthly trend calculations

### Supplier Delivery Eligibility

Delivery statistics use a common eligibility rule.

```text
Fulfilled PO
    → Eligible

Future-due unfulfilled PO
    → Excluded

Past-due unfulfilled PO
    → Eligible and counted as a miss

Cancelled PO
    → Excluded

PO without a usable expected-delivery date
    → Excluded
```

This prevents future-due Purchase Orders from being counted as delivery failures.

### Invoice Cycle-Time and Trend Coverage

Invoice metrics derive the related Purchase Order number from invoice line items using:

```text
invoice.items[].po_number
```

This ensures invoices containing their PO relationship at line level are included in:

* Average invoice cycle time
* Invoice-related trend calculations
* Scorecard invoice metrics

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
* Authorized internal roles can access supplier data according to their assigned permissions
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

An authenticated supplier attempting to access an existing resource owned by another supplier receives `403 Forbidden`.

An unknown supplier/resource returns `404 Not Found` where the endpoint's resource semantics require an existence check.

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
* Compliance-officer authorization
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

This module verifies that protected endpoints cannot be accessed without authentication.

The test removes the authentication dependency override used by the normal test suite and executes the real authentication dependency.

Protected routes are discovered automatically from the Supplier Portal API routers rather than maintaining a hardcoded endpoint list.

The current test discovers and validates:

```text
20 protected endpoint/method combinations
```

Run:

```powershell
python -m pytest tests/test_requires_auth.py -v
```

The test confirms that discovered protected endpoints reject requests without an `Authorization` header.

Expected unauthenticated responses are:

```text
401 Unauthorized
```

or:

```text
403 Forbidden
```

depending on the authentication dependency and endpoint configuration.

This test protects against accidentally removing authentication dependencies from protected routes.

---

## R5 Supplier-Scoping Validation

Round 5 specifically validates that authentication alone does not provide unrestricted supplier access.

The core security rule is:

```text
A valid supplier token does not provide unrestricted supplier access.

The authenticated supplier must own the requested supplier-scoped resource.
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
Supplier Onboarding Resources
Shipment Resources
Goods Receipt Resources
Three-Way Match Resources
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

The R5 strategy validates both:

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

The Round 5 test strategy validates four security layers:

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

This is combined with existing business-rule and validation coverage:

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

The key requirement is:

```text
A supplier can access only supplier-scoped resources
belonging to its authenticated supplier_id.
```

Cross-supplier access to existing resources is explicitly tested and must return:

```text
HTTP 403 Forbidden
```

---

# 22. Business Rules

## Purchase Order Rules

A newly created Purchase Order starts in:

```text
draft
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

In addition, the referenced supplier must be registered and active.

```text
Supplier does not exist
        ↓
PO creation rejected

Supplier exists but is not active
        ↓
PO creation rejected

Supplier is active
        ↓
PO creation permitted
```

For supplier users, supplier-owned Purchase Orders must belong to the authenticated supplier.

```text
Supplier SUP001 → PO SUP001 = Allowed

Supplier SUP001 → PO SUP002 = 403 Forbidden
```

PO collection access is supplier-scoped for supplier users:

```text
Supplier SUP001 → GET /purchase-orders
                ↓
Only SUP001 Purchase Orders returned
```

Internal authorized users can access Purchase Orders according to their assigned role permissions.

---

## Invoice Rules

Invoices require an existing PO.

The legacy invoice service accepts POs in the applicable invoice-processing states:

```text
acknowledged
OR
fulfilled
```

For P2P invoice integration, the additional P2P requirement is:

```text
P2P state = received
```

The invoice supplier must match the PO supplier.

Duplicate invoices are prevented using:

```text
supplier_id + invoice_number
```

Invoice line quantities are validated against available PO quantities.

Rejected invoices do not consume the Purchase Order's available invoice quantity.

---

## Procure-to-Pay Rules

The P2P workflow uses controlled state transitions.

The required processing order is:

```text
acknowledged
      ↓
shipped
      ↓
received
      ↓
invoiced
      ↓
matched / discrepancy
      ↓
payment_approved
```

### Shipment Rule

Shipment processing requires the P2P transaction to be in the appropriate pre-shipment state:

```text
acknowledged → shipped
```

Invalid transitions are rejected.

### Goods Receipt Rule

Goods Receipt processing requires:

```text
P2P state = shipped
```

The valid transition is:

```text
shipped → received
```

Goods Receipt supports partial delivery.

Validation includes:

```text
PO exists

Supplier ownership is valid

Item codes are valid

Receipt quantity > 0

Receipt quantity <= corresponding PO quantity

Duplicate receipt items are rejected

Extra item codes not present on the PO are rejected
```

Missing PO items are allowed in a receipt, which supports partial delivery.

### Invoice P2P Rule

An invoice participating in the P2P workflow requires:

```text
P2P state = received
```

A successful P2P invoice operation progresses:

```text
received → invoiced
```

An invalid or duplicate invoice must not advance the P2P state.

The existing invoice business lifecycle remains independent:

```text
submitted
disputed
adjusted
approved
rejected
```

### Three-Way Match Rule

The match compares:

```text
Purchase Order
+
Goods Receipt
+
Invoice
```

Relevant item, quantity, and price information is compared.

The configured price tolerance is applied during matching.

A discrepancy is flagged for human review:

```text
Quantity mismatch → Human Review

Price mismatch   → Human Review
```

A discrepancy must not automatically progress to payment approval.

### Payment Approval Rule

Only a successfully matched transaction can progress toward:

```text
payment_approved
```

Transactions requiring human review remain outside automatic payment approval.

---

## Supplier Onboarding Rules

The supplier onboarding lifecycle is:

```text
registration
      ↓
documents
      ↓
verification
      ↓
approval
      ↓
active
```

The workflow validates the current state before progressing.

A supplier cannot skip required onboarding stages.

Mock verification is used in the current development implementation.

### Active Supplier Enforcement

Supplier onboarding status is enforced by Purchase Order creation.

A Purchase Order cannot be created for:

```text
Unknown supplier
```

or:

```text
Supplier with non-active onboarding status
```

Only an `active` supplier can be used for Purchase Order creation.

This connects the onboarding lifecycle to the procurement workflow rather than leaving onboarding as an isolated module.

---

## Three-Way Match Tolerance

The configured matching tolerance is:

```text
TOLERANCE = 0.05
```

The tolerance is applied by the three-way matching logic when evaluating price differences.

It should not be interpreted as a blanket invoice-creation acceptance rule.

The invoice service allows price discrepancies to reach the matching layer so that they can be identified and routed for review.

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

Rejected invoices are excluded from consumed quantity.

---

## Supplier On-Time Percentage

Delivery performance uses an eligibility rule rather than treating every unfulfilled PO as a miss.

Eligible Purchase Orders are:

```text
Fulfilled PO
        → Eligible

Past-due unfulfilled PO
        → Eligible and counted as a miss

Future-due unfulfilled PO
        → Excluded

Cancelled PO
        → Excluded

PO without a usable expected-delivery date
        → Excluded
```

For fulfilled Purchase Orders, an on-time delivery satisfies:

```text
actual_delivery_date <= expected_delivery
```

The on-time percentage is therefore calculated from eligible delivery POs:

```text
on-time eligible POs
--------------------- × 100
eligible delivery POs
```

Future-due unfulfilled POs are excluded rather than counted as late.

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
dispute is None
    → Accurate

dispute is not None
    → Inaccurate
```

---

## Supplier Score

The configured scorecard weights are:

```text
40% → On-time delivery
40% → Invoice accuracy
20% → Dispute performance
```

Where:

```text
dispute performance = 100 - dispute rate
```

The scorecard also exposes the underlying performance metrics and invoice cycle-time information.

---

## Invoice Cycle-Time and Trend Rules

Invoice cycle-time calculations identify the related Purchase Order from invoice line items.

The primary relationship is:

```text
invoice.items[].po_number
```

This supports invoices whose PO relationship is stored at line-item level.

The implementation uses the same relationship when calculating applicable invoice-related monthly trends.

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

# 23. Security Controls

The service implements multiple security controls.

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
* Procurement-manager authorization for PO transitions
* Procurement-manager authorization for bulk PO sending
* Authenticated supplier identity validation

## Supplier Data Isolation

R5 introduces explicit supplier-level data isolation.

Supplier users can access only supplier-scoped resources belonging to their authenticated supplier.

Protected resource categories include:

* Purchase Orders
* Purchase Order events
* Invoices
* Invoice documents
* Supplier statistics
* Supplier scorecards
* Supplier onboarding resources
* Shipment resources
* Goods Receipt resources
* Three-way match resources

Cross-supplier access by supplier users is rejected with:

```text
403 Forbidden
```

A supplier without a valid `supplier_id` is also rejected from supplier-scoped resources:

```text
403 Forbidden
```

Collection endpoints are filtered so supplier users do not receive other suppliers' records.

---

## Input Validation

* PO number validation
* Supplier ID validation
* Invoice number validation
* Positive quantities
* Positive unit prices
* Positive invoice amounts
* Percentage boundaries
* Item validation
* Receipt quantity validation
* Duplicate item validation

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
* Safe filename handling
* Relative filesystem paths
* Upload-root resolution
* Path traversal protection
* Supplier-specific directories
* Supplier-scoped document access

---

# 24. Storage

The current implementation intentionally uses in-memory business storage.

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

Other workflow and supplier business data is also maintained in application memory.

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
PO / Invoice / Workflow data exists
      │
      ▼
Application restart
      │
      ▼
In-memory business data cleared
```

Invoice PDF files stored under `uploads/` are filesystem-based and are not automatically removed by an application restart.

A production deployment should replace in-memory business storage with persistent storage.

---

# 25. End-to-End Workflow

The Supplier Portal implements the procure-to-pay workflow:

```text
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
     Shipped
        │
        ▼
 Goods Receipt
        │
        ▼
     Received
        │
        ▼
   Submit Invoice
        │
        ▼
     Invoiced
        │
        ▼
 Three-Way Match
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Matched   Discrepancy
   │         │
   │         ▼
   │    Human Review
   │         │
   ▼         ▼
Payment   Controlled
Approval  Resolution
```

The three-way match compares:

```text
Purchase Order
      │
      ├── Item
      ├── Quantity
      └── Price
      │
      ▼
Goods Receipt
      │
      ├── Item
      └── Received Quantity
      │
      ▼
Invoice
      │
      ├── Item
      ├── Quantity
      └── Price
```

A mismatch is not automatically approved:

```text
Mismatch
   │
   ▼
Discrepancy
   │
   ▼
Human Review
```

---

## Supplier Onboarding Workflow

Supplier onboarding is implemented as a separate lifecycle:

```text
Supplier Registration
          │
          ▼
Document Collection
          │
          ▼
Mock Verification
          │
          ▼
Approval
          │
          ▼
Active Supplier
```

The active status is used by Purchase Order creation to prevent procurement operations from being performed against suppliers that have not completed onboarding.

The onboarding workflow is also protected by authentication and supplier-scoping rules.

---

## Supplier Analytics Workflow

Operational activity contributes to supplier performance analytics:

```text
Purchase Orders
      │
      ├── Delivery Performance
      │
      ▼
Invoices
      │
      ├── Invoice Accuracy
      ├── Invoice Cycle Time
      ├── Disputes
      │
      ▼
Supplier Statistics
      │
      ▼
Supplier Scorecard
```

The scorecard combines the implemented performance metrics while preserving supplier-level authorization.

---

## Complete Business Architecture

The overall business flow can be represented as:

```text
                    SUPPLIER PORTAL
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
     Procurement      Onboarding     Analytics
          │              │              │
          ▼              ▼              ▼
    Purchase Order   Registration   Statistics
          │              │              │
          ▼              ▼              ▼
    Acknowledgement  Documents      Scorecard
          │              │
          ▼              ▼
       Shipment       Verification
          │              │
          ▼              ▼
     Goods Receipt    Approval
          │              │
          ▼              ▼
        Invoice        Active
          │
          ▼
    Three-Way Match
          │
      ┌───┴────┐
      ▼        ▼
   Matched  Discrepancy
      │        │
      ▼        ▼
 Payment     Human
 Approval    Review
```

R5 authentication and supplier-level authorization apply throughout supplier-facing operations.

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

# 26. Current Implementation Status

| Module / Capability                         | Status   |
| ------------------------------------------- | -------- |
| Procure-to-Pay Workflow                     | Complete |
| P2P State Machine                           | Complete |
| Shipment Processing                         | Complete |
| Goods Receipt Workflow                      | Complete |
| Partial Goods Receipt Support               | Complete |
| Goods Receipt Validation                    | Complete |
| P2P Invoice Integration                     | Complete |
| Three-Way Match                             | Complete |
| Quantity Discrepancy Detection              | Complete |
| Price Discrepancy Detection                 | Complete |
| Human-Review Discrepancy Handling           | Complete |
| Payment Approval Workflow                   | Complete |
| Supplier Onboarding Registration            | Complete |
| Supplier Document Collection                | Complete |
| Supplier Mock Verification                  | Complete |
| Supplier Onboarding Approval                | Complete |
| Supplier Activation                         | Complete |
| Active Supplier Enforcement for PO Creation | Complete |
| Supplier Performance Analytics              | Complete |
| Invoice Cycle-Time Metrics                  | Complete |
| Supplier Trend Metrics                      | Complete |
| Deep Supplier-Scoping Validation            | Complete |
| Cross-Supplier Endpoint Testing             | Complete |
| P2P Business-Rule Testing                   | Complete |
| Three-Way Match Discrepancy Testing         | Complete |
| Supplier Onboarding Workflow Testing        | Complete |

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

Supplier collection endpoints are protected by authentication and return only records belonging to the authenticated supplier.

Internal authorized users can access supplier data according to their assigned role permissions.

Where resource-existence semantics apply, unknown supplier resources return:

```text
404 Not Found
```

while an authenticated supplier attempting to access an existing resource belonging to another supplier receives:

```text
403 Forbidden
```

This distinction is intentional.

---

# Rounds 6–8 Completion Status

The Supplier Portal functional expansion completed the five planned milestones.

## Milestone 1 — Full Procure-to-Pay Flow

Status:

```text
Complete
```

Implemented flow:

```text
PO
→ Acknowledgement
→ Shipment
→ Goods Receipt
→ Invoice
→ Three-Way Match
→ Payment Approval
```

Each stage is controlled through business-state transitions.

Goods Receipt supports partial deliveries while preventing invalid quantities and item references.

---

## Milestone 2 — Three-Way Match Automation

Status:

```text
Complete
```

The implementation compares:

```text
Purchase Order
+
Goods Receipt
+
Invoice
```

The matching process identifies:

```text
Quantity discrepancies
Price discrepancies
```

and routes discrepancies for human review instead of automatically approving payment.

The invoice creation and Goods Receipt validation layers allow valid discrepancy scenarios to reach the matching layer.

---

## Milestone 3 — Supplier Onboarding

Status:

```text
Complete
```

Implemented lifecycle:

```text
Registration
→ Documents
→ Mock Verification
→ Approval
→ Active
```

The workflow preserves the supplier-scoping security model introduced in R5.

Additionally, Purchase Order creation now verifies that the referenced supplier exists and has reached the `active` onboarding state.

---

## Milestone 4 — Supplier Performance Analytics

Status:

```text
Complete
```

Supplier performance is available through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The scorecard includes implemented delivery, invoice, dispute, cycle-time, and overall performance metrics.

Delivery eligibility excludes future-due unfulfilled Purchase Orders and counts past-due unfulfilled Purchase Orders as misses.

Invoice metrics correctly identify related Purchase Orders from invoice line items.

---

## Milestone 5 — Deep Supplier-Scoping Security

Status:

```text
Complete
```

Supplier-facing resource access is protected through:

```text
Authentication
      +
Role Authorization
      +
Supplier Ownership
      +
Collection Filtering
```

Cross-supplier access is explicitly tested across supported supplier-facing resource paths.

Detail endpoints perform supplier authorization before exposing resource-existence information where the endpoint requires this protection.

---

## Milestone Summary

The five planned Rounds 6–8 milestones are implemented:

```text
Milestone 1 → Full P2P Flow
Milestone 2 → Three-Way Match Automation
Milestone 3 → Supplier Onboarding
Milestone 4 → Supplier Performance Analytics
Milestone 5 → Deep Supplier-Scoping Security
```

The remaining items are documented as limitations or future enhancements rather than being represented as completed functionality.

---

## Authentication-Required Endpoint Coverage

Authentication-required endpoint coverage is implemented in:

```text
tests/test_requires_auth.py
```

The test automatically discovers protected API routes from the Supplier Portal routers.

Currently, it validates:

```text
20 protected endpoint/method combinations
```

Run:

```powershell
python -m pytest tests/test_requires_auth.py -v
```

The test confirms that protected endpoints reject requests without authentication.

---

# 27. Known Limitations

The current implementation is primarily designed for development, functional validation, and automated testing.

The core R5 authentication, role-based authorization, and supplier-level data-scoping requirements are implemented.

The Rounds 6–8 functional milestones are also implemented.

Remaining limitations fall into two categories:

```text
Production / Infrastructure Limitations

and

Future Functional Enhancements
```

These should not be interpreted as failures of the completed milestones.

---

## Functional Milestone Status

The following capabilities are implemented:

```text
Procure-to-Pay workflow

P2P state transitions

Shipment Processing

Goods Receipt

Partial Goods Receipt

Invoice/P2P integration

Three-Way Match

Quantity discrepancy detection

Price discrepancy detection

Human-review discrepancy handling

Payment Approval workflow

Supplier Onboarding

Active Supplier enforcement

Supplier Performance Analytics

Supplier-Scoping Security
```

---

## Partial Invoice Lifecycle

The current P2P state machine supports invoice progression from:

```text
received → invoiced
```

and supports partial invoice validation at the invoice-service level.

However, the current P2P state model represents the PO at a single `invoiced` state.

Therefore, after a partial invoice advances the P2P state, a subsequent invoice for the remaining PO quantity may require additional lifecycle support.

This means the current implementation does not provide a complete multi-invoice P2P lifecycle for repeated partial invoicing against the same Purchase Order.

A future enhancement should support:

```text
PO quantity = 10

Invoice 1 = 5
      ↓
Remaining quantity = 5
      ↓
Invoice 2 = 5
      ↓
Fully invoiced
```

without incorrectly treating the PO as fully invoiced after the first partial invoice.

---

## In-Memory Business Storage

Purchase Orders, invoices, workflow data, supplier onboarding data, and related business events are currently maintained in Python in-memory data structures.

As a result, application restarts clear business data.

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

Production deployments should provide appropriate service availability, monitoring, timeout handling, and operational recovery mechanisms for the Platform Service.

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

Maintenance operations are separate from normal supplier-facing business operations.

The maintenance endpoints are:

```text
GET    /api/v1/maintenance/orphaned-invoice-files

DELETE /api/v1/maintenance/orphaned-invoice-files
```

These endpoints should remain restricted to the designated administrative authorization implemented by the service and must not be exposed to anonymous callers.

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

These are production-readiness considerations.

---

## Security and Authorization Enhancements

The current supplier-scoping model is implemented and tested.

Future hardening may include:

* More granular permissions for internal roles
* Stronger segregation of duties between procurement, matching, and payment approval
* Centralized role/permission definitions
* More consistent exception-to-HTTP-status mapping
* Additional audit controls for sensitive workflow transitions

These are enhancements to the existing authorization model rather than missing R5 supplier-scoping functionality.

---

## Onboarding Document Validation Enhancements

The supplier onboarding workflow currently supports document collection and mock verification.

Future production hardening may include:

* Strict document type validation
* File-size limits
* Secure filename handling
* Malware scanning
* Durable document storage
* Document retention policies
* Stronger verification integrations

The current onboarding workflow itself is implemented.

---

## End-to-End Test Expansion

The test suite covers the individual P2P services, state transitions, validation rules, and discrepancy scenarios.

A future enhancement would add a single comprehensive API integration test that drives the entire lifecycle through HTTP endpoints:

```text
Create PO
→ Send
→ Acknowledge
→ Shipment
→ Goods Receipt
→ Invoice
→ Three-Way Match
→ Payment Approval
```

This would complement the existing service-level and milestone-specific API tests.

---

## Configuration and Maintainability Enhancements

Some business constants are currently defined in individual service modules.

Future improvements may centralize:

```text
Three-way match tolerance
Scorecard weights
Upload limits
Workflow configuration
```

into shared configuration so that these values are easier to manage consistently across environments.

---

## R5 Security Status

The implemented R5 security model is:

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

The key R5 security requirement is satisfied:

```text
A valid supplier token does not provide unrestricted supplier access.
```

A supplier authenticated as `SUP001` cannot access supplier-scoped resources belonging to `SUP002`.

Cross-supplier access is rejected with:

```text
403 Forbidden
```

Supplier collection endpoints are also filtered so that supplier users do not receive records belonging to other suppliers.

The remaining limitations are primarily related to:

```text
Production Persistence

Durable File Storage

Authentication Service Availability

Partial-Invoice Lifecycle Expansion

Production Operational Hardening

Additional Integration-Test Coverage

Future Authorization / Maintainability Enhancements
```

These limitations are documented separately from the completed R5 and Rounds 6–8 functional requirements.
