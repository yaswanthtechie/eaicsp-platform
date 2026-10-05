# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for managing supplier-facing Purchase Orders, invoices, invoice documents, supplier operational statistics, supplier performance scorecards, supplier onboarding, supplier contract lifecycle management, dispute-resolution suggestions, supplier self-service analytics, and the procure-to-pay workflow.

The Supplier Portal Service is part of the **Enterprise AI Cognitive Supply Chain Platform** and integrates with the Platform Service for authentication and role-based authorization.

The portal also exposes a **Strawberry GraphQL API** for Purchase Orders, invoices, and supplier documents, intended for consumption by the supplier portal frontend through Apollo Client.

Invoice PDFs and supplier onboarding documents are stored in **MinIO**, an S3-compatible object-storage service. Document downloads use short-lived **presigned URLs** after supplier ownership authorization.

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
## Round 12–13 Status

- Milestone 1: done in #152 (supersedes #128)
- Milestone 2: MinIO storage + supplier-scoped presigned URLs: done
- Milestone 3: GraphQL queries, cursor pagination, acknowledge mutation: done
- Not done / known gaps: cursors are list indexes over in-memory data (they shift if records are added); business data is still in-memory.

## Running Locally

```bash
cp .env.example .env
# then set real MinIO credentials

docker compose -f docker-compose.dev.yml up -d --build
# starts MinIO on :9000 (console :9001)

python -m pytest -m "not integration" -q
# unit tests, no Docker needed

python -mpytest -m integration -q
# needs MinIO running
```
## How I Wired MinIO with Docker in r(12,13)

MinIO is used as the S3-compatible object storage for supplier onboarding documents and invoice PDFs, running locally in the existing supplier-portal-minio Docker container.

Before running MinIO-dependent tests, ensure Docker Desktop is running, then verify Docker with docker info and check the MinIO container with docker ps -a.

If supplier-portal-minio is stopped, start it with docker start supplier-portal-minio and verify that docker ps shows the container as Up with ports 9000-9001.

Keep Docker Desktop and MinIO running for the complete test suite and run python -m pytest -q from services/supplier-portal; tests that do not access MinIO can run without Docker.

## How I Wired Business-Logic Integration (Supplier Portal to Compliance)

Read this if you are wiring one service's business decision into another's workflow.

It assumes zero context.

Quick commands
---------------------------------------------------------
docker info
docker ps -a
docker start supplier-portal-minio
docker ps
python -m pytest -q

### 1. What it does, in one sentence

Before a supplier moves `approved -> active`, Supplier Portal asks the Compliance Service whether the supplier is cleared, and only activates on a clean `CLEAR`.

### 2. Where the code is

| File | What it does |
| --- | --- |
| `app/services/compliance_client.py` | The only place that talks to Compliance. Makes the HTTP call, validates the response, and raises typed errors. |
| `app/services/supplier_onboarding_service.py` -> `activate_supplier()` | The trigger point. Checks the supplier is `approved`, calls the client, and activates only on CLEAR. |
| `app/routes/supplier_onboarding.py` -> `activate_supplier_endpoint()` | Maps typed errors to HTTP codes (409 / 503 / 502). No business logic. |
| `app/core/config.py` -> `COMPLIANCE_SERVICE_URL` | Where Compliance lives. Default `http://127.0.0.1:8003`. |
| `tests/test_compliance_client.py`, `tests/test_supplier_onboarding.py` | Client tests and activation integration tests. |

### 3. The order of operations inside `activate_supplier()`

1. Load the supplier (404 if missing).
2. **Check the state first**: must be `approved`, otherwise 400. Compliance is *not* called.
3. Call Compliance.
4. Activate only if `decision == "CLEAR"` **and** `cleared is True`.
5. Anything else raises, and the supplier stays `approved`.

Step 2 comes before step 3 on purpose: never screen, or report a Compliance outage for, a supplier who is not ready to activate.

### 4. The contract

Request:

```http
POST {COMPLIANCE_SERVICE_URL}/api/v1/compliance/internal-check
```

```http
X-Caller-Service: supplier-portal
Content-Type: application/json
```

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

Expected response:

```json
{
  "decision": "CLEAR",
  "cleared": true,
  "reason": "No sanctions or watchlist match found."
}
```

`decision` is one of `CLEAR` / `BLOCK` / `REVIEW`.

`cleared` must be `true` only for `CLEAR`. If the decision and cleared flag contradict each other, the response is treated as unusable and results in a `502`.

> **Dependency status:** The Compliance `/internal-check` contract must remain aligned with the Compliance Service implementation. Supplier Portal expects the fields and decision values documented above.

### 5. Error types to HTTP codes

| Raised by the client/service | Meaning | HTTP |
| --- | --- | ---: |
| `ComplianceBlockedError` | Valid BLOCK / REVIEW decision | 409 |
| `ComplianceServiceUnavailableError` | Timeout, connection or network failure | 503 |
| `ComplianceServiceError` | Compliance returned an error or an unusable/contradictory response | 502 |

Typed exceptions decide the status code, so a decision's `reason` text cannot change the HTTP status.

### 6. Run it locally

```bash
# Terminal 1: Platform
cd services/platform
uvicorn app.main:app --port 8005

# Terminal 2: Compliance
cd services/compliance
uvicorn app.main:app --port 8003

# Terminal 3: Supplier Portal
cd services/supplier-portal
python -m uvicorn app.main:app --port 8004
```

For document storage, a local MinIO instance must also be running and configured through the Supplier Portal environment settings.

### 7. Run the tests

```bash
cd services/supplier-portal
pytest tests/test_compliance_client.py tests/test_supplier_onboarding.py -q
```

### 8. Cloning this pattern for your own service

1. Put the HTTP call in its own `app/services/<other>_client.py`, never in a route.
2. Raise **typed exceptions** for business "no", service unreachable, and service error.
3. Call the client from your service function **after** your own state checks and **before** changing state.
4. Decide explicitly what "unreachable" means for your workflow, write down why, and test that path.
5. Add the service URL to configuration and `.env.example`.

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
17. MinIO Document Storage
18. GraphQL API for Portal Read/Mutation Operations
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

Supplier onboarding is implemented as:

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

**Rounds 9–11** introduced compliance integration, contract lifecycle management, dispute-resolution assistance, and supplier self-service analytics.

**Round 12 (Milestone 2)** introduced MinIO-backed document storage and presigned document downloads.

**Round 13 (Milestone 3)** introduced the Strawberry GraphQL API with cursor pagination, the acknowledge-PO mutation, and resolver-level supplier scoping.

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
* MinIO document storage
* Short-lived presigned document downloads
* GraphQL Purchase Order queries
* GraphQL invoice queries
* GraphQL supplier document queries
* GraphQL cursor pagination
* GraphQL acknowledge-PO mutation
* Resolver-level supplier scoping
* Automated business-rule testing
* Supplier isolation and cross-supplier security testing

### Reviewer-identified functional issues

```text
1. Three-way match discrepancy reachability       → Fixed
2. Scorecard invoice metrics                      → Fixed
3. Supplier ID existence leak                     → Fixed
4. Supplier onboarding enforcement                → Fixed
5. Future-due PO handling in on-time metrics      → Fixed
```

### Rounds 9–11

```text
1. Compliance business-logic integration          → Implemented
2. Compliance failure-path handling                → Implemented
3. Supplier contract lifecycle management          → Implemented
4. Contract expiry/renewal tracking                → Implemented
5. Contract term-change audit history              → Implemented
6. Historical dispute-resolution suggestions       → Implemented
7. Supplier self-service scorecard access          → Implemented
8. Compliance integration test coverage             → Implemented
```

### Round 12 — Milestone 2

```text
1. MinIO document storage                          → Implemented
2. Invoice PDF object storage                      → Implemented
3. Supplier onboarding document storage             → Implemented
4. Presigned document download URLs                 → Implemented
5. Supplier ownership before URL generation         → Implemented
6. Cross-supplier document access protection        → Implemented
7. MinIO unit and integration test coverage         → Implemented
```

### Round 13 — Milestone 3

```text
1. Strawberry GraphQL endpoint                      → Implemented
2. Purchase Order GraphQL queries                   → Implemented
3. Invoice GraphQL queries                          → Implemented
4. Supplier document GraphQL queries                → Implemented
5. Cursor pagination                                → Implemented
6. Acknowledge-Purchase-Order mutation              → Implemented
7. Resolver-level supplier scoping                  → Implemented
8. Cross-supplier GraphQL isolation tests           → Implemented
```

Current infrastructure limitations include:

* Purchase Orders, invoices, P2P records, onboarding data, contract data, and audit events use in-memory business storage.
* In-memory business data is not persistent across service restarts.
* **Invoice PDFs and supplier onboarding documents are stored in MinIO rather than the local filesystem.**
* Authentication depends on the availability of the Platform Service.
* Supplier activation depends on the availability of the Compliance Service.
* Production deployment requires persistent business storage and additional operational hardening.

The current implementation is suitable for development, functional validation, API testing, integration testing, and workflow verification. Production deployment requires additional infrastructure and operational controls.

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

> The invoice service does not block a price difference merely because it exceeds the three-way-match tolerance. Price differences must reach the matching stage so that the matching process can identify and flag the discrepancy.

## Invoice Documents

* PDF-only invoice upload
* Content-Type validation
* PDF signature validation
* 10 MB file-size limit
* MinIO object storage
* Supplier-scoped object-key generation
* Object existence validation
* Short-lived presigned download URLs
* Supplier ownership verification before URL generation
* Cross-supplier document-access protection
* MinIO storage failure handling
* Missing-object handling
* Document storage unit testing
* MinIO integration testing

Documents are no longer stored as local filesystem files.

The security flow is:

```text
Authenticated Request
        │
        ▼
Document Lookup
        │
        ▼
Supplier Ownership Check
        │
        ├── Not Owner ─────► 403 Forbidden
        │
        └── Owner
             │
             ▼
        MinIO Object Check
             │
             ├── Missing ───► 404 Not Found
             │
             └── Exists
                  │
                  ▼
          Generate Presigned URL
                  │
                  ▼
                 200
```

The key security rule is:

```text
Never generate a presigned URL before verifying
that the authenticated supplier owns the document.
```

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
* MinIO-backed onboarding document storage
* Presigned onboarding-document downloads

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

Supported decisions:

```text
CLEAR
  → Supplier activation allowed

BLOCK
  → Supplier activation rejected

REVIEW
  → Supplier activation rejected and requires review
```

If the Compliance Service is unavailable, times out, or cannot be reached, activation does not proceed.

The integration intentionally follows a **fail-closed** approach.

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

## Supplier Self-Service Analytics

Supplier users can access their own supplier performance scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

Supplier ownership is enforced before returning the scorecard.

Supplier self-service analytics are read-only.

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

The service does not automatically modify invoices, approve disputes, or change three-way-match state based on a suggestion.

---

# 3. Architecture

The Supplier Portal follows a layered FastAPI architecture with separate REST, GraphQL, business-service, authentication, and object-storage responsibilities.

```text
                         Client
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
       REST API                       GraphQL
             │                           │
             └─────────────┬─────────────┘
                           ▼
                Authentication /
                Authorization
                           │
                           ▼
                    Service Layer
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
      PO Services     Invoice Services   Supplier
                                           Services
          │                │                 │
          └────────────────┼─────────────────┘
                           │
                           ▼
                 Business State / Stores
                           │
              ┌────────────┼─────────────┐
              │            │             │
              ▼            ▼             ▼
          PO/P2P       Invoice       Supplier Data
                                        │
                                        ▼
                              Contract / Onboarding /
                              Performance Services
```

### MinIO Document Architecture

```text
Supplier Portal
      │
      ▼
Document Storage Service
      │
      ├── Validate metadata
      ├── Validate content
      ├── Build supplier-scoped object key
      └── Store / retrieve object
      │
      ▼
MinIO
      │
      ▼
S3-Compatible Object
```

For downloads:

```text
Authenticated Supplier
        │
        ▼
Document Resolver / REST Endpoint
        │
        ▼
Ownership Check
        │
        ├── Cross-supplier → 403
        │
        ▼
MinIO Object Check
        │
        ▼
Short-Lived Presigned URL
```

Supplier A therefore cannot obtain a presigned URL for Supplier B's document.

### GraphQL Architecture

```text
Apollo Client
      │
      ▼
POST /graphql
      │
      ▼
GraphQL Context
      │
      ▼
Authenticated User
      │
      ▼
GraphQL Resolver
      │
      ▼
Supplier Scope Check
      │
      ▼
Existing Business Service
      │
      ▼
GraphQL Type / Connection
```

GraphQL resolvers enforce supplier ownership **inside the resolver layer**.

Supplier scoping is not dependent only on a surrounding REST route.

### GraphQL Query Operations

The GraphQL API provides operations for:

```text
purchaseOrder
purchaseOrders
invoice
invoices
documents
```

Collection operations support cursor pagination using:

```text
first
after
hasNextPage
endCursor
```

The implementation limits `first` to a maximum of 100 records.

### GraphQL Mutation

The current mutation surface includes:

```text
acknowledgePurchaseOrder
```

The mutation:

1. Reads the authenticated user from GraphQL context.
2. Loads the requested Purchase Order.
3. Checks supplier ownership for supplier users.
4. Calls the existing Purchase Order service.
5. Returns the updated GraphQL representation.

A supplier cannot acknowledge another supplier's Purchase Order.

### GraphQL Supplier Isolation

```text
SUP001 authenticated user
          │
          ▼
GraphQL purchaseOrder(id)
          │
          ▼
Requested PO supplier_id
          │
          ▼
Compare with authenticated supplier_id
          │
     ┌────┴────┐
     │         │
   Match    Mismatch
     │         │
     ▼         ▼
 Return      null
```

This prevents cross-supplier data exposure through GraphQL.

### Compliance Business-Logic Integration

The Supplier Portal calls the Compliance Service during supplier activation:

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

### Supplier Contract Architecture

Supplier contract management remains an independent business service:

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

---

## Procure-to-Pay Architecture

The Supplier Portal extends the existing layered architecture with a dedicated procure-to-pay workflow layer.

```text
                         Client
                           │
                           ▼
                   FastAPI Application
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
                 REST          GraphQL
                    │             │
                    └──────┬──────┘
                           ▼
                Authentication /
                Authorization
                           │
                           ▼
                    Business Services
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
                 ┌─────────┴─────────┐
                 │                   │
                 ▼                   ▼
              Matched          Discrepancy
                                      │
                                      ▼
                                 Human Review
                                      │
                                      ▼
                              Payment Approval
```

The P2P state machine is separate from the existing Purchase Order lifecycle state machine.

---

# 4. Technology Stack

| Technology | Purpose |
| --- | --- |
| Python | Backend programming language |
| FastAPI | REST API framework |
| Strawberry GraphQL | GraphQL API implementation |
| Pydantic | Request and response validation |
| Pydantic Settings | Environment configuration |
| Uvicorn | ASGI application server |
| HTTPX | HTTP client and FastAPI testing |
| Pytest | Automated testing |
| python-multipart | Multipart file upload support |
| MinIO / S3-compatible API | Object storage for documents |

The current dependency versions are maintained in `requirements.txt`.

---

# 5. Project Structure

The Supplier Portal Service follows a layered architecture separating application configuration, authentication, REST routes, GraphQL operations, validation schemas, business logic, document storage, external business-service integration, and automated tests.

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
│   ├── graphql/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── queries.py
│   │   ├── mutations.py
│   │   ├── schema.py
│   │   └── types.py
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
│       ├── document_storage_service.py
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
│   ├── test_dispute_resolution.py
│   ├── test_document_storage_service.py
│   ├── test_supplier_document_download.py
│   ├── test_invoice_document_download.py
│   ├── test_graphql.py
│   │
│   └── integration/
│       └── test_minio_document_storage.py
│
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

The old local `uploads/` directory is no longer part of the document-storage architecture.

### Application Layer

`app/main.py`

Responsible for:

* Creating and configuring the FastAPI application
* Registering REST routers
* Mounting the GraphQL router at `/graphql`
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
* Platform Service failure handling

`app/core/config.py`

Responsible for:

* Environment-based configuration
* Platform authentication service URL
* Compliance Service URL
* MinIO configuration
* Application configuration values

### GraphQL Layer

`app/graphql/`

Responsible for:

* GraphQL schema definition
* Query definitions
* Mutation definitions
* GraphQL type definitions
* Request-scoped authentication context
* Cursor pagination
* Resolver-level supplier authorization
* Conversion of existing business objects to GraphQL types

The GraphQL layer reuses the existing Supplier Portal service layer rather than duplicating Purchase Order or Invoice business logic.

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

The Supplier Portal exposes REST routes for:

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

For supplier-scoped detail endpoints, ownership authorization is performed before exposing resource existence to the supplier caller.

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
* Invoice document handling
* MinIO object-storage operations
* Presigned URL generation
* Supplier-scoped document authorization
* Supplier-scoped business operations

### Document Storage Service

`app/services/document_storage_service.py`

The document storage service provides the storage abstraction between business services and MinIO.

Its responsibilities include:

* Uploading document objects
* Checking object existence
* Generating short-lived presigned URLs
* Handling missing objects
* Handling storage failures
* Keeping storage-specific implementation out of route handlers

Business endpoints must perform supplier ownership checks before requesting a presigned URL.

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

## Authentication Configuration

The Platform Service URL is configured using:

```text
PLATFORM_AUTH_URL
```

The default development value is:

```text
http://127.0.0.1:8005
```

## Authentication Errors

| Situation | Response |
| --- | ---: |
| Missing token | 401 |
| Invalid token | 401 |
| Expired token | 401 |
| Missing user role | 401 |
| Unauthorized role | 403 |
| Supplier identity missing | 403 |
| Supplier resource ownership mismatch | 403 |
| Authentication timeout | 503 |
| Authentication service unavailable | 503 |
| Invalid authentication response | 503 |

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

This applies to:

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

## MinIO Document Scoping

Document ownership is checked **before** generating a presigned URL.

```text
Supplier A
    │
    ▼
Requests Supplier B document
    │
    ▼
Authenticate Supplier A
    │
    ▼
Compare document supplier_id
    │
    ▼
Mismatch
    │
    ▼
403 Forbidden
```

The system must not generate a presigned URL first and perform authorization afterward.

This ensures that knowing another supplier's document ID or object reference is insufficient to obtain access.

## GraphQL Scoping

GraphQL applies supplier authorization inside each resolver.

For a supplier user:

```text
GraphQL Request
      │
      ▼
GraphQL Context
      │
      ▼
Authenticated supplier_id
      │
      ▼
Resolver
      │
      ▼
Requested resource supplier_id
      │
      ├── Same supplier → Return resource
      │
      └── Different supplier → Return null / no data
```

For example:

```text
SUP001 token
     │
     ▼
purchaseOrder(SUP002 PO)
     │
     ▼
Resolver ownership check
     │
     ▼
null
```

This rule is enforced inside the resolver rather than relying only on the REST route.

Collection resolvers also apply supplier filtering **before pagination**.

This prevents unauthorized records from affecting:

* returned edges
* cursors
* page boundaries
* `hasNextPage`
* `endCursor`

## Supplier List Filtering

Collection endpoints are protected by authentication and supplier-level filtering.

The following REST endpoints require authentication:

```http
GET /api/v1/purchase-orders
GET /api/v1/invoices
```

When the authenticated user has the `supplier` role, only records belonging to that supplier are returned.

The GraphQL collection operations follow the same security principle:

```text
purchaseOrders
invoices
documents
```

Supplier filtering occurs before cursor pagination.

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

Examples:

* Purchase Order creation requires `procurement_manager`
* Purchase Order transition requires `procurement_manager`
* Bulk Purchase Order sending requires `procurement_manager`
* Invoice adjustment requires `compliance_officer`
* Goods Receipt creation requires `warehouse_manager`
* Supplier contract creation/update/activation/renewal requires `procurement_manager`
* Supplier-specific resources require the authenticated supplier to own the resource
* Supplier collection endpoints return only the authenticated supplier's resources
* Supplier scorecards are restricted to the authenticated supplier
* GraphQL supplier resolvers enforce the same supplier ownership rules
* GraphQL acknowledge-PO mutation checks supplier ownership before changing PO state

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

SUP001 token → SUP001 Contract    → Allowed
SUP001 token → SUP002 Contract    → 403 Forbidden

SUP001 token → SUP001 Document    → Presigned URL
SUP001 token → SUP002 Document    → 403 Forbidden
```

For GraphQL:

```text
SUP001 token → SUP001 PO          → PO returned
SUP001 token → SUP002 PO          → null

SUP001 token → SUP001 Invoice     → Invoice returned
SUP001 token → SUP002 Invoice     → null

SUP001 token → SUP001 Document    → Document returned
SUP001 token → SUP002 Document    → not returned
```

The same ownership principle applies to supplier-scoped Purchase Order events, invoice documents, statistics, shipments, goods receipts, three-way matches, onboarding resources, contracts, and GraphQL resources.

Supplier-level authorization is enforced at both the REST API and GraphQL resolver layers and is covered by automated tests.
# 7. Purchase Order Management

Purchase Orders are managed through a controlled lifecycle and are integrated with the broader procure-to-pay workflow.

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

The legacy Purchase Order lifecycle is:

```text
             ┌─────────────┐
             │  Cancelled  │
             └─────────────┘
                    ▲
                    │
Draft ───────► Sent ───────► Acknowledged ───────► Fulfilled
```

The legal transitions are:

| Current State | Allowed Transitions |
|---|---|
| `draft` | `sent`, `cancelled` |
| `sent` | `acknowledged`, `cancelled` |
| `acknowledged` | `fulfilled`, `cancelled` |
| `fulfilled` | None |
| `cancelled` | None |

Terminal states:

```text
fulfilled
cancelled
```

cannot transition to another state.

The Supplier Portal also contains a separate P2P state machine for the complete transaction workflow:

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
Payment Approval
```

The legacy PO lifecycle and the P2P state machine serve different purposes and are intentionally kept separate.

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


Pending / Inactive Supplier
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

- PO number
- Supplier ID
- Supplier onboarding / active status
- Items
- Quantity
- Unit price
- Total amount
- Expected delivery
- Duplicate PO number

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

The same supplier-scoping principle is also enforced by the GraphQL Purchase Order resolvers.

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

The GraphQL equivalent also enforces ownership inside the resolver. An unauthorized supplier querying another supplier's PO by ID receives no PO object rather than another supplier's data.

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

REST endpoint:

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

### GraphQL Acknowledgement

The portal also exposes an acknowledge-PO mutation through:

```text
/graphql
```

The GraphQL mutation:

1. Obtains the authenticated user from the GraphQL context.
2. Finds the requested Purchase Order.
3. Verifies supplier ownership when the user is a supplier.
4. Calls the existing PO acknowledgement service only after authorization succeeds.
5. Returns the updated Purchase Order.

A supplier cannot acknowledge another supplier's PO through GraphQL.

The mutation therefore follows the same authorization rules as the REST endpoint.

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

For multiple Goods Receipts, the latest applicable `receipt_date` is used as the actual delivery date.

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

For supplier statistics and scorecards:

- fulfilled POs are eligible;
- past-due unfulfilled POs are eligible and counted as late;
- future-due unfulfilled POs are excluded;
- cancelled POs are excluded;
- POs without an applicable expected delivery date are excluded.

This same delivery eligibility definition is reused by supplier statistics, supplier scorecards, and monthly delivery trends.

---

# 8. Invoice Management

Invoices are linked to Purchase Orders and suppliers.

An invoice can only be created when its referenced PO satisfies the required business rules.

The invoice lifecycle remains separate from the broader P2P state machine.

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

Invoice line items contain the PO reference used by supplier performance calculations and three-way matching.

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

| Current Status | Allowed Status |
|---|---|
| `submitted` | `approved`, `disputed`, `rejected` |
| `disputed` | `approved`, `adjusted`, `rejected` |
| `adjusted` | `approved`, `rejected` |
| `approved` | None |
| `rejected` | None |

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

Invoice price differences are allowed to reach the three-way matching stage. The matching process determines whether the price difference is within the configured tolerance or represents a discrepancy.

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

Supplier authorization is evaluated before exposing another supplier's protected invoice data.

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

R5 supplier scoping additionally ensures that the authenticated supplier identity must match the supplier being acted upon.

## Invoice Line-Item Validation

Each invoice item is validated against the Purchase Order.

The service validates:

- Item exists on the PO
- Quantity is positive
- Quantity does not exceed remaining PO quantity
- Duplicate `(po_number, item_code)` lines are not allowed within one invoice
- Invoice amount matches the calculated line-item total

Invoice quantity and price differences that are valid from an invoice-data perspective are allowed to reach the three-way match process.

The three-way match applies the configured **5% price tolerance** when comparing invoice prices against Purchase Order prices.

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

- Adjust an invoice
- Approve an invoice
- Reject an invoice
- Change three-way-match status
- Resolve the dispute

The final business decision remains with the authorized human user.

---

# 9. Invoice and Onboarding Document Management

Invoice PDFs and supplier onboarding documents are stored in **MinIO**, an S3-compatible object-storage service running locally in the development environment.

The implementation no longer uses the local filesystem as the document-storage backend.

The architecture is:

```text
Supplier Portal
      │
      ▼
Document Storage Service
      │
      ▼
MinIO / S3-Compatible Object Storage
      │
      ▼
PDF / onboarding document object
```

Application data stores the document reference/object key required to retrieve the object from MinIO.

The actual document binary is stored in MinIO rather than in the application database.

## Object Storage

The local development environment uses MinIO as the object-storage server.

Conceptually:

```text
Windows Development Machine
          │
          ▼
Docker Desktop
          │
          ▼
MinIO Container
          │
          ▼
MinIO Server
          │
          ▼
Stored Documents
```

Docker Desktop provides the local container runtime. MinIO provides the S3-compatible object-storage service.

The Supplier Portal communicates with MinIO through the document storage service rather than directly exposing storage credentials or internal storage details to clients.

## Supported Documents

The document-storage implementation covers:

```text
Invoice PDFs
Supplier onboarding documents
```

The storage layer is responsible for storing and retrieving document objects while the application remains responsible for authentication, authorization, and supplier ownership checks.

## PDF Upload

Invoice document endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint is authenticated and supplier-scoped.

For supplier users, the authenticated `supplier_id` must match the supplier associated with the invoice.

A supplier cannot upload a document to another supplier's invoice.

The document is validated before being stored in MinIO.

## PDF Validation

The service performs multiple validation checks before storing an invoice document.

### 1. Content Type

The request must declare:

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

The uploaded bytes are checked so that payloads exceeding the configured limit are rejected.

## Document Object Reference

The application uses an object reference/object key to identify the stored document.

Conceptually:

```text
Supplier
   │
   ▼
Invoice / Onboarding Document
   │
   ▼
Object Key
   │
   ▼
MinIO Object
```

The object key is an internal storage reference.

It is not treated as a public downloadable URL.

The application does not expose MinIO credentials or storage-internal authentication information to suppliers.

## Presigned URL Downloads

Document downloads use short-lived **presigned URLs**.

The download flow is:

```text
Authenticated Request
        │
        ▼
Identify requested document
        │
        ▼
Verify supplier ownership / authorization
        │
        ▼
Verify object exists in MinIO
        │
        ▼
Generate short-lived presigned URL
        │
        ▼
Return URL to authorized caller
```

The important security rule is:

```text
Authorize first
      │
      ▼
Generate presigned URL second
```

A presigned URL is never generated before the application has verified that the authenticated user is authorized to access the requested document.

This prevents an unauthorized supplier from obtaining a valid storage URL simply by knowing another supplier's document identifier or object key.

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
Find invoice/document
        │
        ▼
Check authenticated user
        │
        ▼
Check supplier ownership
        │
        ▼
Check MinIO object
        │
        ▼
Generate short-lived presigned URL
        │
        ▼
Return authorized URL
```

The application does not return the PDF through FastAPI `FileResponse`. The client receives a temporary signed URL for authorized access to the object stored in MinIO.

## Cross-Supplier Document Protection

Supplier scoping is enforced before generating a presigned URL.

Example:

```text
Supplier A
   │
   ├── Requests own document
   │
   └── Ownership verified
           │
           ▼
       URL generated
```

But:

```text
Supplier A
   │
   ├── Requests Supplier B document
   │
   └── Ownership check fails
           │
           ▼
       403 Forbidden
```

Supplier A must never receive a presigned URL for Supplier B's document through any Supplier Portal endpoint.

This applies even when Supplier A knows or guesses:

- another supplier's document identifier;
- invoice number;
- supplier ID;
- object key/reference.

The authorization check is performed before URL generation.

## Document Error Handling

The document-storage implementation distinguishes different failure conditions.

### Unauthorized Supplier Access

```text
403 Forbidden
```

Returned when the authenticated supplier does not own the requested document.

### Document Not Found

```text
404 Not Found
```

Returned when the requested application document/object cannot be found.

### Storage Dependency Failure

```text
503 Service Unavailable
```

Returned when the Supplier Portal cannot use the required MinIO storage dependency.

This allows clients and operators to distinguish:

```text
Wrong supplier
    → 403

Missing document
    → 404

Storage unavailable
    → 503
```

## Onboarding Document Storage

Supplier onboarding documents follow the same MinIO-backed storage model.

Conceptually:

```text
Supplier Onboarding
        │
        ▼
Document Upload
        │
        ▼
Document Storage Service
        │
        ▼
MinIO
```

Supplier ownership is checked before a document download URL is generated.

This prevents one supplier from obtaining another supplier's onboarding-document URL.

## Document Storage Security

The document-storage implementation follows these principles:

- Store document binaries in MinIO rather than the local filesystem.
- Keep application document references separate from public URLs.
- Authenticate every protected document request.
- Enforce supplier ownership before storage access.
- Generate presigned URLs only after authorization succeeds.
- Keep presigned URLs short-lived.
- Never expose MinIO credentials to suppliers.
- Return `403` for cross-supplier document access.
- Return `404` for missing objects/documents.
- Return `503` when the storage dependency is unavailable.

## Document Storage Testing

Document storage is covered by unit and integration tests.

The test coverage includes:

```text
Document storage service
Invoice document downloads
Supplier onboarding document downloads
MinIO integration
Cross-supplier access rejection
Missing object handling
Storage dependency failures
Presigned URL generation
PDF validation
```

The integration tests use a local MinIO instance so that the storage behavior is tested against an actual S3-compatible object-storage service.

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

## GraphQL Supplier Statistics Scope

The Round 13 GraphQL API currently exposes GraphQL operations for:

```text
Purchase Orders
Invoices
Documents
```

Supplier statistics remain available through their REST endpoint.

Where GraphQL resources are supplier-scoped, authorization is enforced inside the corresponding resolver rather than relying only on the `/graphql` route.

This ensures that a supplier cannot bypass REST-level supplier-scoping rules by querying another supplier's protected Purchase Order, invoice, or document through GraphQL.
# 11. Supplier Performance Scorecard

The Supplier Performance Scorecard provides a higher-level view of supplier performance using Purchase Order, invoice, and dispute history.

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

The same scorecard endpoint provides the supplier self-service analytics functionality introduced during R9–R11.

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
monthly trends
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

+

POs without an applicable expected delivery date
```

For fulfilled Purchase Orders, the actual delivery date is derived from the related Goods Receipt records.

When multiple Goods Receipts exist, the latest applicable `receipt_date` is used.

The comparison is:

```text
actual_delivery_date <= expected_delivery
```

Therefore:

```text
Before expected date → On time

Expected date        → On time

After expected date  → Late
```

Past-due unfulfilled POs are counted as late.

Future-due unfulfilled POs are excluded because their delivery deadline has not yet passed.

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

The resulting score is calculated from the implemented metric definitions and weights.

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

The service also supports the legacy/top-level PO reference where present.

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

Supplier performance trends are grouped by Purchase Order creation month.

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

The same Goods Receipt-based actual delivery date is used instead of the current system date.

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

## Scorecard Supplier Scoping

Supplier scorecards follow the R5 supplier-scoping model:

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

A supplier cannot use the scorecard endpoint to inspect another supplier's performance.

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

This separation allows the existing Purchase Order lifecycle to remain intact while the P2P workflow controls end-to-end transaction progression.

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

The `receipt_date` is also used as the source of the actual delivery date for supplier delivery-performance calculations.

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

## Three-Way Match Integration

After the invoice stage, the transaction progresses to three-way matching.

The match compares:

```text
Purchase Order
+
Goods Receipt
+
Invoice
```

The result is either:

```text
matched
```

or:

```text
discrepancy
```

A discrepancy requires human review.

---

## Payment Approval

After invoice processing and a successful three-way match, the transaction can progress toward:

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

- Validating the current P2P state before transition
- Allowing only legal state transitions
- Preventing invalid duplicate processing
- Validating Purchase Order ownership
- Validating related business records
- Requiring the appropriate supplier context
- Requiring an appropriate Goods Receipt before P2P invoicing
- Preventing invalid invoice submissions from advancing the state
- Routing match discrepancies for human review

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

The matching process evaluates:

```text
Item codes

Ordered quantities

Received quantities

Invoiced quantities

Purchase Order prices

Invoice prices
```

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
5.0%
```

The tolerance is inclusive.

For example, when the Purchase Order unit price is:

```text
100
```

a price difference within:

```text
±5%
```

is within the configured tolerance.

Therefore, the following values are within tolerance:

```text
95
100
105
```

while:

```text
106
```

is outside the configured tolerance.

The tolerance is a three-way matching rule, not an invoice-creation rejection rule.

---

## Match Result

A successful match indicates that the relevant Purchase Order, Goods Receipt, and Invoice information satisfies the implemented matching rules.

A matched transaction can continue toward payment approval according to the P2P state machine.

A transaction containing a material quantity or price discrepancy is marked for further review.

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

The suggestion engine does not modify:

```text
Invoice state

Three-way-match state

Payment state
```

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

The implementation supports discrepancy scenarios through the actual P2P workflow.

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

The three-way match uses the centralized price-tolerance configuration.

```text
PRICE_TOLERANCE_PERCENT = 5.0
```

The tolerance is maintained centrally so that the matching logic does not use different tolerance values in different locations.

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

Supplier onboarding documents are stored through the MinIO-backed document storage layer.

The document-storage implementation supports the configured onboarding document types and validates:

```text
Content type

File extension

File content

File size
```

The maximum supported document size is:

```text
10 MB
```

Invalid document uploads are rejected.

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

Onboarding documents are also protected during download. An authorized supplier receives a short-lived presigned URL only after ownership has been verified.

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

The integration ensures that supplier activation depends on an actual compliance decision.

The Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

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

The Supplier Portal sends supplier information such as:

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

The internal service request includes:

```text
X-Caller-Service: supplier-portal
```

The Compliance Service URL is configurable through:

```text
COMPLIANCE_SERVICE_URL
```

The current local development default is:

```text
http://127.0.0.1:8003
```

The Supplier Portal uses a dedicated Compliance client rather than putting the HTTP call directly inside the route handler.

---

## Compliance Decisions

The expected Compliance decisions are:

```text
CLEAR
BLOCK
REVIEW
```

### CLEAR

A `CLEAR` decision with:

```text
cleared = true
```

allows the supplier to become active.

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

The Supplier Portal uses a fail-closed activation policy.

If the Compliance Service cannot provide a usable clearance decision, the supplier is **not activated**.

The supplier remains:

```text
approved
```

This separates a Compliance business decision from a Compliance service failure.

| Compliance result | HTTP response | Supplier status |
|---|---:|---|
| `CLEAR` + `cleared: true` | 201 | `active` |
| `BLOCK` | 409 | stays `approved` |
| `REVIEW` | 409 | stays `approved` |
| Timeout / connection / network failure | 503 | stays `approved` |
| Compliance service error / unusable response | 502 | stays `approved` |

The operator can retry activation after the Compliance dependency becomes available.

Nothing needs to be rolled back because the supplier was never moved to `active`.

---

## Compliance Service Errors

The Supplier Portal uses typed exceptions from the Compliance client.

The mapping is:

```text
ComplianceBlockedError
    → 409 Conflict

ComplianceServiceUnavailableError
    → 503 Service Unavailable

ComplianceServiceError
    → 502 Bad Gateway
```

Typed exceptions are used instead of matching error-message strings.

This prevents a free-form Compliance `reason` from changing the HTTP behavior.

---

## Fail-Closed Activation

The activation rule is:

```text
Supplier must be approved

        AND

Compliance decision must be CLEAR

        AND

cleared must be true

        ↓

Supplier becomes active
```

There is no fallback such as:

```text
Compliance unavailable
        ↓
Assume CLEAR
        ↓
Activate
```

This prevents an unscreened supplier from becoming active when the required Compliance decision cannot be obtained.

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

No activation when Compliance fails
```

The failure-path tests verify that a failed Compliance check does not partially activate the supplier.

---

## Active Supplier

An approved supplier reaches the active state only after the Compliance Service returns a valid clear decision:

```text
Approved
   │
   ▼
Compliance Check
   │
   ▼
CLEAR + cleared=true
   │
   ▼
Active
```

The active-supplier check is then used by Purchase Order creation.

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

This makes onboarding enforcement part of the actual procurement business flow.

---

## Supplier Scoping

Supplier onboarding follows the supplier-level security principles established in Round 5.

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

## Onboarding Document Security

Onboarding documents are stored in MinIO.

The download flow is:

```text
Authenticated Request
        │
        ▼
Verify supplier ownership
        │
        ▼
Check MinIO object
        │
        ▼
Generate short-lived presigned URL
        │
        ▼
Return URL
```

The application performs authorization before generating the presigned URL.

Therefore:

```text
Supplier A
    │
    └── Supplier B document request
              │
              ▼
          403 Forbidden
```

Supplier A cannot obtain Supplier B's onboarding document URL.

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

# How I Wired Business-Logic Integration (Supplier Portal to Compliance)

This integration connects the Supplier Portal activation workflow to the Compliance Service.

### 1. What it does

Before a supplier moves:

```text
approved → active
```

the Supplier Portal asks the Compliance Service whether the supplier is cleared.

The supplier is activated only when:

```text
decision == CLEAR

AND

cleared == true
```

---

### 2. Where the code is

| File | Responsibility |
|---|---|
| `app/services/compliance_client.py` | Makes the Compliance HTTP call, validates the response, and raises typed exceptions. |
| `app/services/supplier_onboarding_service.py` → `activate_supplier()` | Checks the supplier state, calls Compliance, and activates only after a valid CLEAR result. |
| `app/routes/supplier_onboarding.py` → activation endpoint | Maps typed service errors to HTTP responses. |
| `app/core/config.py` → `COMPLIANCE_SERVICE_URL` | Configures the Compliance Service base URL. |
| `tests/test_compliance_client.py` | Tests Compliance client success and failure behavior. |
| `tests/test_supplier_onboarding.py` | Tests activation behavior and failure paths. |

The HTTP integration is intentionally isolated in the dedicated Compliance client rather than being embedded directly in the route.

---

### 3. Order of Operations Inside `activate_supplier()`

The activation flow is:

```text
1. Load supplier
       │
       ▼
2. Verify current state is approved
       │
       ▼
3. Call Compliance
       │
       ▼
4. Validate CLEAR + cleared=true
       │
       ▼
5. Change supplier to active
```

If the supplier is not already `approved`, the Compliance Service is not called.

This prevents unnecessary external calls for suppliers that are not yet eligible for activation.

---

### 4. Integration Contract

Request:

```text
POST {COMPLIANCE_SERVICE_URL}/api/v1/compliance/internal-check
```

Headers:

```http
X-Caller-Service: supplier-portal
Content-Type: application/json
```

Request body:

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

Expected decision structure:

```json
{
  "decision": "CLEAR",
  "cleared": true,
  "reason": "No sanctions or watchlist match found."
}
```

Supported decisions:

```text
CLEAR
BLOCK
REVIEW
```

A contradictory response such as:

```text
decision = CLEAR
cleared = false
```

is not treated as a successful activation response.

---

### 5. Error Types to HTTP Codes

| Client/service error | Meaning | HTTP |
|---|---|---:|
| `ComplianceBlockedError` | Valid `BLOCK` or `REVIEW` decision | 409 |
| `ComplianceServiceUnavailableError` | Timeout, connection, or network failure | 503 |
| `ComplianceServiceError` | Compliance service error or unusable response | 502 |

Typed exceptions decide the HTTP response.

The Compliance `reason` text does not determine the status code.

---

### 6. Dependency Ownership

The `/internal-check` endpoint belongs to the Compliance Service.

The Supplier Portal owns:

```text
Calling Compliance
Validating the response contract
Applying the activation rule
Handling failures
```

The Compliance Service owns:

```text
The actual compliance decision
Sanctions/watchlist evaluation
CLEAR / BLOCK / REVIEW determination
```

The two services therefore have clear responsibilities.

---

### 7. Local Development

Run the services separately:

```bash
# Terminal 1: Platform Authentication
cd services/platform
uvicorn app.main:app --port 8005

# Terminal 2: Compliance
cd services/compliance
uvicorn app.main:app --port 8003

# Terminal 3: Supplier Portal
cd services/supplier-portal
uvicorn app.main:app --port 8004
```

After taking a supplier through:

```text
register
   ↓
documents
   ↓
verify
   ↓
approve
```

the activation request can be performed against the Supplier Portal.

Example:

```bash
curl -X POST http://127.0.0.1:8004/api/v1/suppliers/SUP001/activate \
  -H "Authorization: Bearer <procurement_manager_token>"
```

When Compliance is available and returns a valid CLEAR decision, activation succeeds.

If Compliance is unavailable, the Supplier Portal returns:

```text
503 Service Unavailable
```

and the supplier remains:

```text
approved
```

---

### 8. Run the Integration Tests

```bash
cd services/supplier-portal

python -m pytest \
  tests/test_compliance_client.py \
  tests/test_supplier_onboarding.py \
  -q
```

The tests verify both the happy path and failure behavior.

---

### 9. Pattern for Future Business Integrations

The Supplier Portal uses the following pattern for inter-service business calls:

```text
Route
  │
  ▼
Business Service
  │
  ▼
Dedicated External-Service Client
  │
  ▼
Other Microservice
```

The external client:

1. Owns the HTTP communication.
2. Validates the external response.
3. Raises typed exceptions.
4. Distinguishes business rejection from dependency failure.
5. Keeps transport details out of the route.

The business service:

1. Performs its own state checks first.
2. Calls the external service at the required business decision point.
3. Changes state only after the external decision succeeds.
4. Applies an explicit failure policy.
5. Tests both success and failure paths.

This pattern can be reused when another Supplier Portal workflow needs to integrate with another service.

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

Contracts are associated with suppliers and contain commercial and operational terms.

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

The implemented lifecycle supports:

```text
draft
  ↓
active
```

and renewal/expiry handling around the active contract period.

A renewed contract continues into its next active period while the renewal history records the previous period and renewal action.

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

The configured:

```text
renewal_notice_days
```

value determines the normal renewal-warning window.

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

The renewal records information such as:

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

Where supplier-facing contract access is permitted, supplier users can access only contract resources belonging to their authenticated supplier.

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

The current implementation intentionally has several limitations.

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

Renewal remains an explicit business operation.

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

## GraphQL Scope for Round 13

The Round 13 Strawberry GraphQL API is intentionally focused on the portal resources required by the frontend:

```text
Purchase Orders
Invoices
Documents
```

GraphQL currently provides:

```text
Purchase Order queries
Invoice queries
Document queries
Cursor pagination
Acknowledge-PO mutation
Resolver-level supplier scoping
```

Supplier contracts continue to use their REST API endpoints.

This means the Round 13 GraphQL implementation does not imply that every existing REST resource has been converted to GraphQL.

The architecture currently supports both interfaces:

```text
Frontend / Client
       │
   ┌───┴───────────────┐
   │                   │
   ▼                   ▼
REST API          GraphQL API
   │                   │
   │              GraphQL Resolvers
   │                   │
   └──────────┬────────┘
              ▼
       Existing Service Layer
              │
       ┌──────┴──────┐
       │             │
   Business Data   MinIO
```

This allows the existing REST functionality to remain available while the frontend consumes the required portal resources through GraphQL.

# 16. API Reference

All REST application APIs use the `/api/v1` prefix unless otherwise noted.

The service root endpoint `/` is not under the `/api/v1` prefix.

The Supplier Portal also exposes a Strawberry GraphQL endpoint at:

```text
/graphql
```

Protected REST and GraphQL operations authenticate users through the Platform Service.

Supplier-facing operations additionally enforce supplier-level ownership and data scoping.

Authentication, role authorization, supplier ownership, and business-state validation are enforced according to each operation's requirements.

---

## Root

| Method | Endpoint | Authentication / Role | Description |
| ------ | -------- | --------------------- | ----------- |
| GET | `/` | Public | Service health/message |

---

## Purchase Order APIs

| Method | Endpoint | Authentication / Role | Description |
| ------ | -------- | --------------------- | ----------- |
| POST | `/api/v1/purchase-orders` | `procurement_manager` | Create Purchase Order |
| GET | `/api/v1/purchase-orders` | Authenticated | List Purchase Orders |
| GET | `/api/v1/purchase-orders/{po_number}` | Authenticated | Get Purchase Order |
| PUT | `/api/v1/purchase-orders/{po_number}` | Authenticated | Update Purchase Order |
| DELETE | `/api/v1/purchase-orders/{po_number}` | Authenticated | Delete Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/acknowledge` | Owning supplier | Acknowledge Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/transition` | `procurement_manager` | Transition Purchase Order |
| GET | `/api/v1/purchase-orders/{po_number}/events` | Authenticated | Retrieve Purchase Order events |
| POST | `/api/v1/purchase-orders/bulk-send` | `procurement_manager` | Bulk send Purchase Orders |

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

| Method | Endpoint | Authentication / Role | Description |
| ------ | -------- | --------------------- | ----------- |
| GET | `/api/v1/invoices` | Authenticated | List invoices |
| POST | `/api/v1/invoices` | Authenticated | Create invoice |
| GET | `/api/v1/invoices/{supplier_id}/{invoice_number}` | Authenticated | Get invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Authenticated / endpoint-specific authorization | Transition invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust` | `compliance_officer` | Adjust disputed invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Owning supplier | Upload invoice PDF |
| GET | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Authenticated / supplier-scoped | Obtain invoice document URL |

Invoice identity is scoped by:

```text
(supplier_id, invoice_number)
```

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

Invoice documents are stored in **MinIO**, an S3-compatible object storage service.

The actual PDF binary is stored in MinIO rather than the local application filesystem.

The application keeps the document/object reference needed to locate the file.

### Upload

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

Invoice document uploads are restricted to PDF documents.

The upload operation validates:

```text
Authentication

Supplier ownership

Content type

PDF file signature

Maximum file size
```

The current invoice PDF size limit is:

```text
10 MB
```

A valid PDF is then stored as an object in MinIO.

### Download

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The download operation does not stream the PDF through the Supplier Portal application.

Instead, after authentication and authorization, the service generates a **short-lived presigned URL** for the stored MinIO object.

The flow is:

```text
Authenticated Request
        │
        ▼
Find Invoice
        │
        ▼
Verify Supplier Ownership
        │
        ▼
Find Stored Object Reference
        │
        ▼
Check Object Exists in MinIO
        │
        ▼
Generate Short-Lived Presigned URL
        │
        ▼
Return URL
```

The security rule is:

```text
Authorize first
      ↓
Generate presigned URL second
```

A presigned URL must never be generated before the authenticated user is authorized to access the requested document.

Expected behavior:

```text
Own document
    → 200 + presigned URL

Other supplier's document
    → 403 Forbidden

Document does not exist in MinIO
    → 404 Not Found

MinIO unavailable
    → 503 Service Unavailable
```

Invoice documents and supplier onboarding documents use different validation rules.

Supplier onboarding supports:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

Invoice documents are:

```text
PDF only
Maximum 10 MB
```

---

## Supplier Onboarding Document APIs

Supplier onboarding documents are also stored in MinIO.

The onboarding document flow follows the same storage principle:

```text
Upload
  ↓
Validate file
  ↓
Authorize supplier
  ↓
Store object in MinIO
  ↓
Store object reference
```

Downloads are authorized against the authenticated supplier before a presigned URL is generated.

Supplier A cannot obtain a presigned URL for Supplier B's onboarding document.

---

## GraphQL API

The Supplier Portal exposes a Strawberry GraphQL API at:

```http
/graphql
```

GraphQL authentication uses the same Platform Service authentication mechanism as the protected REST APIs.

The GraphQL context contains the authenticated user information.

The GraphQL layer currently provides operations for:

```text
Purchase Orders

Invoices

Supplier Documents
```

The GraphQL API also provides the Purchase Order acknowledgement mutation.

### GraphQL Query Operations

The available query areas include:

```text
purchaseOrder
purchaseOrders

invoice
invoices

documents
```

Conceptually:

```text
Frontend / Apollo Client
        │
        ▼
     /graphql
        │
        ▼
GraphQL Resolver
        │
        ├── Authentication
        ├── Supplier Scope Check
        ├── Business Logic
        │
        ▼
Existing Supplier Portal Services
        │
        ▼
GraphQL Response
```

### Purchase Order Query

A single Purchase Order can be queried by Purchase Order number.

Supplier users can only retrieve a Purchase Order belonging to their authenticated supplier.

Example:

```text
Authenticated supplier = SUP001

Requested PO = PO-SUP002-001
PO supplier = SUP002

        ↓

Resolver supplier-scope check

        ↓

No Purchase Order returned
```

This supplier check is performed inside the GraphQL resolver.

### Purchase Order Collection

Purchase Orders support cursor-based pagination.

The pagination model uses:

```text
first
after
hasNextPage
endCursor
```

The `first` value is bounded by the GraphQL implementation.

The resolver applies supplier filtering before pagination so that supplier users cannot infer or receive another supplier's records through pagination.

Conceptually:

```text
All Purchase Orders
        │
        ▼
Supplier Scope Filter
        │
        ▼
Authorized Purchase Orders
        │
        ▼
Cursor Pagination
        │
        ▼
GraphQL Connection
```

### Invoice Queries

GraphQL supports invoice queries and invoice collections.

Supplier users are automatically scoped to invoices belonging to their authenticated supplier.

The resolver applies authorization before returning invoice data.

### Document Query

GraphQL exposes supplier document data through the document query.

Supplier users can only retrieve documents belonging to their authenticated supplier.

The resolver performs supplier-level authorization before returning document information.

### Acknowledge Purchase Order Mutation

The GraphQL API provides a Purchase Order acknowledgement mutation.

Conceptually:

```text
acknowledgePurchaseOrder
        │
        ▼
Authenticate User
        │
        ▼
Find Purchase Order
        │
        ▼
Verify Supplier Ownership
        │
        ▼
Call Existing PO Acknowledge Service
        │
        ▼
Return Updated Purchase Order
```

A supplier cannot acknowledge another supplier's Purchase Order.

A cross-supplier acknowledgement request returns no Purchase Order result and does not modify the protected Purchase Order.

### Resolver-Level Supplier Scoping

Supplier scoping is enforced inside every applicable resolver.

The GraphQL security model is therefore:

```text
GraphQL Request
      │
      ▼
Authenticated User
      │
      ▼
Resolver
      │
      ▼
Supplier Scope Check
      │
      ├── Same supplier → Continue
      │
      └── Different supplier → No resource returned
```

Supplier scoping is not delegated only to the `/graphql` route.

This prevents a resolver from accidentally exposing another supplier's data.

---

## Procure-to-Pay APIs

The Supplier Portal exposes P2P operations covering:

| Stage | Purpose |
| ---------------- | ------------------------------------------------------------------ |
| Shipment | Progress an acknowledged P2P transaction to shipped |
| Goods Receipt | Record received goods and progress the P2P state |
| Invoice | Submit an invoice after the required receipt state |
| Three-Way Match | Compare PO, receipt, and invoice data |
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

| Method | Endpoint | Authentication / Scope | Description |
| ------ | ------------------------------------------- | ---------------------- | ----------------------------------------------- |
| GET | `/api/v1/suppliers/{supplier_id}/stats` | Authenticated | Supplier operational statistics |
| GET | `/api/v1/suppliers/{supplier_id}/scorecard` | Authenticated | Supplier performance and self-service scorecard |

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

Supplier users without a valid `supplier_id` are rejected with:

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

Onboarding detail operations are supplier-scoped where supplier ownership applies.

The onboarding service also exposes the supplier's active state so that business operations such as Purchase Order creation can enforce onboarding completion.

Onboarding document uploads validate:

```text
Supported document type

File extension

Empty file

Maximum file size

Supplier ownership
```

Supported onboarding document types are:

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

The configured client timeout is:

```text
5 seconds
```

Decision handling:

| Compliance result | Supplier Portal behavior |
| ----------------- | ------------------------ |
| `CLEAR` | Supplier can become active |
| `BLOCK` | Activation rejected with `409 Conflict` |
| `REVIEW` | Activation rejected with `409 Conflict` |
| Service unavailable | Activation blocked with `503 Service Unavailable` |
| Unusable/unsuccessful upstream response | `502 Bad Gateway` |

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

Goods Receipt `receipt_date` is also used as the actual delivery date for supplier delivery-performance calculations.

When multiple receipts exist, the applicable/latest receipt date is used by the scorecard/statistics implementation.

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

Discrepancies are flagged for human review.

A discrepancy does not automatically approve payment.

A successfully matched transaction can continue toward payment approval through the P2P state machine.

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

| Method | Endpoint | Authentication / Role | Description |
| ------ | --------------------------------------------------- | ------------------------- | ------------------------- |
| POST | `/api/v1/supplier-contracts` | `procurement_manager` | Create supplier contract |
| GET | `/api/v1/supplier-contracts` | Authenticated / scoped | List supplier contracts |
| GET | `/api/v1/supplier-contracts/expiring` | Authenticated / scoped | List expiring contracts |
| GET | `/api/v1/supplier-contracts/{contract_id}` | Authenticated / scoped | Get contract |
| PUT | `/api/v1/supplier-contracts/{contract_id}` | `procurement_manager` | Update contract |
| POST | `/api/v1/supplier-contracts/{contract_id}/activate` | `procurement_manager` | Activate draft contract |
| POST | `/api/v1/supplier-contracts/{contract_id}/renew` | `procurement_manager` | Renew contract |
| GET | `/api/v1/supplier-contracts/{contract_id}/history` | Authenticated / scoped | Retrieve contract history |

Contract operations enforce supplier ownership where supplier-facing access applies.

Contract lifecycle operations are restricted according to the configured procurement authorization rules.

---

## R5 API Security Summary

The protected API model is:

| Resource | Supplier Access | Internal Role Access |
| ------------------------------------------ | --------------- | ----------------------------------------------- |
| Own PO | Allowed | According to role |
| Other supplier PO | `403 Forbidden` | According to role |
| Own invoice | Allowed | According to role |
| Other supplier invoice | `403 Forbidden` | According to role |
| Own invoice document | Allowed | According to role |
| Other supplier document | `403 Forbidden` | According to role |
| Own statistics | Allowed | According to role |
| Other supplier statistics | `403 Forbidden` | According to role |
| Own scorecard | Allowed | According to role |
| Other supplier scorecard | `403 Forbidden` | According to role |
| Own contract where supplier access applies | Allowed | According to role |
| Other supplier contract | `403 Forbidden` | According to role |
| Missing supplier identity | `403 Forbidden` | Not applicable to supplier-scoped supplier access |

The R5 security model combines:

```text
Authentication

      +

Role Authorization

      +

Supplier Data Isolation
```

A successful token verification alone is not sufficient for supplier access.

The authenticated supplier identity must match the supplier associated with the requested supplier-scoped resource.

For document downloads, authorization occurs before a MinIO presigned URL is generated.

For GraphQL, supplier scoping is enforced inside the applicable resolver.

---

## API Error Handling Summary

The Supplier Portal uses explicit HTTP responses for authentication, authorization, validation, resource, storage, and integration failures.

Common responses include:

```text
400 Bad Request
    → Invalid request, invalid state transition, invalid file, or business validation failure

401 Unauthorized
    → Missing or invalid authentication

403 Forbidden
    → Insufficient role or supplier-scope violation

404 Not Found
    → Requested resource or stored document does not exist

409 Conflict
    → Business-rule conflict such as Compliance BLOCK/REVIEW or duplicate resource

422 Unprocessable Entity
    → FastAPI request/schema validation failure

502 Bad Gateway
    → Upstream Compliance Service returned an unusable or unsuccessful response

503 Service Unavailable
    → Platform authentication, Compliance, or MinIO dependency unavailable
```

The exact response depends on the operation and failure condition.

---

# 17. HTTP Response Codes

| Status | Meaning |
| -----: | -------------------------------------------------------------------------------------------- |
| 200 | Successful request |
| 201 | Resource created |
| 400 | Business-rule or input validation failure |
| 401 | Authentication required, invalid, or expired |
| 403 | Authenticated user is not authorized or supplier scope does not match |
| 404 | Resource not found |
| 409 | Duplicate resource, conflicting resource state, or business-rule conflict |
| 422 | FastAPI request/schema validation failure |
| 502 | Downstream Compliance Service returned an unusable or unsuccessful response |
| 503 | Platform authentication, Compliance, or MinIO service unavailable |

For protected supplier-scoped resources, the implementation applies supplier ownership checks on affected detail operations.

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

MinIO unavailable
        → 503 Service Unavailable

Requested stored document does not exist
        → 404 Not Found
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
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

The application also requires configuration for the MinIO/S3-compatible document-storage dependency according to the project's environment configuration.

Environment-specific values should be supplied through `.env` or the deployment environment rather than hard-coded in application code.

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
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
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

## MinIO Document Storage Configuration

Round 12 uses MinIO as the object-storage backend for Supplier Portal documents.

The storage architecture is:

```text
Supplier Portal
      │
      ▼
MinIO / S3-compatible API
      │
      ▼
Object Storage
```

MinIO is used for:

```text
Invoice PDFs

Supplier onboarding documents
```

The application stores object references/metadata while the actual document binary is stored in MinIO.

For local development, MinIO runs as a separate service/container.

The application should use the configured MinIO endpoint, bucket, and credentials supplied through the project's environment configuration.

The storage dependency must not be replaced with local filesystem storage.

The important storage principle is:

```text
Document binary
      →
MinIO

Document reference / metadata
      →
Supplier Portal application state
```

Document downloads use short-lived presigned URLs.

The authorization order is:

```text
Authenticate
      ↓
Check supplier ownership
      ↓
Locate object
      ↓
Generate presigned URL
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

The current implementation stores contract state in application memory.

`auto_renew` is stored as a contract configuration value.

It does not currently trigger an automatic background renewal process.

---

## GraphQL Configuration

The GraphQL API is mounted by the Supplier Portal application at:

```text
/graphql
```

The GraphQL layer uses:

```text
Strawberry GraphQL
```

and is integrated with FastAPI through a GraphQL router.

The GraphQL context receives the authenticated user from the existing Supplier Portal authentication dependency.

The GraphQL layer does not introduce a separate authentication mechanism.

Conceptually:

```text
Authorization Header
        ↓
Platform Verification
        ↓
Supplier Portal Auth Context
        ↓
GraphQL Context
        ↓
Resolver-Level Authorization
```

---

## Environment Template

The project provides:

```text
.env.example
```

The example configuration should contain the required service dependencies, including:

```env
# Platform Service
PLATFORM_AUTH_URL=http://127.0.0.1:8005

# Compliance Service
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

MinIO/object-storage settings should also be supplied according to the project's `.env.example` configuration.

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
Strawberry GraphQL
S3-compatible object-storage client
```

`python-multipart` is required for multipart file-upload handling.

The exact test dependency versions should be taken from the project's dependency configuration rather than hard-coded in the README.

---

## Step 5 — Configure Environment

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Configure the required service and storage settings.

At minimum, the local service configuration includes:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

The Platform Service must be available when running authenticated Supplier Portal endpoints.

The Compliance Service must be available when activating suppliers.

MinIO must be available when uploading or downloading stored documents.

---

# 20. Running the Services

The Supplier Portal depends on multiple service-level integrations:

```text
Platform Service
      ↓
Authentication

Compliance Service
      ↓
Supplier Activation Compliance Check

MinIO
      ↓
Document Object Storage
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
http://127.0.0.1:8003
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

The Compliance Service decision model uses:

```text
CLEAR
BLOCK
REVIEW
```

Only:

```text
CLEAR
```

with a successful clearance allows activation.

`BLOCK` and `REVIEW` leave the supplier outside the `active` state.

If the Compliance Service is unreachable, times out, or returns an unusable response, activation is blocked.

---

## MinIO Object Storage

MinIO provides S3-compatible object storage for Supplier Portal documents.

For local development, MinIO runs separately from the Supplier Portal application.

The architecture is:

```text
Supplier Portal
      │
      │ S3-compatible API
      ▼
MinIO
      │
      ▼
Stored Document Objects
```

Documents stored through the Supplier Portal include:

```text
Invoice PDFs

Supplier onboarding documents
```

The application does not use the old local `uploads/` directory as the document-storage mechanism.

Document download flow:

```text
Client
   │
   ▼
Supplier Portal
   │
   ├── Authenticate
   │
   ├── Verify supplier ownership
   │
   ├── Locate MinIO object
   │
   └── Generate short-lived presigned URL
             │
             ▼
          MinIO
             │
             ▼
       Document Download
```

If MinIO is unavailable, document operations that require storage access fail with an appropriate service-unavailable response.

If the requested object does not exist, the document operation returns `404 Not Found`.

Cross-supplier document access is rejected before a presigned URL is generated.

---

## Supplier Portal Service

From the Supplier Portal project directory:

```powershell
python -m uvicorn app.main:app --reload --port 8004
```

The Supplier Portal runs at:

```text
http://127.0.0.1:8004
```

The root endpoint can be used to confirm that the service is running:

```http
GET /
```

The GraphQL endpoint is:

```http
POST /graphql
```

Protected GraphQL requests require authentication.

---

## Three-Service Business Architecture

The Supplier Portal business architecture is:

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
┌──────────────────────────────────┐
│        Supplier Portal           │
│                                  │
│          Port 8004               │
│                                  │
│ REST API + GraphQL                │
│ PO / Invoice / P2P               │
│ Statistics / Scorecard           │
│ Contracts / Onboarding           │
│ Disputes / Analytics             │
└───────────┬──────────────┬───────┘
            │              │
            │              │
            │              │ S3-compatible API
            │              ▼
            │       ┌───────────────┐
            │       │    MinIO      │
            │       │               │
            │       │ Document      │
            │       │ Object Store  │
            │       └───────────────┘
            │
            │ /api/v1/compliance/internal-check
            ▼
┌─────────────────────────────┐
│      Compliance Service     │
│                             │
│        Port 8003            │
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

The same authenticated identity is made available to GraphQL resolvers through the GraphQL context.

---

## GraphQL Request Flow

```text
Frontend / Apollo Client
          │
          │ GraphQL Query / Mutation
          ▼
       /graphql
          │
          ▼
   GraphQL Context
          │
          ▼
   Authenticated User
          │
          ▼
       Resolver
          │
          ├── Supplier Scope Check
          │
          ├── Business Validation
          │
          ▼
 Existing Supplier Portal Service
          │
          ▼
   GraphQL Response
```

The important security property is that supplier authorization is performed at the resolver level.

```text
Supplier SUP001
      │
      ▼
GraphQL Resolver
      │
      ▼
Requested Resource SUP002
      │
      ▼
Scope mismatch
      │
      ▼
Resource not returned
```

This prevents the GraphQL layer from bypassing the R5 supplier-isolation rules.

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

## Document Storage Flow

Round 12 uses MinIO instead of local filesystem storage.

```text
Client
   │
   ▼
Supplier Portal
   │
   ├── Validate document
   │
   ├── Authenticate
   │
   ├── Verify supplier ownership
   │
   ▼
Document Storage Service
   │
   ▼
MinIO
   │
   ▼
Object Stored
```

For downloads:

```text
Client
   │
   ▼
Supplier Portal
   │
   ├── Authenticate
   │
   ├── Verify ownership
   │
   ├── Check object
   │
   ▼
Generate Presigned URL
   │
   ▼
Client accesses MinIO object
```

The presigned URL is short-lived.

A supplier cannot obtain a presigned URL for another supplier's document.

The key security rule is:

```text
Supplier authorization
        ↓
Object lookup
        ↓
Presigned URL generation
```

Never reverse this order.

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

## GraphQL Implementation Structure

The GraphQL implementation is organized under:

```text
app/graphql/
```

Core files include:

```text
app/graphql/__init__.py
app/graphql/context.py
app/graphql/queries.py
app/graphql/schema.py
app/graphql/types.py
app/graphql/mutations.py
```

Responsibilities:

```text
context.py
    → Authenticated GraphQL request context

queries.py
    → Purchase Order, Invoice, and Document resolvers
    → Supplier scoping
    → Cursor pagination

mutations.py
    → Purchase Order acknowledgement mutation

types.py
    → GraphQL types and enums

schema.py
    → Strawberry GraphQL schema

main.py
    → Mounts GraphQL at /graphql
```

The GraphQL layer reuses the existing Supplier Portal business services instead of duplicating business logic.

---

## Testing the Main Integrations

The Supplier Portal test suite covers:

```text
REST API authentication

Supplier ownership and scoping

Purchase Orders

Invoices

Invoice documents

MinIO document storage

Presigned URL generation

Cross-supplier document access rejection

Supplier onboarding

Compliance integration

P2P lifecycle

Three-way matching

Supplier statistics

Supplier scorecard

Supplier contracts

GraphQL queries

GraphQL cursor pagination

GraphQL Purchase Order acknowledgement

GraphQL resolver-level supplier scoping
```

Examples of focused test commands:

```powershell
python -m pytest -q tests/test_graphql.py
```

```powershell
python -m pytest -q tests/test_document_storage_service.py
```

```powershell
python -m pytest -q tests/test_invoice_document_download.py
```

```powershell
python -m pytest -q tests/test_supplier_document_download.py
```

```powershell
python -m pytest -q tests/integration/test_minio_document_storage.py
```

The full regression suite should be run before merging changes:

```powershell
python -m pytest -q
```

The Round 12 and Round 13 implementation has been regression-tested together with the existing Supplier Portal functionality.
# 21. Swagger Documentation

FastAPI automatically provides interactive REST API documentation for the Supplier Portal.

When the Supplier Portal is running on port `8004`, open Swagger UI at:

```text
http://127.0.0.1:8004/docs
```

Alternative ReDoc documentation:

```text
http://127.0.0.1:8004/redoc
```

Swagger documents the REST APIs exposed by the Supplier Portal.

The Strawberry GraphQL API is available separately at:

```text
http://127.0.0.1:8004/graphql
```

GraphQL operations are not represented as individual REST endpoints in Swagger.

---

## Swagger API Coverage

Swagger can be used to inspect and test supported Supplier Portal REST operations, including:

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
Invoice document URL generation

Supplier onboarding
Supplier onboarding documents

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

Swagger therefore exposes the same REST authorization and supplier-scoping rules as normal API clients.

---

## Swagger Document-Storage Behavior

Invoice and supplier-onboarding documents are stored in MinIO.

Swagger can be used to test document upload and document-download operations.

For invoice documents:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

uploads the PDF to MinIO.

The corresponding download operation:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

returns a short-lived presigned URL after authorization.

The download flow is:

```text
Authenticated Request
        │
        ▼
Supplier Ownership Check
        │
        ▼
Object Lookup in MinIO
        │
        ▼
Generate Presigned URL
        │
        ▼
Return URL
```

Supplier authorization occurs before presigned URL generation.

Cross-supplier access is rejected:

```text
SUP001 token
      │
      ▼
Request SUP002 document
      │
      ▼
403 Forbidden
```

---

# 22. Testing

The Supplier Portal uses **Pytest** for automated testing.

The test suite covers the application's REST APIs, business services, integrations, document storage, and GraphQL layer.

Major test areas include:

```text
Core business logic

Purchase Order lifecycle
P2P state transitions
Shipment processing
Goods Receipt processing
Partial Goods Receipt support

Invoice lifecycle
P2P invoice integration

Three-way matching
Quantity discrepancy detection
Price discrepancy detection

Supplier onboarding
Compliance Service integration
Compliance failure handling

Supplier onboarding document validation

Invoice document storage
MinIO object storage
Presigned URL generation
Document download authorization
Cross-supplier document protection
Missing-object handling
MinIO availability failures

Supplier statistics
Supplier scorecards
Supplier self-service analytics

Supplier contract lifecycle
Contract renewal
Contract expiry handling
Contract term-change audit history

Historical dispute-resolution suggestions

Authentication
Role-based authorization
Supplier-level resource ownership
Collection-level supplier filtering

Round 5 supplier-scoping requirements
Rounds 6–8 functional milestones
Rounds 9–11 functional requirements
Round 12 MinIO document-storage requirements
Round 13 GraphQL requirements
```

Run the complete test suite with:

```powershell
python -m pytest -v
```

The test suite should be executed using the active Python environment.

The README intentionally does not hard-code a particular pytest version. Dependency versions should be taken from the project's current dependency configuration.

---

## Purchase Order Tests

Run the Purchase Order test suite using the project's Purchase Order test module.

The Purchase Order tests cover:

```text
PO creation
PO retrieval
PO listing
PO update
PO deletion
Duplicate PO handling

PO acknowledgement

Legal state transitions
Illegal state transitions
Cancellation
Terminal states

Transition history
Event retrieval
Actor tracking
Timestamp tracking

Delivery tracking
Actual delivery date from Goods Receipt
Multiple Goods Receipt handling

Bulk PO sending

Active supplier enforcement
Unregistered supplier rejection
Inactive supplier rejection
```

### R5 Authorization and Supplier-Scoping Tests

The Purchase Order tests additionally validate:

```text
Supplier can access its own Purchase Order

Supplier cannot access another supplier's Purchase Order

Supplier can acknowledge its own Purchase Order

Supplier cannot acknowledge another supplier's Purchase Order

Supplier can view its own Purchase Order events

Supplier cannot view another supplier's Purchase Order events

Supplier can view only its own Purchase Orders through the PO list endpoint

Supplier cannot retrieve another supplier's Purchase Orders through the PO list endpoint

Supplier can update its own Purchase Order

Supplier cannot update another supplier's Purchase Order

Supplier can delete its own Purchase Order

Supplier cannot delete another supplier's Purchase Order

Supplier cannot perform procurement-manager-only PO transitions

Supplier cannot perform procurement-manager-only bulk PO sending

Unauthorized roles are rejected

Supplier ownership is validated using authenticated supplier_id
```

---

## Invoice Tests

Run:

```powershell
python -m pytest tests/test_invoices.py -v
```

The Invoice tests cover:

```text
Valid invoice creation
Invoice retrieval
Invoice listing
Duplicate invoice protection

Invalid invoice number
Invalid supplier ID
Missing Purchase Order
Invalid Purchase Order status
Purchase Order supplier mismatch

Invoice item validation
Quantity validation
Unit-price validation
Invoice amount validation
Partial invoicing

Invoice transitions
Disputes
Adjustments

Invoice document upload
PDF signature validation
Content-Type validation
10 MB file-size limit

Invoice document retrieval
Missing document handling

Supplier scoping
Compliance-officer authorization
```

Invoice creation does **not** reject price differences solely because they exceed the three-way-match tolerance.

The configured `5%` tolerance is used by the **three-way matching process** to identify price discrepancies.

### R5 Authorization and Supplier-Scoping Tests

The Invoice tests additionally validate:

```text
Supplier can access its own invoice

Supplier cannot access another supplier's invoice

Supplier can view only its own invoices through the invoice list endpoint

Supplier cannot retrieve another supplier's invoices through the invoice list endpoint

Supplier cannot transition another supplier's invoice

Supplier cannot upload a document for another supplier's invoice

Supplier cannot download another supplier's invoice document

Supplier cannot create an invoice for another supplier

Supplier cannot perform compliance-only invoice adjustment

Compliance officer can perform authorized invoice adjustment

Authenticated supplier identity is matched against invoice supplier_id

Supplier ownership is enforced for supplier-facing invoice endpoints
```

---

## Invoice Document Storage Tests

Round 12 introduced MinIO-backed document storage.

The document-storage test coverage validates:

```text
MinIO object creation

Object existence checks

Object retrieval

Object storage references

Presigned URL generation

Missing object handling

MinIO service failures

Invoice document upload

Invoice document download

Supplier onboarding document storage

Supplier onboarding document download
```

The document tests also validate that authorization happens before URL generation.

The important security requirement is:

```text
Authenticate
    ↓
Authorize supplier ownership
    ↓
Locate object
    ↓
Generate presigned URL
```

A supplier must never receive a presigned URL for another supplier's document.

### Cross-Supplier Document Test

The security test explicitly attempts:

```text
Supplier A
    ↓
Request Supplier B document
    ↓
Supplier ownership check
    ↓
403 Forbidden
```

The test verifies that no unauthorized document URL is returned.

### Missing Object Test

When the MinIO service is available but the requested object does not exist:

```text
Document request
      ↓
MinIO lookup
      ↓
Object not found
      ↓
404 Not Found
```

### MinIO Unavailable Test

When MinIO cannot be reached:

```text
Document request
      ↓
MinIO unavailable
      ↓
503 Service Unavailable
```

These tests distinguish:

```text
Authorization failure
        ≠
Missing object
        ≠
Storage dependency failure
```

---

## MinIO Integration Tests

The MinIO integration tests use a real local MinIO service/container rather than only mocking the storage client.

Run:

```powershell
python -m pytest -q tests/integration/test_minio_document_storage.py
```

The integration coverage validates the complete storage path:

```text
Supplier Portal
      ↓
Document Storage Service
      ↓
MinIO
      ↓
Stored Object
```

and the retrieval path:

```text
Supplier Portal
      ↓
Authorize Supplier
      ↓
Locate MinIO Object
      ↓
Generate Presigned URL
      ↓
Document Access
```

This verifies that the application is using object storage rather than falling back to local filesystem storage.

---

## Document Storage Service Tests

Run:

```powershell
python -m pytest -q tests/test_document_storage_service.py
```

These tests cover the storage-service behavior independently from the HTTP routes.

Coverage includes:

```text
Object upload
Object existence
Object retrieval
Object deletion where supported
Missing-object behavior
MinIO/S3 error handling
Presigned URL generation
Storage dependency failure handling
```

---

## Invoice Document Download Tests

Run:

```powershell
python -m pytest -q tests/test_invoice_document_download.py
```

The tests validate:

```text
Authenticated document access

Supplier ownership

Valid document URL generation

Missing document behavior

Storage error behavior

Cross-supplier access rejection

Short-lived presigned URL behavior
```

---

## Supplier Document Download Tests

Run:

```powershell
python -m pytest -q tests/test_supplier_document_download.py
```

The tests validate:

```text
Supplier onboarding document ownership

Authenticated access

Cross-supplier access rejection

Missing document handling

Presigned URL generation

MinIO-backed document retrieval
```

---

## Procure-to-Pay and Milestone Testing

The test suite validates the implemented procure-to-pay and supplier workflow milestones.

### P2P Workflow Tests

The P2P tests validate:

```text
P2P state initialization

Valid P2P transitions
Invalid P2P transitions

Shipment progression

Goods Receipt creation
Partial Goods Receipt support
Goods Receipt validation

Purchase Order existence validation
Supplier ownership validation

Item validation
Quantity validation
Duplicate Goods Receipt item protection
Extra item rejection

Invoice submission after the required receipt state
Invoice submission advancing the P2P workflow
Invalid invoice submission not advancing P2P state
Duplicate invoice protection

Three-way match processing
Quantity discrepancy detection
Price discrepancy detection

Discrepancy routing for human review

Prevention of automatic payment approval for discrepancies

Payment approval progression after successful matching
```

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

```text
Supplier registration
Document collection
Mock verification
Approval

Compliance Service check

Compliance CLEAR decision
Compliance BLOCK decision
Compliance REVIEW decision

Compliance Service unavailable
Compliance timeout
Compliance service error
Invalid Compliance response

Fail-closed activation
Approval preservation when activation is blocked
Activation only after Compliance CLEAR

Valid onboarding state transitions
Invalid onboarding transitions

Supplier-level authorization
Cross-supplier access protection

Active-supplier enforcement for Purchase Order creation

Supported onboarding document types
Empty document rejection
File-extension validation
MIME-type validation
10 MB document-size limit
```

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

Invalid Compliance response
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

The integration is fail-closed.

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

The tolerance is inclusive:

```text
PO price = 100

95  → Match
100 → Match
105 → Match
106 → Price discrepancy
```

---

## Historical Dispute-Resolution Suggestion Tests

Historical dispute-resolution suggestions are tested independently from current dispute resolution.

The tests validate:

```text
Historical resolved matches are considered

Current unresolved disputes are not treated as historical evidence

Unresolved historical disputes are ignored

Price mismatch patterns can produce correct_invoice

Quantity mismatch patterns can produce credit_note

Unclassified historical reasons are ignored

No-evidence cases return no suggested action

Current resolved/matched cases cannot be treated as unresolved suggestions

Unknown matches return 404

Supplier scope is enforced

Compliance-officer authorization is enforced

Suggestions are read-only

Suggestion generation does not mutate three-way-match state
```

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

```text
Supplier statistics
Supplier not found

Purchase Order count

On-time delivery
Late delivery
Mixed delivery performance

Unfulfilled Purchase Orders
Future-due Purchase Orders
Past-due unfulfilled Purchase Orders

Delivery exactly on expected date

Actual delivery date from Goods Receipt
Missing delivery date

Average invoice cycle time
Invoice line-level po_number handling

Date normalization
Invalid dates
Negative cycle times

Scorecard calculation
Dispute rate
Invoice accuracy
Dispute performance
Overall score

Scorecard details
Invoice-only suppliers

Supplier scoping
Schema validation
Percentage boundaries
Monthly trend calculations

Supplier self-service scorecard access
```

For fulfilled Purchase Orders, the actual delivery date is derived from the applicable/latest Goods Receipt `receipt_date`.

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

```text
Contract creation
Contract retrieval
Contract listing

Duplicate contract-number protection

Active-supplier validation
Contract date validation

Draft-to-active transition

Contract updates

Expiry detection
Expiring-contract queries

Renewal
Renewal date validation
Renewal history

Contract transition history
Term-change audit history

Actor information in history
Reason information in history

No-op update without unnecessary history entry

Supplier ownership and scoping

Procurement-manager authorization
```

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

```text
Supplier can view its own scorecard

Supplier cannot view another supplier's scorecard

Supplier identity is matched against authenticated supplier_id

Supplier without supplier_id is rejected

Scorecard contains on-time delivery percentage

Scorecard contains dispute rate percentage

Scorecard contains invoice accuracy

Scorecard contains overall performance information

Internal authorized roles can access supplier data according to their role permissions
```

Example:

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

The authentication and authorization tests validate the authentication path between the Supplier Portal and Platform Service.

Tests cover:

```text
Valid access-token verification
Missing authentication token
Invalid authentication token
Expired authentication token

Authentication service unavailable
Authentication service timeout
Unexpected authentication-service response
Invalid authentication-service response

Authentication response with valid = false

Missing user_id
Missing user role

Supplier identity returned by Platform Service
supplier_id propagation

X-Request-ID generation and forwarding

Allowed role authorization
Unauthorized role rejection

Procurement-manager authorization
Compliance-officer authorization

Role-based access control
Authentication failure handling
```

---

## Authentication-Required Endpoint Tests

The project includes dedicated protection tests for authentication-required routes.

These tests verify that protected endpoints cannot be accessed without authentication.

The tests use the real authentication dependency rather than relying only on the normal authenticated test overrides.

The protected-route checks confirm that requests without an `Authorization` header are rejected.

Expected unauthenticated responses depend on the endpoint/authentication configuration and may be:

```text
401 Unauthorized
```

or:

```text
403 Forbidden
```

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
Supplier without supplier_id
        → 403 Forbidden

Supplier accessing another supplier's resource
        → 403 Forbidden

Unauthorized role
        → 403 Forbidden

Missing token
        → 401 Unauthorized

Invalid token
        → 401 Unauthorized

Authentication service failure
        → 503 Service Unavailable
```

---

## R12 MinIO Security Validation

Round 12 adds object-storage-specific security tests.

The tests verify that:

```text
Documents are stored in MinIO

Documents are not served from the old local filesystem path

Supplier ownership is checked before document access

Cross-supplier document access is rejected

Presigned URLs are generated only after authorization

Missing MinIO objects return 404

MinIO availability failures return 503
```

The most important security test is:

```text
Supplier A
    ↓
Requests Supplier B document
    ↓
Supplier ownership check
    ↓
403 Forbidden
    ↓
No presigned URL generated
```

This prevents a supplier from using a known document identifier or object reference to bypass supplier isolation.

---

## R13 GraphQL Tests

Round 13 adds dedicated GraphQL test coverage.

Run:

```powershell
python -m pytest -q tests/test_graphql.py
```

The GraphQL tests validate:

```text
GraphQL schema creation

GraphQL authentication

Purchase Order queries

Purchase Order collection queries

Cursor pagination

first pagination argument

after cursor handling

hasNextPage

endCursor

Invoice queries

Invoice collection queries

Supplier document queries

Purchase Order acknowledgement mutation

Resolver-level supplier authorization

Cross-supplier Purchase Order protection

Cross-supplier invoice protection

Cross-supplier document protection
```

### GraphQL Supplier-Scoping Test

The key R13 security requirement is tested directly inside the resolver.

Example:

```text
Authenticated supplier
        ↓
SUP001
        ↓
GraphQL purchaseOrder query
        ↓
Requested PO belongs to SUP002
        ↓
Resolver supplier-scope check
        ↓
No Purchase Order returned
```

The test confirms that Supplier A cannot retrieve Supplier B's Purchase Order by ID.

### GraphQL Mutation Scoping

The acknowledgement mutation also performs supplier ownership validation before invoking the existing Purchase Order service.

Example:

```text
SUP001
  ↓
acknowledgePurchaseOrder(SUP002 PO)
  ↓
Resolver scope check
  ↓
No mutation performed
```

The protected Purchase Order remains unchanged.

---

## R13 GraphQL Pagination Tests

GraphQL Purchase Order, invoice, and document collections use cursor-based pagination.

The tests validate:

```text
First page retrieval

after cursor retrieval

Correct edge ordering

hasNextPage

endCursor

Pagination limits

Invalid cursor handling

Supplier filtering before pagination
```

The important security ordering is:

```text
All records
    ↓
Supplier scope filter
    ↓
Authorized records
    ↓
Cursor pagination
    ↓
GraphQL response
```

This prevents pagination from exposing another supplier's records.

---

## R13 GraphQL Authentication Tests

GraphQL requests use the existing Supplier Portal authentication dependency.

The tests verify:

```text
Missing token
    → Authentication failure

Invalid token
    → Authentication failure

Valid token
    → GraphQL context receives authenticated user
```

The GraphQL context contains the authenticated user and request information required by the resolvers.

GraphQL does not introduce an independent authentication system.

---

## R5 Supplier-Scoping Matrix

The expected access behavior is:

| Request | Expected Result |
| -------------------------------------------------- | ------------------------- |
| Supplier → Own PO | Allowed |
| Supplier → Other supplier PO | `403 Forbidden` |
| Supplier → Own invoice | Allowed |
| Supplier → Other supplier invoice | `403 Forbidden` |
| Supplier → Own invoice document | Allowed |
| Supplier → Other supplier document | `403 Forbidden` |
| Supplier → Own statistics | Allowed |
| Supplier → Other supplier statistics | `403 Forbidden` |
| Supplier → Own scorecard | Allowed |
| Supplier → Other supplier scorecard | `403 Forbidden` |
| Supplier → Own contract | Allowed |
| Supplier → Other supplier contract | `403 Forbidden` |
| Supplier → Own contract history | Allowed |
| Supplier → Other supplier contract history | `403 Forbidden` |
| Supplier without `supplier_id` → Supplier resource | `403 Forbidden` |
| Internal authorized role → Other supplier data | Allowed according to role |

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

## R12–13 Test Coverage Summary

Round 12 validates the migration of document storage to MinIO:

```text
MinIO storage
Presigned URLs
Document ownership
Cross-supplier rejection
Missing-object handling
Storage dependency failures
Invoice PDF storage
Supplier onboarding document storage
```

Round 13 validates the GraphQL portal API:

```text
Strawberry GraphQL schema
Authenticated context
Purchase Order queries
Invoice queries
Document queries
Cursor pagination
Purchase Order acknowledgement mutation
Resolver-level supplier scoping
Cross-supplier resource protection
```

Together, these milestones extend the existing R5 security model into both object storage and GraphQL.

---

## Full Regression Testing

Run the complete Supplier Portal test suite with:

```powershell
python -m pytest -q
```

The full regression suite should be executed after changes to:

```text
Authentication

Supplier scoping

Purchase Orders

Invoices

P2P workflow

Supplier onboarding

Compliance integration

Document storage

MinIO integration

GraphQL resolvers

Supplier statistics

Supplier scorecards

Supplier contracts
```

The goal is to verify that the R12 and R13 additions do not regress the existing Supplier Portal functionality.

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

Invalid transitions return a business-rule validation error.

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

Invoices require an existing Purchase Order.

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

## Invoice Document Rules

Invoice documents must satisfy:

```text
PDF format
Valid PDF signature
application/pdf content type
Maximum 10 MB
Authenticated access
Supplier ownership where supplier scope applies
```

Invoice documents are stored in MinIO.

The actual PDF binary is not stored in the application database.

The application maintains the object reference required to locate the document.

Download access uses:

```text
Authentication
    ↓
Supplier ownership validation
    ↓
MinIO object lookup
    ↓
Short-lived presigned URL
```

A supplier cannot receive a presigned URL for another supplier's invoice document.

Expected failure behavior:

```text
Other supplier document
    → 403 Forbidden

Missing object
    → 404 Not Found

MinIO unavailable
    → 503 Service Unavailable
```

---

## Supplier Onboarding Document Rules

Supplier onboarding documents support:

```text
PDF
JPG
JPEG
PNG
DOC
DOCX
```

Maximum size:

```text
10 MB
```

The upload operation validates:

```text
Authentication
Supplier ownership
File extension
Content type
File content requirements
File size
```

Onboarding documents are stored in MinIO.

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

Expired contracts are represented as:

```text
expired
```

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

Audited changes include fields such as:

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

The endpoint is self-service but remains protected by the same supplier-scoping rules as other supplier-facing resources.

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

For fulfilled Purchase Orders, the actual delivery date is based on the applicable/latest Goods Receipt `receipt_date`.

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

This supports invoices whose Purchase Order relationship is stored at line-item level.

Date values are normalized before cycle-time calculations.

Invalid or negative cycle-time values are not treated as valid operational cycle times.

---

## GraphQL Business Rules

The GraphQL API exposes the existing Supplier Portal business data through a GraphQL interface.

GraphQL does not bypass the existing business rules.

Resolvers must apply:

```text
Authentication
+
Supplier Scope
+
Business Validation
+
Existing Service Logic
```

### GraphQL Purchase Order Rule

A supplier can query only Purchase Orders belonging to the authenticated supplier.

Example:

```text
Authenticated supplier = SUP001

Requested PO supplier = SUP002

        ↓

Resolver scope validation

        ↓

Purchase Order not returned
```

### GraphQL Invoice Rule

Supplier invoice queries are filtered using the authenticated supplier identity.

A supplier cannot retrieve another supplier's invoice through GraphQL.

### GraphQL Document Rule

Supplier document queries are supplier-scoped.

A supplier cannot retrieve another supplier's document through GraphQL.

### GraphQL Acknowledgement Rule

The Purchase Order acknowledgement mutation must verify supplier ownership before calling the existing acknowledgement service.

Therefore:

```text
Supplier owns PO
    → Acknowledgement can proceed

Supplier does not own PO
    → Mutation does not modify PO
```

### GraphQL Pagination Rule

Collection queries use cursor-based pagination.

The implementation applies supplier filtering before pagination:

```text
Source records
      ↓
Authorization / Supplier filtering
      ↓
Cursor pagination
      ↓
GraphQL response
```

This prevents pagination from becoming a data-leak mechanism.

---

## Document Storage Security Rule

Round 12 introduces an explicit object-storage security rule:

```text
Never generate a presigned URL before verifying authorization.
```

The required order is:

```text
Authenticate
      ↓
Identify authenticated supplier
      ↓
Identify requested resource owner
      ↓
Compare supplier identities
      ↓
Locate MinIO object
      ↓
Generate short-lived presigned URL
```

For example:

```text
SUP001 token
      ↓
Request SUP002 document
      ↓
Supplier mismatch
      ↓
403 Forbidden
      ↓
No presigned URL
```

Knowing a document ID, invoice number, or object reference does not bypass supplier authorization.

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

The same principle applies across:

```text
REST endpoints
GraphQL resolvers
Invoice documents
Supplier onboarding documents
Purchase Orders
Invoices
Statistics
Scorecards
Contracts
P2P resources
```

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
* GraphQL purchase-order queries
* GraphQL invoice queries
* GraphQL document queries
* GraphQL acknowledge-PO mutation

Cross-supplier access by supplier users is rejected with:

```text
403 Forbidden
```

A supplier without a valid `supplier_id` is also rejected from supplier-scoped resources:

```text
403 Forbidden
```

Collection endpoints are filtered so supplier users do not receive other suppliers' records.

GraphQL applies the same supplier-scoping rules **inside each resolver**.

For example:

```text
Supplier A
   ↓
GraphQL purchaseOrder(id)
   ↓
Resolver identifies authenticated supplier
   ↓
Resolver checks PO supplier_id
   ↓
Supplier IDs do not match
   ↓
No PO returned
```

Supplier authorization is therefore not dependent only on a REST route-level check.

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
* GraphQL pagination limits
* GraphQL cursor validity

Allowed identifier format:

```regex
^[A-Za-z0-9_-]+$
```

GraphQL pagination limits are bounded so clients cannot request an unbounded collection in a single query.

---

## Document Security

### Invoice Documents

Invoice documents are stored in MinIO using S3-compatible object storage.

Document access is protected through:

* PDF Content-Type validation
* PDF signature validation
* 10 MB size limit
* Supplier ownership validation
* Supplier-scoped object references
* Object existence validation
* Short-lived presigned download URLs
* Authorization before presigned URL generation

The application does **not** expose the MinIO object directly through a permanent public URL.

The download flow is:

```text
Authenticated Request
        ↓
Document Lookup
        ↓
Supplier Ownership Check
        ↓
Object Existence Check
        ↓
Short-Lived Presigned URL
        ↓
Client Downloads From MinIO
```

The critical security rule is:

```text
Never generate a presigned URL
before verifying document ownership.
```

Therefore:

```text
Supplier A requests Supplier B document
        ↓
Ownership validation
        ↓
403 Forbidden
        ↓
No presigned URL generated
```

A missing object while MinIO is available results in a not-found response rather than an authorization bypass.

---

### Supplier Onboarding Documents

Supplier onboarding documents are stored in MinIO.

They are protected through:

* Supported MIME-type validation
* File-extension validation
* 10 MB size limit
* Empty-file validation
* Supplier ownership validation
* Supplier-scoped object keys
* Object existence validation
* Short-lived presigned download URLs
* Authorization before URL generation

Supported onboarding document types:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

---

## MinIO Storage Security

The application uses MinIO as an S3-compatible object-storage service.

The application keeps document metadata/reference information separately from the actual binary object.

The storage flow is:

```text
Supplier Portal
      ↓
Document Validation
      ↓
Supplier Authorization
      ↓
MinIO Object Upload
      ↓
Object Reference Stored
      ↓
Later Download Request
      ↓
Supplier Authorization
      ↓
Short-Lived Presigned URL
```

A supplier knowing another supplier's document identifier or object key does not bypass supplier ownership validation.

MinIO unavailability is treated as a storage dependency failure rather than as a successful upload/download.

---

## GraphQL Security

GraphQL authentication uses the same Platform Service authentication mechanism as protected REST operations.

The GraphQL context contains the authenticated request identity.

Each supplier-scoped resolver performs its own authorization.

Examples include:

```text
purchaseOrder
purchaseOrders
invoice
invoices
documents
acknowledgePurchaseOrder
```

Supplier collection queries apply authorization filtering **before pagination**.

This prevents unauthorized supplier records from entering the paginated result set.

For a single-resource query:

```text
Supplier A
   ↓
purchaseOrder(Supplier B PO)
   ↓
Resolver ownership check
   ↓
null
```

For a collection query:

```text
Supplier A
   ↓
purchaseOrders
   ↓
Filter to Supplier A records
   ↓
Pagination
   ↓
Supplier A results only
```

---

## Contract Audit Security

Contract history records are protected by supplier scope and role authorization.

A supplier can access only its own contract history.

Internal users can access contract information according to their assigned permissions.

Contract history captures the actor and reason for meaningful lifecycle and term changes, supporting accountability for contract modifications.


# 25. Storage

The current implementation uses two different storage approaches:

```text
Business / workflow data
        ↓
In-memory application stores

Uploaded documents
        ↓
MinIO object storage
```

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

---

## Document Object Storage

Round 12 moves uploaded documents from local filesystem storage to MinIO.

The application stores:

```text
Invoice PDF documents
Supplier onboarding documents
```

in MinIO buckets/objects.

The application does not rely on:

```text
uploads/
```

for the active document-storage implementation.

The architecture is:

```text
Windows Development Environment
          ↓
Docker Desktop
          ↓
MinIO Container
          ↓
MinIO S3-Compatible Server
          ↓
Object Storage
```

The actual document binary is stored as an object in MinIO.

The application retains the necessary document metadata/object reference required to locate the object.

---

## Presigned Download URLs

Documents are downloaded through short-lived presigned URLs.

The application first verifies authorization and ownership.

Only after successful authorization does it generate the signed URL.

```text
Download Request
      ↓
Authenticate
      ↓
Validate Supplier Ownership
      ↓
Check Object
      ↓
Generate Short-Lived URL
      ↓
Client Download
```

This prevents a supplier from obtaining a reusable public URL to another supplier's document.

---

## MinIO Failure Behaviour

When MinIO is unavailable:

```text
Application
      ↓
MinIO Request
      ↓
Storage Dependency Failure
      ↓
Service Error
```

The application does not treat the operation as successful.

A storage dependency failure is surfaced as an appropriate service-unavailable response.

When MinIO is running but the requested object does not exist:

```text
MinIO Available
      ↓
Object Lookup
      ↓
Object Missing
      ↓
404 Not Found
```

Cross-supplier access remains an authorization failure:

```text
Wrong Supplier
      ↓
Ownership Check
      ↓
403 Forbidden
```

---

## Application Restart Behaviour

Business data remains in memory:

```text
Application running
      ↓
PO / Invoice / Workflow / Contract data exists
      ↓
Application restart
      ↓
In-memory business data cleared
```

MinIO objects are managed independently from the application's in-memory business stores.

Therefore, restarting the Supplier Portal process does not by itself remove documents already stored in MinIO.

Production deployments should still provide durable database persistence for business metadata and appropriate MinIO backup, retention, and recovery controls.

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

in durable database storage.


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

---

## Supplier Onboarding Workflow

Supplier onboarding is implemented as:

```text
Supplier Registration
          ↓
Document Collection
          ↓
Document Storage in MinIO
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

## Document Download Workflow

Both invoice PDFs and onboarding documents follow the same security pattern:

```text
Authenticated Supplier
          ↓
Request Document
          ↓
Find Document Metadata
          ↓
Validate Supplier Ownership
          ↓
Check MinIO Object
          ↓
Generate Short-Lived Presigned URL
          ↓
Client Downloads Document
```

Cross-supplier request:

```text
Supplier A
    ↓
Supplier B Document
    ↓
Ownership Check
    ↓
403 Forbidden
```

No presigned URL is generated for the unauthorized request.

---

## GraphQL Workflow

Round 13 introduces a GraphQL API for the supplier portal.

The flow is:

```text
Supplier Portal Frontend
          ↓
      Apollo Client
          ↓
       /graphql
          ↓
GraphQL Context / Authentication
          ↓
       Resolver
          ↓
Supplier Ownership Check
          ↓
Existing Service Layer
          ↓
GraphQL Type Conversion
          ↓
       Response
```

Supported GraphQL operations include:

```text
Purchase Order Queries
Invoice Queries
Document Queries
Acknowledge Purchase Order Mutation
```

Collection queries support cursor pagination.

The pagination model is:

```text
first
after
  ↓
Edges
  ↓
PageInfo
  ↓
hasNextPage
endCursor
```

Supplier authorization is applied before pagination.

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
| MinIO Document Storage                      | Complete |
| MinIO Invoice Document Download             | Complete |
| MinIO Supplier Document Download            | Complete |
| Presigned Document URLs                     | Complete |
| Cross-Supplier Document Isolation           | Complete |
| GraphQL API                                 | Complete |
| GraphQL Purchase Order Queries              | Complete |
| GraphQL Invoice Queries                     | Complete |
| GraphQL Document Queries                    | Complete |
| GraphQL Cursor Pagination                   | Complete |
| GraphQL Acknowledge-PO Mutation             | Complete |
| GraphQL Resolver-Level Supplier Scoping     | Complete |
| GraphQL Cross-Supplier PO Testing            | Complete |


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
→ Compliance Check
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


# Rounds 9–11 Completion Status

The Rounds 9–11 implementation extended the Supplier Portal with business-logic integration, contract lifecycle management, dispute intelligence, and supplier self-service analytics.

The previously completed R9–11 functionality remains implemented and tested.

[Existing R9–11 Task 1–6 sections remain unchanged.]


# Round 12 — Milestone 2 Completion Status

## Milestone 2 — MinIO Document Storage

Status:

```text
Complete
```

Round 12 moves invoice PDFs and supplier onboarding documents from local filesystem storage to MinIO.

Implemented capabilities include:

```text
MinIO object storage
Invoice PDF object storage
Supplier onboarding document object storage
Supplier-scoped object references
Object existence validation
Short-lived presigned download URLs
Supplier ownership validation before URL generation
Cross-supplier document rejection
MinIO failure handling
```

The document architecture is:

```text
Supplier Portal
      ↓
Document Validation
      ↓
Supplier Ownership
      ↓
MinIO
      ↓
Object Storage
```

Downloads use:

```text
Authenticated Request
      ↓
Ownership Validation
      ↓
Object Lookup
      ↓
Short-Lived Presigned URL
```

The key security requirement is:

```text
Supplier A must never receive a presigned URL
for Supplier B's document.
```

This is enforced before URL generation.

### Round 12 Test Coverage

Dedicated document-storage tests include:

```text
Invoice document download tests
Document storage service tests
MinIO integration tests
Supplier document download tests
Cross-supplier document access tests
Missing-object tests
MinIO failure tests
Presigned URL tests
```

Verified test counts include:

```text
tests/test_invoice_document_download.py
17 passed

tests/test_document_storage_service.py
28 passed

tests/integration/test_minio_document_storage.py
10 passed

tests/test_supplier_document_download.py
11 passed
```


# Round 13 — Milestone 3 Completion Status

## Milestone 3 — GraphQL API

Status:

```text
Complete
```

The Supplier Portal now provides a Strawberry GraphQL endpoint:

```http
POST /graphql
```

The GraphQL API supports:

```text
Purchase Order queries
Invoice queries
Document queries
Acknowledge Purchase Order mutation
Cursor pagination
Supplier-level resolver authorization
```

GraphQL is implemented using:

```text
Strawberry
FastAPI
Existing Supplier Portal service layer
Platform Service authentication
```

The architecture is:

```text
Apollo Client
      ↓
GraphQL /graphql
      ↓
GraphQL Context
      ↓
Authenticated User
      ↓
Resolver
      ↓
Supplier Scope Check
      ↓
Existing Service
      ↓
GraphQL Type
```

### GraphQL Supplier Scoping

Supplier authorization is implemented inside the GraphQL resolvers.

For example:

```text
Supplier A
      ↓
Query Supplier B PO
      ↓
Resolver checks supplier_id
      ↓
Mismatch
      ↓
null
```

Collection queries filter supplier data before pagination:

```text
All POs
  ↓
Supplier authorization filter
  ↓
Authorized POs
  ↓
Cursor pagination
  ↓
GraphQL response
```

This prevents unauthorized records from appearing through pagination.

### GraphQL Cursor Pagination

Collection queries support:

```text
first
after
```

and return:

```text
edges
pageInfo
```

with:

```text
hasNextPage
endCursor
```

The requested page size is bounded to prevent unbounded collection retrieval.

### Acknowledge-PO Mutation

The acknowledge mutation:

```text
Receives PO identifier
        ↓
Authenticates user
        ↓
Finds PO
        ↓
Checks supplier ownership
        ↓
Calls existing acknowledgement service
        ↓
Returns updated GraphQL PO
```

A supplier cannot acknowledge another supplier's PO.

### Round 13 Test Coverage

The dedicated GraphQL test suite contains:

```text
48 passed
```

Coverage includes:

```text
GraphQL authentication
Purchase Order queries
Purchase Order collections
Invoice queries
Invoice collections
Document queries
Cursor pagination
Invalid cursor handling
Acknowledge-PO mutation
Supplier authorization
Cross-supplier PO rejection
Collection-level supplier filtering
```


The milestone-specific verification therefore includes:

```text
Round 12
MinIO document storage
Presigned URLs
Document supplier isolation
Storage failure handling

+

Round 13
GraphQL API
Cursor pagination
PO acknowledgement mutation
Resolver-level supplier scoping

+

Existing
R5 authentication/scoping
R6–8 P2P
R9–11 business integrations
```

The complete regression suite passes without requiring changes to the Platform Service.


# 28. Known Limitations

The current implementation is primarily designed for development, functional validation, and automated testing.

The core R5 authentication, role-based authorization, and supplier-level data-scoping requirements are implemented.

Rounds 6–8, Rounds 9–11, Round 12, and Round 13 functional requirements are also implemented.

Remaining limitations are primarily related to:

```text
Production Database Persistence
Automatic Contract Renewal
Partial-Invoice Lifecycle Expansion
Production Operational Hardening
External Supplier Verification
Payment-Service Integration
Advanced GraphQL Features
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

---

## In-Memory Business Storage

Purchase Orders, invoices, workflow data, supplier onboarding metadata, contract data, dispute data, and related business events are currently maintained in Python in-memory data structures.

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

## Document Storage

Round 12 has completed the migration of invoice PDFs and supplier onboarding documents to MinIO.

Therefore, local:

```text
uploads/
```

storage is no longer the active document-storage mechanism.

The remaining production considerations are:

```text
MinIO backup
Object retention
Encryption at rest
Lifecycle management
Disaster recovery
Production access policies
```

These are production-hardening considerations rather than unfinished Round 12 functionality.

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

A future implementation may introduce explicit immutable contract versions.

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

---

## GraphQL Expansion

The Round 13 GraphQL requirements are complete for the currently defined scope:

```text
Purchase Orders
Invoices
Documents
Cursor Pagination
Acknowledge-PO Mutation
Supplier Scoping
```

Future GraphQL enhancements may include:

```text
Additional mutations
Additional business domains
Richer pagination metadata
Subscriptions
More granular GraphQL permissions
GraphQL query complexity controls
Production GraphQL observability
```

These are future enhancements rather than gaps in the defined Round 13 milestone.

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
* Durable document/object-storage lifecycle management
* Backup and recovery procedures

The production persistence architecture should preserve the existing authorization model so that moving from in-memory storage to persistent storage does not weaken supplier-level data isolation.


# 29. Future Enhancements

The following enhancements are outside the currently completed R5, R6–8, R9–11, Round 12, and Round 13 scope.

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

## Advanced Document Storage Operations

Round 12 already uses MinIO for active document storage.

Future production capabilities may include:

* Encryption at rest
* Object lifecycle policies
* Retention policies
* Backup and recovery
* Object versioning
* Malware scanning
* Document classification
* Disaster recovery

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

---

## Production Supplier Verification

Replace mock verification with an actual supplier verification integration.

---

## Payment Service Integration

The current payment approval workflow is represented within the Supplier Portal P2P state model.

A future implementation could integrate payment approval with a dedicated payment or finance service.

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

---

## Advanced Supplier Analytics

Future analytics may include:

* Supplier trend dashboards
* Delivery-risk indicators
* Invoice anomaly detection
* Supplier benchmarking
* Historical scorecard trends
* Predictive supplier performance analytics

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

---

## Expanded GraphQL API

Round 13 currently covers:

```text
Purchase Orders
Invoices
Documents
Acknowledge PO
Cursor Pagination
Supplier Scoping
```

Future GraphQL capabilities may include:

```text
Additional Queries
Additional Mutations
Contract GraphQL APIs
Shipment GraphQL APIs
Goods Receipt GraphQL APIs
Scorecard GraphQL APIs
GraphQL Subscriptions
Richer Connection Metadata
Query Complexity Protection
GraphQL Observability
```

---

## Expanded Integration Testing

A future enhancement would introduce a complete end-to-end integration test that drives:

```text
Supplier Registration
        ↓
Documents
        ↓
MinIO Document Storage
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

This would complement the existing focused service, REST API, MinIO, and GraphQL tests.

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
* MinIO availability monitoring
* P2P workflow monitoring
* Contract expiry monitoring
* GraphQL request monitoring
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

The existing supplier ownership model should remain the foundation of these enhancements.

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
* Document access events
* GraphQL mutations
* Administrative maintenance operations

---

## Summary of Future Scope

The current implementation completes the defined:

```text
R5
R6–8
R9–11
Round 12
Round 13
```

functional requirements.

Future work primarily focuses on:

```text
Production Database Persistence
Advanced MinIO Operations
Complete Multi-Invoice Lifecycle
Automatic Contract Renewal
Explicit Contract Versioning
External Supplier Verification
Payment-Service Integration
Event-Driven Processing
Advanced Analytics
Advanced Dispute Intelligence
Expanded GraphQL API
Expanded Integration Testing
Production Observability
Advanced Authorization
Persistent Audit Controls
```

These enhancements build on the implemented authentication, supplier-scoping, P2P, Compliance, contract, dispute-suggestion, self-service analytics, MinIO document-storage, and GraphQL functionality.