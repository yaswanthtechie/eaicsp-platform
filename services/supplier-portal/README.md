# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for managing supplier-facing Purchase Orders, invoices, invoice documents, supplier operational statistics, supplier performance scorecards, supplier onboarding, supplier contract lifecycle management, dispute-resolution suggestions, supplier self-service analytics, and the procure-to-pay workflow.

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

15. [Supplier Contract Lifecycle Management](#15-supplier-contract-lifecycle-management)

16. [API Reference](#16-api-reference)

17. [HTTP Response Codes](#17-http-response-codes)

18. [Configuration](#18-configuration)

19. [Installation](#19-installation)

20. [Running the Services](#20-running-the-services)

21. [Swagger Documentation](#21-swagger-documentation)

22. [Testing](#22-testing)

23. [Business Rules](#23-business-rules)

24. [Security Controls](#24-security-controls)

25. [Storage](#25-storage)

26. [End-to-End Workflow](#26-end-to-end-workflow)

27. [Current Implementation Status](#27-current-implementation-status)

28. [Known Limitations](#28-known-limitations)

29. [Future Enhancements](#29-future-enhancements)

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

9. Supplier Contract Lifecycle Management

10. Supplier Statistics

11. Supplier Performance Scorecard

12. Supplier Self-Service Analytics

13. Invoice Document Management

14. Historical Dispute-Resolution Suggestions

15. Authentication, Authorization, and Supplier Scoping

16. Compliance Business-Logic Integration
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

Compliance Check

      │

      ├── CLEAR ───────► Active
      │
      ├── BLOCK ───────► Activation Blocked
      │
      ├── REVIEW ──────► Activation Blocked / Human Review
      │
      └── Unavailable ─► Activation Blocked
```

A supplier must be **registered, approved, and active** before a Purchase Order can be created for that supplier.

Supplier-level authorization introduced in Round 5 remains enforced throughout supplier-facing workflows.

Rounds 9–11 extend the onboarding and supplier lifecycle with business-logic integration, contract management, dispute-resolution assistance, and supplier self-service analytics.

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

* Compliance Service integration during supplier activation

* Fail-closed handling when Compliance Service is unavailable

* Active-supplier enforcement during PO creation

* Supplier statistics

* Supplier performance scorecards

* Supplier self-service analytics

* Supplier contract lifecycle management

* Contract renewal and expiry tracking

* Contract term-change audit history

* Historical dispute-resolution suggestions

* Invoice document security

* Automated business-rule testing

* Supplier isolation and cross-supplier security testing

The five reviewer-identified functional issues were addressed:

```text
1. Three-way match discrepancy reachability       → Fixed

2. Scorecard invoice metrics                      → Fixed

3. Supplier ID existence leak                    → Fixed

4. Supplier onboarding enforcement                → Fixed

5. Future-due PO handling in on-time metrics      → Fixed
```

Rounds 9–11 additionally introduced:

```text
1. Compliance business-logic integration         → Implemented

2. Compliance failure-path handling               → Implemented

3. Supplier contract lifecycle management         → Implemented

4. Contract expiry/renewal tracking               → Implemented

5. Contract term-change audit history              → Implemented

6. Historical dispute-resolution suggestions      → Implemented

7. Supplier self-service scorecard access         → Implemented

8. Compliance integration test coverage            → Implemented
```

The remaining limitations are primarily related to persistence, infrastructure, and future workflow enhancements.

Current infrastructure limitations include:

* Purchase Orders, invoices, P2P records, onboarding data, contract data, and audit events use in-memory storage.

* In-memory business data is not persistent across service restarts.

* Invoice PDF documents use local filesystem storage.

* Authentication depends on the availability of the Platform Service.

* Supplier activation depends on the availability of the Compliance Service.

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

* Historical dispute-resolution suggestions

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

* Supplier self-service scorecard access

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

* Compliance Service activation check

* CLEAR/BLOCK/REVIEW compliance decisions

* Fail-closed Compliance Service failure handling

* Active supplier validation before PO creation

### Compliance Business-Logic Integration

Supplier activation performs a real business-logic integration with the Compliance Service.

Before a supplier can move from the approved onboarding state to `active`, the Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

The request contains:

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "Example Supplier",
  "country": "India"
}
```

The request also includes:

```text
X-Caller-Service: supplier-portal
```

A five-second timeout is used for the Compliance Service call.

The supported Compliance decisions are:

```text
CLEAR
   → Supplier activation allowed

BLOCK
   → Supplier activation rejected

REVIEW
   → Supplier activation rejected and requires review
```

If the Compliance Service is unavailable, times out, or cannot be reached, the activation does not proceed.

The integration intentionally follows a **fail-closed** approach:

```text
Supplier Approved
       │
       ▼
Compliance Check
       │
       ├── CLEAR ─────► Active
       │
       ├── BLOCK ─────► Activation blocked
       │
       ├── REVIEW ────► Activation blocked
       │
       └── Unavailable ► Activation blocked
```

This prevents a supplier from becoming active without a successful compliance decision.

## Supplier Contract Lifecycle Management

* Create supplier contracts

* Retrieve supplier contracts

* Retrieve a contract by contract ID

* Update contract terms

* Contract status tracking

* Draft-to-active lifecycle

* Contract expiry detection

* Expiring-contract listing

* Renewal processing

* Renewal date validation

* Renewal reason tracking

* Contract payment terms tracking

* Contract delivery terms tracking

* Contract pricing terms tracking

* Minimum order value tracking

* Renewal notice period tracking

* Auto-renew configuration tracking

* Supplier-scoped contract access

* Contract lifecycle history

* Contract term-change audit history

Contract lifecycle states are:

```text
draft
  │
  ▼
active
  │
  └──► renewed
          │
          ▼
        active

active
  │
  ▼
expired
```

Contract updates record the changed terms in the contract history when an actual value changes.

A no-op update does not create unnecessary audit history.

The current implementation stores `auto_renew` as a contract configuration value; automatic scheduled renewal is not performed by the current in-memory implementation.

## Supplier Self-Service Analytics

Supplier users can access their own supplier performance scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The endpoint exposes supplier-specific performance information such as:

* On-time delivery percentage

* Dispute rate percentage

* Invoice accuracy

* Overall score

* Performance rating

* Performance status

* Performance breakdown

* Historical/monthly trends

Supplier ownership is enforced before returning the scorecard.

Therefore:

```text
SUP001 token
     │
     ▼
SUP001 scorecard
     │
     ▼
Allowed

SUP001 token
     │
     ▼
SUP002 scorecard
     │
     ▼
403 Forbidden
```

Supplier self-service analytics are read-only and do not allow a supplier to modify its performance data.

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

### Historical Dispute-Resolution Suggestions

The Supplier Portal provides advisory resolution suggestions based on previously resolved three-way-match disputes.

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

The service analyzes historical resolved disputes and identifies recurring resolution patterns.

Examples include:

```text
Historical price mismatch
        │
        ▼
Suggested action:
correct_invoice
```

```text
Historical quantity mismatch
        │
        ▼
Suggested action:
credit_note
```

If historical disputes do not contain enough classified evidence, the service returns no suggested action rather than inventing a recommendation.

The suggestion service is **read-only** and advisory:

```text
Historical Disputes
        │
        ▼
Pattern Analysis
        │
        ▼
Resolution Suggestion
        │
        ▼
Human Decision
```

The system does not automatically modify invoices, approve disputes, or change three-way-match state based on the suggestion.

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

     Purchase          Invoice          Supplier

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

          ┌────────────────┼─────────────────────────┐

          │                │                         │

          ▼                ▼                         ▼

      PO Store       Invoice Store          Supplier Stores

                                                   │

                                                   ▼

                                      Contract / Onboarding /

                                      Performance Services

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

               Matched        Discrepancy

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

### Compliance Business-Logic Integration

Rounds 9–11 introduce a service-to-service business-logic integration between Supplier Portal and Compliance Service.

```text
Supplier Portal
      │
      │ Supplier activation request
      ▼
Supplier Onboarding Service
      │
      │ Compliance check
      ▼
Compliance Service
      │
      ├── CLEAR
      ├── BLOCK
      └── REVIEW
      │
      ▼
Supplier Portal
      │
      ├── CLEAR → Activate supplier
      │
      └── BLOCK/REVIEW/Failure → Do not activate
```

The integration is isolated in:

```text
app/services/compliance_client.py
```

The onboarding service therefore owns the supplier lifecycle decision, while the Compliance Service owns the compliance decision.

The integration does not decode or manage authentication tokens locally. The Supplier Portal continues to use the Platform Service for user authentication and authorization.

### Supplier Contract Architecture

Supplier contract management is implemented as an independent business service:

```text
Supplier Contract Route
        │
        ▼
Authentication / Authorization
        │
        ▼
Supplier Contract Service
        │
        ├── Contract Validation
        ├── Lifecycle Transition
        ├── Renewal Processing
        ├── Expiry Calculation
        └── History / Audit
        │
        ▼
In-Memory Contract Store
```

This keeps contract lifecycle rules separate from Purchase Order and Invoice lifecycle rules.

### Historical Dispute-Resolution Architecture

```text
Three-Way Match Records
        │
        ▼
Dispute Resolution Service
        │
        ├── Historical dispute filtering
        ├── Resolution reason classification
        ├── Pattern counting
        └── Suggestion generation
        │
        ▼
Advisory Resolution Suggestion
```

The service does not mutate the underlying dispute, invoice, or three-way-match records.

### Supplier Self-Service Architecture

```text
Supplier User
      │
      ▼
Scorecard Endpoint
      │
      ▼
Supplier Ownership Check
      │
      ▼
Supplier Performance Service
      │
      ▼
Supplier Scorecard
```

Supplier users can read only their own scorecard.

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

                           │

                           ▼

                    Three-Way Match

                           │

                  ┌────────┴────────┐

                  │                 │

                  ▼                 ▼

               Matched        Discrepancy

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

   ├── Supplier Onboarding
   ├── Supplier Contracts
   ├── Supplier Performance
   ├── Dispute Resolution
   └── Compliance Integration

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

The Supplier Portal Service follows a layered FastAPI architecture separating application configuration, authentication, API routes, validation schemas, business logic, external business-service integration, and automated tests.

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

│   │   ├── supplier_contract.py

│   │   └── supplier_stats_routes.py

│   │

│   ├── schemas/

│   │   ├── purchase_order.py

│   │   ├── shipment.py

│   │   ├── goods_receipt.py

│   │   ├── invoice.py

│   │   ├── three_way_match.py

│   │   ├── supplier_onboarding.py

│   │   ├── supplier_contract.py

│   │   └── supplier_stats.py

│   │

│   └── services/

│       ├── purchase_order_service.py

│       ├── shipment_service.py

│       ├── goods_receipt_service.py

│       ├── invoice_service.py

│       ├── three_way_match_service.py

│       ├── supplier_onboarding_service.py

│       ├── supplier_contract_service.py

│       ├── supplier_stats_service.py

│       ├── dispute_resolution_service.py

│       ├── compliance_client.py

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

│   ├── test_supplier_onboarding.py

│   ├── test_supplier_contract.py

│   └── test_dispute_resolution.py

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

* Compliance Service URL

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

* Supplier onboarding and activation

* Supplier contract lifecycle management

* Supplier statistics and performance scorecards

* Supplier self-service analytics

* Historical dispute-resolution suggestions

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

* Supplier-contract data models

* Supplier-statistics and scorecard data models

* Dispute-resolution suggestion response models

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

* Compliance Service integration

* Supplier contract lifecycle management

* Contract expiry and renewal processing

* Contract lifecycle audit history

* Supplier performance calculations

* Supplier scorecard calculations

* Supplier self-service analytics

* Historical dispute pattern analysis

* Advisory dispute-resolution suggestions

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

* Supplier contracts

* Supplier contract history

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

* Supplier contract creation/update/activation/renewal requires `procurement_manager`

* Supplier-specific resources require the authenticated supplier to own the resource

* Supplier collection endpoints return only the authenticated supplier's resources

* Supplier scorecards are restricted to the authenticated supplier

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

## Supplier Contract Authorization

Supplier contract operations apply both role authorization and supplier scoping.

Internal contract-management operations are restricted to the appropriate internal role, while supplier users are limited to contracts belonging to their own supplier.

The contract service validates the authenticated supplier identity before returning or modifying supplier-scoped contract data.

Contract lifecycle operations include:

```text
Create
  │
  ▼
Update
  │
  ▼
Activate
  │
  ▼
Renew
  │
  ▼
Expire
  │
  ▼
History
```

Contract history is read-only audit information and cannot be directly modified by the caller.

## Supplier Self-Service Scorecard Authorization

Supplier self-service analytics use the same supplier ownership model.

```text
Supplier Token
      │
      ▼
supplier_id = SUP001
      │
      ▼
GET /api/v1/suppliers/SUP001/scorecard
      │
      ▼
Allowed
```

A cross-supplier request is rejected:

```text
supplier_id = SUP001

       │

       ▼

GET /api/v1/suppliers/SUP002/scorecard

       │

       ▼

403 Forbidden
```

The scorecard endpoint is read-only for supplier users.

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

SUP001 token → SUP001 Contract    → Allowed

SUP001 token → SUP002 Contract    → 403 Forbidden
```

The same ownership principle applies to supplier-scoped Purchase Order events, invoice documents, statistics, shipments, goods receipts, three-way matches, onboarding resources, and contract resources.

Supplier-level authorization is enforced at the API layer and covered by automated tests, including:

* Supplier cannot view another supplier's Purchase Order

* Supplier cannot acknowledge another supplier's Purchase Order

* Supplier cannot view another supplier's Invoice

* Supplier cannot access another supplier's Scorecard

* Supplier cannot access another supplier's Statistics

* Supplier cannot access another supplier's Contract

* Supplier cannot access another supplier's Contract History

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

The actual delivery date is derived from the related Goods Receipt rather than simply using the date on which the PO status changes to `fulfilled`.

For multiple Goods Receipts, the latest applicable receipt date is used as the actual delivery date.

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

## Historical Dispute-Resolution Suggestions

Resolved historical three-way-match disputes can be analyzed to provide advisory resolution suggestions.

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Authorization:

```text
compliance_officer
```

The service:

1. Identifies relevant historical three-way-match records.

2. Ignores the current unresolved dispute when generating its historical pattern.

3. Ignores unresolved historical disputes.

4. Classifies known resolution reasons.

5. Counts recurring resolution actions.

6. Returns the resulting suggestion as advisory information.

Known patterns include:

```text
Price mismatch
    → correct_invoice

Quantity mismatch
    → credit_note
```

If there is insufficient classified historical evidence, the service returns no suggested action.

The endpoint does not automatically:

* Adjust an invoice

* Approve an invoice

* Reject an invoice

* Change three-way-match status

* Resolve the dispute

The final business decision remains with the authorized human user.

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
# 9. Invoice Document Management

Invoice documents are stored as PDF files on the local filesystem.

The upload directory is:

```text
uploads/
```

Invoice documents are stored using a supplier-specific path so that invoice files remain associated with the supplier that owns the invoice.

Example:

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

This historical information is also used by supplier performance calculations and the historical dispute-resolution suggestion feature.

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

A supplier user without a `supplier_id` is rejected from supplier-scoped statistics access with:

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

Supplier delivery statistics use the same delivery-eligibility rule as the Supplier Performance Scorecard and monthly trend calculations.

A Purchase Order is eligible for delivery-performance calculation when it is:

```text
fulfilled
```

or when:

```text
expected delivery date has passed
```

Cancelled POs are excluded.

Future-due unfulfilled POs are excluded because their delivery deadline has not yet passed.

The implemented rule is:

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

A fulfilled PO is considered on time when its actual delivery date is on or before the expected delivery date.

The actual delivery date is derived from the related Goods Receipt records.

When multiple Goods Receipts exist for the same Purchase Order, the latest recorded `receipt_date` is used as the actual delivery date.

Therefore, the implementation does not use the current system date as the delivery date when calculating supplier performance.

Past-due unfulfilled POs are counted as delivery misses.

Future-due unfulfilled POs do not count as misses.

The result is rounded to two decimal places.

Example:

```text
Eligible POs = 3

On-time POs = 2

On-time percentage = 66.67%
```

This delivery-eligibility rule is shared by:

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

Purchase Order references are taken from invoice line items:

```text
invoice.items[].po_number
```

The service also supports the legacy/top-level `po_number` value when present.

Example:

```text
PO created:   August 1

Invoice date: August 4

Cycle time = 3 days
```

Negative cycle times are ignored.

Invalid or unusable date records are ignored rather than causing the entire supplier-statistics calculation to fail.

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

These values are normalized before calculations are performed.

---

## Supplier Not Found

If the requested supplier cannot be identified from the supplier-related data maintained by the Supplier Portal, the statistics operation returns:

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

## R5 Supplier-Scoping Security

Supplier-scoped analytics endpoints enforce supplier ownership.

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
 Owner    Not owner
   │         │
   ▼         ▼
Continue   403 Forbidden
```

This prevents an unauthorized supplier from accessing another supplier's statistics.

The same supplier-scoping principle is applied across protected supplier detail and analytics endpoints.

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

The scorecard includes:

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
Monthly trends
```

The same scorecard endpoint also provides the supplier self-service analytics capability introduced in R9–11.

---

## Supplier Self-Service Analytics

Supplier users can view their own performance analytics through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

A supplier can access the endpoint only when:

```text
authenticated supplier_id == requested supplier_id
```

A cross-supplier request is rejected with:

```text
403 Forbidden
```

A supplier token without a valid `supplier_id` cannot access supplier-scoped scorecard information.

The supplier-facing scorecard exposes metrics including:

```text
on-time delivery percentage
dispute rate percentage
invoice accuracy
overall score
rating
performance status
PO performance details
invoice performance details
trends
```

This allows suppliers to view their own performance without exposing another supplier's operational data.

---

## Scorecard Metrics

### On-Time Delivery

The scorecard uses the same delivery-eligibility rule as Supplier Statistics.

Eligible Purchase Orders are:

```text
Fulfilled POs

+

Past-due unfulfilled POs
```

Excluded Purchase Orders are:

```text
Cancelled POs

+

Future-due unfulfilled POs
```

The actual delivery date for fulfilled Purchase Orders is derived from the related Goods Receipt records.

When multiple receipts exist, the latest receipt date is used.

Weight:

```text
40%
```

---

### Invoice Accuracy

Invoice accuracy is calculated from the supplier's invoice history.

For the implemented scorecard calculation, invoices without recorded dispute information are treated as accurate.

Conceptually:

```text
invoice accuracy =
accurate invoices / total invoices × 100
```

Weight:

```text
40%
```

Historical dispute information is retained.

Therefore, an invoice that was previously disputed continues to contribute to historical dispute metrics even after later adjustment or approval.

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

The implemented scorecard converts dispute rate into dispute performance:

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

## Scorecard Details

Purchase Order metrics include:

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

Invoice cycle-time calculations use:

```text
invoice.items[].po_number
```

to associate invoices with their Purchase Orders.

---

## Historical Dispute Tracking

A resolved dispute remains part of the supplier's historical performance.

Example:

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

This prevents supplier performance calculations from losing the history of previously disputed invoices.

---

## Monthly Supplier Trends

Supplier performance trends are grouped by the Purchase Order creation month.

Trend calculations use the same delivery eligibility and actual Goods Receipt date rules used by the main scorecard.

This ensures that:

```text
Current Scorecard

+

Supplier Statistics

+

Monthly Trends
```

use consistent business definitions for delivery performance.

---

## Invoice-Only Suppliers

A supplier can be identified from invoice data even if it currently has no Purchase Orders.

Supplier identification can therefore use relevant supplier data maintained by the service, including:

```text
Purchase Order data

        OR

Invoice data
```

This prevents an invoice-only supplier from incorrectly receiving a `404 Not Found` solely because it currently has no Purchase Orders.

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
Compliance Check
        ↓
Active
        ↓
PO Creation Allowed
```

The Compliance Check is performed before activation and is part of the actual business workflow.

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

The matching process evaluates item codes, quantities, and unit prices.

Quantity and price discrepancies are identified and flagged for human review.

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
 ┌───┴─────────────┐
 │                 │
 ▼                 ▼
Matched       Discrepancy
 │                 │
 ▼                 ▼
Continue       Human Review
to Payment
Approval
```

The matching process does not automatically approve transactions that contain discrepancies.

---

## Quantity Matching

The matching process validates quantities across:

```text
Purchase Order
Goods Receipt
Invoice
```

A quantity mismatch is identified as a discrepancy.

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

Because Goods Receipt supports partial receiving, a short receipt can reach the three-way matching stage instead of being rejected earlier.

---

## Price Matching

Invoice creation does not reject an otherwise valid invoice solely because its unit price differs from the Purchase Order price.

This allows price differences to reach the three-way matching stage.

Example:

```text
PO unit price      = 100

Invoice unit price = 120
```

Result:

```text
Price discrepancy
        │
        ▼
Human Review
```

---

## Price Tolerance

The configured price tolerance is:

```text
PRICE_TOLERANCE_PERCENT = 5.0
```

The tolerance is inclusive.

Therefore, a price difference of up to and including 5% is considered within tolerance.

For example, when the Purchase Order price is:

```text
PO unit price = 100
```

the following range is within the configured tolerance:

```text
95 through 105
```

A price of:

```text
106
```

is outside the configured tolerance and can be reported as a price discrepancy.

The tolerance is therefore a three-way matching rule, not an invoice-creation rejection rule.

---

## Match Result

A successful match indicates that the relevant Purchase Order, Goods Receipt, and Invoice information satisfies the implemented matching rules.

A matched transaction can continue toward payment approval according to the P2P state machine.

---

## Discrepancy Handling

The three-way match does not automatically approve transactions containing discrepancies.

Supported discrepancy categories include:

```text
Quantity mismatch

Price mismatch
```

The control flow is:

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
Matched          Discrepancy
 │                   │
 ▼                   ▼
Payment           Human Review
Approval
```

---

## Historical Dispute-Resolution Suggestions

The Supplier Portal provides advisory dispute-resolution suggestions based on previously resolved three-way-match disputes.

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Authorization:

```text
compliance_officer
```

The service analyzes historical resolved disputes and identifies previously used resolution patterns.

The suggestion engine does not modify the invoice, three-way match, or payment state.

It provides an advisory result for human review.

---

## Historical Pattern Analysis

Historical dispute records are classified using the recorded resolution reason.

Implemented patterns include:

```text
Price mismatch
    →
correct_invoice

Quantity mismatch
    →
credit_note
```

Historical disputes without sufficient evidence for a known action are not assigned an automatic action.

Unresolved historical disputes are ignored.

The current unresolved dispute is not used as its own historical evidence.

Therefore:

```text
Historical resolved disputes
          │
          ▼
Pattern analysis
          │
          ▼
Advisory suggestion
          │
          ▼
Human decision
```

The system does not automatically execute the suggested action.

---

## Real-Flow Discrepancy Support

The implementation supports discrepancy scenarios through the actual API workflow.

### Quantity Discrepancy

A partial Goods Receipt can be created first, allowing a short-receipt scenario to reach the matching stage.

Example:

```text
PO quantity       = 100

Goods Receipt     = 90

Invoice quantity  = 100
```

The three-way match can identify the quantity discrepancy.

Workflow:

```text
PO
 │
 ▼
Acknowledged
 │
 ▼
Shipped
 │
 ▼
Partial Goods Receipt
 │
 ▼
Received
 │
 ▼
Invoice
 │
 ▼
Three-Way Match
 │
 ▼
Quantity Discrepancy
 │
 ▼
Human Review
```

### Price Discrepancy

Invoice creation allows a price difference to reach the matching stage.

Example:

```text
PO unit price      = 100

Invoice unit price = 120
```

The three-way match can identify the price discrepancy.

This prevents invoice validation from hiding a price exception before the matching process has an opportunity to evaluate it.

---

## Matching Tolerance Configuration

The three-way match uses the centralized configuration value:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

This value is maintained in:

```text
app/core/config.py
```

The three-way match service uses this configuration rather than maintaining a separate hardcoded tolerance.

This keeps the matching rule centralized and avoids different parts of the application applying different price-tolerance values.

---

## Human Review Requirement

The three-way match is designed to identify exceptions rather than make an uncontrolled automatic business decision.

The intended behavior is:

```text
Three-Way Match
      │
      ├── Match successful
      │       │
      │       ▼
      │   Continue toward
      │   Payment Approval
      │
      └── Discrepancy detected
              │
              ▼
          Human Review
              │
              ▼
       Controlled Resolution
```

Therefore, a quantity or price discrepancy does not automatically result in payment approval.

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
Compliance Check
      │
      ▼
Active
```

The Compliance Check is a real business-logic integration with the Compliance Service.

A supplier is not moved to `active` until the Compliance Service returns a successful `CLEAR` decision.

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
compliance check
      ↓
active
```

The onboarding service validates the current stage before allowing the supplier to progress.

Invalid state transitions are rejected instead of silently changing the supplier's onboarding state.

---

## Registration

The workflow begins when a supplier is registered.

The registration stage establishes the supplier onboarding record before document collection, verification, and approval.

A supplier that has only been registered is not considered active.

---

## Document Collection

Required supplier documentation can be collected as part of onboarding.

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

Supplier onboarding document uploads currently support:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

The maximum supported document size is:

```text
10 MB
```

The implementation validates both the uploaded content type and the corresponding file extension.

The following validation failures are rejected:

```text
Unsupported document type
    → 400 Bad Request

File extension does not match content type
    → 400 Bad Request

Empty document
    → 400 Bad Request

Document larger than 10 MB
    → 400 Bad Request
```

Supplier ownership is validated separately from file validation:

```text
Authenticated supplier
        │
        ▼
Requested onboarding supplier
        │
        ├── Same → Allowed
        │
        └── Different → 403 Forbidden
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

Mock verification is intentionally used instead of an external supplier-verification provider in the current implementation.

---

## Approval

After successful verification, the supplier can progress through the approval stage.

```text
Verified
   │
   ▼
Approved
```

The onboarding service validates the current onboarding state before allowing approval.

Approval does not immediately make the supplier active.

The supplier must pass the Compliance Service check before activation.

---

## Compliance Business-Logic Integration

Before an approved supplier can become active, the Supplier Portal calls the Compliance Service.

The integration exists to ensure that supplier activation is dependent on the required compliance decision.

The Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

The configured Compliance Service URL is used as the base URL.

Conceptually:

```text
Supplier Portal
      │
      │ POST /api/v1/compliance/internal-check
      ▼
Compliance Service
      │
      ▼
Compliance Decision
      │
 ┌────┼─────────┐
 │    │         │
CLEAR BLOCK    REVIEW
 │    │         │
 ▼    ▼         ▼
Active  Block   Keep Approved
```

---

## Compliance Request

The Supplier Portal sends the following supplier information:

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "Example Supplier",
  "country": "India"
}
```

The internal service request includes:

```text
X-Caller-Service: supplier-portal
```

The Compliance Service call uses a timeout of:

```text
5 seconds
```

The Supplier Portal does not decode or independently interpret authentication tokens for this integration.

---

## Compliance Decisions

The Compliance Service can return:

```text
CLEAR
BLOCK
REVIEW
```

### CLEAR

A `CLEAR` decision allows the supplier to become active.

```text
Approved
   │
   ▼
Compliance CLEAR
   │
   ▼
Active
```

### BLOCK

A `BLOCK` decision prevents activation.

The supplier remains in the approved state.

```text
Approved
   │
   ▼
Compliance BLOCK
   │
   ▼
Activation rejected
```

The API returns:

```text
409 Conflict
```

### REVIEW

A `REVIEW` decision also prevents activation.

The supplier remains approved until the required compliance outcome is available.

The API returns:

```text
409 Conflict
```

---

## Compliance Failure Handling

The Compliance integration is intentionally fail-closed.

If the Compliance Service is unavailable, the Supplier Portal does not activate the supplier.

Examples include:

```text
Connection timeout
Connection failure
Network error
```

These failures are converted into:

```text
503 Service Unavailable
```

This ensures that:

```text
Compliance Service unavailable
        │
        ▼
Activation blocked
        │
        ▼
Supplier remains approved
```

The system does not assume that an unavailable Compliance Service means the supplier is compliant.

---

## Compliance Service Errors

If the Compliance Service responds with an unexpected HTTP/service failure, the Supplier Portal returns:

```text
502 Bad Gateway
```

This distinguishes an upstream Compliance Service failure from the Compliance business decision itself.

The error handling is therefore:

```text
CLEAR
  → Activation allowed

BLOCK
  → 409 Conflict

REVIEW
  → 409 Conflict

Compliance unavailable
  → 503 Service Unavailable

Compliance service error
  → 502 Bad Gateway
```

---

## Fail-Closed Activation

The activation rule is:

```text
Supplier must be approved

        AND

Compliance decision must be CLEAR

        ↓

Supplier becomes active
```

There is no fallback path such as:

```text
Compliance unavailable
        ↓
Assume CLEAR
```

This prevents activation when the required compliance decision cannot be obtained.

---

## Compliance Integration Testing

The integration is covered by tests for:

```text
Successful CLEAR decision

BLOCK decision

REVIEW decision

Compliance service unavailable

Compliance service error

Correct request payload

Correct internal caller header

Activation ordering

No active-state history when compliance fails
```

The failure-path tests verify that a failed compliance check does not partially activate the supplier.

---

## Active Supplier

An approved supplier reaches the active state only after the Compliance Service returns `CLEAR`:

```text
Approved
   │
   ▼
Compliance Check
   │
   ▼
CLEAR
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

This makes onboarding enforcement part of the actual procurement business flow rather than documentation-only behavior.

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

A supplier token without a valid `supplier_id` cannot access supplier-scoped onboarding resources.

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
compliance check
      ↓
active
```

Invalid progression is rejected rather than silently changing the supplier's onboarding state.

A supplier cannot skip required onboarding stages.

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
Approval
   │
   ▼
Compliance CLEAR
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

A supplier that has not completed onboarding and passed Compliance cannot be used for new Purchase Order creation.

---

## How the Business-Logic Integration Is Wired

The Supplier Portal owns the onboarding workflow, while the Compliance Service owns the compliance decision.

The responsibilities are separated:

```text
Supplier Portal
    │
    ├── Registration
    ├── Documents
    ├── Verification
    ├── Approval
    └── Activation workflow
             │
             ▼
       Compliance Service
             │
             └── Compliance decision
```

The Supplier Portal does not duplicate Compliance Service business logic.

Instead, it:

1. Builds the internal compliance request.
2. Calls the Compliance Service.
3. Validates the returned decision.
4. Allows activation only for `CLEAR`.
5. Converts upstream failures into explicit API errors.
6. Keeps the supplier approved when activation is blocked.

This design keeps compliance ownership inside the Compliance Service while keeping supplier lifecycle ownership inside the Supplier Portal.

---

# 15. Supplier Contract Lifecycle Management

The Supplier Portal implements Supplier Contract Lifecycle Management for tracking supplier contracts, commercial terms, expiry dates, renewals, and contract history.

The contract lifecycle supports:

```text
Create Contract
      │
      ▼
Draft
      │
      ▼
Active
      │
      ├──────────────┐
      │              │
      ▼              ▼
Renewed          Expired
      │
      ▼
Active
```

Contracts are associated with a supplier and contain commercial and operational terms.

---

## Contract Information

A supplier contract can contain:

```text
supplier_id
contract_number
title
description
start_date
end_date
payment_terms
delivery_terms
pricing_terms
minimum_order_value
renewal_notice_days
auto_renew
status
```

Contract numbers are unique within the Supplier Portal.

---

## Contract Status

Supported contract statuses are:

```text
draft
active
renewed
expired
```

The implemented transition rules are:

```text
draft
  ↓
active

active
  ↓
renewed / expiry handling

renewed
  ↓
active

expired
  ↓
renewal can create an active renewed period
```

Invalid status transitions are rejected.

---

## Contract Creation

Endpoint:

```http
POST /api/v1/supplier-contracts
```

Authorization:

```text
procurement_manager
```

Contract creation validates:

```text
Supplier existence

Supplier active status

Unique contract number

Valid start date

Valid end date

Required contract information
```

A new contract is initially created in:

```text
draft
```

A history record is created for the initial contract state.

---

## Contract Update

Endpoint:

```http
PUT /api/v1/supplier-contracts/{contract_id}
```

Authorization:

```text
procurement_manager
```

Contract updates can modify mutable commercial and operational terms.

Examples include:

```text
title
description
end_date
payment_terms
delivery_terms
pricing_terms
minimum_order_value
renewal_notice_days
auto_renew
```

Supplier identity and contract number are not treated as freely mutable contract terms.

Expired contracts cannot be arbitrarily modified through the normal update operation.

---

## Contract Term-Change Audit History

Contract changes are audited.

The history records information such as:

```text
history_id
contract_id
supplier_id
from_status
to_status
actor_id
actor_name
role
reason
timestamp
```

When contract terms are changed, the service records the changed fields and their previous/new values in the audit reason.

Example:

```text
payment_terms:
    old → Net 30
    new → Net 45
```

A no-op update does not create unnecessary history.

Therefore:

```text
Actual term change
      │
      ▼
Audit history created
```

while:

```text
No effective change
      │
      ▼
No additional history record
```

This provides traceability for commercial-term changes.

---

## Contract Activation

Endpoint:

```http
POST /api/v1/supplier-contracts/{contract_id}/activate
```

Authorization:

```text
procurement_manager
```

A draft contract can be activated after the required validation checks succeed.

The transition is:

```text
draft
  │
  ▼
active
```

The activation is recorded in contract history.

---

## Contract Expiry Tracking

The service calculates contract expiry information from the contract end date.

Contract responses can expose:

```text
expiring_soon
days_until_expiry
status
end_date
```

The service distinguishes between:

```text
Active and not near expiry

Active and expiring soon

Expired
```

Expired contracts are not treated as active contracts.

---

## Expiring Contracts

Endpoint:

```http
GET /api/v1/supplier-contracts/expiring
```

The endpoint returns contracts approaching their expiry date.

The configured `renewal_notice_days` value determines the contract's normal renewal-warning window.

An optional supplier filter can be used to retrieve expiring contracts for a particular supplier.

Expired contracts are excluded from the normal expiring-soon result.

---

## Contract Renewal

Endpoint:

```http
POST /api/v1/supplier-contracts/{contract_id}/renew
```

Authorization:

```text
procurement_manager
```

Renewal accepts:

```text
new_start_date
new_end_date
reason
```

The service validates the new dates before renewing the contract.

The renewal records:

```text
previous_end_date
new_start_date
new_end_date
renewed_at
renewed_by
reason
```

The contract's new lifecycle period becomes active.

A renewal history record is created so that the previous contract period and renewal action remain auditable.

---

## Renewal Flow

The renewal process is:

```text
Existing Contract
      │
      ▼
Renewal Request
      │
      ▼
Validate New Dates
      │
      ▼
Update Contract Period
      │
      ▼
Active Renewed Contract
      │
      ▼
Record Renewal History
```

The same contract record is reused for renewal while its lifecycle history retains the previous transition information.

---

## Contract History

Endpoint:

```http
GET /api/v1/supplier-contracts/{contract_id}/history
```

The history endpoint exposes contract lifecycle and audit information.

History can contain events such as:

```text
Contract Created

Contract Activated

Contract Terms Updated

Contract Renewed

Contract Status Changed
```

Each history event identifies the actor and timestamp where applicable.

---

## Contract Supplier Scoping

Supplier contracts follow the same supplier-scoping principles established in Round 5.

Supplier users can access only contract resources belonging to their authenticated supplier where supplier-facing contract access is permitted.

The core ownership rule is:

```text
Authenticated supplier_id
        │
        ▼
Contract supplier_id
        │
        ├── Same → Allowed
        │
        └── Different → 403 Forbidden
```

Internal users access contracts according to their assigned role permissions.

Contract creation, activation, updating, and renewal are restricted to the appropriate procurement role.

---

## Contract Lifecycle Audit

Contract lifecycle operations preserve an audit trail.

The audit flow is:

```text
Business Operation
      │
      ▼
Validate Current State
      │
      ▼
Apply Change
      │
      ▼
Record Actor
      │
      ▼
Record Timestamp
      │
      ▼
Record Reason / Changed Terms
```

This makes contract lifecycle changes traceable.

---

## Contract Lifecycle Limitations

The current implementation intentionally has several limitations:

### In-Memory Storage

Contract data is currently maintained in application memory:

```python
supplier_contracts: dict[str, dict] = {}
supplier_contract_history: dict[str, list[dict]] = {}
```

A persistent database implementation can replace this storage in a later production-hardening phase.

### Auto-Renew Configuration

The `auto_renew` field is stored as contract configuration.

The current implementation does not run a background scheduler that automatically renews contracts.

Therefore:

```text
auto_renew = true
```

does not by itself execute an automatic renewal.

### Contract Versioning

Renewals reuse the same contract record.

The history retains the previous dates and renewal information, but the current implementation does not create a separate version-numbered contract record for every renewal period.

---

## Contract API Summary

The implemented Supplier Contract Lifecycle endpoints are:

```text
POST /api/v1/supplier-contracts

GET /api/v1/supplier-contracts

GET /api/v1/supplier-contracts/expiring

GET /api/v1/supplier-contracts/{contract_id}

PUT /api/v1/supplier-contracts/{contract_id}

POST /api/v1/supplier-contracts/{contract_id}/activate

POST /api/v1/supplier-contracts/{contract_id}/renew

GET /api/v1/supplier-contracts/{contract_id}/history
```

The contract lifecycle therefore provides:

```text
Contract Creation

Contract Term Management

Contract Activation

Expiry Tracking

Renewal

Lifecycle History

Term-Change Audit

Supplier Scoping
```

---

# 16. API Reference

All application APIs use the `/api/v1` prefix unless otherwise noted.

The service root endpoint `/` is not under the `/api/v1` prefix.

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

---

## Invoice Collection Scoping

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

Invoice document uploads are restricted to PDF documents.

The upload operation validates:

```text
Authentication

Supplier ownership

Content type

PDF signature

Maximum file size

Safe filesystem path
```

The current invoice PDF size limit is:

```text
10 MB
```

The download operation validates:

```text
Authentication

Supplier ownership where applicable

Stored document path

Path traversal protection

File existence
```

Invoice document validation is separate from supplier onboarding document validation.

Supplier onboarding supports:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

while invoice documents are PDF-only.

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

The implemented P2P state sequence is:

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

## Supplier Statistics and Scorecard APIs

| Method | Endpoint                                    | Authentication / Scope | Description                                     |
| ------ | ------------------------------------------- | ---------------------- | ----------------------------------------------- |
| GET    | `/api/v1/suppliers/{supplier_id}/stats`     | Authenticated          | Supplier operational statistics                 |
| GET    | `/api/v1/suppliers/{supplier_id}/scorecard` | Authenticated          | Supplier performance and self-service scorecard |

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

Compliance check

Activation

Status

History
```

Supplier onboarding detail operations are supplier-scoped.

The onboarding service also exposes the active-supplier state internally so that business operations such as Purchase Order creation can enforce onboarding completion.

Onboarding document uploads validate:

```text
Supported document type

File extension

Empty file

Maximum file size

Supplier ownership
```

The supported onboarding document types are:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

The maximum document size is:

```text
10 MB
```

Activation additionally requires a successful Compliance Service `CLEAR` decision.

---

## Compliance Integration API

The Supplier Portal integrates with the Compliance Service through:

```http
POST /api/v1/compliance/internal-check
```

The integration is called internally before supplier activation.

The Supplier Portal sends:

```text
supplier_id

supplier_name

country
```

and identifies itself using:

```text
X-Caller-Service: supplier-portal
```

The integration timeout is:

```text
5 seconds
```

Decision handling:

| Compliance result      | Supplier Portal behavior                          |
| ---------------------- | ------------------------------------------------- |
| `CLEAR`                | Supplier can become active                        |
| `BLOCK`                | Activation rejected with `409 Conflict`           |
| `REVIEW`               | Activation rejected with `409 Conflict`           |
| Service unavailable    | Activation blocked with `503 Service Unavailable` |
| Upstream service error | `502 Bad Gateway`                                 |

The integration is fail-closed.

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

Receipt quantities must be greater than zero and cannot exceed the corresponding Purchase Order quantity.

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

The configured price tolerance is:

```text
5%
```

The tolerance is inclusive.

For example, if the PO unit price is `100`:

```text
95  → Match
100 → Match
105 → Match
106 → Price discrepancy
```

Supported discrepancy categories include:

```text
Quantity mismatch

Price mismatch
```

Discrepancies are flagged for human review and do not automatically result in payment approval.

---

## Historical Dispute-Resolution Suggestion API

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Authorization:

```text
compliance_officer
```

The endpoint analyzes historical resolved dispute patterns and returns advisory suggestions.

Examples include:

```text
Price mismatch
    →
correct_invoice

Quantity mismatch
    →
credit_note
```

The suggestion endpoint is read-only.

It does not:

```text
Modify invoices

Modify three-way matches

Change P2P state

Approve payments
```

The current unresolved dispute is excluded from its own historical pattern analysis.

Unresolved historical disputes and unclassified resolution reasons are ignored.

---

## Supplier Contract APIs

| Method | Endpoint                                            | Authentication / Role  | Description               |
| ------ | --------------------------------------------------- | ---------------------- | ------------------------- |
| POST   | `/api/v1/supplier-contracts`                        | `procurement_manager`  | Create supplier contract  |
| GET    | `/api/v1/supplier-contracts`                        | Authenticated / scoped | List supplier contracts   |
| GET    | `/api/v1/supplier-contracts/expiring`               | Authenticated / scoped | List expiring contracts   |
| GET    | `/api/v1/supplier-contracts/{contract_id}`          | Authenticated / scoped | Get contract              |
| PUT    | `/api/v1/supplier-contracts/{contract_id}`          | `procurement_manager`  | Update contract           |
| POST   | `/api/v1/supplier-contracts/{contract_id}/activate` | `procurement_manager`  | Activate draft contract   |
| POST   | `/api/v1/supplier-contracts/{contract_id}/renew`    | `procurement_manager`  | Renew contract            |
| GET    | `/api/v1/supplier-contracts/{contract_id}/history`  | Authenticated / scoped | Retrieve contract history |

Contract operations enforce supplier ownership where supplier-facing access applies.

Contract lifecycle operations are restricted according to the configured procurement authorization rules.

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

| Resource                                   | Supplier Access | Internal Role Access                              |
| ------------------------------------------ | --------------- | ------------------------------------------------- |
| Own PO                                     | Allowed         | According to role                                 |
| Other supplier PO                          | `403 Forbidden` | According to role                                 |
| Own invoice                                | Allowed         | According to role                                 |
| Other supplier invoice                     | `403 Forbidden` | According to role                                 |
| Own invoice document                       | Allowed         | According to role                                 |
| Other supplier document                    | `403 Forbidden` | According to role                                 |
| Own statistics                             | Allowed         | According to role                                 |
| Other supplier statistics                  | `403 Forbidden` | According to role                                 |
| Own scorecard                              | Allowed         | According to role                                 |
| Other supplier scorecard                   | `403 Forbidden` | According to role                                 |
| Own contract where supplier access applies | Allowed         | According to role                                 |
| Other supplier contract                    | `403 Forbidden` | According to role                                 |
| Missing supplier identity                  | `403 Forbidden` | Not applicable to supplier-scoped supplier access |

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

## API Error Handling Summary

The Supplier Portal uses explicit HTTP responses for authentication, authorization, validation, resource, and integration failures.

Common responses include:

```text
400 Bad Request
    → Invalid request, invalid state transition, invalid file, or validation failure

401 Unauthorized
    → Missing or invalid authentication

403 Forbidden
    → Insufficient role or supplier-scope violation

404 Not Found
    → Requested resource does not exist

409 Conflict
    → Business-rule conflict such as Compliance BLOCK/REVIEW or duplicate resource

502 Bad Gateway
    → Upstream Compliance Service error

503 Service Unavailable
    → Compliance Service unavailable or unreachable
```

This keeps authentication, authorization, business validation, and cross-service failure conditions distinguishable to API consumers.

# 17. HTTP Response Codes

| Status | Meaning                                                                                      |
| -----: | -------------------------------------------------------------------------------------------- |
|    200 | Successful request                                                                           |
|    201 | Resource created                                                                             |
|    400 | Business-rule or input validation failure                                                    |
|    401 | Authentication required, invalid, or expired                                                 |
|    403 | Authenticated user is not authorized or supplier scope does not match                        |
|    404 | Resource not found                                                                           |
|    409 | Duplicate resource, conflicting resource state, or business-rule conflict                    |
|    422 | FastAPI request/schema validation failure                                                    |
|    502 | Downstream Compliance Service returned an unusable or unsuccessful business/service response |
|    503 | Platform authentication service or Compliance Service unavailable                            |

For protected supplier-scoped resources, the implementation applies supplier ownership checks on affected detail endpoints.

This prevents unauthorized supplier users from accessing resources belonging to another supplier.

Typical examples are:

```text
Missing / invalid token
        → 401 Unauthorized

Valid supplier token + different supplier resource
        → 403 Forbidden

Unknown resource
        → 404 Not Found

Duplicate resource
        → 409 Conflict

Invalid business input
        → 400 Bad Request

Invalid request schema
        → 422 Unprocessable Entity

Platform authentication unavailable
        → 503 Service Unavailable

Compliance Service unavailable
        → 503 Service Unavailable

Compliance Service returned an unsuccessful/unusable response
        → 502 Bad Gateway

Compliance decision = BLOCK / REVIEW
        → 409 Conflict
```

The Compliance Service integration is intentionally fail-closed.

If Compliance cannot be reached or does not return a usable successful decision, the Supplier Portal does not activate the supplier.

---

# 18. Configuration

The Supplier Portal uses Pydantic Settings for environment-based configuration.

Create a `.env` file in the project root when local configuration needs to be changed.

Example:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8000
```

The Platform authentication service and Compliance Service URLs are configurable through environment variables.

---

## Platform Authentication Configuration

The Supplier Portal uses the Platform Service as its centralized authentication provider.

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The Supplier Portal sends token-verification requests to the configured Platform Service instead of decoding authentication tokens locally.

The authentication verification endpoint is:

```http
POST /api/v1/auth/verify
```

Authentication failures and Platform availability failures are handled centrally by the Supplier Portal authentication dependency.

---

## Compliance Service Configuration

Supplier activation depends on the Compliance Service.

```env
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8000
```

The Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

before allowing a supplier to move into the `active` state.

The Compliance request contains:

```text
supplier_id
supplier_name
country
```

and includes:

```http
X-Caller-Service: supplier-portal
```

The Compliance client uses a bounded timeout.

Current timeout:

```text
5 seconds
```

The integration is fail-closed:

```text
Compliance CLEAR
        ↓
Activation allowed

Compliance BLOCK
        ↓
Activation blocked

Compliance REVIEW
        ↓
Activation blocked

Compliance unavailable
        ↓
Activation blocked

Invalid / unusable Compliance response
        ↓
Activation blocked
```

---

## Three-Way Match Configuration

The three-way matching price tolerance is centrally configured in:

```text
app/core/config.py
```

Current configuration:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

This represents an inclusive price tolerance of:

```text
±5%
```

For a Purchase Order unit price of `100`:

```text
95  → Match
100 → Match
105 → Match
106 → Price discrepancy
```

The tolerance is used by the three-way matching service.

It is not used as a blanket invoice-creation rejection rule.

This allows valid price discrepancies to reach the matching layer and be flagged for human review.

---

## Supplier Contract Configuration

Supplier Contract Lifecycle Management uses configurable contract terms stored with each contract.

The contract model supports:

```text
Contract Number
Title
Description
Start Date
End Date
Payment Terms
Delivery Terms
Pricing Terms
Minimum Order Value
Renewal Notice Days
Auto-Renew
```

Contract statuses are:

```text
draft
active
renewed
expired
```

The current implementation stores the contract configuration in application memory.

`auto_renew` is currently stored as a contract configuration value.

It does not currently trigger an automatic background renewal process.

---

## Environment Template

The project provides:

```text
.env.example
```

The example configuration should contain the service dependencies:

```env
# Platform Service
PLATFORM_AUTH_URL=http://127.0.0.1:8005

# Compliance Service
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8000
```

To create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

The `.env` file should not be committed to source control when it contains sensitive or environment-specific configuration.

---

# 19. Installation

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

Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
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

The test environment uses:

```text
pytest==8.4.1
pytest-asyncio==1.2.0
```

`pytest==8.4.1` is used because the configured `pytest-asyncio` version requires a pytest version below 9.

`python-multipart` is required for multipart file-upload handling.

---

## Step 5 — Configure Environment

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

The local configuration should contain:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8000
```

The Platform Service must be available when running authenticated Supplier Portal endpoints.

The Compliance Service must be available when activating suppliers.

---

# 20. Running the Services

The Supplier Portal depends on two service-level integrations:

```text
Platform Service
      ↓
Authentication

Compliance Service
      ↓
Supplier Activation Compliance Check
```

Therefore, the dependent services run separately.

---

## Platform Service

Start the Platform Service on:

```text
http://127.0.0.1:8005
```

From the Platform Service directory:

```powershell
python -m uvicorn app.main:app --reload --port 8005
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

## Compliance Service

The Supplier Portal also integrates with the Compliance Service for supplier activation.

The configured local endpoint is:

```text
http://127.0.0.1:8000
```

The Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

before supplier activation.

The integration is performed by:

```text
app/services/compliance_client.py
```

The Compliance Service returns a decision such as:

```text
CLEAR
BLOCK
REVIEW
```

Only:

```text
CLEAR
```

allows activation.

`BLOCK` and `REVIEW` leave the supplier outside the `active` state.

If the Compliance Service is unreachable, times out, or returns an unusable response, activation is blocked.

---

## Supplier Portal Service

From the Supplier Portal project directory:

```powershell
python -m uvicorn app.main:app --reload --port 8001
```

The Supplier Portal runs at:

```text
http://127.0.0.1:8001
```

The root endpoint can be used to confirm that the service is running:

```http
GET /
```

---

## Three-Service Business Architecture

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
               ▼
┌─────────────────────────────┐
│      Supplier Portal        │
│                             │
│        Port 8001            │
│                             │
│ PO / Invoice / P2P          │
│ Statistics / Scorecard      │
│ Contracts / Onboarding      │
│ Disputes / Analytics        │
└──────────────┬──────────────┘
               │
               │ /api/v1/compliance/internal-check
               ▼
┌─────────────────────────────┐
│     Compliance Service      │
│                             │
│        Port 8000            │
│                             │
│ Supplier Compliance Check   │
└─────────────────────────────┘
```

---

## Authentication Flow

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
  │
  ├── Role Check
  │
  ├── Supplier Ownership Check
  │
  └── Business Rule Validation
```

---

## Supplier Activation Compliance Flow

```text
Supplier
   │
   ▼
Registration
   │
   ▼
Documents
   │
   ▼
Verification
   │
   ▼
Approval
   │
   ▼
Supplier Portal
   │
   │ POST /api/v1/compliance/internal-check
   ▼
Compliance Service
   │
   ├── CLEAR
   │      ↓
   │   Activate Supplier
   │
   ├── BLOCK
   │      ↓
   │   Activation Blocked
   │
   └── REVIEW
          ↓
       Activation Blocked
```

Compliance errors are handled explicitly:

```text
Compliance timeout / connection failure
        → 503

Compliance service error / unusable response
        → 502

Compliance decision BLOCK / REVIEW
        → 409
```

The activation operation is fail-closed so that a supplier cannot become active without a successful compliance clearance.

---

## Business-Logic Integration Design

The Supplier Portal keeps the external Compliance integration isolated in:

```text
app/services/compliance_client.py
```

The client is responsible for:

```text
Building Compliance request
        ↓
Sending HTTP request
        ↓
Applying timeout
        ↓
Validating response
        ↓
Returning CLEAR/BLOCK/REVIEW
        ↓
Mapping technical failures
```

The onboarding service is responsible for the business decision:

```text
CLEAR
   → Continue activation

BLOCK / REVIEW
   → Keep supplier non-active

Unavailable / invalid response
   → Fail closed
```

This separation keeps HTTP integration logic out of the core onboarding business rules.

---

# 21. Swagger Documentation

FastAPI automatically provides interactive API documentation for the Supplier Portal.

When the Supplier Portal is running on port `8001`, open Swagger UI at:

```text
http://127.0.0.1:8001/docs
```

Alternative ReDoc documentation:

```text
http://127.0.0.1:8001/redoc
```

---

## Swagger API Coverage

Swagger can be used to inspect and test supported Supplier Portal operations, including:

```text
Purchase Orders
PO acknowledgement
PO transitions
PO events
Bulk PO sending

Shipment processing
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
Supplier self-service analytics

Supplier contracts
Contract activation
Contract renewal
Contract expiry queries
Contract history

Three-way matching
Historical dispute-resolution suggestions
Payment approval
```

Protected endpoints require a valid bearer token.

The Supplier Portal delegates token verification to the Platform Service, so authenticated Swagger requests must use a token that the configured Platform Service can verify.

---

## Swagger Authentication Flow

```text
Swagger UI
     │
     │ Bearer Token
     ▼
Supplier Portal
     │
     │ Token verification
     ▼
Platform Service :8005
     │
     ▼
Authenticated Identity
     │
     ▼
Role / Supplier Scope Validation
     │
     ▼
Supplier Portal Endpoint
```

Supplier users are still subject to supplier-level ownership checks when using Swagger.

For example:

```text
SUP001 token
      │
      ▼
Request SUP001 resource
      │
      ▼
Allowed
```

while:

```text
SUP001 token
      │
      ▼
Request SUP002 resource
      │
      ▼
403 Forbidden
```

Swagger therefore exposes the same authorization and supplier-scoping rules as normal API clients.

---

# 22. Testing

The Supplier Portal uses **Pytest** for automated testing.

The test suite covers:

* Core business logic
* Purchase Order lifecycle
* P2P state transitions
* Shipment processing
* Goods Receipt processing
* Partial Goods Receipt support
* Invoice lifecycle
* P2P invoice integration
* Three-way matching
* Quantity discrepancy detection
* Price discrepancy detection
* Supplier onboarding
* Compliance Service integration
* Compliance failure handling
* Supplier onboarding document validation
* Supplier statistics and scorecards
* Supplier self-service scorecard access
* Supplier contract lifecycle
* Contract renewal and expiry handling
* Contract term-change audit history
* Historical dispute-resolution suggestions
* Authentication
* Role-based authorization
* Supplier-level resource ownership
* Collection-level supplier filtering
* Invoice document security
* Authentication-required endpoint protection
* Round 5 supplier-scoping requirements
* Rounds 6–8 functional milestones
* Rounds 9–11 functional requirements

Run the complete test suite with:

```powershell
python -m pytest -v
```

The test suite uses `python -m pytest` so that tests execute using the active Python environment.

The project uses:

```text
pytest==8.4.1
```

This version is compatible with the configured `pytest-asyncio` dependency.

---

## Purchase Order Tests

Run:

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
* Actual delivery date from Goods Receipt
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
* Supplier ownership is validated using authenticated `supplier_id`

---

## Invoice Tests

Run:

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

## Supplier Onboarding Tests

The onboarding workflow tests validate:

* Supplier registration
* Document collection
* Mock verification
* Approval
* Compliance Service check
* Compliance CLEAR decision
* Compliance BLOCK decision
* Compliance REVIEW decision
* Compliance Service unavailable
* Compliance timeout
* Compliance service error
* Invalid Compliance response
* Fail-closed activation
* Approval preservation when activation is blocked
* Activation only after Compliance CLEAR
* Valid onboarding state transitions
* Invalid onboarding transitions
* Supplier-level authorization
* Cross-supplier access protection
* Active-supplier enforcement for Purchase Order creation
* Supported onboarding document types
* Empty document rejection
* File-extension validation
* MIME-type validation
* 10 MB document-size limit

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
Compliance CLEAR
      ↓
active
```

A `BLOCK` or `REVIEW` decision does not activate the supplier.

A Compliance Service failure also does not activate the supplier.

---

## Compliance Integration Tests

The Compliance integration has dedicated coverage for both successful and failure paths.

The tests validate:

```text
Compliance CLEAR
        → Activation allowed

Compliance BLOCK
        → Activation blocked

Compliance REVIEW
        → Activation blocked

Compliance timeout
        → 503

Compliance connection failure
        → 503

Compliance service error
        → 502

Invalid Compliance JSON
        → Activation blocked

Invalid decision
        → Activation blocked
```

The tests also verify that the Compliance request contains:

```text
supplier_id
supplier_name
country
```

and:

```http
X-Caller-Service: supplier-portal
```

The activation ordering is tested so that:

```text
Compliance Check
        ↓
Activation
```

occurs in that order.

Failed Compliance checks do not create an active onboarding state/history entry.

---

## Three-Way Match Tests

The three-way matching tests validate successful matching and discrepancy scenarios.

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

The matching implementation uses:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

The tolerance is inclusive.

---

## Historical Dispute-Resolution Suggestion Tests

Historical dispute-resolution suggestions are tested independently from current dispute resolution.

The tests validate:

* Historical resolved matches are considered
* Current unresolved disputes are not treated as historical evidence
* Unresolved historical disputes are ignored
* Price mismatch patterns can produce `correct_invoice`
* Quantity mismatch patterns can produce `credit_note`
* Unclassified historical reasons are ignored
* No-evidence cases return no suggested action
* Current resolved/matched cases cannot be treated as unresolved suggestions
* Unknown matches return `404`
* Supplier scope is enforced
* Compliance-officer authorization is enforced
* Suggestions are read-only
* Suggestion generation does not mutate three-way-match state

The endpoint is:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

The feature is advisory only:

```text
Historical Disputes
        ↓
Pattern Analysis
        ↓
Suggested Action
        ↓
Human Decision
```

The Supplier Portal does not automatically change the invoice or three-way-match state based on the suggestion.

---

## Supplier Statistics and Scorecard Tests

Run:

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
* Actual delivery date from Goods Receipt
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
* Supplier self-service scorecard access

For fulfilled Purchase Orders, the actual delivery date is derived from the latest applicable Goods Receipt `receipt_date`.

Therefore:

```text
Goods Receipt receipt_date
          ↓
Actual delivery date
          ↓
On-time / late calculation
```

The on-time calculation uses:

```text
actual_delivery_date <= expected_delivery
```

---

## Supplier Contract Tests

The Supplier Contract Lifecycle is covered by dedicated tests.

The tests validate:

* Contract creation
* Contract retrieval
* Contract listing
* Duplicate contract-number protection
* Active-supplier validation
* Contract date validation
* Draft-to-active transition
* Contract updates
* Expiry detection
* Expiring-contract queries
* Renewal
* Renewal date validation
* Renewal history
* Contract transition history
* Term-change audit history
* Actor information in history
* Reason information in history
* No-op update without unnecessary history entry
* Supplier ownership and scoping
* Procurement-manager authorization

The lifecycle is:

```text
draft
   ↓
active
   ↓
renewed
   ↓
active
```

Expired contracts are represented as:

```text
expired
```

Contract history records state changes and meaningful term changes.

---

## Supplier Self-Service Analytics Tests

Supplier self-service analytics is tested through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The tests validate that:

* Supplier can view its own scorecard
* Supplier cannot view another supplier's scorecard
* Supplier identity is matched against authenticated `supplier_id`
* Supplier without `supplier_id` is rejected
* Scorecard contains on-time delivery percentage
* Scorecard contains dispute rate percentage
* Scorecard contains invoice accuracy
* Scorecard contains overall performance information
* Internal authorized roles can access supplier data according to their role permissions

Example supplier-scoped behavior:

```text
SUP001 token
      ↓
GET /api/v1/suppliers/SUP001/scorecard
      ↓
200 Allowed
```

while:

```text
SUP001 token
      ↓
GET /api/v1/suppliers/SUP002/scorecard
      ↓
403 Forbidden
```

---

## Authentication and Authorization Tests

Run:

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
* Missing `user_id`
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

---

## Authentication-Required Endpoint Tests

The project includes:

```text
tests/test_requires_auth.py
```

This module verifies that protected endpoints cannot be accessed without authentication.

The test removes the authentication dependency override used by the normal test suite and executes the real authentication dependency.

Protected routes are discovered automatically from the Supplier Portal API routers rather than maintaining a hardcoded endpoint list.

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

---

## R5 Supplier-Scoping Validation

Round 5 specifically validates that authentication alone does not provide unrestricted supplier access.

The core security rule is:

```text
A valid supplier token does not provide unrestricted supplier access.

The authenticated supplier must own the requested supplier-scoped resource.
```

The R5 test suite validates supplier ownership across supported supplier-facing resources, including:

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
Supplier Contract Resources
Supplier Contract History
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
| Supplier → Own contract                            | Allowed                   |
| Supplier → Other supplier contract                 | `403 Forbidden`           |
| Supplier → Own contract history                    | Allowed                   |
| Supplier → Other supplier contract history         | `403 Forbidden`           |
| Supplier without `supplier_id` → Supplier resource | `403 Forbidden`           |
| Internal authorized role → Other supplier data     | Allowed according to role |

---

## R9–11 Test Coverage Summary

The R9–11 implementation adds dedicated validation for:

```text
Compliance Integration
        +
Compliance Failure Handling
        +
Supplier Contract Lifecycle
        +
Contract Renewal / Expiry
        +
Contract Term Audit History
        +
Historical Dispute Suggestions
        +
Supplier Self-Service Analytics
```

The test strategy verifies both successful business paths and failure/security paths.

---

# 23. Business Rules

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

Purchase Order creation requires:

```text
procurement_manager
```

and the referenced supplier must be:

```text
registered
+
active
```

---

## Invoice Rules

Invoices require an existing PO.

The legacy invoice service accepts POs in applicable invoice-processing states:

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

Rejected invoices do not consume the Purchase Order's available invoice quantity.

Invoice creation does not reject price differences solely because they exceed the three-way-match tolerance.

Price discrepancies are evaluated by the three-way matching process.

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

Shipment processing requires:

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

### Three-Way Match Rule

The match compares:

```text
Purchase Order
+
Goods Receipt
+
Invoice
```

The configured price tolerance is:

```text
PRICE_TOLERANCE_PERCENT = 5.0
```

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
Compliance Check
      ↓
active
```

The workflow validates the current state before progressing.

A supplier cannot skip required onboarding stages.

Mock verification is used in the current development implementation.

### Supplier Activation Compliance Rule

Before activation, the Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

The request includes:

```text
supplier_id
supplier_name
country
```

with:

```http
X-Caller-Service: supplier-portal
```

Only:

```text
CLEAR
```

allows activation.

The following decisions prevent activation:

```text
BLOCK
REVIEW
```

Technical failures also prevent activation:

```text
Timeout
Connection failure
Network failure
Invalid JSON
Invalid decision
Unusable Compliance response
```

The integration therefore follows:

```text
Compliance Success + CLEAR
        → Activate

Compliance BLOCK / REVIEW
        → Keep supplier non-active

Compliance unavailable / unusable
        → Fail closed
```

### Supplier Onboarding Document Rules

Supported document types are:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

Maximum document size:

```text
10 MB
```

---

## Supplier Contract Rules

Supplier contracts support:

```text
draft
active
renewed
expired
```

The valid state transitions are:

```text
draft → active

active → renewed

renewed → active
```

Expired contracts are terminal until a renewal operation explicitly updates the contract.

Contract creation requires an active supplier.

Contract numbers must be unique.

Contract dates must satisfy:

```text
end_date > start_date
```

Expired contracts cannot be modified through normal term updates.

Renewal requires valid new dates and records the renewal reason.

---

## Supplier Contract Term Audit Rule

Meaningful contract term changes create an audit-history entry.

Audited changes include changed contract fields such as:

```text
Title
Description
End Date
Payment Terms
Delivery Terms
Pricing Terms
Minimum Order Value
Renewal Notice Days
Auto Renew
```

The history records information including:

```text
contract_id
supplier_id
from_status
to_status
actor_id
actor_name
role
reason
timestamp
```

A no-op update where no contract value changes does not create an unnecessary term-change history entry.

This provides traceability for meaningful contract changes.

---

## Supplier Contract Expiry Rule

A contract is considered expired when its effective end date has passed.

The service also calculates:

```text
days_until_expiry
```

and:

```text
expiring_soon
```

using the configured renewal-notice period.

The expiring-contract endpoint allows authorized users to identify contracts approaching their renewal/expiry window.

---

## Historical Dispute-Resolution Suggestion Rules

Historical dispute suggestions are advisory only.

The service analyzes historical three-way-match resolution information.

The implementation can identify patterns such as:

```text
Price mismatch
      →
correct_invoice

Quantity mismatch
      →
credit_note
```

Cases without sufficient evidence do not receive an automatic action.

The current unresolved dispute is not treated as its own historical evidence.

The service does not automatically:

```text
modify invoice
modify match
approve payment
resolve dispute
```

Instead:

```text
Historical Data
      ↓
Pattern Analysis
      ↓
Suggested Action
      ↓
Human Decision
```

The endpoint requires the appropriate authorization and supplier scope.

---

## Supplier Self-Service Analytics Rules

Supplier users can access their own scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The authenticated supplier must satisfy:

```text
token supplier_id
        =
requested supplier_id
```

Otherwise:

```text
403 Forbidden
```

The scorecard exposes implemented metrics including:

```text
On-time delivery percentage
Dispute rate percentage
Invoice accuracy
Invoice cycle-time information
Overall score
Performance breakdown
Trend information
```

The endpoint is self-service, but remains protected by the same supplier-scoping rules as other supplier-facing resources.

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

For fulfilled Purchase Orders, the actual delivery date is based on the latest applicable Goods Receipt `receipt_date`.

```text
Goods Receipt
     ↓
receipt_date
     ↓
actual_delivery_date
     ↓
On-time / late calculation
```

An on-time delivery satisfies:

```text
actual_delivery_date <= expected_delivery
```

The on-time percentage is:

```text
on-time eligible POs
--------------------- × 100
eligible delivery POs
```

---

## Invoice Dispute Rate

```text
disputed invoices
------------------ × 100
total invoices
```

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

---

## Invoice Cycle-Time and Trend Rules

Invoice cycle-time calculations identify the related Purchase Order from invoice line items:

```text
invoice.items[].po_number
```

This supports invoices whose PO relationship is stored at line-item level.

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

# 24. Security Controls

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
* Compliance-officer authorization for historical dispute suggestions
* Procurement-manager authorization for PO creation
* Procurement-manager authorization for PO transitions
* Procurement-manager authorization for bulk PO sending
* Procurement-manager authorization for contract management
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
* Supplier contracts
* Supplier contract history

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

## Compliance Integration Security

The Compliance integration includes:

* Dedicated internal service client
* `X-Caller-Service` identification
* Bounded HTTP timeout
* Response validation
* Explicit decision validation
* Fail-closed activation behavior
* Supplier activation blocked when Compliance is unavailable
* Supplier activation blocked for `BLOCK`
* Supplier activation blocked for `REVIEW`

The Supplier Portal does not treat an unavailable Compliance Service as a successful compliance result.

---

## Input Validation

The service validates:

* PO number format
* Supplier ID format
* Invoice number format
* Positive quantities
* Positive unit prices
* Positive invoice amounts
* Percentage boundaries
* Item validation
* Receipt quantity validation
* Duplicate item validation
* Onboarding document type
* Onboarding document extension
* Onboarding document size
* Empty uploaded documents
* Contract dates
* Contract number uniqueness
* Contract renewal dates

Allowed identifier format:

```regex
^[A-Za-z0-9_-]+$
```

---

## Document Security

### Invoice Documents

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

### Supplier Onboarding Documents

Supplier onboarding documents are protected through:

* Supported MIME-type validation
* File-extension validation
* 10 MB size limit
* Empty-file validation
* Supplier ownership validation
* Supplier-specific storage paths

Supported onboarding document types:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

---

## Contract Audit Security

Contract history records are protected by supplier scope and role authorization.

A supplier can access only its own contract history.

Internal users can access contract information according to their assigned permissions.

Contract history captures the actor and reason for meaningful lifecycle and term changes, supporting accountability for contract modifications.

---

# 25. Storage

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

Supplier contracts:

```python
supplier_contracts = {}
```

Supplier contract history:

```python
supplier_contract_history = {}
```

Other workflow and supplier business data is also maintained in application memory.

Invoice documents and supplier onboarding documents are stored locally under:

```text
uploads/
```

---

## Application Restart Behaviour

Because business data is stored in memory:

```text
Application running
      ↓
PO / Invoice / Workflow / Contract data exists
      ↓
Application restart
      ↓
In-memory business data cleared
```

Files stored under `uploads/` are filesystem-based and are not automatically removed by an application restart.

A production deployment should replace in-memory business storage with persistent storage.

---

## File Storage

The current development implementation stores uploaded documents under the local upload directory.

The application currently manages:

```text
Invoice PDF documents
Supplier onboarding documents
```

Production deployments should replace local filesystem storage with durable document or object storage.

---

## Contract Storage

Supplier contracts and their history are currently stored in application memory.

The current implementation therefore provides:

```text
Contract lifecycle tracking
Contract expiry calculation
Contract renewal
Contract history
Term-change audit
```

but does not provide durable contract persistence across application restarts.

A production implementation should persist:

```text
Contracts
Contract versions
Contract history
Renewal records
Audit records
```

in durable storage.

---

# 26. End-to-End Workflow

The Supplier Portal implements the procure-to-pay workflow:

```text
Create Purchase Order
        ↓
      Draft
        ↓
       Sent
        ↓
Supplier Acknowledgement
        ↓
  Acknowledged
        ↓
     Shipped
        ↓
 Goods Receipt
        ↓
     Received
        ↓
   Submit Invoice
        ↓
     Invoiced
        ↓
 Three-Way Match
        ↓
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
   ↓
Discrepancy
   ↓
Human Review
```

Historical dispute suggestions can support the human-review stage:

```text
Historical Dispute Data
        ↓
Pattern Analysis
        ↓
Resolution Suggestion
        ↓
Human Review / Decision
```

---

## Supplier Onboarding Workflow

Supplier onboarding is implemented as:

```text
Supplier Registration
          ↓
Document Collection
          ↓
Mock Verification
          ↓
Approval
          ↓
Compliance Check
          ↓
CLEAR
          ↓
Active Supplier
```

If Compliance returns:

```text
BLOCK
```

or:

```text
REVIEW
```

the supplier does not become active.

If the Compliance Service is unavailable:

```text
Activation blocked
```

This ensures the Supplier Portal does not bypass the required Compliance business-logic integration.

---

## Supplier Contract Workflow

Supplier contracts follow a separate lifecycle:

```text
Create Contract
      ↓
    Draft
      ↓
   Activate
      ↓
    Active
      │
      ├───────────────┐
      │               │
      ▼               ▼
   Renew          Expiry
      │               │
      ▼               ▼
  Renewed          Expired
      │
      ▼
    Active
```

Contract updates create audit history when meaningful terms change.

Renewals record:

```text
Previous End Date
New Start Date
New End Date
Renewal Reason
Renewed By
Renewed At
```

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
      │
      ▼
Supplier Self-Service
```

For fulfilled Purchase Orders, delivery performance uses Goods Receipt dates to determine the actual delivery date.

Supplier users can view their own scorecard while remaining restricted from other suppliers' scorecards.

---

## Complete Business Architecture

The overall business flow can be represented as:

```text
                         SUPPLIER PORTAL
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   Procurement           Onboarding            Analytics
        │                     │                     │
        ▼                     ▼                     ▼
 Purchase Order         Registration          Statistics
        │                     │                     │
        ▼                     ▼                     ▼
 Acknowledgement        Documents             Scorecard
        │                     │                     │
        ▼                     ▼                     ▼
     Shipment           Verification       Self-Service
        │                     │
        ▼                     ▼
 Goods Receipt           Approval
        │                     │
        ▼                     ▼
      Invoice        Compliance Check
        │                     │
        ▼                     ▼
 Three-Way Match            Active
        │
    ┌───┴────┐
    ▼        ▼
 Matched  Discrepancy
    │        │
    ▼        ▼
 Payment   Human Review
 Approval     │
              ▼
       Resolution Suggestion
```

Additional contract management operates alongside the core P2P workflow:

```text
Supplier
   ↓
Contract
   ↓
Terms
   ↓
Expiry / Renewal
   ↓
Contract History / Audit
```

R5 authentication and supplier-level authorization apply throughout supplier-facing operations.

---

# 27. Current Implementation Status

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
| Supplier Onboarding Document Validation     | Complete |
| Supplier Mock Verification                  | Complete |
| Supplier Onboarding Approval                | Complete |
| Compliance Service Activation Check         | Complete |
| Compliance CLEAR/BLOCK/REVIEW Handling      | Complete |
| Compliance Failure Handling                 | Complete |
| Fail-Closed Supplier Activation             | Complete |
| Active Supplier Enforcement for PO Creation | Complete |
| Supplier Performance Analytics              | Complete |
| Invoice Cycle-Time Metrics                  | Complete |
| Supplier Trend Metrics                      | Complete |
| Supplier Self-Service Scorecard             | Complete |
| Supplier Contract Lifecycle                 | Complete |
| Contract Expiry Tracking                    | Complete |
| Contract Renewal                            | Complete |
| Contract Term-Change Audit History          | Complete |
| Historical Dispute-Resolution Suggestions   | Complete |
| Deep Supplier-Scoping Validation            | Complete |
| Cross-Supplier Endpoint Testing             | Complete |
| P2P Business-Rule Testing                   | Complete |
| Three-Way Match Discrepancy Testing         | Complete |
| Supplier Onboarding Workflow Testing        | Complete |
| Compliance Integration Testing              | Complete |
| Contract Lifecycle Testing                  | Complete |
| Dispute Suggestion Testing                  | Complete |
| Self-Service Scorecard Testing              | Complete |
| Authentication-Required Endpoint Testing    | Complete |

---

## R5 Completion Status

Round 5 supplier authentication, role authorization, and supplier-level data-scoping requirements have been implemented and covered by automated tests.

The implemented security model ensures:

```text
Valid supplier token

      ≠

Unrestricted supplier access
```

Instead, access follows:

```text
Valid Token
     ↓
Platform Service Verification
     ↓
Authenticated Identity
     ↓
Role Check
     ↓
supplier_id Ownership Check
     ↓
Resource Access
```

For supplier users, the authenticated `supplier_id` must match the supplier associated with the requested supplier-scoped resource.

Cross-supplier access attempts are rejected with:

```text
403 Forbidden
```

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

using the configured inclusive 5% price tolerance.

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

Purchase Order creation verifies that the referenced supplier exists and has reached the `active` onboarding state.

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

For fulfilled Purchase Orders, actual delivery is derived from applicable Goods Receipt dates.

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

---

# Rounds 9–11 Completion Status

The Rounds 9–11 implementation extends the Supplier Portal with business-logic integration, contract lifecycle management, dispute intelligence, and supplier self-service analytics.

## Task 1 — Compliance Business-Logic Integration

Status:

```text
Complete
```

The Supplier Portal integrates with the Compliance Service before supplier activation.

Integration endpoint:

```http
POST /api/v1/compliance/internal-check
```

The Supplier Portal sends:

```text
supplier_id
supplier_name
country
```

with:

```http
X-Caller-Service: supplier-portal
```

The Compliance decision is:

```text
CLEAR
BLOCK
REVIEW
```

Only `CLEAR` permits activation.

---

## Task 2 — Compliance Failure Handling

Status:

```text
Complete
```

The integration explicitly handles:

```text
Timeout
Connection Failure
Network Failure
HTTP Service Error
Invalid JSON
Invalid Decision
Unusable Response
```

The behavior is fail-closed:

```text
Compliance unavailable
        ↓
Supplier activation blocked
```

This prevents a technical dependency failure from being interpreted as successful compliance.

---

## Task 3 — Supplier Contract Lifecycle Management

Status:

```text
Complete
```

Implemented capabilities include:

```text
Contract creation
Contract retrieval
Contract listing
Contract updates
Contract activation
Contract renewal
Contract expiry tracking
Expiring-contract queries
Contract history
Term-change audit history
```

Contract states include:

```text
draft
active
renewed
expired
```

---

## Task 4 — Historical Dispute-Resolution Suggestions

Status:

```text
Complete
```

The Supplier Portal analyzes historical dispute-resolution patterns and produces advisory suggestions.

Examples include:

```text
Price mismatch
      →
correct_invoice

Quantity mismatch
      →
credit_note
```

Suggestions are advisory only and do not automatically modify business state.

---

## Task 5 — Supplier Self-Service Analytics

Status:

```text
Complete
```

Supplier users can access their own scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The endpoint remains protected by supplier ownership validation.

---

## Task 6 — Full R9–11 Test Coverage

Status:

```text
Complete
```

Coverage includes:

```text
Compliance CLEAR
Compliance BLOCK
Compliance REVIEW
Compliance unavailable
Compliance timeout
Compliance service error
Invalid Compliance response
Fail-closed activation

Contract creation
Contract update
Contract renewal
Contract expiry
Contract history
Term-change audit

Historical dispute pattern analysis
Resolution suggestions
Suggestion authorization
Suggestion supplier scoping

Supplier self-service scorecard
Cross-supplier scorecard rejection
```

---

## R9–11 Milestone Summary

```text
Task 1 → Compliance Business-Logic Integration
Task 2 → Compliance Failure Handling
Task 3 → Supplier Contract Lifecycle
Task 4 → Historical Dispute Suggestions
Task 5 → Supplier Self-Service Analytics
Task 6 → Full Test Coverage
```

All planned R9–11 functional requirements are implemented.

---

# 28. Known Limitations

The current implementation is primarily designed for development, functional validation, and automated testing.

The core R5 authentication, role-based authorization, and supplier-level data-scoping requirements are implemented.

Rounds 6–8 and Rounds 9–11 functional requirements are also implemented.

Remaining limitations are primarily related to:

```text
Production Persistence
Durable File Storage
Automatic Contract Renewal
Partial-Invoice Lifecycle Expansion
Production Operational Hardening
External Supplier Verification
Payment-Service Integration
```

---

## Partial Invoice Lifecycle

The current P2P state machine supports:

```text
received → invoiced
```

and supports partial invoice validation at the invoice-service level.

However, the current P2P state model represents the PO at a single `invoiced` state.

Therefore, repeated partial invoicing against the same Purchase Order requires additional lifecycle support.

Future enhancement:

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

---

## In-Memory Business Storage

Purchase Orders, invoices, workflow data, supplier onboarding data, contract data, dispute data, and related business events are currently maintained in Python in-memory data structures.

As a result, application restarts clear business data.

```text
Application Restart
       ↓
In-Memory Data Cleared
       ↓
Purchase Orders / Invoices / Contracts / Events Lost
```

A production deployment should use persistent database storage.

---

## Local File Storage

Invoice PDF documents and supplier onboarding documents are currently stored locally under:

```text
uploads/
```

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

If the Platform Service is unavailable or authentication verification times out, protected endpoints can return:

```text
503 Service Unavailable
```

This dependency is intentional because the Platform Service is the centralized authentication provider.

---

## Compliance Service Dependency

Supplier activation depends on the Compliance Service.

If the Compliance Service is unavailable:

```text
Supplier activation is blocked
```

The current implementation intentionally fails closed.

Production deployments should provide:

* Compliance Service availability monitoring
* Timeout monitoring
* Dependency health monitoring
* Alerting
* Operational recovery mechanisms

The fail-closed business rule should remain in place unless the compliance architecture is formally changed.

---

## Automatic Contract Renewal

The contract model supports:

```text
auto_renew
```

as a stored configuration value.

However, the current implementation does not include:

```text
Background scheduler
Automatic renewal worker
Automatic contract-version generation
Automatic renewal execution
```

Therefore, renewal currently requires an explicit renewal operation.

---

## Contract Versioning

Contract renewal currently updates the existing contract record and records renewal history.

A future implementation may introduce explicit immutable contract versions:

```text
Contract
   ↓
Version 1
   ↓
Version 2
   ↓
Version 3
```

This would provide stronger historical reconstruction of every contract version.

---

## Historical Dispute Suggestions

The current dispute-resolution suggestion feature is advisory.

It does not automatically:

```text
Resolve disputes
Adjust invoices
Create credit notes
Approve payments
Change match status
```

The suggestion is intended to support human review.

Future versions may improve the pattern engine using richer historical data and more detailed resolution classifications.

---

## Administrative and Maintenance Endpoint Hardening

Core supplier-facing authentication, role-based authorization, and supplier-level data scoping are implemented.

Maintenance operations remain separate from normal supplier-facing business operations.

The maintenance endpoints are:

```text
GET    /api/v1/maintenance/orphaned-invoice-files

DELETE /api/v1/maintenance/orphaned-invoice-files
```

These endpoints remain restricted to the designated administrative authorization implemented by the service and must not be exposed to anonymous callers.

---

## Production Persistence

A production implementation should introduce:

* Persistent database storage
* Transaction management
* Database-backed Purchase Order records
* Database-backed invoice records
* Persistent event and audit history
* Durable supplier records
* Durable contract records
* Durable contract history
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
* Platform authentication availability monitoring
* Compliance Service availability monitoring

These are production-readiness considerations rather than failures of the implemented milestones.

---

## Onboarding Document Validation Status

Supplier onboarding document validation is implemented.

The current implementation validates:

```text
Supported MIME type
File extension
Empty file
Maximum file size
Supplier ownership
```

Supported types:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

Maximum size:

```text
10 MB
```

Future production hardening may still include:

* Malware scanning
* Durable document storage
* Document retention policies
* Stronger external verification integrations

---

## End-to-End Test Expansion

The test suite covers individual P2P services, state transitions, validation rules, authorization behavior, discrepancy scenarios, Compliance failure paths, contract lifecycle behavior, dispute suggestions, and self-service analytics.

A future enhancement would add one comprehensive HTTP integration test that drives:

```text
Supplier Onboarding
→ Compliance CLEAR
→ Active Supplier
→ Create PO
→ Send
→ Acknowledge
→ Shipment
→ Goods Receipt
→ Invoice
→ Three-Way Match
→ Payment Approval
```

This would complement the existing focused service and API tests.

---

## Configuration and Maintainability Status

The three-way match price tolerance is already centralized in:

```text
app/core/config.py
```

using:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

The Compliance Service URL is also environment-configured through:

```text
COMPLIANCE_SERVICE_URL
```

Other business constants may still be centralized further in future iterations, including:

```text
Scorecard weights
Upload limits
Contract defaults
Workflow configuration
```

---

## R5 Security Status

The implemented R5 security model is:

```text
Platform Service Authentication
            ↓
Role-Based Authorization
            ↓
Supplier Ownership Validation
            ↓
Collection-Level Supplier Filtering
            ↓
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

---

## Current Remaining Limitations Summary

The remaining limitations are primarily:

```text
Production Persistence
Durable File Storage
Partial-Invoice Lifecycle Expansion
Automatic Contract Renewal
Explicit Contract Versioning
External Supplier Verification
Payment-Service Integration
Production Operational Hardening
Expanded End-to-End Integration Testing
Advanced Dispute Intelligence
```

These limitations are documented separately from the completed R5, R6–8, and R9–11 functionality.

---

# 29. Future Enhancements

The following enhancements are outside the currently completed R5, R6–8, and R9–11 scope.

## Persistent Database Storage

Replace in-memory business stores with a production database.

Potential future persisted entities:

```text
Purchase Orders
Invoices
PO Events
P2P State
Supplier Onboarding
Goods Receipts
Shipments
Scorecards
Contracts
Contract History
Audit History
```

---

## Durable Document Storage

Replace local:

```text
uploads/
```

storage with durable object or document storage.

Future capabilities may include:

* Object storage
* Encryption at rest
* Access policies
* Retention policies
* Backup and recovery
* Document versioning

---

## Complete Multi-Invoice P2P Lifecycle

Extend the P2P state model to support repeated partial invoicing.

Example:

```text
PO quantity = 10

Invoice 1 = 5
      ↓
Remaining = 5
      ↓
Invoice 2 = 5
      ↓
Fully invoiced
```

The future state model should distinguish between partially invoiced and fully invoiced quantities.

---

## Automatic Contract Renewal

Extend the existing `auto_renew` configuration into an actual automated renewal mechanism.

Potential future architecture:

```text
Contract
   ↓
Renewal Notice Window
   ↓
Scheduler / Worker
   ↓
Renewal Eligibility Check
   ↓
Automatic or Approval-Based Renewal
   ↓
New Contract Version
   ↓
Audit History
```

---

## Explicit Contract Versioning

Introduce immutable contract versions so that historical terms can be reconstructed.

Example:

```text
Contract
   ↓
Version 1
   ↓
Version 2
   ↓
Version 3
```

Each version could retain:

```text
Terms
Start Date
End Date
Created By
Created At
Change Reason
```

---

## Production Supplier Verification

Replace mock verification with an actual supplier verification integration.

Potential future flow:

```text
Supplier Registration
        ↓
Document Collection
        ↓
External Verification
        ↓
Verification Result
        ↓
Compliance Check
        ↓
Approval
        ↓
Active
```

The existing Compliance Service integration should remain a separate business-logic check.

---

## Document Security Enhancements

Future production document security may include:

* Malware scanning
* Content inspection
* Stronger file-type verification
* Document retention policies
* Document versioning
* Secure object-storage integration

---

## Payment Service Integration

The current payment approval workflow is represented within the Supplier Portal P2P state model.

A future implementation could integrate payment approval with a dedicated payment or finance service:

```text
Three-Way Match
       ↓
Payment Approval
       ↓
Finance / Payment Service
       ↓
Payment Execution
```

---

## Event-Driven P2P Processing

A future implementation could publish business events for major P2P transitions:

```text
PO Acknowledged
Shipment Created
Goods Received
Invoice Submitted
Three-Way Match Completed
Payment Approved
```

These events could be consumed by other supply-chain services.

---

## Advanced Supplier Analytics

Future analytics may include:

* Supplier trend dashboards
* Delivery-risk indicators
* Invoice anomaly detection
* Supplier benchmarking
* Historical scorecard trends
* Predictive supplier performance analytics

These would extend the current operational statistics, scorecard, and supplier self-service implementation.

---

## Advanced Dispute Intelligence

The current historical dispute-resolution feature is advisory and rule/pattern based.

Future enhancements may include:

* More detailed historical classifications
* Larger historical datasets
* Confidence indicators
* Explainable recommendation evidence
* More resolution-action categories
* Human feedback capture
* Resolution effectiveness tracking

The future system should continue to keep final dispute decisions under authorized human control unless business requirements explicitly introduce automated resolution.

---

## Expanded Integration Testing

A future enhancement would introduce a complete end-to-end integration test that drives:

```text
Supplier Registration
        ↓
Documents
        ↓
Verification
        ↓
Compliance CLEAR
        ↓
Active Supplier
        ↓
Create PO
        ↓
Send PO
        ↓
Supplier Acknowledgement
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

This would complement the existing focused service and API tests.

---

## Production Observability

Future production deployment should introduce:

* Centralized logging
* Metrics
* Distributed tracing
* Health checks
* Readiness checks
* Platform authentication dependency monitoring
* Compliance dependency monitoring
* P2P workflow monitoring
* Contract expiry monitoring
* Alerting

---

## Advanced Authorization

Future authorization enhancements may include:

```text
Fine-Grained Permissions
        ↓
Segregation of Duties
        ↓
Workflow-Specific Permissions
        ↓
Audit Controls
```

This can provide more granular separation between:

```text
Procurement
Invoice Management
Compliance
Three-Way Matching
Payment Approval
Contract Management
```

---

## Audit and Compliance Enhancements

Future versions may provide persistent audit history for:

* PO transitions
* Supplier onboarding transitions
* Compliance decisions
* Invoice transitions
* Goods Receipt creation
* Shipment events
* Three-way match decisions
* Payment approvals
* Contract term changes
* Contract renewals
* Administrative maintenance operations

The existing event and authorization concepts can be extended into a durable audit subsystem.

---

## Summary of Future Scope

The current implementation completes the defined R5, R6–8, and R9–11 functional requirements.

Future work primarily focuses on:

```text
Production Persistence
Durable Document Storage
Complete Multi-Invoice Lifecycle
Automatic Contract Renewal
Explicit Contract Versioning
External Supplier Verification
Payment-Service Integration
Event-Driven Processing
Advanced Analytics
Advanced Dispute Intelligence
Expanded Integration Testing
Production Observability
Advanced Authorization
Persistent Audit Controls
```

These enhancements build on the implemented Supplier Portal rather than replacing the existing authentication, supplier-scoping, P2P, Compliance, contract, dispute-suggestion, or self-service analytics functionality.
