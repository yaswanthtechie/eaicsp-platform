# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for supplier-facing purchase orders, invoices, document management, supplier onboarding, contracts, performance scorecards, dispute-resolution suggestions, and procure-to-pay workflows.

The service integrates with the **Platform Service** for authentication and role-based authorization, the **Compliance Service** for supplier activation checks, **MinIO** for document storage, **Strawberry GraphQL** for portal queries and mutations, and **Apache Kafka** for ongoing supplier compliance status changes.

Invoice PDFs and onboarding documents are stored in MinIO. Authorized downloads use short-lived presigned URLs after access and supplier-ownership checks.

Round 14 adds Kafka event validation, idempotency, out-of-order event protection, compliance audit history, manual offset management, and dead-letter queue (DLQ) handling.

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

- **Milestone 1:** Completed in PR #152, superseding PR #128.
- **Milestone 2:** MinIO document storage and supplier-scoped presigned download URLs.
- **Milestone 3:** Strawberry GraphQL queries, cursor pagination, acknowledge-PO mutation, and resolver-level supplier scoping.

**Known limitation:** GraphQL cursors represent positions in in-memory lists, so their positions may change when records are added or removed. Most business records are not durable across application restarts.

## Round 14 Status

**Round 14 – Pod 1: Supplier Compliance Status Event Consumption**

Implemented capabilities:

- Kafka consumer for `compliance.supplier.status_changed`
- Consumer group `supplier-portal-service`
- Event schema, type, and version validation
- `event_id` idempotency and `occurred_at` ordering protection
- Compliance state mapping and audit history
- Manual Kafka offset management and DLQ handling
- REST and GraphQL compliance access enforcement
- Supplier PO, invoice, and document access restrictions
- Local Kafka Docker infrastructure and consumer tests

Compliance state mapping:

| Event decision | Supplier Portal state | Supplier access |
|---|---|---|
| `CLEAR` | `cleared` | Permitted reads and authorized writes |
| `REVIEW` | `needs_review` | Reads allowed; protected writes denied |
| `BLOCK` | `suspended` | Supplier-facing protected access denied |

Round 14 compliance access state is separate from the supplier onboarding lifecycle status.

The synchronous Compliance Service check during activation remains unchanged:

`approved → Compliance internal-check → CLEAR → active`

Kafka handles ongoing compliance status changes after activation.

**Event contract boundary:** The compliance event carries no `supplier_id`. The producer sends `payload.supplier_name` and uses the supplier name as the Kafka key. Supplier Portal matches the event to a supplier by comparing a normalized `payload.supplier_name` with the onboarding record's `company_name`, ignoring case and extra spaces. The Kafka key is not used for identity.

---

## Running Locally

Create the local environment file:

```bash
cp .env.example .env
```

Configure valid MinIO credentials and the required application settings in `.env`:

```text
MINIO_ACCESS_KEY=<your-minio-access-key>
MINIO_SECRET_KEY=<your-minio-secret-key>

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=supplier-portal-service
KAFKA_STATUS_CHANGED_TOPIC=compliance.supplier.status_changed
KAFKA_DLQ_TOPIC=compliance.supplier.status_changed.dlq
KAFKA_AUTO_OFFSET_RESET=earliest
```

Start the development dependencies from the repository root:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Expected local endpoints:

| Service | Endpoint |
|---|---|
| MinIO API | `http://127.0.0.1:9000` |
| MinIO Console | `http://127.0.0.1:9001` |
| Kafka broker | `localhost:9092` |

Create the required Kafka topics if they do not already exist:

```bash
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --if-not-exists \
  --topic compliance.supplier.status_changed \
  --partitions 1 \
  --replication-factor 1

docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create --if-not-exists \
  --topic compliance.supplier.status_changed.dlq \
  --partitions 1 \
  --replication-factor 1
```

Start the Supplier Portal:

```bash
cd services/supplier-portal
python -m uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
# Exclude integration tests
python -m pytest -m "not integration" -q

# MinIO integration tests
python -m pytest -m integration -q

# Complete test suite
python -m pytest -q
```

---

## MinIO Document Storage — Rounds 12–13

MinIO provides S3-compatible storage for invoice PDFs and supplier onboarding documents. The application uses `docker-compose.dev.yml` for local development.

Typical configuration:

```text
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=<configured-value>
MINIO_SECRET_KEY=<configured-value>
MINIO_BUCKET=supplier-documents
MINIO_SECURE=false
MINIO_PRESIGNED_EXPIRY_SECONDS=300
```

Start or inspect MinIO:

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker ps
```

If the container exists but is stopped:

```bash
docker start supplier-portal-minio
```
### Start Kafka for Round 14

Start the Kafka service using Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up -d kafka
```

Verify that the Kafka container is running:

```bash
docker ps
```

Run the Round 14 consumer tests:

```bash
python -m pytest tests/test_kafka_consumer.py tests/test_r14_enforcement.py -q
```

The targeted tests validate the consumer and compliance enforcement behavior. Run them separately from live Kafka integration checks when Kafka infrastructure is required.

### Document access flow

**Upload:** validate the document, authenticate the caller, check authorization and supplier ownership, then store the object in MinIO.

**Download:** authenticate, enforce compliance access, locate the document, verify supplier ownership, check the MinIO object, and generate a short-lived presigned URL.

Cross-supplier access must return `403 Forbidden` without generating a presigned URL. A suspended supplier cannot obtain a new presigned URL through the protected download flow.

Storage failures are handled as dependency failures, not client-validation errors.

Run the MinIO tests using:

```bash
python -m pytest tests/test_document_storage_service.py tests/test_supplier_document_download.py -q
python -m pytest -m integration -q
```

---

## Supplier Portal–Compliance Integration

Before a supplier moves from `approved` to `active`, the Supplier Portal calls the Compliance Service.

**Endpoint**

```http
POST {COMPLIANCE_SERVICE_URL}/api/v1/compliance/internal-check
```

**Headers**

```http
X-Caller-Service: supplier-portal
Content-Type: application/json
```

**Request example**

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

**Expected response example**

```json
{
  "decision": "CLEAR",
  "cleared": true,
  "reason": "No sanctions or watchlist match found."
}
```

Activation is allowed only when `decision == "CLEAR"` and `cleared is True`. `BLOCK`, `REVIEW`, contradictory responses, or an unavailable Compliance Service prevent activation.

| Failure or decision | HTTP response |
|---|---:|
| Valid `BLOCK` or `REVIEW` decision | `409` |
| Timeout or connection failure | `503` |
| Error or unusable Compliance response | `502` |

Relevant implementation files:

| File | Responsibility |
|---|---|
| `app/services/compliance_client.py` | Calls Compliance and validates its response |
| `app/services/supplier_onboarding_service.py` | Implements activation decision |
| `app/routes/supplier_onboarding.py` | Maps service errors to HTTP responses |
| `app/core/config.py` | Configures `COMPLIANCE_SERVICE_URL` |
| `tests/test_compliance_client.py` | Client tests |
| `tests/test_supplier_onboarding.py` | Activation tests |

Run the integration tests:

```bash
python -m pytest tests/test_compliance_client.py tests/test_supplier_onboarding.py -q
```

Platform Service code remains unchanged by this integration.

---

## Kafka Compliance Status Changes — Round 14

Kafka consumption is separate from the synchronous activation check. The consumer runs as an application background task; it is not a REST or Swagger endpoint.

| Setting | Value |
|---|---|
| Topic | `compliance.supplier.status_changed` |
| Consumer group | `supplier-portal-service` |
| Dead-letter queue | `compliance.supplier.status_changed.dlq` |
| Auto offset reset | `earliest`, when no committed offset exists |

### Processing behaviour

1. Parse the Kafka message and validate its schema, event type, and version.
2. Validate `payload.supplier_id`.
3. Check `event_id` for duplicate processing.
4. Compare `occurred_at` to prevent stale events from overwriting newer state.
5. Apply the compliance state and record audit history.
6. Commit the offset after successful processing.

Invalid or unknown-supplier events are routed to the DLQ. Unexpected processing failures do not commit the original offset, allowing Kafka to redeliver the message.

The consumer uses manual offset management (`enable.auto.commit = false`). The application records processed event IDs to support idempotency.

### Access enforcement

- `cleared`: supplier reads and otherwise-authorized writes are allowed.
- `needs_review`: reads are allowed; protected supplier writes are denied.
- `suspended`: supplier-facing protected operations, including protected document downloads, are denied.

Compliance access checks do not replace role authorization or supplier-ownership checks. Internal roles continue to use their existing authorization rules.

The event producer is external to this implementation. End-to-end producer publishing is not claimed as a Supplier Portal deliverable.

---

# 1. Overview

The Supplier Portal Service provides APIs for supplier and procurement workflows, including:

- Purchase orders, shipment notices, and goods receipts
- Invoices, three-way matching, discrepancy review, and payment approval
- Supplier registration, onboarding, and activation
- Supplier contracts, renewals, and lifecycle history
- Supplier statistics, performance scorecards, and self-service analytics
- Historical dispute-resolution suggestions
- MinIO-backed document storage and secure downloads
- REST and GraphQL authorization and supplier isolation
- Synchronous compliance checks during activation
- Kafka-based compliance status updates and access enforcement

### Procure-to-pay workflow

```text
Purchase Order
     ↓
Acknowledgement
     ↓
Shipment Notice
     ↓
Goods Receipt
     ↓
Invoice
     ↓
Three-Way Match
     ├── Matched
     └── Discrepancy → Human Review
                           ↓
                    Payment Approval
```

Three-way matching compares the Purchase Order, Goods Receipt, and Invoice to identify quantity or price discrepancies.

### Supplier onboarding

```text
Registration → Document Collection → Verification
     → Approval → Compliance Check
                      ├── CLEAR → Active
                      └── BLOCK / REVIEW / Failure → Not Activated
```

A supplier must be registered, approved, and active before a Purchase Order can be created for that supplier.

### Compliance after activation

Onboarding status and compliance access state are distinct. An active supplier may later be restricted by a Kafka compliance event without changing the onboarding lifecycle state.

| Round | Main deliverables |
|---|---|
| Rounds 5–8 | Supplier scoping, authentication enforcement, PO and invoice workflows |
| Rounds 9–11 | Compliance activation integration, contracts, dispute suggestions, self-service analytics |
| Round 12 | MinIO document storage and presigned downloads |
| Round 13 | GraphQL queries, cursor pagination, acknowledge-PO mutation, resolver-level scoping |
| Round 14 | Kafka compliance events, idempotency, ordering protection, audit history, offset and DLQ handling |

### Storage limitations

- Purchase Orders, invoices, P2P records, onboarding records, and contract data use in-memory business storage.
- Those business records are not durable across application restarts.
- R14 compliance access state, processed-event information, and compliance audit history are SQLite-backed.
- Invoice PDFs and onboarding documents are stored in MinIO.
- Authentication depends on the Platform Service; supplier activation depends on the Compliance Service.
- Local Kafka development configuration is not production security configuration.
- The external producer must publish events that follow the agreed event contract.

The service supports development, functional validation, and automated testing. Production deployment requires appropriate database operations, backups, monitoring, security hardening, and durable storage for business records.

---

# 2. Key Features

## Purchase Orders

- Create, retrieve, update, and delete Purchase Orders
- Supplier acknowledgement, cancellation, and controlled state transitions
- Transition history, actor tracking, and timestamps
- Expected and actual delivery tracking
- Duplicate PO protection and bulk sending
- Active-supplier validation during PO creation
- Compliance-aware supplier access

Supplier compliance rules:

| State | Supplier PO access |
|---|---|
| `cleared` | View and acknowledge when otherwise authorized |
| `needs_review` | View; acknowledgement blocked |
| `suspended` | Supplier-facing protected access blocked |

## Invoices

- Create and retrieve invoices with data, PO, ownership, line-item, and amount validation
- Duplicate protection, partial invoices, and multiple line items
- Invoice state transitions, disputes, adjustments, and history
- Compliance-officer dispute adjustment
- P2P integration and three-way-match discrepancy support
- Historical dispute-resolution suggestions

Price differences exceeding the three-way-match tolerance are handled by the matching process; invoice creation does not automatically reject an invoice solely for that reason.

## Invoice Documents

- PDF-only uploads with content-type, signature, and 10 MB size validation
- MinIO object storage and supplier-scoped object references
- Object-existence checks and short-lived presigned downloads
- Compliance and ownership checks before URL generation
- Cross-supplier protection and storage-failure handling
- Unit and integration tests

Documents are stored in MinIO rather than the old local-filesystem upload directory.

**Security rule:** Never generate a presigned URL before authentication, compliance-access authorization, and supplier-ownership validation.

## Supplier Statistics

- Purchase Order counts and on-time delivery percentage
- Average invoice cycle time and invoice metrics
- Date normalization and invalid/missing-date handling
- Supplier existence validation
- Exclusion of future-due, cancelled, and undated POs from the on-time denominator
- Treatment of past-due unfulfilled POs as late

## Supplier Performance Scorecard

- On-time delivery, invoice accuracy, dispute rate, and overall performance
- Performance ratings and status
- PO and invoice performance details
- Historical dispute tracking and invoice cycle time
- Monthly trends and supplier-scoped self-service access

Invoice-related scorecard calculations use the `po_number` stored on invoice line items.

## Procure-to-Pay and Three-Way Match

- PO acknowledgement, shipment notice, and Goods Receipt processing
- Partial/short receipts and P2P state transitions
- PO/Receipt/Invoice matching
- Quantity and price discrepancy detection
- Human-review handling and prevention of automatic approval when discrepancies exist
- Payment-approval workflow states

Historical dispute-resolution suggestions are advisory. They do not automatically modify invoices, approve disputes, or change matching state.

## Supplier Onboarding

- Registration, document collection, mock verification, approval, and activation
- Supplier-scoped onboarding access and lifecycle-state management
- Compliance Service activation checks and fail-closed error handling
- Active-supplier enforcement before PO creation
- MinIO-backed onboarding documents and presigned downloads
- Separate Kafka-driven compliance access-state updates after activation

## Supplier Contract Lifecycle Management

- Create, retrieve, and update supplier contracts
- Draft-to-active lifecycle and status tracking
- Expiry detection, renewal processing, and renewal-date validation
- Renewal reasons, notice periods, and auto-renew configuration
- Payment terms, delivery terms, pricing terms, and minimum order values
- Supplier-scoped access and contract history

Contract records and contract history remain in-memory.

## Supplier Self-Service Analytics

Supplier users can retrieve their own scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The service enforces supplier ownership and compliance access. Self-service analytics are read-only.

---

# 3. Architecture

The service uses a layered FastAPI architecture with separate REST routes, GraphQL operations, authentication and authorization, business services, document storage, and event consumption.

```text
Client
  ├── REST API
  └── GraphQL API
          ↓
Authentication / Role Authorization
          ↓
Compliance Access + Supplier Scoping
          ↓
Business Services
  ├── Purchase Orders / P2P
  ├── Shipments / Goods Receipts
  ├── Invoices / Three-Way Match
  ├── Onboarding / Contracts
  └── Statistics / Scorecards
          ↓
Storage and Integrations
  ├── In-memory business records
  ├── SQLite-backed R14 compliance state/history
  ├── MinIO document objects
  ├── Platform Service authentication
  ├── Compliance Service activation check
  └── Kafka compliance events
```

## REST and GraphQL authorization

The authorization flow is:

```text
Authentication
    ↓
Role Authorization
    ↓
Compliance Access
    ↓
Supplier Ownership
    ↓
Resource / Business Operation
```

Compliance checks do not replace role-based authorization or resource ownership checks.

### GraphQL

The GraphQL endpoint is `POST /graphql`. Supported query operations include Purchase Orders, invoices, and supplier documents. Collection operations support cursor pagination using `first`, `after`, `hasNextPage`, and `endCursor`; `first` is limited to 100 records.

The current mutation surface includes `acknowledgePurchaseOrder`. Resolvers use the existing business services and enforce compliance access and supplier ownership.

**Known limitation:** Cursors are based on positions in in-memory lists and are not stable identifiers for records.

### MinIO documents

The document storage service handles object uploads, existence checks, missing objects, storage errors, and presigned URL generation. REST endpoints and GraphQL resolvers must authorize the request before exposing protected document information or generating a download URL.

### Kafka compliance processing

```text
External Compliance Producer
          ↓
Kafka: compliance.supplier.status_changed
          ↓
Supplier Portal Consumer
          ↓
Schema / Identity / Event Validation
          ↓
Idempotency + occurred_at Ordering
          ↓
SQLite-backed Compliance State and History
          ↓
REST / GraphQL Authorization
```

Invalid events are routed to the DLQ. Unexpected processing failures do not commit the original offset. The consumer is integrated with the FastAPI application lifecycle.

### Contracts and dispute suggestions

Contract management is handled by a separate business service using an in-memory contract store. The dispute-resolution service analyses historical three-way-match dispute information to produce advisory suggestions.

---

# 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| Strawberry GraphQL | GraphQL API |
| Pydantic / Pydantic Settings | Validation and configuration |
| Uvicorn | ASGI server |
| HTTPX | HTTP client and API testing |
| Pytest | Automated testing |
| `python-multipart` | Multipart file uploads |
| MinIO / S3-compatible API | Invoice and onboarding document storage |
| Apache Kafka | Supplier compliance status events |
| `confluent-kafka` | Kafka consumer and DLQ publishing |

Dependency versions are maintained in `requirements.txt`. The Supplier Portal consumes compliance status events; external producer implementation is outside its scope.

---

# 5. Project Structure

The project separates application configuration, authentication, REST routes, GraphQL operations, schemas, business services, storage integrations, Kafka processing, and tests.

```text
supplier-portal/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── auth.py
│   │   └── config.py
│   ├── graphql/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── queries.py
│   │   ├── mutations.py
│   │   ├── schema.py
│   │   └── types.py
│   ├── routes/
│   │   ├── purchase_order.py
│   │   ├── shipment.py
│   │   ├── goods_receipt.py
│   │   ├── invoice.py
│   │   ├── three_way_match.py
│   │   ├── supplier_onboarding.py
│   │   ├── supplier_contract.py
│   │   └── supplier_stats_routes.py
│   ├── schemas/
│   │   ├── purchase_order.py
│   │   ├── shipment.py
│   │   ├── goods_receipt.py
│   │   ├── invoice.py
│   │   ├── three_way_match.py
│   │   ├── supplier_onboarding.py
│   │   ├── supplier_contract.py
│   │   ├── supplier_stats.py
│   │   └── events.py
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
│       ├── supplier_compliance_service.py
│       ├── document_storage_service.py
│       ├── po_p2p_state_machine.py
│       ├── kafka_consumer.py
│       └── kafka_consumer_runner.py
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
│   ├── test_kafka_consumer.py
│   └── integration/
│       └── test_minio_document_storage.py
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

This is a representative project structure for the files described here; keep it aligned with the actual repository when adding or removing files. The old local `uploads/` directory is not the current document-storage architecture.

## Application and Core

- `app/main.py`: creates the FastAPI application, registers REST and GraphQL routes, and manages the Kafka consumer lifecycle.
- `app/core/auth.py`: handles bearer-token authentication through Platform Service, role authorization, supplier identity, request IDs, and access checks.
- `app/core/config.py`: loads application, Platform, Compliance, MinIO, and Kafka configuration.

## GraphQL

`app/graphql/` defines the schema, queries, mutations, types, request context, pagination, and resolver-level authorization. It reuses existing business services rather than duplicating PO or invoice logic.

`app/graphql/context.py` centralizes GraphQL compliance access checks through `require_graphql_view_access(user)` and `require_graphql_write_access(user)`.

## Routes and Schemas

- `app/routes/`: REST endpoint definitions, dependency injection, access checks, HTTP responses, resource validation, and calls to business services.
- `app/schemas/`: request/response validation and data models for POs, shipments, receipts, invoices, matching, onboarding, contracts, scorecards, and events.
- `app/schemas/events.py`: validates incoming compliance status-change events.

## Business Services

`app/services/` contains the workflow and business logic for POs, P2P transitions, shipments, goods receipts, invoices, matching, onboarding, contracts, scorecards, dispute suggestions, compliance integration, and document storage.

### Supplier compliance service

`app/services/supplier_compliance_service.py` maps compliance decisions to access states, rejects stale events, tracks duplicate event IDs, maintains compliance audit history, and exposes state to authorization logic. R14 compliance state and related event/audit information are SQLite-backed.

### Kafka consumer

`app/services/kafka_consumer.py` validates and processes compliance events, applies access-state changes, routes invalid messages to the DLQ, and manages offset commits.

`app/services/kafka_consumer_runner.py` runs the consumer in the application background and handles shutdown.

### Document storage

`app/services/document_storage_service.py` provides MinIO object uploads, object-existence checks, presigned URLs, missing-object handling, and storage-failure handling. Callers must complete authentication, compliance authorization, and supplier-ownership checks before requesting a presigned URL.
# 6. Authentication and Authorization

The Supplier Portal delegates authentication to the **Platform Service**. It does not locally decode or independently validate JWT tokens. Instead, it forwards the received Bearer token to the Platform Service for verification.

Authentication endpoint:

```http
POST /api/v1/auth/verify
```

## 6.1 Authentication Flow

```text
Client
  │ Authorization: Bearer <token>
  ▼
Supplier Portal
  │
  ▼
Platform Service
  │ Validates token and returns user identity
  ▼
Supplier Portal
  │
  ├── Role authorization
  ├── Supplier identity validation
  ├── Compliance access check
  └── Resource ownership check
        │
        ▼
    Protected operation
```

The authenticated identity can include:

```text
user_id
email
full_name
role
supplier_id
is_active
```

The Supplier Portal uses the returned identity for authorization and supplier scoping.

## 6.2 Authentication Configuration

The Platform Service URL is configured using:

```text
PLATFORM_AUTH_URL
```

Default development value:

```text
http://127.0.0.1:8005
```

The Platform Service remains the authentication provider; the Supplier Portal applies its own resource-level authorization rules.

## 6.3 Authentication and Authorization Errors

| Situation | Expected response |
|---|---:|
| Missing, invalid, or expired token | `401 Unauthorized` |
| Missing required user role or invalid identity | `401 Unauthorized` |
| Authenticated user lacks the required role | `403 Forbidden` |
| Supplier identity missing for a supplier-scoped operation | `403 Forbidden` |
| Supplier attempts to access another supplier's resource | `403 Forbidden` |
| Authentication service timeout or unavailability | `503 Service Unavailable` |
| Invalid authentication response from the Platform Service | `503 Service Unavailable` |

The exact response also depends on the specific endpoint and its authorization implementation.

## 6.4 Supplier Scoping

For supplier users, the authenticated `supplier_id` must match the supplier associated with the requested resource.

For example:

```text
Authenticated supplier: SUP001
Requested resource owner: SUP002
Result: 403 Forbidden
```

This rule applies to supplier-scoped resources, including:

- Purchase Orders and PO events
- Invoices and invoice documents
- Supplier statistics and scorecards
- Shipments and Goods Receipts
- Three-way-match records
- Supplier onboarding documents and records
- Supplier contracts and contract history
- Supplier-facing GraphQL resources

Supplier filtering must be applied before returning collection results. GraphQL resolvers must enforce ownership independently of the REST routes.

For a GraphQL lookup, an unauthorized resource must not be exposed. Depending on the resolver, the result may be `null` or a GraphQL authorization error.

## 6.5 Round 14 Compliance Access Control

Round 14 adds a compliance access state to the existing authentication, role, and ownership checks. The compliance state is maintained separately from the supplier's onboarding lifecycle status.

The status mapping is:

| Compliance decision | Supplier Portal access state |
|---|---|
| `CLEAR` | `cleared` |
| `REVIEW` | `needs_review` |
| `BLOCK` | `suspended` |

For supplier-facing operations, the access rules are:

| Compliance state | Read operations | Protected writes |
|---|---|---|
| `cleared` | Allowed, subject to authorization | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization | Blocked |
| `suspended` | Blocked | Blocked |

The standard denial messages are:

```text
Supplier account is suspended due to compliance status
```

```text
Supplier account is under compliance review. This action is not permitted.
```

These restrictions apply to supplier users. Authorized internal roles continue to follow their existing role-based permissions.

The effective security flow is:

```text
Platform Authentication
        ↓
Role and Supplier Identity
        ↓
Compliance Access
        ↓
Resource Ownership
        ↓
Business Operation
```

Authentication, role authorization, compliance access, and resource ownership are separate checks. Passing one check does not automatically grant access to every resource.

## 6.6 MinIO Document Authorization

Invoice and onboarding document downloads require authorization before a presigned URL is generated.

```text
Authenticated request
        ↓
Supplier compliance check
        ↓
Supplier ownership / role authorization
        ↓
Document and object validation
        ↓
Generate presigned URL
        ↓
Return URL to authorized caller
```

A supplier cannot access another supplier's document merely by knowing its document ID, invoice number, supplier ID, or object reference.

A suspended supplier is rejected before the MinIO object lookup and before new presigned URL generation.

## 6.7 GraphQL Authorization

GraphQL authorization is enforced inside the relevant resolver and shared GraphQL access checks, not only at the `/graphql` endpoint.

For supplier users:

- Collection resolvers filter records to the authenticated supplier.
- Resource resolvers check ownership before exposing protected data.
- Protected mutations check compliance write access before modifying data.
- Supplier filtering is applied before cursor pagination, so unauthorized records do not affect returned edges, cursors, or page boundaries.

The relevant collection operations include:

```text
purchaseOrders
invoices
documents
```

The GraphQL acknowledgement mutation also checks compliance access and supplier ownership before changing PO state.

## 6.8 Role-Based Authorization

The Supplier Portal uses role-based authorization through helpers such as:

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

Examples of role-restricted operations include:

| Operation | Required role |
|---|---|
| Purchase Order creation and state transitions | `procurement_manager` |
| Bulk PO sending | `procurement_manager` |
| Invoice adjustment | `compliance_officer` |
| Three-way-match dispute resolution | `compliance_officer` |
| Goods Receipt creation | `warehouse_manager` |
| Supplier contract creation, update, activation, and renewal | `procurement_manager` |

Supplier-facing operations additionally enforce supplier ownership and Round 14 compliance access where applicable.

## 6.9 Round 5 Supplier-Scoping Requirement

The central Round 5 requirement remains:

> A valid supplier token does not provide unrestricted access to supplier resources.

Examples:

```text
SUP001 token → SUP001 PO        → Allowed, if authorized
SUP001 token → SUP002 PO        → 403 Forbidden

SUP001 token → SUP001 Invoice   → Allowed, if authorized
SUP001 token → SUP002 Invoice   → 403 Forbidden

SUP001 token → SUP001 Document  → Authorized URL, if permitted
SUP001 token → SUP002 Document  → 403 Forbidden
```

The same principle applies to supplier-scoped statistics, scorecards, contracts, onboarding resources, shipments, Goods Receipts, three-way matches, and GraphQL resources.

Round 14 adds compliance restrictions without replacing the existing authentication and supplier-scoping model.

---

# 7. Purchase Order Management

The Supplier Portal supports Purchase Order (PO) creation, retrieval, updates, cancellation, acknowledgement, controlled state transitions, event history, bulk sending, and delivery tracking.

## 7.1 Purchase Order Capabilities

The PO functionality includes:

- PO creation, retrieval, update, and deletion
- Supplier acknowledgement
- Controlled PO state transitions and cancellation
- Transition event history and actor tracking
- Expected and actual delivery tracking
- Duplicate PO-number validation
- Bulk PO sending
- Supplier onboarding and active-status validation
- Integration with the broader P2P workflow

## 7.2 PO Authorization and Active Supplier Validation

PO creation is an internal procurement operation restricted to:

```text
procurement_manager
```

Endpoint:

```http
POST /api/v1/purchase-orders
```

Before creating a PO, the service validates the referenced supplier and its onboarding status.

```text
Supplier exists?
    ├── No → Reject
    ▼
Supplier status is active?
    ├── No → Reject
    ▼
Validate PO fields and totals
    ▼
Create PO
```

The service validates the PO number, supplier ID, items, quantities, unit prices, total amount, expected delivery date, and duplicate PO numbers. The submitted total must match the calculated line-item total.

Supplier onboarding status and Round 14 compliance access state are separate concepts. A supplier being `active` for onboarding does not automatically mean its compliance access state is `cleared`.

## 7.3 PO Lifecycle

The legacy PO lifecycle is separate from the P2P state machine.

| Current state | Allowed next states |
|---|---|
| `draft` | `sent`, `cancelled` |
| `sent` | `acknowledged`, `cancelled` |
| `acknowledged` | `fulfilled`, `cancelled` |
| `fulfilled` | None |
| `cancelled` | None |

`fulfilled` and `cancelled` are terminal states.

```text
draft → sent → acknowledged → fulfilled
  └──────────────┴──────────────→ cancelled
```

The service validates each transition and rejects illegal transitions rather than silently changing the PO state.

## 7.4 PO List and Retrieval

List endpoint:

```http
GET /api/v1/purchase-orders
```

Single PO endpoint:

```http
GET /api/v1/purchase-orders/{po_number}
```

Both endpoints require authentication.

For supplier users, the authenticated `supplier_id` must match the supplier associated with the PO. Supplier collection results are filtered to the authenticated supplier.

Internal users can access resources according to their assigned roles and the endpoint's authorization rules.

A supplier attempting to access another supplier's PO receives `403 Forbidden`.

## 7.5 PO Update and Deletion

Update endpoint:

```http
PUT /api/v1/purchase-orders/{po_number}
```

Delete endpoint:

```http
DELETE /api/v1/purchase-orders/{po_number}
```

These endpoints require authentication and apply the appropriate role, supplier ownership, and compliance checks.

Supplier-facing protected writes require the supplier to be `cleared`. Supplier users in `needs_review` or `suspended` states cannot perform protected writes.

PO deletion does not remove historical transition events. This preserves the PO audit trail after the PO record is deleted.

## 7.6 Supplier PO Acknowledgement

REST endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/acknowledge
```

The acknowledgement operation is supplier-scoped and must verify that the authenticated supplier owns the PO.

The intended transition is:

```text
sent → acknowledged
```

The authorization flow is:

```text
Platform authentication
        ↓
Supplier identity
        ↓
Compliance write access
        ↓
Supplier ownership
        ↓
PO state validation
        ↓
Acknowledge PO
```

For supplier users:

| Compliance state | Acknowledgement |
|---|---|
| `cleared` | Allowed if the PO transition is valid |
| `needs_review` | `403 Forbidden` |
| `suspended` | `403 Forbidden` |

## 7.7 PO State Transition

Endpoint:

```http
POST /api/v1/purchase-orders/{po_number}/transition
```

Required role:

```text
procurement_manager
```

Example request:

```json
{
  "target_state": "sent",
  "actor": "admin"
}
```

The authenticated user's identity is used for transition auditing rather than trusting the actor value supplied by the request body. Invalid transitions return `400 Bad Request`.

Successful transition history records:

```text
po_number
supplier_id
actor
from_status
to_status
timestamp
```

Events are stored separately in the `po_events` collection/store. They preserve the transition history even when the associated PO is deleted.

## 7.8 Bulk PO Sending

Endpoint:

```http
POST /api/v1/purchase-orders/bulk-send
```

Required role:

```text
procurement_manager
```

Example request:

```json
{
  "po_numbers": [
    "PO1001",
    "PO1002",
    "PO9999"
  ]
}
```

Each PO is processed independently. A failure for one PO does not stop the remaining POs from being processed.

The response reports the total, successful and failed counts, together with individual results.

## 7.9 PO Event History

Endpoint:

```http
GET /api/v1/purchase-orders/{po_number}/events
```

The endpoint requires authentication and applies the relevant role, supplier ownership, and compliance read-access checks.

For supplier users:

- `cleared`: PO event history can be viewed, subject to ownership.
- `needs_review`: PO event history can be viewed, subject to ownership.
- `suspended`: supplier-facing access is blocked.

Historical events remain available according to the endpoint's authorization rules even after the PO itself is deleted.

## 7.10 PO and P2P Relationship

The PO lifecycle and P2P state machine are related but distinct.

The broader P2P workflow is:

```text
Purchase Order
      ↓
Acknowledgement
      ↓
Shipment Notice
      ↓
Goods Receipt
      ↓
Invoice
      ↓
Three-Way Match
      ↓
Payment Approval
```

The P2P state machine tracks transaction progression through states such as:

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

The legacy PO lifecycle tracks PO status; the P2P state machine tracks the broader purchasing transaction.

## 7.11 GraphQL PO Operations

The GraphQL API exposes PO query operations, including:

```text
purchaseOrder
purchaseOrders
```

It also exposes the acknowledgement mutation:

```text
acknowledgePurchaseOrder
```

GraphQL resolvers enforce supplier ownership. The acknowledgement mutation checks compliance write access and ownership before invoking the state-changing operation.

## 7.12 Delivery Tracking

When a PO is fulfilled, its actual delivery date is derived from the related Goods Receipt records rather than simply using the date on which the PO status changed.

When multiple Goods Receipts exist, the latest applicable `receipt_date` is used.

A PO is considered on time when:

```text
actual_delivery_date <= expected_delivery
```

The delivery-performance eligibility rules are:

| PO condition | Treatment |
|---|---|
| Fulfilled | Eligible |
| Unfulfilled and past due | Eligible and counted as late |
| Unfulfilled and not yet due | Excluded |
| Cancelled | Excluded |
| No applicable expected delivery date | Excluded |

This same delivery-eligibility definition is used by supplier statistics, supplier scorecards, and monthly delivery trends.

---

# 8. Invoice Management

Invoices are associated with suppliers and Purchase Orders. Invoice processing has its own lifecycle, separate from the broader P2P state machine.

Supplier-facing invoice operations also enforce Round 14 compliance access restrictions.

## 8.1 Invoice Data Model

An invoice can contain:

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

Invoice line items contain PO references used by invoice validation, supplier performance calculations, and three-way matching.

The invoice lookup key is:

```text
(supplier_id, invoice_number)
```

Invoice numbers are therefore scoped to the supplier.

## 8.2 Invoice Lifecycle

The implemented invoice lifecycle supports these states and transitions:

| Current status | Allowed next statuses |
|---|---|
| `submitted` | `approved`, `disputed`, `rejected` |
| `disputed` | `approved`, `adjusted`, `rejected` |
| `adjusted` | `approved`, `rejected` |
| `approved` | None |
| `rejected` | None |

`approved` and `rejected` are terminal states.

```text
submitted
   ├── approved
   ├── rejected
   └── disputed
          ├── approved
          ├── rejected
          └── adjusted
                 ├── approved
                 └── rejected
```

Valid transitions are checked by the invoice service. Invalid transitions are rejected.

## 8.3 Invoice Creation

Endpoint:

```http
POST /api/v1/invoices
```

The endpoint requires authentication and validates the supplier, PO, invoice data, and applicable business rules.

The service validates:

- Invoice number and duplicate invoice checks
- Supplier identity and PO supplier consistency
- PO existence and eligible status
- Invoice items and item codes
- Positive quantities and remaining PO quantities
- Unit prices and calculated invoice amount

For supplier users, the authenticated `supplier_id` must match the invoice supplier.

Invoice price differences are allowed to reach the three-way-match process when the invoice data otherwise satisfies the creation rules. The three-way match determines whether the price difference is within the configured tolerance.

## 8.4 PO Requirements for Invoices

An invoice can reference a PO whose legacy status is:

```text
acknowledged
fulfilled
```

Invoices cannot be created against POs in `draft` or `sent` status.

The P2P invoice transition has an additional workflow requirement: the PO must have reached the appropriate `received` state before the P2P invoice transition occurs.

These checks serve different purposes: the PO lifecycle controls PO eligibility, while the P2P state machine controls transaction progression.

## 8.5 Invoice Line-Item Validation and Three-Way Matching

Each invoice line item is checked against the PO. The service validates that:

- The item exists on the PO.
- Quantity is positive.
- Quantity does not exceed the remaining PO quantity.
- Duplicate `(po_number, item_code)` lines are not present within the same invoice.
- The invoice amount matches the calculated line-item total.

Rejected invoices do not consume PO quantity.

The three-way match uses a configured **5% price tolerance** when comparing invoice prices against PO prices.

```text
Invoice creation
      ↓
Validate invoice data and quantities
      ↓
Invoice accepted
      ↓
Three-way match
      ├── Within tolerance → Matched
      └── Outside tolerance → Discrepancy
```

Invoice validation and discrepancy resolution are intentionally separate stages.

## 8.6 Invoice List and Retrieval

List endpoint:

```http
GET /api/v1/invoices
```

Single invoice endpoint:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}
```

Both endpoints require authentication.

For supplier users, invoice access is restricted to the authenticated supplier. Internal authorized users can access invoices according to their role permissions.

For supplier users, compliance access follows these rules:

| Compliance state | Invoice reads |
|---|---|
| `cleared` | Allowed, subject to ownership |
| `needs_review` | Allowed, subject to ownership |
| `suspended` | `403 Forbidden` |

## 8.7 Invoice Disputes

An invoice can move from `submitted` to `disputed`. A dispute requires a reason.

Dispute history can record:

```text
reason
actor_id
actor_name
role
timestamp
```

Historical dispute information is retained so that a previously disputed invoice remains identifiable as historically disputed after a later adjustment or approval.

For supplier users, invoice state changes are protected writes. Supplier users in `needs_review` or `suspended` states cannot perform protected writes. Authorized internal roles continue to follow their own role-based permissions.

## 8.8 Invoice Adjustment

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/adjust
```

Required role:

```text
compliance_officer
```

An adjustment is permitted only when the invoice is currently `disputed`.

The operation can update invoice line items and recalculate the invoice amount. The adjustment history records relevant audit information, such as:

```text
actor
reason
timestamp
old amount
new amount
old items
new items
```

The invoice moves to `adjusted` and can subsequently transition to an appropriate final state, such as `approved` or `rejected`, subject to the invoice state machine.

## 8.9 Invoice Transition

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/transition
```

The endpoint applies authentication, role authorization, supplier scoping, and compliance checks as appropriate.

The service validates:

1. Invoice existence
2. Current invoice status
3. Requested target status
4. Whether the transition is legal
5. Applicable supplier compliance access

For supplier users, `cleared` permits otherwise valid protected transitions, while `needs_review` and `suspended` block protected writes.

Illegal transitions return `400 Bad Request`.

The invoice lifecycle remains separate from the P2P state machine.

## 8.10 Historical Dispute-Resolution Suggestions

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Required role:

```text
compliance_officer
```

The endpoint uses classified historical three-way-match resolution data to provide advisory suggestions.

The service:

1. Identifies relevant historical match records.
2. Excludes the current unresolved dispute from the historical pattern.
3. Excludes unresolved historical disputes.
4. Classifies known resolution reasons.
5. Counts recurring resolution actions.
6. Returns a suggestion when there is sufficient classified evidence.

Examples of known patterns include:

```text
Price mismatch     → correct_invoice
Quantity mismatch  → credit_note
```

If the historical evidence is insufficient, the service returns no suggested action.

Suggestions are advisory only. The endpoint does not automatically adjust, approve, reject, or resolve an invoice or three-way match. The final decision remains with an authorized human user.

---

# 9. Invoice and Onboarding Document Management

The Supplier Portal stores invoice PDFs and supplier onboarding documents in **MinIO**, an S3-compatible object-storage service.

Document binaries are stored in MinIO. The application maintains the references required to locate and authorize those objects.

```text
Supplier Portal
      ↓
Document Storage Service
      ↓
MinIO / S3-Compatible Object Storage
      ↓
Invoice PDF or onboarding document
```

The document storage service handles object storage operations. The application remains responsible for authentication, authorization, supplier ownership, and compliance access.

## 9.1 Supported Documents and Configuration

The document-storage implementation covers:

- Invoice PDFs
- Supplier onboarding documents

The local development setup uses Docker to run MinIO. Configuration includes:

```text
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
MINIO_SECURE
MINIO_PRESIGNED_EXPIRY_SECONDS
```

Typical local development values may include:

```text
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_BUCKET=supplier-documents
MINIO_SECURE=false
MINIO_PRESIGNED_EXPIRY_SECONDS=300
```

Credentials should be configured locally through environment variables and must not be committed as real secrets.

## 9.2 Invoice PDF Upload

Endpoint:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint requires authentication and applies the appropriate role and supplier ownership checks.

For supplier users, the authenticated `supplier_id` must match the supplier associated with the invoice.

The document is validated before it is stored in MinIO.

### PDF validation

The upload validates the declared content type, PDF signature, and file size.

| Validation | Requirement |
|---|---|
| Content type | `application/pdf` |
| File signature | Begins with `%PDF-` |
| Maximum size | 10 MB |

A file is not accepted as a PDF solely because its request declares `Content-Type: application/pdf`. The file content must also have the expected PDF signature.

### Compliance access

Invoice document upload is a supplier-facing write operation.

| Compliance state | Upload |
|---|---|
| `cleared` | Allowed, subject to authorization |
| `needs_review` | `403 Forbidden` |
| `suspended` | `403 Forbidden` |

## 9.3 Object References

A document's object key is an internal storage reference, not a public download URL.

Conceptually:

```text
Supplier
   ↓
Invoice / onboarding document
   ↓
Application document reference
   ↓
MinIO object key
   ↓
Stored document
```

MinIO credentials and internal storage authentication details are not exposed to suppliers.

## 9.4 Presigned URL Downloads

Downloads use short-lived presigned URLs.

```text
Authenticated request
        ↓
Identify requested document
        ↓
Check role and supplier compliance access
        ↓
Verify supplier ownership / authorization
        ↓
Check object existence
        ↓
Generate presigned URL
        ↓
Return URL to authorized caller
```

The application must complete authorization before generating a URL. A document ID or object key alone does not grant access.

For supplier users, the expected compliance behavior is:

| Compliance state | Document download |
|---|---|
| `cleared` | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization |
| `suspended` | `403 Forbidden` |

For a suspended supplier, the request is rejected before the MinIO object lookup and before new presigned URL generation.

## 9.5 Invoice PDF Download

Endpoint:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The endpoint requires authentication and enforces the applicable role and supplier ownership checks.

The application returns a temporary signed URL rather than serving the PDF through FastAPI `FileResponse`.

The URL provides time-limited access to the MinIO object. Its configured expiration is controlled by `MINIO_PRESIGNED_EXPIRY_SECONDS`.

## 9.6 Onboarding Document Storage

Supplier onboarding documents use the same MinIO-backed storage model.

The application stores the object reference and verifies authorization before generating a download URL. Supplier-facing downloads also apply compliance access checks.

A supplier must not obtain another supplier's onboarding document URL, even if it knows the other supplier's document identifier or object reference.

## 9.7 Document Error Handling

The document endpoints distinguish authorization errors, missing documents, and storage failures.

| Situation | Expected behavior |
|---|---|
| Cross-supplier access | `403 Forbidden` |
| Suspended supplier | `403 Forbidden` |
| Missing application document or object | `404 Not Found` |
| Storage dependency unavailable | Service error, typically `503 Service Unavailable` |
| Presigned URL generation failure | Appropriate upstream/service error |

The precise status for a storage operation depends on the failure and the endpoint's exception mapping. The implementation should not describe every MinIO error as the same HTTP response.

## 9.8 Document Storage Security

The document-storage implementation follows these principles:

- Store document binaries in MinIO rather than using the local filesystem as the storage backend.
- Keep object references separate from public download URLs.
- Authenticate protected document requests.
- Apply role and supplier ownership checks.
- Apply Round 14 compliance access checks for supplier users.
- Generate presigned URLs only after authorization succeeds.
- Keep presigned URLs short-lived.
- Never expose MinIO credentials to suppliers.
- Reject cross-supplier document access.
- Block suspended suppliers before new MinIO URL generation.

## 9.9 Document Storage Tests

Document storage is covered by unit and integration tests for areas including:

```text
Document storage service
Invoice document downloads
Supplier onboarding document downloads
MinIO integration
Cross-supplier access rejection
Suspended supplier access rejection
Missing object handling
Storage dependency failures
Presigned URL generation
PDF validation
```

Unit tests can mock the storage client to test application behavior. Integration tests should use a running local MinIO instance to verify actual S3-compatible object storage behavior.

Run the relevant tests from the Supplier Portal service directory:

```bash
python -m pytest tests/test_document_storage_service.py -q
python -m pytest tests/test_supplier_document_download.py -q
python -m pytest tests/integration/test_minio_document_storage.py -q
```

The integration test requires the local MinIO environment to be configured and running.

---

# 10. Supplier Statistics

Supplier statistics are available through:

```http
GET /api/v1/suppliers/{supplier_id}/stats
```

The endpoint requires authentication. For supplier users, the authenticated `supplier_id` must match the requested supplier ID.

The response includes operational metrics such as:

```text
supplier_id
po_count
on_time_percentage
average_invoice_cycle_time
```

Supplier statistics are read-only supplier-facing resources. Round 14 adds compliance access enforcement without replacing existing supplier ownership checks.

## 10.1 Supplier-Level Authorization

For supplier users:

```text
Authenticated supplier: SUP001

GET /api/v1/suppliers/SUP001/stats
    → Allowed, subject to compliance access

GET /api/v1/suppliers/SUP002/stats
    → 403 Forbidden
```

A supplier user without a valid `supplier_id` is rejected from supplier-scoped statistics access.

Internal authorized users can access statistics according to their assigned roles and the endpoint's authorization rules.

## 10.2 Round 14 Compliance Access

| Compliance state | Statistics access |
|---|---|
| `cleared` | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization |
| `suspended` | `403 Forbidden` |

The compliance check is applied before supplier statistics are returned.

## 10.3 Purchase Order Count

The PO count represents the total number of Purchase Orders associated with the supplier, including the applicable PO states:

```text
draft
sent
acknowledged
fulfilled
cancelled
```

This is a total count, not the count of only open or fulfilled orders.

## 10.4 Delivery Eligibility and On-Time Percentage

Supplier delivery statistics use the same delivery-eligibility definition as supplier scorecards and monthly delivery trends.

A PO is eligible for delivery-performance calculation when it is fulfilled or when its expected delivery date has passed.

| PO condition | Treatment |
|---|---|
| Fulfilled | Eligible |
| Unfulfilled and past due | Eligible and counted as late |
| Unfulfilled and future due | Excluded |
| Cancelled | Excluded |
| No applicable expected delivery date | Excluded |

For eligible POs:

\[
\text{On-time percentage} =
\frac{\text{On-time eligible POs}}{\text{Eligible POs}} \times 100
\]

A fulfilled PO is on time when its actual delivery date is on or before its expected delivery date.

The actual delivery date is derived from the related Goods Receipt records. When multiple Goods Receipts exist for a PO, the latest applicable `receipt_date` is used.

The calculation must not substitute the current system date for the actual receipt date.

Example:

```text
Eligible POs: 3
On-time POs: 2

On-time percentage: 66.67%
```

If no POs are eligible, the service should follow its implemented zero-eligible-record behavior rather than assuming a percentage.

This delivery-eligibility definition is shared by:

```text
Supplier Statistics
Supplier Scorecard
Supplier Monthly Delivery Trends
```

## 10.5 Average Invoice Cycle Time

Invoice cycle time measures the difference between the invoice date and the associated PO creation date.

Conceptually:

\[
\text{Invoice cycle time} =
\text{Invoice date} - \text{PO creation date}
\]

PO references are obtained from invoice line items:

```text
invoice.items[].po_number
```

The service also supports the legacy/top-level `po_number` field when present.

Example:

```text
PO created:   August 1
Invoice date: August 4

Cycle time: 3 days
```

Negative cycle times and invalid or unusable date records are excluded from the calculation rather than being treated as valid durations.

## 10.6 Date Normalization

The statistics service normalizes supported date representations before performing calculations, including:

```text
date
datetime
ISO date string
ISO datetime string
ISO datetime with Z
```

Normalization helps ensure that date calculations are consistent across stored records.

## 10.7 Supplier Not Found

If the requested supplier cannot be identified in the supplier-related data maintained by the Supplier Portal, the endpoint returns:

```http
404 Not Found
```

Example response:

```json
{
  "detail": "Supplier 'SUP999' not found."
}
```

The exact response depends on the endpoint's implemented exception handling.

## 10.8 Round 5 Scoping and Round 14 Compliance

The statistics endpoint combines the existing supplier-scoping model with Round 14 compliance access.

```text
Authenticated request
        ↓
Platform authentication
        ↓
Role and supplier identity
        ↓
Compliance read-access check
        ↓
Supplier ownership check
        ↓
Statistics calculation
        ↓
Return authorized result
```

A supplier cannot access another supplier's statistics by changing the `supplier_id` in the URL.

The GraphQL API currently exposes PO, invoice, and document operations; supplier statistics remain available through REST. GraphQL resources that are supplier-scoped enforce their own resolver-level authorization and compliance checks.

For supplier-facing GraphQL resources:

```text
cleared
    → Reads and otherwise authorized writes

needs_review
    → Reads allowed; protected writes blocked

suspended
    → Supplier-facing access blocked
```

These controls preserve the existing supplier-level authorization model while applying the additional Round 14 compliance access layer.
# 11. Supplier Performance Scorecard

The Supplier Performance Scorecard provides supplier-level analytics based on Purchase Orders, Goods Receipts, invoices, and dispute history.

**Endpoint**

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

Authentication is required. Supplier users can access only their own scorecard; internal users are governed by their existing role permissions.

## 11.1 Supplier Analytics and Round 14 Enforcement

The scorecard exposes:

- On-time delivery percentage
- Invoice accuracy
- Dispute rate and dispute performance
- Overall score, rating, and performance status
- Purchase Order and invoice metrics
- Monthly performance trends

The scorecard is read-only. Round 14 applies supplier compliance access enforcement:

| Compliance access state | Supplier's own scorecard |
|---|---|
| `cleared` | Allowed |
| `needs_review` | Allowed |
| `suspended` | `403 Forbidden` |

A supplier token without a valid `supplier_id`, or a request targeting another supplier, cannot bypass the existing supplier-ownership checks.

Suspended suppliers receive the configured response:

```text
Supplier account is suspended due to compliance status
```

## 11.2 On-Time Delivery

The scorecard uses the same delivery-eligibility rules as Supplier Statistics.

Eligible Purchase Orders include:

- Fulfilled Purchase Orders
- Past-due, unfulfilled Purchase Orders

Excluded Purchase Orders include:

- Cancelled Purchase Orders
- Future-due, unfulfilled Purchase Orders
- Purchase Orders without an applicable expected delivery date

For fulfilled Purchase Orders, the actual delivery date is derived from the related Goods Receipt records. When multiple receipts exist, the latest applicable `receipt_date` is used.

The comparison is:

```text
actual_delivery_date <= expected_delivery
```

A delivery on the expected date is on time. A delivery after the expected date is late. Past-due, unfulfilled Purchase Orders count as late, while future-due, unfulfilled Purchase Orders are excluded.

**Documented overall-score weight: 40%.**

## 11.3 Invoice Accuracy

Invoice accuracy is calculated from the supplier's invoice history:

```text
invoice accuracy =
    accurate invoices / total invoices × 100
```

In the implemented calculation, invoices without recorded dispute information are treated as accurate. This is a calculation rule, not an independent verification that every invoice is correct.

**Documented overall-score weight: 40%.**

## 11.4 Dispute Rate and Dispute Performance

An invoice is treated as historically disputed when:

```python
invoice.get("dispute") is not None
```

The dispute rate is:

```text
dispute rate =
    disputed invoices / total invoices × 100
```

The scorecard converts dispute rate into dispute performance:

```text
dispute performance = 100 - dispute rate
```

**Documented overall-score weight for dispute performance: 20%.**

Historical dispute information is retained after later adjustment or approval, so a resolved dispute continues to contribute to historical dispute metrics.

## 11.5 Overall Score

The documented calculation combines the three metrics:

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

Overall score =
    (75 × 0.40)
  + (80 × 0.40)
  + (90 × 0.20)

  = 30 + 32 + 18
  = 80
```

The final score, rating, and performance status are derived from the scorecard implementation. Confirm the documented weights against the current service code before treating them as a verified production rule.

## 11.6 Scorecard Details

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

Invoice cycle-time calculations use `invoice.items[].po_number` to associate an invoice with its Purchase Order. The service also supports a legacy top-level PO reference where present.

## 11.7 Monthly Trends and Invoice-Only Suppliers

Monthly supplier trends are grouped by Purchase Order creation month and use the same delivery-eligibility and Goods Receipt date rules as the main scorecard.

The service can also identify a supplier from invoice data when that supplier has no Purchase Orders. Supplier identification can therefore use relevant Purchase Order **or** invoice data, avoiding a `404 Not Found` solely because the supplier currently has no Purchase Orders.

## 11.8 Scorecard Access Model

Supplier scorecard access combines:

```text
Platform Authentication
        ↓
Supplier Identity
        ↓
Compliance Access
        ↓
Supplier Ownership
        ↓
Scorecard Data
```

Both compliance enforcement and supplier scoping remain active. Internal users continue to use their existing role-based permissions.

---

# 12. Procure-to-Pay Lifecycle

The Supplier Portal implements a Procure-to-Pay (P2P) workflow connecting Purchase Orders, shipment processing, Goods Receipts, invoices, three-way matching, and payment approval.

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

The workflow uses an explicit P2P state machine. Round 14 adds supplier compliance enforcement before protected supplier-facing operations without replacing the underlying state machine.

## 12.1 P2P State Machine

The P2P processing states are separate from the legacy Purchase Order lifecycle.

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

The state machine validates the current state before allowing a transition. Invalid transitions are rejected rather than allowing the transaction to skip required processing stages.

The Purchase Order lifecycle separately manages statuses such as:

```text
draft
sent
acknowledged
fulfilled
cancelled
```

These concepts remain independent:

```text
Purchase Order Lifecycle
        +
P2P Processing State
        +
Supplier Compliance Access
```

Compliance changes do not overwrite the Purchase Order lifecycle or P2P state.

## 12.2 Shipment Notice

After acknowledgement, the transaction can progress to shipment processing.

```text
acknowledged
      ↓
shipped
```

Shipment-related operations validate the related Purchase Order and supplier context before advancing the P2P state.

For supplier users, protected shipment writes require `cleared` compliance access. Suppliers in `needs_review` or `suspended` are denied the applicable write operation. Internal users remain governed by their existing role permissions.

## 12.3 Goods Receipt

Goods Receipt represents the receiving of shipped goods. Receipt information can include:

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

Validation includes Purchase Order existence, supplier ownership, item-code validity, quantity rules, duplicate-item detection, and receipt information.

The expected P2P transition is:

```text
shipped
   ↓
received
```

The recorded `receipt_date` is also used to determine the actual delivery date for supplier performance calculations.

### Partial Goods Receipt

Partial receiving is supported. For example:

```text
PO quantity       = 100
Received quantity = 40
```

A receipt can omit PO items when only part of the order has been received. Each included item must have a positive quantity that does not exceed the corresponding PO quantity. Extra PO items and duplicate item codes within a receipt are rejected.

This allows partial deliveries to reach three-way matching for further evaluation.

## 12.4 Invoice Integration

P2P invoicing requires the transaction to have reached `received` before progressing to `invoiced`.

The existing invoice lifecycle remains separate:

```text
submitted
    ├── approved
    ├── rejected
    └── disputed
           ↓
        adjusted
```

An invalid or duplicate invoice submission must not advance the P2P state.

For supplier users, invoice submission is a protected write operation:

| Compliance state | P2P invoice submission |
|---|---|
| `cleared` | Allowed when business rules permit |
| `needs_review` | `403 Forbidden` |
| `suspended` | `403 Forbidden` |

## 12.5 Three-Way Match and Payment Approval

Three-way matching compares the Purchase Order, Goods Receipt, and invoice. The result is either a match or a discrepancy requiring human review.

```text
Three-Way Match
      │
      ├── No discrepancy
      │       ↓
      │   Continue toward
      │   payment approval
      │
      └── Discrepancy
              ↓
          Human review
```

A discrepancy must not automatically progress to payment approval. Payment approval remains subject to the implemented business rules and authorized resolution process.

## 12.6 P2P Compliance Enforcement

For supplier-facing operations, the access policy is:

| Operation | `cleared` | `needs_review` | `suspended` |
|---|---|---|---|
| View permitted POs and P2P information | Allow | Allow | 403 |
| Acknowledge PO | Allow | 403 | 403 |
| Protected shipment/P2P write | Allow | 403 | 403 |
| Submit invoice | Allow | 403 | 403 |

The underlying business rules still apply when compliance access is allowed. `cleared` does not make an invalid state transition valid.

The conceptual enforcement sequence is:

```text
Authentication
      ↓
Supplier Identity
      ↓
Compliance Access
      ↓
Supplier Ownership
      ↓
P2P Business Validation
      ↓
State Transition
```

## 12.7 Active Supplier Requirement

Purchase Order creation is connected to supplier onboarding. A supplier must exist and have reached the required active onboarding status before the service allows Purchase Order creation.

```text
Registration
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

The onboarding activation check and Round 14 event-driven access state serve different purposes.

- **Activation check:** calls the Compliance Service before an approved supplier becomes active.
- **Event-driven access:** updates supplier access when a later compliance status-change event is consumed from Kafka.

The onboarding `status` and `compliance_access_status` are separate fields/concepts. A supplier can remain onboarding-status `active` while its compliance access becomes `needs_review` or `suspended`.

---

# 13. Three-Way Match

The Supplier Portal implements three-way matching between:

```text
Purchase Order
      +
Goods Receipt
      +
Invoice
```

The matching process evaluates item codes, ordered quantities, received quantities, invoiced quantities, PO prices, and invoice prices.

Its purpose is to identify exceptions before a transaction proceeds toward payment approval.

## 13.1 Quantity Matching

The matching process evaluates quantities across the PO, Goods Receipt, and invoice.

Example:

```text
PO quantity       = 100
Received quantity = 90
Invoice quantity  = 100
```

The difference can be identified as a quantity discrepancy and routed for human review.

Because partial Goods Receipt is supported, a short receipt can reach the matching stage instead of being rejected simply because the entire PO quantity has not arrived.

## 13.2 Price Matching and Tolerance

Invoice creation does not reject an otherwise valid invoice solely because its unit price differs from the Purchase Order price. The difference can therefore be evaluated by three-way matching.

The configured tolerance is:

```text
PRICE_TOLERANCE_PERCENT = 5.0
```

The tolerance is inclusive. For a PO unit price of `100`, values `95`, `100`, and `105` are within the configured ±5% range, while `106` is outside it.

Example:

```text
PO unit price      = 100
Invoice unit price = 120
```

This price difference is outside the tolerance and can be flagged for human review.

The tolerance is a matching rule, not an invoice-creation rejection rule.

## 13.3 Match Results and Discrepancy Handling

The match result indicates whether the relevant PO, receipt, and invoice information satisfies the implemented matching rules.

```text
Three-Way Match
      │
      ├── Matched
      │      ↓
      │  Continue toward
      │  payment approval
      │
      └── Discrepancy
             ↓
         Human review
```

Supported discrepancy categories include quantity mismatch and price mismatch. A material discrepancy is not automatically approved for payment.

## 13.4 P2P Integration

Three-way matching takes place after the transaction has progressed through acknowledgement, shipment, receipt, and invoicing.

The P2P state machine and matching logic remain responsible for their respective business rules. Round 14 adds compliance access enforcement to protected supplier-facing operations; it does not change the matching algorithm or the configured price tolerance.

## 13.5 Historical Dispute-Resolution Suggestions

The Supplier Portal provides advisory suggestions based on historical, resolved three-way-match disputes.

**Endpoint**

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

**Authorization:** `compliance_officer`

The service analyzes historical resolved disputes and identifies previously used resolution patterns. It does not automatically change invoice, match, or payment state.

Implemented historical patterns include:

| Historical resolution pattern | Suggested action |
|---|---|
| Price mismatch | `correct_invoice` |
| Quantity mismatch | `credit_note` |

Unresolved historical disputes are ignored. Records without sufficient evidence for a known action are not assigned an automatic action, and the current unresolved dispute is not used as its own historical evidence.

The result is advisory:

```text
Historical resolved disputes
          ↓
Pattern analysis
          ↓
Advisory suggestion
          ↓
Human decision
```

## 13.6 Human Review Requirement

The matching system identifies exceptions rather than making an uncontrolled automatic business decision. A successful match can proceed toward payment approval according to the P2P state machine. A discrepancy requires controlled review and resolution before any permitted subsequent transition.

---

# 14. Supplier Onboarding

The Supplier Portal implements a supplier onboarding workflow for registering, verifying, approving, and activating suppliers.

```text
Registration
      ↓
Document Collection
      ↓
Mock Verification
      ↓
Approval
      ↓
Compliance Check
      ↓
Active
```

The onboarding service validates the current stage before allowing progression. A supplier that has only registered is not considered active, and approval alone does not activate the supplier.

## 14.1 Registration and Document Collection

Registration creates the supplier onboarding record. The document-collection stage gathers the required supplier documents but does not itself activate the supplier.

Onboarding documents use the MinIO-backed document-storage layer. Upload validation includes:

- Content type
- File extension
- File content
- File size

The maximum supported document size is **10 MB**. Invalid uploads are rejected.

Supplier ownership is checked independently of file validation. During document download, ownership is verified before a short-lived MinIO presigned URL is generated. Round 14 prevents suspended suppliers from reaching protected document retrieval and URL-generation steps.

## 14.2 Mock Verification

The current implementation uses mock verification logic for development and functional validation. It represents the document and supplier-information review stage before approval; it is not an integration with an external supplier-verification provider.

## 14.3 Approval and Activation

After successful verification, the supplier can reach the approved state. Activation then requires a successful Compliance Service decision.

The Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

The Compliance client is configured through:

```text
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

The default URL is for local development. The request includes supplier information such as:

```json
{
  "supplier_id": "SUP001",
  "supplier_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

It also includes the caller header:

```text
X-Caller-Service: supplier-portal
```

The integration is implemented through a dedicated Compliance client rather than embedding the HTTP call directly in the route handler.

## 14.4 Compliance Decisions

The Compliance Service can return `CLEAR`, `BLOCK`, or `REVIEW`.

| Result | HTTP response | Activation outcome |
|---|---:|---|
| `CLEAR` and `cleared: true` | 201 | Supplier becomes `active` |
| `BLOCK` | 409 | Remains `approved` |
| `REVIEW` | 409 | Remains `approved` |
| Timeout, connection, or network failure | 503 | Remains `approved` |
| Service error or unusable response | 502 | Remains `approved` |

Only a successful `CLEAR` decision with `cleared = true` allows activation.

The integration uses typed exceptions:

```text
ComplianceBlockedError
    → 409 Conflict

ComplianceServiceUnavailableError
    → 503 Service Unavailable

ComplianceServiceError
    → 502 Bad Gateway
```

This avoids basing HTTP behavior on free-form error-message text.

## 14.5 Fail-Closed Activation

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

If the Compliance Service cannot provide a usable clearance decision, the Supplier Portal does not activate the supplier. The supplier remains `approved`, and activation can be retried after the dependency becomes available.

## 14.6 Activation Compliance vs Event-Driven Compliance

The synchronous activation check and Round 14 Kafka consumer are separate integrations.

**Activation compliance**

```text
Approved supplier
       ↓
Compliance internal-check
       ↓
CLEAR + cleared=true
       ↓
Active
```

**Event-driven access compliance**

```text
Compliance status change
       ↓
Kafka event
       ↓
Supplier Portal consumer
       ↓
cleared / needs_review / suspended
```

The first determines whether the supplier can become active. The second enforces later compliance status changes without replacing the onboarding lifecycle.

---

# Round 14. Event-Driven Supplier Compliance Access

Round 14 adds an event-driven compliance access layer to the Supplier Portal. The service consumes compliance status-change events from Apache Kafka and enforces the resulting access state across protected supplier-facing resources.

## R14.1 Kafka Event Flow

The topic is:

```text
compliance.supplier.status_changed
```

The consumer group is:

```text
supplier-portal-service
```

The high-level flow is:

```text
Compliance Service
       ↓
Apache Kafka
       ↓
Supplier Portal Consumer
       ↓
Event Validation
       ↓
Supplier Compliance Service
       ↓
Compliance Access State
       ↓
REST and GraphQL Enforcement
```

The event consumer is independent of the synchronous Compliance activation check.

## R14.2 Event Status Mapping

The event's `new_status` maps to the Supplier Portal's compliance access state:

| Compliance event status | Supplier Portal access state |
|---|---|
| `CLEAR` | `cleared` |
| `REVIEW` | `needs_review` |
| `BLOCK` | `suspended` |

The onboarding status is not overwritten. For example, a supplier can have onboarding status `active` and compliance access state `suspended`.

## R14.3 Event Contract

The consumer validates the versioned event structure. A representative event is:

```json
{
  "event_id": "uuid",
  "event_type": "compliance.supplier.status_changed",
  "event_version": 1,
  "occurred_at": "2026-10-08T10:00:00Z",
  "producer": "compliance-service",
  "payload": {
    "supplier_id": "SUP001",
    "old_status": "CLEAR",
    "new_status": "BLOCK",
    "matched_list": ["OFAC"],
    "reason": "Supplier matched a compliance list."
  }
}
```

The payload must contain the supplier identity and status-change information. The consumer validates the event structure, type, version, timestamp, supplier identity, and compliance status before applying it.

**Important:** `payload.supplier_id` is required. The Supplier Portal does not infer supplier identity from `supplier_name` or `country`. Invalid or ambiguous events are not applied to supplier state.

## R14.4 Kafka Configuration

The relevant settings are:

```text
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=supplier-portal-service
KAFKA_STATUS_CHANGED_TOPIC=compliance.supplier.status_changed
KAFKA_DLQ_TOPIC=compliance.supplier.status_changed.dlq
KAFKA_AUTO_OFFSET_RESET=earliest
```

Automatic offset commits are disabled:

```text
enable.auto.commit = false
```

The consumer commits the offset after successful processing or after a failed/invalid event has been successfully published to the dead-letter topic.

## R14.5 Compliance Access Rules

The access states have the following meaning:

| State | Read access | Protected supplier writes |
|---|---|---|
| `cleared` | Allowed, subject to existing authorization | Allowed when business rules permit |
| `needs_review` | Allowed, subject to existing authorization | Restricted |
| `suspended` | Denied for protected supplier-facing resources | Denied |

Internal roles continue to use their existing role-based authorization model. Supplier ownership checks remain in effect regardless of compliance state.

## R14.6 Access Enforcement Matrix

| Supplier-facing operation | `cleared` | `needs_review` | `suspended` |
|---|---|---|---|
| View Purchase Orders | Allow | Allow | 403 |
| View individual Purchase Order | Allow | Allow | 403 |
| View permitted P2P information | Allow | Allow | 403 |
| Acknowledge or modify a PO | Allow when valid | 403 | 403 |
| Submit invoice | Allow when valid | 403 | 403 |
| Protected invoice transition | Allow when valid | 403 | 403 |
| Upload invoice document | Allow | 403 | 403 |
| Download own invoice document | Allow | Allow | 403 |
| View permitted onboarding documents | Allow | Allow | 403 |
| View supplier statistics | Allow | Allow | 403 |
| View supplier scorecard | Allow | Allow | 403 |
| GraphQL queries | Allow | Allow | 403 |
| GraphQL mutations | Allow when valid | 403 | 403 |

This matrix describes the compliance layer, not a replacement for endpoint-specific permissions or resource ownership validation.

For a supplier in `needs_review`, the standard restricted-write message is:

```text
Supplier account is under compliance review. This action is not permitted.
```

For a suspended supplier, the standard access-denial message is:

```text
Supplier account is suspended due to compliance status
```

## R14.7 Document and MinIO Protection

Document download requires authorization before protected object access.

For a suspended supplier, the request is rejected before MinIO object lookup or presigned URL generation:

```text
Authenticated request
       ↓
Compliance access check
       ↓
Suspended
       ↓
403 Forbidden
```

Therefore, the blocked request does not proceed to:

```text
MinIO object lookup
       ↓
Presigned URL generation
```

This prevents a suspended supplier from obtaining a new download URL through the protected document endpoint.

## R14.8 REST and GraphQL Protection

The REST enforcement layer applies the compliance access policy to protected supplier-facing resources.

The GraphQL layer applies equivalent compliance checks at the resolver/access-control layer. A supplier cannot bypass REST restrictions by invoking a GraphQL query or mutation directly.

Existing authentication, role checks, supplier ownership checks, and business validation continue to apply.

## R14.9 Event Idempotency

The consumer uses `event_id` to identify duplicate events.

```text
First delivery
    ↓
Validate and process

Duplicate delivery
    ↓
Recognize previously processed event
    ↓
Do not apply a duplicate state change
```

This protects the compliance state and audit history from duplicate processing when Kafka redelivers an event.

## R14.10 Out-of-Order Event Handling

Events are ordered per supplier using `occurred_at`.

For example:

```text
Event A: 10:00 — BLOCK
Event B: 09:59 — CLEAR
```

If the later event has already established the current state, the older event is treated as stale and must not revert the supplier to the older status.

```text
Incoming event
       ↓
Compare occurred_at with stored timestamp
       ├── Newer → Apply
       └── Stale → Ignore
```

This protects the current compliance access state from out-of-order event delivery.

## R14.11 Audit Trail and Persistence

Successfully applied events record audit information such as:

```text
event_id
supplier_id
old_status
new_status
matched_list
reason
occurred_at
processed_at
```

A later `CLEAR` event can restore access without removing the historical record of an earlier suspension.

The current implementation stores Round 14 compliance state, processed-event/idempotency information, and audit history in **SQLite-backed storage**. These records are therefore distinct from the in-memory Purchase Order, invoice, and contract business stores.

Durability and recovery still depend on preserving and backing up the configured SQLite database file.

## R14.12 Offset Commit and Failure Handling

The consumer follows this processing sequence:

```text
Consume event
     ↓
Deserialize and validate
     ↓
Process compliance state
     ↓
Persist successful processing
     ↓
Commit offset
```

For invalid events, the consumer attempts to publish the original event information to the DLQ and commits the source offset only after the DLQ publication succeeds.

If processing fails unexpectedly, the offset is not committed, allowing Kafka to redeliver the event.

This provides at-least-once processing behavior. Idempotency protects against duplicate application when an event is redelivered.

## R14.13 Dead-Letter Topic

Malformed or invalid events are routed to:

```text
compliance.supplier.status_changed.dlq
```

The intended flow is:

```text
Kafka event
     ↓
Deserialize and validate
     ├── Valid → Process → Commit
     └── Invalid → Publish to DLQ → Commit
```

The original event information is preserved for investigation. If DLQ publication fails, the consumer must not treat the source event as successfully handled.

## R14.14 Consumer Lifecycle

The Kafka consumer is started and stopped with the FastAPI application lifecycle rather than creating a long-lived connection at module import time.

```text
Application startup
       ↓
Consumer runner
       ↓
Background consumer
       ↓
Subscribe to status-change topic
```

During shutdown, the runner stops the consumer and closes the Kafka connection.

## R14.15 Implementation Files

The Round 14 implementation is organized into dedicated components:

```text
app/
├── schemas/
│   └── events.py
├── services/
│   ├── supplier_compliance_service.py
│   ├── kafka_consumer.py
│   └── kafka_consumer_runner.py
├── core/
│   ├── auth.py
│   └── config.py
└── main.py
```

Related tests include:

```text
tests/
├── test_kafka_consumer.py
└── test_r14_enforcement.py
```

The existing invoice, PO, GraphQL, MinIO, onboarding, statistics, and scorecard modules remain responsible for their respective business functionality.

## R14.16 Local Kafka Development

The development environment includes Kafka alongside the existing MinIO service. The configured Kafka broker is exposed on port `9092`.

Create the status-change topic:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic compliance.supplier.status_changed --partitions 1 --replication-factor 1
```

Create the dead-letter topic:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic compliance.supplier.status_changed.dlq --partitions 1 --replication-factor 1
```

List topics:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Inspect consumer groups:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
```

Inspect the Supplier Portal consumer group:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group supplier-portal-service
```

Expected topic names:

```text
compliance.supplier.status_changed
compliance.supplier.status_changed.dlq
```

Expected consumer group:

```text
supplier-portal-service
```

## R14.17 Testing

Kafka consumer unit tests are designed to run without a live Kafka broker. Coverage includes:

- Valid events and CLEAR, REVIEW, and BLOCK mappings
- Suspended supplier and needs-review enforcement
- Access restoration after CLEAR
- Duplicate and out-of-order events
- Invalid events and unknown suppliers
- DLQ publication
- Offset commits and processing failures
- Consumer configuration and group settings

The broader regression suite covers enforcement across REST, GraphQL, invoices, Purchase Orders, document downloads, MinIO access, supplier statistics, and the scorecard.

Run tests from the `services/supplier-portal` directory:

```powershell
python -m pytest tests/test_kafka_consumer.py tests/test_r14_enforcement.py -q
```

This command runs the targeted tests; it does not imply that the full test suite has passed.

## R14.18 End-to-End Access Flow

```text
Compliance Service
       ↓
Status-change event
       ↓
Kafka
       ↓
Supplier Portal consumer
       ↓
Validate event and supplier identity
       ↓
Check idempotency and event ordering
       ↓
Persist compliance state and audit information
       ↓
Supplier access enforcement
       ├── REST
       ├── GraphQL
       └── Protected documents
```

The external Compliance producer owns production event publication. The Supplier Portal validates the agreed event contract and requires `payload.supplier_id`; it does not guess the supplier identity from a name or country.

Round 14 does not modify the Platform Service, decode JWTs locally, replace the onboarding lifecycle, change the P2P state machine, change the three-way-match tolerance, or alter MinIO storage semantics.

---

# 15. Supplier Contract Lifecycle Management

The Supplier Portal provides REST-based Supplier Contract Lifecycle Management for tracking contract terms, expiry, renewals, and lifecycle history.

Supplier contracts are not currently exposed through the Round 13 GraphQL API.

## 15.1 Contract Information and Status

A contract can contain:

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

The documented contract statuses are:

```text
draft
active
renewed
expired
```

The lifecycle supports draft activation and renewal/expiry handling. A renewed contract continues into its next active period, while history retains information about the previous period and renewal action.

Contract lifecycle status remains separate from supplier compliance access. For example, a contract can remain `active` while its supplier's compliance access is `suspended`.

## 15.2 Contract Creation

**Endpoint**

```http
POST /api/v1/supplier-contracts
```

**Authorization:** `procurement_manager`

Creation validates supplier existence, supplier active status, contract-number uniqueness, date validity, and required contract information.

A new contract begins in `draft`, and the service records its initial history entry.

## 15.3 Contract Update

**Endpoint**

```http
PUT /api/v1/supplier-contracts/{contract_id}
```

**Authorization:** `procurement_manager`

Mutable terms can include:

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

Supplier identity and contract number are not treated as freely mutable terms. Expired contracts cannot be arbitrarily modified through the normal update operation.

The service records actual term changes in history, including previous and new values where supported. No-op updates do not create unnecessary history entries.

Example:

```text
payment_terms:
    old → Net 30
    new → Net 45
```

## 15.4 Contract Activation

**Endpoint**

```http
POST /api/v1/supplier-contracts/{contract_id}/activate
```

**Authorization:** `procurement_manager`

A draft contract can be activated after validation:

```text
draft
  ↓
active
```

The transition is recorded in contract history.

## 15.5 Expiry Tracking

Contract responses can expose:

```text
expiring_soon
days_until_expiry
status
end_date
```

The `renewal_notice_days` value defines the normal renewal-warning window. Expired contracts are not treated as active contracts and are excluded from the normal expiring-soon result.

**Endpoint**

```http
GET /api/v1/supplier-contracts/expiring
```

An optional supplier filter can restrict the results to a particular supplier.

## 15.6 Contract Renewal

**Endpoint**

```http
POST /api/v1/supplier-contracts/{contract_id}/renew
```

**Authorization:** `procurement_manager`

The renewal request accepts:

```text
new_start_date
new_end_date
reason
```

The service validates the new dates, updates the contract period, and records renewal information such as:

```text
previous_end_date
new_start_date
new_end_date
renewed_at
renewed_by
reason
```

The current implementation reuses the same contract record for renewal. The history preserves the previous period and renewal action.

## 15.7 Contract History and Audit

**Endpoint**

```http
GET /api/v1/supplier-contracts/{contract_id}/history
```

History can include contract creation, activation, term updates, renewal, and status changes.

Records can contain:

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

The service validates the operation, applies the permitted change, and records actor and timestamp information where applicable. Term-change history captures changed fields and their previous/new values.

Contract lifecycle audit history is separate from Round 14's supplier compliance event audit history.

## 15.8 Supplier Scoping and Compliance Access

Where supplier-facing contract access is supported, supplier users can access only contracts belonging to their authenticated supplier.

```text
Authenticated supplier_id
        ↓
Contract supplier_id
        ├── Same → Continue authorization
        └── Different → 403 Forbidden
```

Contract creation, activation, update, and renewal are restricted to the appropriate procurement role.

Round 14 compliance access is an independent layer:

| Compliance state | Supplier-facing contract access |
|---|---|
| `cleared` | Permitted access, subject to normal authorization |
| `needs_review` | Read-only access where available; protected writes restricted |
| `suspended` | Supplier-facing access denied |

Internal procurement operations continue to follow their existing role permissions. Compliance access does not rewrite the contract number, contract status, renewal history, or contract lifecycle history.

## 15.9 Contract Lifecycle Limitations

### In-memory storage

Contract data is currently maintained in application memory:

```python
supplier_contracts: dict[str, dict] = {}
supplier_contract_history: dict[str, list[dict]] = {}
```

Consequently, contract records and history are not durable across a full application restart. A persistent database can be introduced as a later production-hardening task.

### Auto-renew configuration

The `auto_renew` field is stored as contract configuration. The current implementation does not run a background scheduler that automatically renews contracts.

```text
auto_renew = true
```

does not, by itself, execute a renewal. Renewal remains an explicit business operation.

### Contract versioning

Renewals reuse the same contract record rather than creating a separate version-numbered record for each contract period. History retains the previous dates and renewal information.

## 15.10 Contract API Summary

The contract lifecycle endpoints are:

```http
POST /api/v1/supplier-contracts
GET  /api/v1/supplier-contracts
GET  /api/v1/supplier-contracts/expiring
GET  /api/v1/supplier-contracts/{contract_id}
PUT  /api/v1/supplier-contracts/{contract_id}
POST /api/v1/supplier-contracts/{contract_id}/activate
POST /api/v1/supplier-contracts/{contract_id}/renew
GET  /api/v1/supplier-contracts/{contract_id}/history
```

Together, these endpoints provide contract creation, term management, activation, expiry tracking, renewal, lifecycle history, audit information, and supplier scoping.

---

# GraphQL Scope — Round 13

The Round 13 Strawberry GraphQL API focuses on the frontend resources currently supported by the implementation:

```text
Purchase Orders
Invoices
Documents
```

GraphQL provides Purchase Order and invoice queries, document queries, cursor pagination, an acknowledge-PO mutation, and resolver-level supplier scoping.

Supplier contracts continue to use REST endpoints. The GraphQL implementation does not imply that every REST resource has been converted to GraphQL.

```text
Frontend / Client
       │
   ┌───┴────────┐
   │            │
   ▼            ▼
 REST API   GraphQL API
   │            │
   │       GraphQL Resolvers
   │            │
   └─────┬──────┘
         ▼
   Existing Service Layer
         │
     ┌───┴─────┐
     │         │
     ▼         ▼
Business Data  MinIO
```

Round 14 adds Kafka as an asynchronous compliance-status input to the same Supplier Portal service:

```text
Compliance Service
       ↓
Apache Kafka
       ↓
Supplier Portal Consumer
       ↓
Compliance Access State
       ↓
REST and GraphQL Enforcement
```

REST and GraphQL continue to apply their existing authentication, role, supplier-ownership, and business-validation rules in addition to compliance access enforcement.

# 16. API Reference

The Supplier Portal exposes REST APIs under the `/api/v1` prefix and a Strawberry GraphQL API at `/graphql`.

The root endpoint `/` is not part of the `/api/v1` prefix.

Protected REST and GraphQL operations use centralized authentication through the Platform Service. Depending on the operation, authorization includes role checks, supplier ownership, compliance access state, and business-state validation.

## 16.1 Root Endpoint

| Method | Endpoint | Authentication | Description |
|---|---|---|---|
| GET | `/` | Public | Returns the service health/message response |

## 16.2 Purchase Order APIs

| Method | Endpoint | Authorization | Description |
|---|---|---|---|
| POST | `/api/v1/purchase-orders` | `procurement_manager` | Create a Purchase Order |
| GET | `/api/v1/purchase-orders` | Authenticated | List Purchase Orders |
| GET | `/api/v1/purchase-orders/{po_number}` | Authenticated | Retrieve a Purchase Order |
| PUT | `/api/v1/purchase-orders/{po_number}` | Authenticated; role/business rules apply | Update a Purchase Order |
| DELETE | `/api/v1/purchase-orders/{po_number}` | Authenticated; role/business rules apply | Delete a Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/acknowledge` | Owning supplier | Acknowledge a Purchase Order |
| POST | `/api/v1/purchase-orders/{po_number}/transition` | `procurement_manager` | Transition a Purchase Order |
| GET | `/api/v1/purchase-orders/{po_number}/events` | Authenticated | Retrieve Purchase Order events |
| POST | `/api/v1/purchase-orders/bulk-send` | `procurement_manager` | Send Purchase Orders in bulk |

For supplier users, collection and applicable detail operations are restricted to Purchase Orders belonging to the authenticated supplier.

Example:

```text
Authenticated supplier: SUP001
Requested Purchase Order belongs to: SUP002

Result: 403 Forbidden
```

Supplier collection requests return only the authenticated supplier's Purchase Orders.

### Round 14 compliance policy

| Compliance state | Supplier-facing access |
|---|---|
| `CLEARED` | Permitted operations proceed subject to normal authorization and business rules |
| `NEEDS_REVIEW` | Permitted reads are allowed; protected supplier writes are rejected |
| `SUSPENDED` | Supplier-facing access is rejected |

Internal users remain subject to their assigned roles and endpoint-specific permissions.

## 16.3 Invoice APIs

| Method | Endpoint | Authorization | Description |
|---|---|---|---|
| GET | `/api/v1/invoices` | Authenticated | List invoices |
| POST | `/api/v1/invoices` | Authenticated; business rules apply | Create an invoice |
| GET | `/api/v1/invoices/{supplier_id}/{invoice_number}` | Authenticated | Retrieve an invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Endpoint-specific authorization | Transition an invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust` | `compliance_officer` | Adjust a disputed invoice |
| POST | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Owning supplier | Upload an invoice PDF |
| GET | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Authenticated; supplier-scoped | Obtain an invoice document URL |

Invoice identity is scoped by the combination:

```text
(supplier_id, invoice_number)
```

For supplier users, invoice collections and applicable detail operations are scoped to the authenticated supplier. A supplier token cannot be used to retrieve another supplier's invoices.

Compliance access is also enforced:

- `CLEARED`: permitted invoice operations may proceed.
- `NEEDS_REVIEW`: permitted invoice reads remain available; protected writes, such as invoice creation, transitions, and uploads, are blocked.
- `SUSPENDED`: supplier-facing invoice access is blocked.

Internal users continue to follow endpoint-specific role permissions.

## 16.4 Invoice Document APIs

Invoice PDF binaries are stored in MinIO, an S3-compatible object-storage service. The application retains the object reference or associated metadata needed to locate each document.

### Upload

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

Invoice documents are PDF-only, with a maximum file size of **10 MB**.

The upload flow validates the applicable authentication, supplier ownership, compliance state, file content/type, and file-size requirements before storing the document in MinIO.

### Download

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The application returns a short-lived presigned URL rather than streaming the PDF through the Supplier Portal.

The intended authorization flow is:

```text
Authenticate
    ↓
Verify supplier ownership
    ↓
Check compliance access
    ↓
Locate the document reference
    ↓
Check the stored object
    ↓
Generate a short-lived presigned URL
    ↓
Return the URL
```

Authorization must occur before generating a presigned URL. A suspended supplier or a supplier requesting another supplier's document must not receive a new presigned URL.

Expected behavior, subject to the endpoint's implemented error mapping:

| Condition | Expected result |
|---|---|
| Authorized access to an existing document | `200 OK` with the document URL |
| Supplier requests another supplier's document | `403 Forbidden` |
| Suspended supplier requests supplier-facing access | `403 Forbidden` |
| Requested document does not exist | `404 Not Found` |
| Required storage dependency is unavailable | Service-unavailable response |

Invoice document rules are different from onboarding document rules:

- **Invoice documents:** PDF only, maximum 10 MB.
- **Onboarding documents:** PDF, JPG/JPEG, PNG, DOC, or DOCX, subject to the onboarding validator's size and content rules.

## 16.5 Supplier Onboarding APIs

Supplier onboarding covers registration, document collection, verification, approval, compliance checks, activation, status, and history.

Onboarding document operations validate the applicable file type, extension, content, empty-file condition, size limit, and supplier authorization.

The supported onboarding formats are:

```text
PDF
JPG / JPEG
PNG
DOC
DOCX
```

Onboarding document binaries are stored in MinIO. The application retains the corresponding object references and metadata.

Downloads must authorize the supplier before generating a presigned URL. Cross-supplier document access is rejected, and suspended suppliers cannot obtain new supplier-facing document URLs.

Supplier activation requires a successful Compliance Service clearance. The synchronous activation check is separate from the asynchronous Round 14 event consumer.

## 16.6 GraphQL API

The Strawberry GraphQL endpoint is:

```http
POST /graphql
```

The GraphQL layer uses the existing Platform Service authentication mechanism and passes authenticated user information into the GraphQL context.

The implemented GraphQL scope includes:

- Purchase Order queries and collections.
- Invoice queries and collections.
- Supplier document queries.
- Purchase Order acknowledgement mutation.
- Cursor-based Purchase Order collection pagination.

Contract management remains available through REST unless a GraphQL contract operation is explicitly implemented.

### GraphQL query areas

```text
purchaseOrder
purchaseOrders

invoice
invoices

documents
```

The exact field names and argument types are defined by the active Strawberry schema.

### GraphQL authorization flow

```text
GraphQL request
       ↓
Platform token verification
       ↓
Authenticated GraphQL context
       ↓
Compliance access enforcement
       ↓
Resolver-level authorization
       ↓
Supplier ownership check
       ↓
Existing Supplier Portal business service
       ↓
GraphQL response
```

Supplier scoping must be enforced inside the applicable resolvers, not solely at the `/graphql` route.

A supplier must not be able to retrieve another supplier's records by changing GraphQL arguments or pagination cursors.

### Purchase Order pagination

The Purchase Order connection supports the following pagination concepts:

```text
first
after
hasNextPage
endCursor
```

The maximum page size is governed by the GraphQL implementation.

Supplier filtering must be applied before pagination so that a supplier receives only its authorized records.

If cursors are based on an in-memory list position, changes to the list may affect subsequent pagination results. This is a limitation of position-based cursors and should be considered when moving to persistent database-backed pagination.

### Acknowledge Purchase Order mutation

The acknowledgement mutation calls the existing Purchase Order acknowledgement business logic after the applicable authentication, compliance, and supplier-ownership checks.

```text
Authenticate
    ↓
Check compliance access
    ↓
Find Purchase Order
    ↓
Verify supplier ownership
    ↓
Call existing acknowledgement service
    ↓
Return the updated Purchase Order
```

`NEEDS_REVIEW` and `SUSPENDED` suppliers cannot perform a protected supplier-facing acknowledgement. A supplier cannot acknowledge another supplier's Purchase Order.

## 16.7 Procure-to-Pay APIs

P2P operations cover the following business stages:

| Stage | Purpose |
|---|---|
| Shipment | Record shipment and progress the P2P state |
| Goods receipt | Record received goods |
| Invoice | Submit an invoice after the required receipt state |
| Three-way match | Compare Purchase Order, receipt, and invoice data |
| Payment approval | Progress eligible matched transactions toward payment approval |

The implemented P2P lifecycle is:

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

Each operation validates the applicable authentication, role, supplier ownership, compliance state, and current business state.

A discrepancy requires review or resolution before payment approval. It must not be treated as automatic approval.

Supplier-facing operations follow the Round 14 compliance policy. Internal users remain subject to their own role permissions.

## 16.8 Supplier Statistics and Scorecard APIs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/suppliers/{supplier_id}/stats` | Supplier operational statistics |
| GET | `/api/v1/suppliers/{supplier_id}/scorecard` | Supplier performance scorecard |

For supplier users, the authenticated `supplier_id` must match the requested supplier ID.

- `CLEARED`: access is allowed subject to normal authorization.
- `NEEDS_REVIEW`: permitted read access remains available.
- `SUSPENDED`: supplier-facing access is blocked.

Internal users access these resources according to their role permissions.

The scorecard uses the applicable delivery, invoice-accuracy, and dispute-performance metrics defined by the implementation.

## 16.9 Three-Way Match and Resolution Suggestion APIs

Three-way matching compares:

```text
Purchase Order
      +
Goods Receipt
      +
Invoice
```

The matching service evaluates the applicable item codes, quantities, and unit prices. The configured price tolerance is 5%, inclusive.

For a PO unit price of `100`:

```text
95  → Within tolerance
100 → Within tolerance
105 → Within tolerance
106 → Outside tolerance
```

Quantity or price discrepancies are flagged for review. A discrepancy does not automatically approve payment.

The historical resolution-suggestion endpoint is:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Authorization:

```text
compliance_officer
```

The endpoint provides advisory suggestions based on eligible historical resolved disputes. It is read-only: it does not change invoices, matches, P2P state, or payment approval. The current unresolved dispute must not be used as its own historical example.

## 16.10 Supplier Contract APIs

| Method | Endpoint | Authorization | Description |
|---|---|---|---|
| POST | `/api/v1/supplier-contracts` | `procurement_manager` | Create a supplier contract |
| GET | `/api/v1/supplier-contracts` | Authenticated; scope applies | List supplier contracts |
| GET | `/api/v1/supplier-contracts/expiring` | Authenticated; scope applies | List expiring contracts |
| GET | `/api/v1/supplier-contracts/{contract_id}` | Authenticated; scope applies | Retrieve a contract |
| PUT | `/api/v1/supplier-contracts/{contract_id}` | `procurement_manager` | Update a contract |
| POST | `/api/v1/supplier-contracts/{contract_id}/activate` | `procurement_manager` | Activate a draft contract |
| POST | `/api/v1/supplier-contracts/{contract_id}/renew` | `procurement_manager` | Renew a contract |
| GET | `/api/v1/supplier-contracts/{contract_id}/history` | Authenticated; scope applies | Retrieve contract history |

Supplier-facing contract access must enforce ownership where applicable. Contract lifecycle changes require the configured procurement permissions.

## 16.11 API Security Summary

The protected API security model combines:

```text
Authentication
      +
Role authorization
      +
Supplier data isolation
      +
Compliance access enforcement
      +
Business-state validation
```

Typical supplier access rules:

| Resource | Supplier access rule |
|---|---|
| Own Purchase Order | Allowed according to compliance state and operation |
| Another supplier's Purchase Order | `403 Forbidden` |
| Own invoice | Allowed according to compliance state and operation |
| Another supplier's invoice | `403 Forbidden` |
| Own document | Allowed according to compliance state and operation |
| Another supplier's document | `403 Forbidden` |
| Own statistics or scorecard | Allowed according to compliance state |
| Another supplier's statistics or scorecard | `403 Forbidden` |
| Own contract, where supplier access is supported | Subject to scope and compliance rules |
| Another supplier's contract | `403 Forbidden` |
| Supplier-scoped access with missing supplier identity | Rejected |

A successfully verified token alone is not sufficient to authorize access to supplier-scoped data.

---

# 17. HTTP Response Codes

The Supplier Portal uses explicit HTTP responses for authentication, authorization, request validation, business conflicts, resource lookup, and dependency failures.

| Status | Meaning |
|---:|---|
| `200 OK` | Request completed successfully |
| `201 Created` | Resource created successfully |
| `400 Bad Request` | Business-rule or input validation failure |
| `401 Unauthorized` | Authentication is missing or invalid |
| `403 Forbidden` | Role authorization, supplier scope, or compliance policy blocks the operation |
| `404 Not Found` | Requested resource or stored document does not exist |
| `409 Conflict` | Conflicting state, duplicate resource, or activation rejected by a `BLOCK`/`REVIEW` compliance decision |
| `422 Unprocessable Entity` | FastAPI request or schema validation failure |
| `502 Bad Gateway` | Downstream service returned an unusable or unsuccessful response |
| `503 Service Unavailable` | Required dependency is unavailable |

Examples:

```text
Missing or invalid token
    → 401 Unauthorized

Valid supplier token requesting another supplier's resource
    → 403 Forbidden

Suspended supplier requesting supplier-facing access
    → 403 Forbidden

NEEDS_REVIEW supplier attempting a protected write
    → 403 Forbidden

Unknown resource
    → 404 Not Found

Conflicting business state
    → 409 Conflict

Invalid request schema
    → 422 Unprocessable Entity

Platform authentication dependency unavailable
    → 503 Service Unavailable

Compliance Service unavailable during activation
    → 503 Service Unavailable

Compliance Service returns an unusable response
    → 502 Bad Gateway

Compliance decision BLOCK or REVIEW during activation
    → 409 Conflict
```

The precise response depends on the endpoint and the implemented error mapping. For example, some business validation failures may use `400`, while FastAPI schema validation normally uses `422`.

The synchronous Compliance integration is fail-closed. If the Compliance Service is unavailable or does not return a usable clearance, supplier activation is not permitted.

Round 14 compliance-status events are asynchronous Kafka messages and therefore use consumer, retry, offset, and dead-letter handling rather than HTTP response codes.

---

# 18. Configuration

The Supplier Portal uses environment-based configuration. Local settings should be provided through `.env`, while deployment environments should inject the appropriate values securely.

Create a local environment file from the example:

```powershell
Copy-Item .env.example .env
```

Use the configuration names actually supported by the project's settings class and `.env.example`. The examples below document the service integrations; verify that every variable is defined and consumed by the current implementation before relying on it.

## 18.1 Platform Authentication

Example:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The Supplier Portal delegates token verification to the Platform Service rather than independently decoding authentication tokens.

The configured verification endpoint is:

```http
POST /api/v1/auth/verify
```

The returned identity and role information is used for authorization and supplier scoping. Authentication dependency failures are handled centrally.

The Supplier Portal R14 implementation does not require changes to `services/platform`.

## 18.2 Compliance Service

Example:

```env
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

Supplier activation uses:

```http
POST /api/v1/compliance/internal-check
```

The request includes supplier identity information and identifies the caller with:

```http
X-Caller-Service: supplier-portal
```

The client uses a bounded timeout. The current documented timeout is five seconds, subject to the actual settings and client implementation.

Decision handling:

```text
CLEAR
    → Activation may proceed

BLOCK
    → Activation rejected

REVIEW
    → Activation rejected

Timeout / connection failure
    → Activation blocked

Unusable upstream response
    → Activation blocked
```

This synchronous integration handles initial activation. Ongoing compliance changes are processed through Kafka.

## 18.3 Kafka — Round 14

The Supplier Portal consumes asynchronous supplier compliance-status events from Apache Kafka.

Example configuration:

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONSUMER_GROUP=supplier-portal-service
KAFKA_STATUS_CHANGED_TOPIC=compliance.supplier.status_changed
KAFKA_DLQ_TOPIC=compliance.supplier.status_changed.dlq
KAFKA_AUTO_OFFSET_RESET=earliest
```

Use the exact variable names declared by the project's settings class and `.env.example`.

The documented consumer group and topics are:

```text
Consumer group:
supplier-portal-service

Main topic:
compliance.supplier.status_changed

Dead-letter topic:
compliance.supplier.status_changed.dlq
```

The consumer disables automatic offset commits and commits offsets explicitly after successful event processing or successful DLQ publication, according to the processing path.

### Event processing

```text
Kafka message
      ↓
Validate schema, event type, and version
      ↓
Check event idempotency
      ↓
Check occurred_at ordering
      ↓
Apply compliance access state
      ↓
Persist state and audit information
      ↓
Commit offset
```

Invalid events and unknown-supplier events are handled according to the consumer's DLQ policy. Unexpected processing failures must not be silently acknowledged.

The Round 14 compliance access state, processed-event/idempotency information, and compliance audit history are SQLite-backed in the current implementation. This persistence is distinct from the in-memory business stores used by other Supplier Portal features.

## 18.4 MinIO Document Storage

MinIO provides S3-compatible object storage for invoice PDFs and supplier onboarding documents.

The application retains object references and metadata; the document binaries are stored in MinIO.

Configure the endpoint, credentials, bucket, and presigned-URL expiry using the actual settings names in the project.

The document flow is:

```text
Validate upload
      ↓
Authorize the request
      ↓
Check supplier ownership
      ↓
Check compliance access
      ↓
Store or locate the MinIO object
      ↓
Generate a presigned URL when required
```

Downloads must authorize the caller before generating a URL. A cross-supplier request or suspended supplier must not receive a new presigned URL.

MinIO must be available for operations that require object storage. Do not silently replace the configured MinIO storage implementation with local filesystem storage.

## 18.5 Three-Way Match Tolerance

The price tolerance is centrally configured in:

```text
app/core/config.py
```

Current configured value:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

The intended tolerance is inclusive at the upper and lower limits.

For a PO unit price of `100`, prices from `95` through `105` are within the 5% tolerance. A price of `106` is outside the tolerance.

The tolerance belongs to the matching logic; it is not a blanket invoice-creation rejection rule.

## 18.6 Supplier Contract Configuration

The contract model supports terms such as:

```text
Contract number
Title
Description
Start date
End date
Payment terms
Delivery terms
Pricing terms
Minimum order value
Renewal notice days
Auto-renew setting
```

The lifecycle statuses include:

```text
draft
active
renewed
expired
```

The current contract implementation stores contract records and history in application memory. Consequently, this data is not durable across an application restart unless a persistent storage implementation is added.

The `auto_renew` field is configuration only. It does not by itself guarantee scheduled automatic renewal.

## 18.7 GraphQL Configuration

The GraphQL API is mounted at:

```text
/graphql
```

The implementation uses Strawberry GraphQL integrated with FastAPI. GraphQL requests reuse the Supplier Portal authentication mechanism and the authenticated user context.

The GraphQL authorization layer enforces applicable supplier scope and compliance access before protected resolver operations proceed.

## 18.8 Environment Template and Secrets

The project includes an environment template:

```text
.env.example
```

Use it as the source of truth for required variable names, including Platform, Compliance, Kafka, and MinIO settings.

Create a local `.env` with:

```powershell
Copy-Item .env.example .env
```

Do not commit `.env` files containing credentials, tokens, or environment-specific secrets. Use deployment secret management for production credentials.

---

# 19. Installation

The following steps describe a local Windows PowerShell setup.

## Step 1 — Open the Supplier Portal Directory

```powershell
cd C:\Users\Lenovo\Desktop\EAICSC\eaicsp-platform\services\supplier-portal
```

## Step 2 — Create a Virtual Environment

```powershell
python -m venv venv
```

## Step 3 — Activate the Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, follow your organization's approved PowerShell execution policy rather than changing system-wide settings unnecessarily.

## Step 4 — Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The exact dependency versions should be taken from the project's dependency files. Relevant dependencies include:

```text
FastAPI
Uvicorn
Pydantic
python-multipart
HTTPX
Pytest
Strawberry GraphQL
MinIO/S3-compatible storage client
confluent-kafka
```

`python-multipart` supports multipart form uploads. `confluent-kafka` supports the Round 14 Kafka consumer.

## Step 5 — Configure the Environment

```powershell
Copy-Item .env.example .env
```

Configure the required Platform, Compliance, MinIO, and Kafka settings using the variable names supported by the application.

## Step 6 — Start Required Dependencies

Before testing the features that depend on them, make sure the required services are running:

| Dependency | Purpose |
|---|---|
| Platform Service | Token verification and authenticated user identity |
| Compliance Service | Synchronous supplier activation clearance |
| MinIO | Document upload and download |
| Apache Kafka | Asynchronous Round 14 compliance-status events |

The Supplier Portal can start independently only if its startup configuration and dependency initialization allow it. Operations requiring an unavailable dependency may fail until that dependency is running.

---

# 20. Running the Services

The Supplier Portal integrates with the Platform Service, Compliance Service, MinIO, and Apache Kafka. Each dependency has a separate responsibility.

```text
Platform Service
    → Authentication

Compliance Service
    → Supplier activation clearance

MinIO
    → Document object storage

Apache Kafka
    → Ongoing compliance-status events
```

## 20.1 Start the Platform Service

The configured local Platform Service URL is:

```text
http://127.0.0.1:8005
```

From the Platform Service directory, use the startup command appropriate to that service. If it uses the same FastAPI/Uvicorn entry point, the local command may be:

```powershell
python -m uvicorn app.main:app --reload --port 8005
```

The Platform Service provides authentication operations such as:

```http
POST /api/v1/auth/login
POST /api/v1/auth/verify
GET /api/v1/users/me
```

The Supplier Portal delegates token verification to the Platform Service and uses the returned identity and role information for authorization and supplier scoping.

**The Supplier Portal Round 14 work does not require changes to `services/platform`.**

## 20.2 Start the Compliance Service

The configured local endpoint is:

```text
http://127.0.0.1:8003
```

The Supplier Portal uses:

```http
POST /api/v1/compliance/internal-check
```

during supplier activation.

The decision values are:

```text
CLEAR
BLOCK
REVIEW
```

Only a valid, successful `CLEAR` decision permits activation. `BLOCK` and `REVIEW` reject activation, while an unavailable or unusable Compliance response blocks activation with the appropriate dependency error.

The ongoing status-change event producer belongs to the Compliance Service. The Supplier Portal consumes the agreed event contract and must not infer `supplier_id` from supplier name, country, or other unrelated fields.

## 20.3 Start MinIO

MinIO runs separately from the Supplier Portal and provides S3-compatible storage.

```text
Supplier Portal
      │
      │ S3-compatible API
      ▼
MinIO
      │
      ▼
Stored document objects
```

Stored documents include invoice PDFs and supplier onboarding documents.

For downloads, the application authenticates the request, checks ownership and compliance access, locates the stored object, and then generates a short-lived presigned URL.

```text
Client
   ↓
Supplier Portal
   ↓
Authentication and authorization
   ↓
MinIO object lookup
   ↓
Presigned URL
   ↓
Client retrieves the document
```

If the object does not exist, the endpoint returns the implemented not-found response. If the storage dependency is unavailable, the endpoint returns the appropriate storage/dependency error.

Cross-supplier access and suspended supplier access must be rejected before a new presigned URL is generated.

## 20.4 Start Apache Kafka — Round 14

The configured local Kafka broker is:

```text
localhost:9092
```

The main and dead-letter topics are:

```text
compliance.supplier.status_changed
compliance.supplier.status_changed.dlq
```

The consumer group is:

```text
supplier-portal-service
```

### Docker Compose

From the directory containing the development Compose file, start the configured dependencies:

```powershell
docker compose -f docker-compose.dev.yml up -d
```

Confirm the actual Compose file and Kafka container/service name in the repository before running container-specific commands.

If the Kafka container is named `supplier-portal-kafka` and the image exposes the following Kafka scripts, the topics can be created with:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic compliance.supplier.status_changed --partitions 1 --replication-factor 1
```

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic compliance.supplier.status_changed.dlq --partitions 1 --replication-factor 1
```

List the available topics:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

List consumer groups:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list
```

After the consumer has started, inspect its group:

```powershell
docker exec supplier-portal-kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group supplier-portal-service
```

These commands depend on the configured container name, image paths, and broker listener. Adjust them to match the repository's actual Compose configuration.

### Kafka consumer lifecycle

The Supplier Portal's configured consumer runner integrates with application startup and shutdown.

```text
Supplier Portal starts
        ↓
Consumer runner starts
        ↓
Consumer joins supplier-portal-service
        ↓
Consumes compliance.supplier.status_changed
        ↓
Applies valid events or publishes failed messages to the DLQ
```

Offsets are managed explicitly. Unexpected processing failures must not be silently acknowledged.

## 20.5 Start the Supplier Portal

From the Supplier Portal directory:

```powershell
cd C:\Users\Lenovo\Desktop\EAICSC\eaicsp-platform\services\supplier-portal
```

Activate the virtual environment if it is not already active:

```powershell
.\venv\Scripts\Activate.ps1
```

Start the application:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The service runs at:

```text
http://127.0.0.1:8000
```

Check the root endpoint:

```http
GET /
```

The GraphQL endpoint is:

```http
POST /graphql
```

Protected REST and GraphQL operations require authentication. When the application is configured to start the Kafka consumer as a background worker, the consumer runner starts with the application and is stopped during application shutdown.

## 20.6 Service Architecture

```text
┌──────────────────────────────┐
│       Platform Service       │
│          Port 8005           │
│                              │
│    Authentication Provider   │
└──────────────┬───────────────┘
               │ Token verification
               ▼
┌──────────────────────────────────┐
│         Supplier Portal          │
│           Port 8000              │
│                                  │
│ REST API + GraphQL               │
│ Purchase Orders / Invoices       │
│ P2P / Three-Way Matching          │
│ Onboarding / Contracts            │
│ Statistics / Scorecard            │
│ Compliance authorization         │
│ Kafka consumer                   │
└───────┬───────────────┬──────────┘
        │               │
        │               │ S3-compatible API
        │               ▼
        │        ┌───────────────┐
        │        │    MinIO      │
        │        │ Document      │
        │        │ Object Store  │
        │        └───────────────┘
        │
        │ Synchronous activation check
        ▼
┌──────────────────────────────┐
│      Compliance Service      │
│          Port 8003            │
│                              │
│ Supplier compliance check    │
│ Status-change event producer│
└──────────────┬───────────────┘
               │
               │ Status-change event
               ▼
        ┌───────────────┐
        │ Apache Kafka  │
        │   Port 9092   │
        └───────┬───────┘
                │
                ▼
        Supplier Portal consumer
```

## 20.7 Authentication Flow

```text
Client
  │ Bearer token
  ▼
Supplier Portal
  │ POST /api/v1/auth/verify
  ▼
Platform Service
  │
  ▼
Authenticated user identity
  │
  ├── user_id
  ├── email
  ├── full_name
  ├── role
  ├── supplier_id, when applicable
  └── is_active
  │
  ▼
Supplier Portal authorization
  │
  ├── Role authorization
  ├── Supplier ownership
  ├── Compliance access
  └── Business validation
```

The authenticated identity is also supplied to the GraphQL context for protected resolver operations.

## 20.8 Supplier Activation Flow

```text
Supplier registration
        ↓
Document collection
        ↓
Verification and approval
        ↓
POST /api/v1/compliance/internal-check
        ↓
Compliance decision
        ├── CLEAR  → Activation may proceed
        ├── BLOCK  → Activation rejected
        └── REVIEW → Activation rejected
```

Dependency failures are fail-closed:

```text
Compliance unavailable / timeout
    → Activation blocked

Compliance response unusable
    → Activation blocked
```

## 20.9 Ongoing Compliance Status Flow — Round 14

The synchronous activation check does not replace asynchronous status-change processing.

```text
Compliance Service
        │
        │ compliance.supplier.status_changed
        ▼
Apache Kafka
        ▼
Supplier Portal consumer
        ▼
Event validation
        ▼
Idempotency and occurred_at checks
        ▼
Persist compliance access state and audit history
        ▼
REST / GraphQL authorization
```

Status mapping:

```text
CLEAR
    → CLEARED

REVIEW
    → NEEDS_REVIEW

BLOCK
    → SUSPENDED
```

The onboarding lifecycle and compliance access state are separate concepts:

```text
supplier.status
    ≠
supplier.compliance_access_status
```

For example, a supplier can remain historically onboarded as `active` while its current compliance access state is `SUSPENDED`. The separate compliance state controls supplier-facing access.

## 20.10 Compliance Audit History

Successfully applied compliance changes are recorded in compliance audit history. The available audit information includes fields such as:

```text
event_id
supplier_id
old_status
new_status
matched_list
reason
occurred_at
processed_at
```

The audit history retains prior status changes instead of erasing them when a later event changes the current state.

The Round 14 compliance state, processed-event/idempotency information, and audit history are SQLite-backed in the current implementation.

## 20.11 Document Storage Flow

```text
Upload
  ↓
Validate document
  ↓
Authorize supplier
  ↓
Check compliance access
  ↓
Store binary in MinIO
  ↓
Retain document reference/metadata
```

Download:

```text
Client
  ↓
Supplier Portal
  ↓
Authentication
  ↓
Supplier ownership
  ↓
Compliance access
  ↓
Object lookup
  ↓
Generate short-lived presigned URL
```

A suspended supplier or a supplier requesting another supplier's document must not receive a new presigned URL.

## 20.12 Business-Logic Integration Structure

The synchronous Compliance integration is isolated in:

```text
app/services/compliance_client.py
```

Its responsibilities include preparing the request, applying the configured timeout, calling the Compliance Service, validating the response, and mapping dependency failures.

The onboarding business logic uses the result to decide whether activation may proceed.

Round 14 asynchronous processing is organized around the following modules, subject to the current repository structure:

```text
app/schemas/events.py
app/services/supplier_compliance_service.py
app/services/kafka_consumer.py
app/services/kafka_consumer_runner.py
```

Responsibilities:

```text
events.py
    → Event schema and validation

supplier_compliance_service.py
    → Compliance state mapping
    → Idempotency and event ordering
    → Compliance audit history

kafka_consumer.py
    → Kafka subscription and message processing
    → Offset handling and DLQ publishing

kafka_consumer_runner.py
    → Background worker lifecycle
    → Application startup/shutdown integration
```

The consumer does not decode authentication tokens and does not modify the Platform Service.

## 20.13 GraphQL Implementation Structure

The GraphQL implementation is organized under:

```text
app/graphql/
```

Core modules may include:

```text
app/graphql/context.py
app/graphql/queries.py
app/graphql/schema.py
app/graphql/types.py
app/graphql/mutations.py
```

Their responsibilities are:

```text
context.py
    → Authenticated request context

queries.py
    → Purchase Order, invoice, and document queries
    → Supplier scoping and pagination

mutations.py
    → Purchase Order acknowledgement mutation

types.py
    → GraphQL types and enums

schema.py
    → Strawberry schema

main.py
    → GraphQL route mounting and application integration
```

Confirm filenames against the actual repository before documenting them as an exhaustive file list. The GraphQL layer should reuse existing Supplier Portal business services instead of duplicating their business logic.

## 20.14 Testing the Main Integrations

The regression suite should cover the applicable areas:

```text
REST authentication and authorization
Supplier ownership and data isolation
Compliance access enforcement
Purchase Orders
Invoices and invoice documents
MinIO storage and presigned URLs
Supplier onboarding and activation
Synchronous Compliance integration
Kafka event schema validation
Kafka idempotency and occurred_at ordering
Kafka offset handling and DLQ behavior
Compliance audit history
P2P lifecycle and Goods Receipt
Three-way matching and dispute resolution
Supplier statistics and scorecard
Supplier contract lifecycle
GraphQL queries and pagination
GraphQL Purchase Order acknowledgement
GraphQL resolver-level supplier scoping
GraphQL compliance access enforcement
```

Run focused tests from the Supplier Portal directory.

Kafka consumer tests:

```powershell
python -m pytest -q tests/test_kafka_consumer.py
```

GraphQL tests:

```powershell
python -m pytest -q tests/test_graphql.py
```

Document-storage unit tests:

```powershell
python -m pytest -q tests/test_document_storage_service.py
```

Supplier onboarding document-download tests:

```powershell
python -m pytest -q tests/test_supplier_document_download.py
```

MinIO integration tests:

```powershell
python -m pytest -q tests/integration/test_minio_document_storage.py
```

Run the complete regression suite before merging:

```powershell
python -m pytest -q
```

The MinIO integration tests require the configured storage environment. Kafka runtime integration requires a reachable broker, while isolated Kafka unit tests should use mocks or test fixtures where designed to do so.

A passing focused test suite does not replace the full regression suite. Record the actual command and result from the current run rather than copying a historical test count into the README.
# 21. Swagger and API Documentation

FastAPI automatically generates interactive documentation for the Supplier Portal REST APIs.

When the service is running locally on port `8000`, open:

**Swagger UI**
```text
http://127.0.0.1:8000/docs
```

**ReDoc**
```text
http://127.0.0.1:8000/redoc
```

**GraphQL endpoint**
```text
http://127.0.0.1:8000/graphql
```

Swagger documents REST endpoints. GraphQL operations are accessed through the GraphQL endpoint and are not listed as separate REST endpoints in Swagger.

## 21.1 REST API Coverage

Swagger can be used to inspect and test the REST operations implemented by the Supplier Portal, including:

- Purchase Orders, acknowledgement, transitions, events, and bulk sending
- Shipment processing and Goods Receipts
- Invoice creation, retrieval, transitions, disputes, and adjustments
- Invoice document upload and download URL generation
- Supplier registration, onboarding, and onboarding documents
- Supplier statistics, scorecards, and self-service analytics
- Supplier contracts, activation, renewal, expiry queries, and history
- Three-way matching and historical dispute-resolution suggestions
- Payment approval
- Supplier compliance access enforcement

The exact operations available depend on the routers registered in the running application.

## 21.2 Authentication in Swagger

Protected REST endpoints require a bearer token accepted by the configured Platform Service.

The Supplier Portal delegates token verification to the Platform Service; it does not independently replace the Platform Service's token-validation process.

Authentication and authorization flow:

```text
Swagger UI
    |
    | Bearer token
    v
Supplier Portal
    |
    | Token verification
    v
Platform Service
    |
    v
Authenticated identity
    |
    v
Role and supplier-scope validation
    |
    v
Compliance access validation
    |
    v
Endpoint business logic
```

In Swagger, select **Authorize** and provide a valid token in the format expected by the OpenAPI security configuration.

A valid token does not grant unrestricted access to every supplier's resources.

For example:

```text
SUP001 token
    |
    +--> Request SUP001 resource --> Allowed if other checks pass
    |
    +--> Request SUP002 resource --> 403 Forbidden
```

## 21.3 Compliance Access in Swagger

Supplier-facing operations are subject to the R14 compliance access policy.

| Compliance access state | Supplier read operations | Protected supplier writes |
|---|---|---|
| `CLEARED` | Allowed when authorized | Allowed when role and business rules permit |
| `NEEDS REVIEW` | Permitted reads remain available | Restricted |
| `SUSPENDED` | Rejected | Rejected |

Examples of protected writes include supplier PO acknowledgement and invoice submission.

Internal users continue to be governed by their existing role permissions. Supplier-specific compliance restrictions should not be treated as a replacement for role-based authorization.

## 21.4 Document Operations in Swagger

Invoice and supplier-onboarding documents are stored in MinIO.

The invoice document operations include:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

and:

```http
GET /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

The exact request schema and response format are defined by the registered endpoint.

The protected download flow is:

```text
Authenticated request
    |
    v
Supplier ownership validation
    |
    v
Compliance access validation
    |
    v
MinIO object lookup
    |
    v
Short-lived presigned URL
```

A suspended supplier must be rejected before a new presigned URL is generated. A supplier must not receive a URL for another supplier's document.

---

# 22. Automated Testing

The Supplier Portal uses **Pytest** for automated testing.

The test suite covers business logic, REST APIs, authentication, supplier authorization, external integrations, MinIO document storage, Kafka event processing, compliance enforcement, and GraphQL resolvers.

Run the full test suite from the Supplier Portal service directory:

```powershell
python -m pytest -v
```

For a concise result:

```powershell
python -m pytest -q
```

Run commands from the active project environment with the service dependencies installed. The current dependency configuration is the source of truth for Python and package versions.

## 22.1 Test Coverage Areas

Major coverage areas include:

- Purchase Order lifecycle and supplier scoping
- P2P state transitions, shipments, and Goods Receipts
- Partial Goods Receipts and receipt-date handling
- Invoice lifecycle, disputes, adjustments, and document validation
- Three-way matching and discrepancy handling
- Supplier onboarding and Compliance Service integration
- Supplier statistics, scorecards, and self-service analytics
- Supplier contracts, renewal, expiry, and audit history
- Historical dispute-resolution suggestions
- Platform Service authentication and role authorization
- Supplier ownership and collection filtering
- MinIO object storage and presigned URL authorization
- GraphQL queries, mutation authorization, and cursor pagination
- Kafka compliance status events, idempotency, ordering, and DLQ handling
- R5 supplier-scoping requirements
- R12 MinIO requirements
- R13 GraphQL requirements
- R14 event-driven compliance access requirements

The presence of a feature in this list describes its intended test coverage; the current test run determines whether the tests pass.

## 22.2 Purchase Order Tests

Run the Purchase Order test module used by the repository. For example, if the project contains `tests/test_purchase_orders.py`:

```powershell
python -m pytest tests/test_purchase_orders.py -v
```

Purchase Order coverage includes:

- Creation, retrieval, listing, update, and deletion
- Duplicate PO handling
- Acknowledgement and legal state transitions
- Cancellation and terminal-state behavior
- Transition history and event retrieval
- Actor and timestamp tracking
- Bulk PO sending
- Active-supplier validation
- Actual delivery date derived from Goods Receipt data
- Multiple Goods Receipt handling

Authorization tests validate that supplier users can access and modify only their own permitted POs. Procurement-manager-only actions, including protected PO transitions and bulk sending, must reject unauthorized roles.

### R5 Supplier-Scoping Tests

The supplier-scoping tests verify that:

```text
Supplier accesses its own PO
    -> Allowed when authorized

Supplier accesses another supplier's PO
    -> 403 Forbidden

Supplier without supplier_id accesses a supplier-scoped resource
    -> 403 Forbidden
```

The same ownership principle applies to supported PO listing, acknowledgement, events, updates, and deletion operations.

### R14 PO Compliance Tests

The tests should verify that:

- `CLEARED` suppliers can perform otherwise permitted operations.
- `NEEDS REVIEW` suppliers can perform permitted reads but cannot perform protected supplier writes.
- `SUSPENDED` suppliers are blocked from supplier-facing PO operations.
- Internal procurement roles retain their existing role-based permissions.

## 22.3 Invoice Tests

Run:

```powershell
python -m pytest tests/test_invoices.py -v
```

The module covers the invoice functionality implemented by the project, including:

- Invoice creation, retrieval, and listing
- Duplicate invoice protection
- Supplier and PO validation
- PO status and supplier-matching rules
- Invoice item, quantity, unit-price, and amount validation
- Partial invoicing
- Invoice transitions, disputes, and adjustments
- PDF document validation and size limits
- Supplier scoping and role authorization

Invoice creation and three-way matching are separate stages. The configured `5%` price tolerance is used by the matching process; invoice creation does not automatically reject an invoice solely because its price differs from the PO price.

### Invoice Authorization and Compliance Tests

Tests should verify that:

- Suppliers cannot access or modify another supplier's invoice.
- Supplier identity is checked against the requested `supplier_id`.
- Compliance-only invoice adjustments reject unauthorized roles.
- `NEEDS REVIEW` blocks protected supplier invoice writes while allowing permitted reads.
- `SUSPENDED` blocks supplier-facing invoice access, including protected document operations.

Expected compliance error messages should match the actual response definitions in the application.

## 22.4 Document Storage Tests

Round 12 introduced MinIO-backed storage for invoice and supplier-onboarding documents.

The storage-service tests cover object upload, object existence, retrieval, missing-object behavior, presigned URL generation, and storage dependency errors.

Run the document-storage service tests:

```powershell
python -m pytest -q tests/test_document_storage_service.py
```

Run invoice document-download tests if the named module exists in the repository:

```powershell
python -m pytest -q tests/test_invoice_document_download.py
```

Run supplier onboarding document-download tests:

```powershell
python -m pytest -q tests/test_supplier_document_download.py
```

These tests should verify:

- Document ownership and supplier scoping
- MinIO-backed document references
- Presigned URL generation
- Missing-object responses
- Storage dependency failure handling
- Authorization before URL generation
- Rejection of cross-supplier access
- Rejection of suspended supplier downloads before MinIO URL generation

A missing object and an unavailable storage service are different conditions:

```text
Object does not exist
    -> Not found

Storage dependency is unavailable
    -> Service dependency error
```

The HTTP status should match the application's implemented exception mapping.

### MinIO Integration Tests

The integration test module uses a real MinIO instance rather than only a mocked client.

If Docker and the integration environment are configured, run:

```powershell
python -m pytest -q tests/integration/test_minio_document_storage.py
```

The integration test validates the actual application-to-MinIO storage and retrieval path. It should not be described as a successful test unless it has been executed against the configured environment.

## 22.5 P2P Workflow Tests

The P2P tests validate the controlled progression:

```text
acknowledged
    |
    v
shipped
    |
    v
received
    |
    v
invoiced
    |
    v
matched / discrepancy
    |
    v
payment_approved
```

Coverage includes:

- Valid and invalid state transitions
- Shipment progression
- Goods Receipt creation and validation
- Partial Goods Receipt support
- PO and supplier validation
- Item and receipt-quantity validation
- Duplicate and extra receipt-item rejection
- Invoice submission only after the required receipt state
- Invalid or duplicate invoice operations not advancing the workflow
- Quantity and price discrepancy detection
- Human review for discrepancies
- Prevention of automatic payment approval for unresolved discrepancies

A discrepancy must be resolved through the authorized business process before the transaction can progress to payment approval.

## 22.6 Supplier Onboarding and Compliance Integration Tests

Onboarding tests cover registration, document collection, verification, approval, and activation.

The Compliance Service integration is tested for:

- `CLEAR`, `BLOCK`, and `REVIEW` decisions
- Connection failures and timeouts
- Invalid or unusable responses
- Fail-closed activation behavior
- Supplier ownership and role authorization
- Active-supplier enforcement where required

The activation check uses:

```http
POST /api/v1/compliance/internal-check
```

with the required supplier information and the caller identification header:

```http
X-Caller-Service: supplier-portal
```

Only a valid `CLEAR` decision with the required positive clearance field allows activation. A `BLOCK` or `REVIEW` decision, or a technical failure, must not activate the supplier.

## 22.7 Kafka Compliance Event Tests — R14

Run the consumer tests:

```powershell
python -m pytest tests/test_kafka_consumer.py -v
```

Run the enforcement tests:

```powershell
python -m pytest tests/test_r14_enforcement.py -v
```

The R14 tests cover:

- Event schema and version validation
- Event type validation
- Supplier ID validation
- `CLEAR`, `REVIEW`, and `BLOCK` mapping
- Duplicate `event_id` handling
- Out-of-order `occurred_at` protection
- Unknown supplier handling
- Invalid event and DLQ handling
- Manual offset commits
- Processing-failure behavior
- REST and GraphQL compliance enforcement
- Document access protection for suspended suppliers

Kafka configuration:

```text
Consumer group:
supplier-portal-service

Status topic:
compliance.supplier.status_changed

Dead-letter topic:
compliance.supplier.status_changed.dlq
```

The consumer uses manual offset management:

```text
enable.auto.commit = false
```

The intended processing behavior is:

```text
Valid event successfully applied
    -> Commit original offset

Invalid event successfully published to DLQ
    -> Commit original offset

Unexpected processing failure
    -> Do not commit original offset
```

This prevents an event from being acknowledged before it has been successfully applied or safely routed to the dead-letter topic.

## 22.8 Three-Way Match Tests

Three-way matching compares:

```text
Purchase Order
    +
Goods Receipt
    +
Invoice
```

Tests cover quantity discrepancies, price discrepancies, successful matches, and the requirement for human review when a discrepancy is detected.

The configured tolerance is:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

For a PO unit price of `100`, a price within the inclusive tolerance is considered within the configured price range:

```text
95  -> Within tolerance
100 -> Within tolerance
105 -> Within tolerance
106 -> Outside tolerance
```

This example illustrates the configured price tolerance; actual match outcomes also depend on the implemented quantity, receipt, and invoice validations.

## 22.9 Historical Dispute-Resolution Suggestion Tests

The historical suggestion tests validate that:

- Historical resolved cases can provide evidence for suggestions.
- Unresolved cases are not treated as resolved historical evidence.
- Cases without sufficient evidence do not produce an unsupported suggestion.
- Supplier scoping and compliance-officer authorization are enforced.
- Suggestions are read-only and do not modify invoice or match state.

Endpoint:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

The feature is advisory:

```text
Historical evidence
    -> Pattern analysis
    -> Suggested action
    -> Human decision
```

It must not automatically resolve a dispute or approve payment.

## 22.10 Supplier Statistics and Scorecard Tests

Run:

```powershell
python -m pytest tests/test_supplier_stats.py -v
```

Coverage includes:

- Supplier statistics and missing suppliers
- PO counts and delivery performance
- Past-due and future-due unfulfilled POs
- Goods Receipt-based delivery dates
- Invoice cycle-time calculations
- Invoice accuracy and dispute rate
- Overall score and percentage boundaries
- Monthly trends
- Supplier ownership and self-service access
- Compliance access enforcement

For fulfilled POs, actual delivery is based on the applicable/latest Goods Receipt `receipt_date`, as implemented by the scorecard service.

The on-time comparison is:

```text
actual_delivery_date <= expected_delivery
```

Tests should also verify that cancelled POs, future-due unfulfilled POs, and records without a usable expected-delivery date are treated according to the scorecard's eligibility rules.

## 22.11 Supplier Contract Tests

Contract tests cover:

- Contract creation, retrieval, and listing
- Duplicate contract-number protection
- Active-supplier validation
- Contract date validation
- Draft-to-active transitions
- Contract updates and expiry queries
- Renewal and renewal history
- State-transition and term-change history
- Actor and reason recording
- No-op updates without unnecessary history entries
- Supplier scoping and procurement-manager authorization

The current implementation supports contract lifecycle and renewal tracking. An `auto_renew` field should not be documented as an automatically executing renewal scheduler unless such a scheduler has actually been implemented.

## 22.12 GraphQL Tests — R13

Run:

```powershell
python -m pytest -q tests/test_graphql.py
```

The GraphQL tests cover the Strawberry schema and implemented operations, including:

- Purchase Order queries and collections
- Invoice queries and collections
- Supplier document queries
- Cursor-based pagination
- Purchase Order acknowledgement mutation
- Authenticated GraphQL context
- Resolver-level supplier authorization
- Cross-supplier access protection
- Compliance access enforcement

GraphQL uses the existing authentication and authorization mechanisms rather than introducing an independent authentication system.

Collection queries must apply supplier filtering before pagination:

```text
Source records
    |
    v
Supplier authorization and filtering
    |
    v
Compliance access validation
    |
    v
Cursor pagination
    |
    v
GraphQL response
```

The actual error or `null` behavior for an unauthorized single-resource query must match the resolver's implemented response contract.

## 22.13 Authentication and Authorization Tests

Authentication tests cover:

- Missing, invalid, and expired tokens
- Platform Service validation failures
- Timeouts and dependency errors
- Invalid authentication responses
- Missing user identity or role
- Supplier identity propagation
- Request ID generation and forwarding
- Role-based authorization
- Procurement-manager and compliance-officer restrictions
- Supplier ownership enforcement

Expected unauthenticated responses are determined by the configured authentication dependency. Protected requests should not be documented as returning a fixed status unless that behavior has been verified.

## 22.14 Full Regression Testing

After changes to authentication, supplier scoping, compliance enforcement, document storage, GraphQL, or Kafka processing, run:

```powershell
python -m pytest -q
```

For a verbose regression run:

```powershell
python -m pytest -v
```

Record the actual result from the latest execution rather than copying an old pass count into the README.

---

# 23. Business Rules

## 23.1 Purchase Order Rules

A newly created PO starts in:

```text
draft
```

The primary lifecycle is:

```text
draft -> sent -> acknowledged -> fulfilled
```

Cancellation is permitted only from the states allowed by the PO transition implementation. Invalid transitions are rejected.

PO creation requires an authorized procurement role and a supplier that satisfies the application's registration and activation requirements.

Supplier-facing operations also enforce supplier ownership and R14 compliance access.

## 23.2 Invoice Rules

Invoices require an existing, eligible PO.

The legacy invoice service accepts only the PO states allowed by its implemented validation. In the P2P workflow, invoice submission additionally requires the P2P state to be `received`.

The invoice supplier must match the PO supplier.

Duplicate invoices are prevented using the supplier and invoice identifiers:

```text
supplier_id + invoice_number
```

Rejected or invalid invoice submissions must not advance the P2P state.

Invoice lifecycle state and supplier compliance access are separate concepts:

```text
Invoice lifecycle
    !=
Supplier compliance access state
```

A supplier under review may read permitted invoice information but cannot perform protected supplier invoice writes. A suspended supplier cannot perform supplier-facing invoice operations.

## 23.3 Invoice Document Rules

Invoice documents must satisfy the application's PDF validation requirements, including:

- PDF content type
- Valid PDF signature
- Maximum file size of 10 MB
- Authentication and supplier ownership checks
- Compliance access checks for protected supplier-facing operations

The binary document is stored in MinIO. The application maintains the object reference and any required document metadata.

The download sequence is:

```text
Authenticate
    |
    v
Validate resource ownership
    |
    v
Validate compliance access
    |
    v
Locate the MinIO object
    |
    v
Generate a short-lived presigned URL
```

A missing object and a storage dependency failure must be handled separately according to the application's exception mapping.

## 23.4 Supplier Onboarding Document Rules

Supported onboarding document types are configured by the onboarding implementation. The currently documented formats are:

```text
PDF
JPG / JPEG
PNG
DOC / DOCX
```

The maximum file size is 10 MB.

Upload validation includes the implemented checks for file size, file extension, content type, empty files, authentication, supplier ownership, and protected supplier access.

Onboarding documents are stored in MinIO.

## 23.5 Procure-to-Pay Rules

The P2P workflow uses controlled transitions:

```text
acknowledged
    -> shipped
    -> received
    -> invoiced
    -> matched / discrepancy
    -> payment_approved
```

### Shipment

Shipment processing requires the PO/P2P state to permit shipment. Invalid transitions are rejected.

### Goods Receipt

Goods Receipt processing follows shipment and supports partial delivery.

Validation includes:

- PO existence
- Supplier ownership
- Valid item codes
- Positive receipt quantities
- Receipt quantities within the corresponding PO quantities
- Rejection of duplicate receipt items
- Rejection of extra item codes not present on the PO

Missing PO items can be valid for a partial receipt.

### Invoice Submission

P2P invoice submission requires:

```text
P2P state = received
```

A valid submission advances the workflow to `invoiced`. Invalid or duplicate submissions must not advance it.

### Three-Way Matching and Payment Approval

Matching compares PO, Goods Receipt, and invoice information. The configured price tolerance is `5%`.

A quantity or price discrepancy requires human review. It must not be automatically approved for payment.

Only a transaction that satisfies the implemented matching and review rules can progress to payment approval.

Compliance access is independent of the P2P state machine. A compliance status change restricts access; it does not itself change the P2P business state.

## 23.6 Supplier Onboarding and Activation Rules

The onboarding lifecycle is:

```text
registration
    -> documents
    -> verification
    -> approval
    -> compliance check
    -> active
```

The workflow validates the current state before advancing. Required stages cannot be skipped.

Before activation, the Supplier Portal calls:

```http
POST /api/v1/compliance/internal-check
```

The request includes the required supplier information and:

```http
X-Caller-Service: supplier-portal
```

Only a valid `CLEAR` decision with the required positive clearance field permits activation.

`BLOCK`, `REVIEW`, timeout, connection failure, or an unusable Compliance response must not activate the supplier. This is a fail-closed integration.

### Ongoing Compliance Changes — R14

The synchronous onboarding check and the Kafka event consumer serve different purposes.

Initial activation:

```text
Supplier approved
    -> Compliance internal check
    -> CLEAR
    -> Activation allowed
```

Ongoing status changes:

```text
Compliance status event
    -> Kafka
    -> Supplier Portal consumer
    -> Separate compliance access state
    -> REST / GraphQL / document enforcement
```

The event status mapping is:

```text
CLEAR  -> cleared
REVIEW -> needs_review
BLOCK  -> suspended
```

The compliance access state is separate from the onboarding lifecycle status. A later `BLOCK` event should suspend supplier-facing access without falsely rewriting the onboarding lifecycle state.

## 23.7 Supplier Contract Rules

The contract lifecycle supports:

```text
draft
active
renewed
expired
```

The implemented lifecycle includes activation, renewal, and expiry handling. Contract creation requires an eligible supplier and a unique contract number. The end date must be later than the start date.

Renewal validates the new dates and records the renewal information. The current implementation reuses the contract record for renewal rather than automatically creating a separate contract for every renewal period.

An `auto_renew` field is configuration unless a separate automated renewal process is implemented.

## 23.8 Contract Audit Rules

Meaningful contract term changes create history records.

Audited fields can include:

- Title and description
- End date
- Payment and delivery terms
- Pricing terms
- Minimum order value
- Renewal notice period
- Auto-renew configuration

History records can include the contract and supplier identifiers, previous and new states, actor details, reason, and timestamp, according to the implemented schema.

A no-op update should not create an unnecessary term-change history record.

## 23.9 Contract Expiry Rules

The service provides contract expiry information and expiring-contract queries based on the configured dates and renewal-notice period.

Expiry and `days_until_expiry` calculations should use consistent date handling. Expiring-contract queries identify contracts approaching the configured renewal or expiry window.

## 23.10 Historical Dispute-Resolution Suggestions

Historical dispute suggestions are advisory.

The service analyzes suitable historical match-resolution evidence and may suggest actions such as:

```text
Price mismatch
    -> correct_invoice

Quantity mismatch
    -> credit_note
```

These are example mappings; the suggestion must depend on the evidence and rules actually implemented.

The feature must not automatically modify invoices, resolve disputes, change match status, or approve payment.

## 23.11 Supplier Self-Service Analytics

Suppliers can retrieve their own scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The authenticated supplier identity must match the requested supplier ID.

The scorecard exposes the metrics implemented by the service, such as on-time delivery, invoice accuracy, dispute performance, overall score, and trends.

The endpoint remains subject to supplier scoping and compliance access:

```text
CLEARED
    -> Permitted scorecard reads

NEEDS REVIEW
    -> Permitted scorecard reads

SUSPENDED
    -> Supplier-facing access rejected
```

## 23.12 Scorecard Calculation Rules

The current scorecard configuration uses these weights:

```text
40% -> On-time delivery
40% -> Invoice accuracy
20% -> Dispute performance
```

Dispute performance is calculated as:

```text
dispute performance = 100 - dispute rate
```

The overall score is:

```text
overall score =
    (on-time delivery percentage * 0.40)
  + (invoice accuracy percentage * 0.40)
  + (dispute performance percentage * 0.20)
```

Example:

```text
On-time delivery = 75
Invoice accuracy = 80
Dispute performance = 90

Overall score =
    (75 * 0.40)
  + (80 * 0.40)
  + (90 * 0.20)

Overall score = 80
```

The scorecard's implemented treatment of invoices without a recorded dispute should be kept consistent with its tests and service logic.

### On-Time Delivery Eligibility

The scorecard eligibility rules distinguish:

- Fulfilled POs, which use their actual delivery date
- Past-due unfulfilled POs, which count as misses
- Future-due unfulfilled POs, which are excluded
- Cancelled POs, which are excluded
- POs without a usable expected-delivery date, which are excluded

For fulfilled POs, the actual delivery date is derived from the applicable/latest Goods Receipt `receipt_date`.

An on-time delivery satisfies:

```text
actual_delivery_date <= expected_delivery
```

The percentage is:

```text
On-time eligible POs
--------------------- * 100
Eligible delivery POs
```

### Invoice Dispute Rate

```text
Disputed invoices
------------------ * 100
Total invoices
```

### Invoice Accuracy

The implemented accuracy calculation uses the service's dispute-recording rules to classify invoices as accurate or inaccurate. Keep the README definition aligned with the actual scorecard implementation.

### Invoice Cycle Time and Trends

Cycle-time calculations use the invoice and PO date information available in the implementation. Where the PO reference is stored at invoice-line level, the service uses the relevant `invoice.items[].po_number` relationship.

Date normalization and invalid or negative cycle-time values should follow the service's implemented validation rules.

## 23.13 GraphQL Business Rules

The GraphQL API exposes implemented Supplier Portal operations through Strawberry. It must preserve the existing authentication, supplier-scoping, compliance, and business rules.

### Purchase Orders

Supplier users can query only POs belonging to their authenticated supplier identity.

### Invoices

Supplier invoice queries must enforce supplier ownership. A supplier cannot use GraphQL to retrieve another supplier's invoice.

### Documents

Document queries must enforce supplier ownership and applicable compliance access. A GraphQL resolver must not expose another supplier's protected document reference.

### PO Acknowledgement Mutation

Before acknowledging a PO, the mutation must validate ownership and the applicable compliance write permission, then call the existing acknowledgement logic.

### Cursor Pagination

Collection queries use the cursor-based pagination implemented by the service. Supplier filtering must occur before records are returned to the client.

```text
Source records
    -> Authorization and supplier filtering
    -> Compliance access validation
    -> Cursor pagination
    -> GraphQL response
```

Cursor behavior and invalid-cursor handling should follow the actual schema and resolver implementation.

---

# 24. Security Controls

The Supplier Portal applies several layers of security. Authentication alone does not authorize access to every resource.

## 24.1 Authentication

The service uses:

- Bearer-token authentication
- Central token validation through the Platform Service
- Authentication dependency timeout and failure handling
- Authentication response validation
- Authenticated user and role extraction
- Supplier identity validation
- Request ID generation and propagation

The Supplier Portal delegates token verification to the Platform Service. The Platform Service implementation is outside the scope of the Supplier Portal changes.

## 24.2 Role-Based Authorization

Role-based controls protect operations such as:

- PO creation and restricted PO transitions
- Bulk PO sending
- Invoice adjustment
- Historical dispute-resolution suggestions
- Contract management and renewal

Procurement-manager-only and compliance-officer-only operations must reject unauthorized roles.

Role authorization does not replace supplier ownership checks.

## 24.3 Supplier Data Isolation — R5

Supplier users can access only the supplier-scoped resources they own.

The rule is:

```text
Authenticated supplier_id
    ==
Resource supplier_id
```

Cross-supplier requests are rejected with `403 Forbidden` when the caller is authenticated but lacks access.

A supplier without the required `supplier_id` must not gain supplier-scoped access.

This rule applies to supported supplier-facing resources, including:

- Purchase Orders and PO events
- Invoices and invoice documents
- Shipment and Goods Receipt resources
- Supplier statistics and scorecards
- Onboarding resources
- Three-way matches
- Supplier contracts and contract history
- GraphQL Purchase Order, invoice, and document operations

Collection endpoints must filter results to the authenticated supplier before returning data.

## 24.4 Supplier Compliance Access — R14

R14 introduces event-driven compliance access enforcement.

Supported internal access states are:

```text
cleared
needs_review
suspended
```

Mapping:

```text
Compliance CLEAR  -> cleared
Compliance REVIEW -> needs_review
Compliance BLOCK  -> suspended
```

The enforcement policy is:

```text
CLEARED
    -> Normal supplier access, subject to role and business rules

NEEDS REVIEW
    -> Permitted reads remain available
    -> Protected supplier writes are restricted

SUSPENDED
    -> Supplier-facing REST and GraphQL access is rejected
    -> Protected document downloads are rejected
```

The compliance access state is maintained separately from the onboarding lifecycle status.

For internal authorized roles, existing role permissions continue to apply. The supplier-specific compliance guard must not be mistaken for a universal replacement for authorization.

## 24.5 Compliance Activation Security

The synchronous Compliance Service integration protects supplier activation.

Activation is allowed only after a valid clearance decision. A `BLOCK`, `REVIEW`, timeout, connection failure, or invalid response must not be interpreted as successful clearance.

This is a fail-closed rule:

```text
Valid CLEAR
    -> Activation may proceed

BLOCK / REVIEW
    -> Activation rejected

Compliance unavailable or response invalid
    -> Activation rejected
```

## 24.6 Kafka Consumer Reliability — R14

The consumer processes:

```text
compliance.supplier.status_changed
```

and publishes invalid messages to:

```text
compliance.supplier.status_changed.dlq
```

The consumer group is:

```text
supplier-portal-service
```

Manual offset handling is enabled. The consumer must not commit the original offset before the event has been successfully applied or safely routed to the DLQ.

The consumer validates the event structure, type, version, ID, timestamp, supplier ID, and compliance status.

It also protects against duplicate events and older events overwriting newer compliance state.

An event must include its supplier ID. The consumer must not infer the supplier identity from a company name or country.

## 24.7 Compliance Audit History

The current compliance access state and compliance audit history serve different purposes.

The current state determines whether a supplier-facing request is permitted. The audit history preserves evidence of processed status changes.

Where the implementation persists compliance state, processed-event/idempotency information, and audit history in SQLite, these records can survive a service restart. This does not imply that all Supplier Portal business entities use durable database storage.

Audit records should preserve the event and supplier identifiers, old and new status, relevant match information, reason, and event/processing timestamps according to the implemented schema.

## 24.8 Input Validation

The service validates inputs according to each endpoint's schema and business rules, including:

- Supplier, PO, and invoice identifiers
- Positive quantities and unit prices
- Invoice amounts and percentage boundaries
- Receipt quantities and item codes
- Onboarding document type, size, and content
- Contract number uniqueness and contract dates
- Renewal dates and contract update fields
- GraphQL pagination limits and cursors
- Kafka event structure, type, version, supplier ID, and status

Where the application uses the following identifier pattern, document it as:

```regex
^[A-Za-z0-9_-]+$
```

Do not assume this pattern applies to every identifier unless the corresponding schemas enforce it.

## 24.9 Document Storage Security — R12

Invoice and onboarding document binaries are stored in MinIO using S3-compatible object storage. The application keeps the object references and any required metadata.

Protected download operations must validate authorization before generating a presigned URL:

```text
Authenticate
    -> Identify requested resource
    -> Validate supplier ownership
    -> Validate compliance access
    -> Locate MinIO object
    -> Generate short-lived presigned URL
```

The key security requirements are:

- No cross-supplier document access
- No presigned URL before authorization
- No new supplier-facing presigned URL for suspended suppliers
- Missing objects handled separately from storage dependency failures
- MinIO failures must not be treated as successful uploads or downloads

A document ID, invoice number, or object key alone is not proof of authorization.

## 24.10 GraphQL Security — R13

GraphQL uses the existing Supplier Portal authentication mechanism and authenticated request context.

Each supplier-scoped resolver must enforce the relevant ownership and compliance rules. Collection resolvers must apply supplier filtering before pagination.

Protected GraphQL operations include the implemented Purchase Order, invoice, document, and acknowledgement operations.

GraphQL must not become a path around REST-equivalent authorization or business validation.

## 24.11 Contract Audit Security

Contract retrieval and history access are protected by role authorization and supplier scoping.

Meaningful contract changes should record the actor, reason, timestamp, and relevant lifecycle or term-change information supported by the implementation.

A supplier must not be able to retrieve another supplier's contract or contract history by changing a contract identifier.

## 24.12 Security Summary

The Supplier Portal security model combines:

```text
Authentication
    +
Role authorization
    +
Supplier ownership
    +
Compliance access
    +
Input validation
    +
Protected document storage
    +
Auditable event processing
```

These controls apply across the supported REST endpoints, GraphQL resolvers, document-download operations, and compliance event-processing workflow. Each layer complements the others; none should be treated as a substitute for the remaining checks.
# 25. Storage Architecture

The Supplier Portal currently uses different storage mechanisms for business workflow data, uploaded documents, and Round 14 compliance processing.

```text
Supplier Portal
      |
      +-----------------------------+
      |                             |
      v                             v
Business / Workflow Data       Uploaded Documents
      |                             |
      v                             v
In-Memory Stores               MinIO Object Storage

      R14 Compliance State and Audit Data
                       |
                       v
                 SQLite Storage
```

## Business and Workflow Storage

The following business data is currently maintained using Python in-memory data structures:

```python
purchase_orders = {}
invoices = {}
po_events = {}
supplier_contracts = {}
supplier_contract_history = {}
```

Related workflow data, such as shipment, goods receipt, onboarding, and other business records, also uses the application's current in-memory storage implementation where applicable.

This approach supports local development and functional testing but does not provide durable persistence for these records across application restarts.

**Restart behavior:** business records held only in memory are lost when the process restarts.

## Document Object Storage

Round 12 migrated active document storage from local filesystem storage to MinIO.

The application stores the binary content of:

- Invoice PDF documents
- Supplier onboarding documents

in MinIO object storage.

The architecture is:

```text
Windows Development Environment
              |
              v
        Docker Desktop
              |
              v
        MinIO Container
              |
              v
   S3-Compatible Object Storage
              |
              v
    Invoice and Onboarding Files
```

The application maintains the document metadata and object references needed to locate stored files.

The active document-storage implementation does not depend on the local `uploads/` directory for storing document binaries.

MinIO objects are stored independently of the Supplier Portal's in-memory business stores. Restarting the Supplier Portal process does not, by itself, delete objects already stored in MinIO.

## Presigned Document Download URLs

Documents are made available through short-lived presigned URLs.

The application performs the applicable authentication, supplier ownership, and compliance checks before generating a URL for a supplier-facing request.

```text
Document Download Request
             |
             v
       Authentication
             |
             v
   Resource / Ownership Check
             |
             v
   Compliance Access Check
             |
             v
       Object Lookup
             |
             v
  Generate Presigned Download URL
             |
             v
       Client Downloads File
```

For a suspended supplier, the expected enforcement behavior is:

```text
SUSPENDED
    |
    v
Compliance Authorization Denied
    |
    v
403 Forbidden
    |
    v
No New Presigned URL
```

Authorization must occur before generating a presigned URL. A previously generated URL may remain usable until it expires, depending on the storage configuration and URL validation behavior. Therefore, short expiry times are important, and the application should not describe previously issued URLs as instantly revoked unless that capability is implemented.

## MinIO Failure Behavior

The application must not report a document operation as successful when the required storage operation fails.

```text
Document Request
       |
       v
  MinIO Request
       |
       +----------------------+
       |                      |
       v                      v
Storage Available       Storage Unavailable
       |                      |
       v                      v
Object Lookup           Storage Error
       |                      |
       v                      v
Object Result        Appropriate Service Error
```

The expected response behavior is:

| Condition | Expected behavior |
|---|---|
| Request is not authorized | Reject the request before issuing a download URL |
| Supplier attempts to access another supplier's document | `403 Forbidden` |
| Supplier is suspended | `403 Forbidden` |
| Requested document or object does not exist | `404 Not Found`, where mapped by the endpoint |
| MinIO dependency is unavailable | Appropriate storage/service error; use `503 Service Unavailable` where implemented |
| Presigned URL generation fails | Return an error instead of a successful download response |

These response codes should be verified against the actual endpoint exception handling before being treated as guaranteed for every storage operation.

## R14 Compliance State and Audit Storage

Round 14 uses SQLite-backed persistence for compliance access state and event-processing records.

The persisted information includes:

```text
Processed Event IDs
Latest Event Timestamps
Current Supplier Compliance Access State
Compliance Audit History
```

This supports:

- Event idempotency across process restarts
- Protection against stale or out-of-order events
- Persistence of the current compliance access state
- Compliance audit history beyond the lifetime of a single process

The exact durability guarantees depend on the SQLite configuration, transaction handling, and deployment storage. In particular, the SQLite database file must be retained and protected in the deployment environment.

```text
Kafka Compliance Event
          |
          v
   Supplier Portal Consumer
          |
          v
      SQLite Store
          |
          +--------------------+
          |                    |
          v                    v
 Current Access State    Event / Audit Records
```

## Application Restart Behavior

Storage behavior differs by data category:

| Data category | Storage | Expected restart behavior |
|---|---|---|
| Purchase orders | In-memory | Lost on process restart |
| Invoices | In-memory | Lost on process restart |
| P2P workflow data | In-memory | Lost on process restart |
| Supplier onboarding business metadata | In-memory, where currently implemented | Lost on process restart |
| Supplier contracts and contract history | In-memory | Lost on process restart |
| MinIO document binaries | MinIO object storage | Remain stored unless deleted or otherwise affected by storage operations |
| R14 compliance access state | SQLite | Persists if the database file is retained and readable |
| R14 processed-event records | SQLite | Persist if the database file is retained and readable |
| R14 compliance audit history | SQLite | Persists if the database file is retained and readable |

Production deployment should provide durable database persistence for business metadata and appropriate backup, retention, and recovery controls for both SQLite data and MinIO objects.

## Contract Storage

Supplier contracts and contract history currently use in-memory application stores.

The current implementation supports the defined contract lifecycle operations, including:

```text
Contract Lifecycle Tracking
Contract Expiry Calculation
Explicit Contract Renewal
Contract History
Term-Change Audit History
```

However, these records are not durable across process restarts.

The `auto_renew` configuration value does not, by itself, mean that a background scheduler automatically renews contracts.

A production implementation should persist:

```text
Contracts
Contract Versions
Contract History
Renewal Records
Audit Records
```

in durable storage.

---

# 26. End-to-End Workflows

## Procure-to-Pay Workflow

The Supplier Portal implements the defined procure-to-pay (P2P) workflow.

```text
Create Purchase Order
          |
          v
        Draft
          |
          v
         Sent
          |
          v
Supplier Acknowledgement
          |
          v
     Acknowledged
          |
          v
        Shipped
          |
          v
      Goods Receipt
          |
          v
       Received
          |
          v
     Submit Invoice
          |
          v
       Invoiced
          |
          v
    Three-Way Match
          |
          +---------------------+
          |                     |
          v                     v
       Matched             Discrepancy
          |                     |
          v                     v
 Payment Approval          Human Review
                                |
                                v
                       Controlled Resolution
```

The precise state transitions are governed by the P2P state machine and endpoint validation. A discrepancy must not be treated as automatically approved merely because the matching operation has completed.

## Three-Way Match

The three-way match compares the Purchase Order, Goods Receipt, and Invoice.

```text
Purchase Order
      |
      +-- Item
      +-- Ordered Quantity
      +-- Agreed Price
      |
      v
Goods Receipt
      |
      +-- Item
      +-- Received Quantity
      |
      v
Invoice
      |
      +-- Item
      +-- Invoiced Quantity
      +-- Invoiced Price
      |
      v
Three-Way Match
      |
      +--------------------+
      |                    |
      v                    v
   Matched             Discrepancy
                           |
                           v
                      Human Review
```

The configured price tolerance is 5%. The implementation applies its configured inclusive tolerance when evaluating price differences. Quantity differences are evaluated separately from price tolerance.

A discrepancy is routed for controlled review and resolution. It must not bypass the applicable authorization or approval rules.

The current P2P state model does not represent a complete repeated-partial-invoice lifecycle. Partial invoice validation does not, by itself, guarantee that multiple invoices can be processed against one Purchase Order through to a fully invoiced state.

## Supplier Onboarding and Initial Compliance Check

The onboarding process is:

```text
Supplier Registration
          |
          v
   Document Collection
          |
          v
 Document Storage in MinIO
          |
          v
   Verification / Review
          |
          v
        Approval
          |
          v
Compliance Service Internal Check
          |
          +--------------------------+
          |             |            |
          v             v            v
        CLEAR         REVIEW        BLOCK
          |             |            |
          v             +------------+
    Activation       Activation
      Permitted       Not Permitted
```

The onboarding integration calls:

```http
POST /api/v1/compliance/internal-check
```

The request identifies the calling service using:

```http
X-Caller-Service: supplier-portal
```

The Supplier Portal permits activation only when the Compliance response satisfies the required clear decision and `cleared is True`.

- `CLEAR` with `cleared is True`: activation may proceed, subject to the other onboarding requirements.
- `BLOCK` or `REVIEW`: activation is not permitted.
- Compliance dependency unavailable: activation fails closed.
- Invalid or unusable Compliance response: activation is not permitted.

The initial onboarding check and the R14 ongoing status-change consumer are separate integration paths. The onboarding lifecycle status must not be confused with the current compliance access state.

## Ongoing Supplier Compliance Access

Round 14 adds event-driven compliance access enforcement.

The event topic is:

```text
compliance.supplier.status_changed
```

The consumer group is:

```text
supplier-portal-service
```

The consumer maps compliance decisions to access states:

| Compliance decision | Supplier compliance access state | Intended access |
|---|---|---|
| `CLEAR` | `cleared` | Normal permitted access, subject to authentication and ownership rules |
| `REVIEW` | `needs_review` | Restricted, view-only access where supported |
| `BLOCK` | `suspended` | Protected access denied |

The current compliance access state is separate from the supplier's onboarding lifecycle status.

```text
Compliance Service
        |
        v
      Kafka
        |
        v
Supplier Portal Consumer
        |
        v
Persisted Compliance Access State
        |
        +----------------+----------------+
        |                |                |
        v                v                v
     CLEARED        NEEDS REVIEW      SUSPENDED
        |                |                |
        v                v                v
 Normal Permitted    Restricted        Protected
     Access           View Access      Access Denied
```

The actual restrictions depend on the enforcement implemented by each REST endpoint, GraphQL resolver, and document-download path.

## R14 Kafka Event Processing

The consumer processes events from:

```text
compliance.supplier.status_changed
```

The expected processing sequence is:

```text
Receive Kafka Event
          |
          v
      Parse JSON
          |
          v
 Validate Event Contract
          |
          v
 Validate Supplier Identity
          |
          v
  Check event_id Idempotency
          |
          v
 Check occurred_at Ordering
          |
          v
 Persist Access-State Change
          |
          v
 Persist Audit / Processing Records
          |
          v
      Commit Offset
```

The event contract requires `payload.supplier_id`. The consumer does not infer supplier identity from `supplier_name` or `country`.

For invalid events, the consumer's configured dead-letter handling sends the message to:

```text
compliance.supplier.status_changed.dlq
```

The original offset is committed only according to the implemented invalid-message handling path.

For unexpected processing failures, the consumer must not acknowledge the event as successfully processed. Manual offset management is used to avoid treating an unsuccessful state update as a completed operation.

The consumer's SQLite persistence and Kafka offset management serve different purposes. They must be coordinated carefully: durable idempotency records help protect against replay, while offset commits control the consumer's progress through the Kafka partition.

## Supplier Compliance State Restoration

A subsequent `CLEAR` event can restore access after a prior suspension, provided the event is valid and is not stale or already processed.

```text
BLOCK Event
     |
     v
  SUSPENDED
     |
     v
Valid, Newer CLEAR Event
     |
     v
   CLEARED
     |
     v
Access Restored
```

Restoring access does not erase previous audit records. The historical suspension and subsequent clearance remain part of the compliance event history.

## Document Download Workflow

Invoice PDFs and onboarding documents use MinIO for binary storage.

```text
Authenticated Request
          |
          v
  Locate Document Metadata
          |
          v
 Validate Supplier Ownership
          |
          v
 Validate Compliance Access
          |
          v
      Check Object
          |
          v
 Generate Presigned URL
          |
          v
   Client Downloads File
```

A cross-supplier request must be rejected:

```text
Supplier A
    |
    v
Requests Supplier B's Document
    |
    v
Ownership Validation
    |
    v
403 Forbidden
```

A suspended supplier's protected document request must also be rejected before a new presigned URL is generated.

## GraphQL Workflow

Round 13 introduces a Strawberry GraphQL API for the defined Supplier Portal scope.

```text
Supplier Portal Frontend
          |
          v
      Apollo Client
          |
          v
       /graphql
          |
          v
GraphQL Context / Authentication
          |
          v
        Resolver
          |
          v
 Supplier Ownership Validation
          |
          v
 Compliance Access Validation
          |
          v
 Existing Service / Data Access
          |
          v
 GraphQL Type Conversion
          |
          v
       Response
```

The implemented GraphQL scope includes:

```text
Purchase Order Queries
Invoice Queries
Document Queries
Acknowledge-PO Mutation
Cursor Pagination
Supplier-Level Authorization
```

Collection queries use cursor-based pagination with connection information such as:

```text
first
after
  |
  v
Edges
  |
  v
PageInfo
  |
  +-- hasNextPage
  +-- endCursor
```

Supplier authorization must be applied before returning collection results. Cursor pagination is currently based on the existing collection implementation; it should not be described as stable database-backed pagination. If the underlying in-memory collection changes, cursor positions may shift.

## Supplier Contract Workflow

Supplier contracts follow a lifecycle separate from the P2P state machine.

```text
Create Contract
       |
       v
     Draft
       |
       v
    Activate
       |
       v
     Active
       |
       +------------------+
       |                  |
       v                  v
     Renew              Expiry
       |                  |
       v                  v
    Renewed             Expired
       |
       v
    Active
```

The explicit renewal operation records the applicable renewal details, including:

```text
Previous End Date
New Start Date
New End Date
Renewal Reason
Renewed By
Renewed At
```

Meaningful term changes can create contract audit-history entries. Contract renewal currently updates the existing contract record and records history; it does not imply that immutable contract-version storage or automatic renewal scheduling is implemented.

## Supplier Analytics Workflow

Operational activity feeds supplier performance analytics.

```text
Purchase Orders
       |
       v
Goods Receipts
       |
       v
Invoices and Disputes
       |
       v
Supplier Statistics
       |
       v
Supplier Scorecard
       |
       v
Supplier Self-Service
```

The analytics include the metrics supported by the current implementation, such as delivery performance, invoice accuracy, invoice cycle time, disputes, and applicable trends.

For fulfilled Purchase Orders, the actual delivery date is based on the applicable Goods Receipt date rather than automatically substituting the current date.

Supplier-facing scorecard requests remain subject to authentication, supplier ownership, and compliance access restrictions. A supplier must not be able to retrieve another supplier's scorecard.

---

# 27. Current Implementation Status

The following table summarizes the defined functionality. “Complete” describes the implementation scope; it does not independently certify production readiness or replace the automated test results.

| Module / Capability | Status |
|---|---|
| Procure-to-Pay Workflow | Implemented |
| P2P State Machine | Implemented |
| Shipment Processing | Implemented |
| Goods Receipt Workflow | Implemented |
| Partial Goods Receipt Support | Implemented |
| Goods Receipt Validation | Implemented |
| P2P Invoice Integration | Implemented |
| Three-Way Match | Implemented |
| Quantity Discrepancy Detection | Implemented |
| Price Discrepancy Detection | Implemented |
| Human-Review Discrepancy Handling | Implemented |
| Payment Approval Workflow | Implemented |
| Supplier Onboarding Registration | Implemented |
| Supplier Document Collection | Implemented |
| Supplier Onboarding Document Validation | Implemented |
| Supplier Mock Verification | Implemented |
| Supplier Onboarding Approval | Implemented |
| Compliance Service Activation Check | Implemented |
| Compliance CLEAR / BLOCK / REVIEW Handling | Implemented |
| Compliance Failure Handling | Implemented |
| Fail-Closed Supplier Activation | Implemented |
| Active Supplier Enforcement for PO Creation | Implemented |
| Supplier Performance Analytics | Implemented |
| Invoice Cycle-Time Metrics | Implemented |
| Supplier Trend Metrics | Implemented |
| Supplier Self-Service Scorecard | Implemented |
| Supplier Contract Lifecycle | Implemented |
| Contract Expiry Tracking | Implemented |
| Explicit Contract Renewal | Implemented |
| Contract Term-Change Audit History | Implemented |
| Historical Dispute-Resolution Suggestions | Implemented |
| Supplier-Scoping Validation | Implemented |
| Cross-Supplier Endpoint Testing | Implemented |
| P2P Business-Rule Testing | Implemented |
| Three-Way Match Discrepancy Testing | Implemented |
| Supplier Onboarding Workflow Testing | Implemented |
| Compliance Integration Testing | Implemented |
| Contract Lifecycle Testing | Implemented |
| Dispute Suggestion Testing | Implemented |
| Self-Service Scorecard Testing | Implemented |
| Authentication-Required Endpoint Testing | Implemented |
| MinIO Document Storage | Implemented |
| MinIO Invoice Document Download | Implemented |
| MinIO Supplier Document Download | Implemented |
| Presigned Document URLs | Implemented |
| Cross-Supplier Document Isolation | Implemented |
| GraphQL API | Implemented |
| GraphQL Purchase Order Queries | Implemented |
| GraphQL Invoice Queries | Implemented |
| GraphQL Document Queries | Implemented |
| GraphQL Cursor Pagination | Implemented |
| GraphQL Acknowledge-PO Mutation | Implemented |
| GraphQL Supplier Scoping | Implemented |
| GraphQL Cross-Supplier PO Testing | Implemented |
| R14 Kafka Status-Change Consumer | Implemented |
| R14 Supplier Compliance Access State | Implemented |
| R14 CLEAR / REVIEW / BLOCK Mapping | Implemented |
| R14 Event Idempotency | Implemented |
| R14 Event Ordering Protection | Implemented |
| R14 Kafka DLQ Handling | Implemented |
| R14 Manual Offset Management | Implemented |
| R14 REST Compliance Enforcement | Implemented |
| R14 GraphQL Compliance Enforcement | Implemented |
| R14 MinIO Suspension Protection | Implemented |
| R14 Compliance Audit History | Implemented |
| R14 SQLite-Backed State and Processing Records | Implemented |

**Scope note:** Automatic contract renewal, repeated partial invoicing through a complete P2P lifecycle, durable persistence for all business data, and production-grade observability are not included in the completed functionality listed above.

## Rounds 6–8 Completion Status

The five planned functional milestones cover the following areas.

### Milestone 1 — Procure-to-Pay Flow

Status: **Implemented**

```text
PO
→ Acknowledgement
→ Shipment
→ Goods Receipt
→ Invoice
→ Three-Way Match
→ Payment Approval
```

### Milestone 2 — Three-Way Match Automation

Status: **Implemented**

The matching logic compares Purchase Order, Goods Receipt, and Invoice information. It identifies quantity and price discrepancies using the configured inclusive 5% price tolerance.

Discrepancies are routed for human review instead of being automatically approved.

### Milestone 3 — Supplier Onboarding

Status: **Implemented**

```text
Registration
→ Documents
→ Mock Verification
→ Approval
→ Compliance Check
→ Active
```

Purchase Order creation validates the referenced supplier and its onboarding status according to the implemented business rules.

### Milestone 4 — Supplier Performance Analytics

Status: **Implemented**

Supplier performance is exposed through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

For fulfilled Purchase Orders, actual delivery performance uses applicable Goods Receipt dates.

### Milestone 5 — Supplier-Scoping Security

Status: **Implemented**

Supplier-facing access applies the applicable combination of:

```text
Authentication
      +
Role Authorization
      +
Supplier Ownership
      +
Collection Filtering
      +
Compliance Access Enforcement
```

Cross-supplier access is covered by the implemented endpoint tests.

## Rounds 9–11 Completion Status

Rounds 9–11 extended the Supplier Portal with:

- Compliance business-logic integration
- Supplier contract lifecycle management
- Contract expiry and explicit renewal
- Contract term-change audit history
- Historical dispute-resolution suggestions
- Supplier self-service analytics and scorecards

The existing R9–11 Task 1–6 sections remain unchanged.

## Round 12–13 Completion Status

Round 12 implemented the MinIO document-storage migration, and Round 13 implemented the defined GraphQL API scope.

Implemented capabilities include:

```text
MinIO Invoice Document Storage
MinIO Supplier Onboarding Document Storage
Presigned Document URLs
Document Ownership Protection

Strawberry GraphQL
Purchase Order Queries
Invoice Queries
Document Queries
Cursor Pagination
Acknowledge-PO Mutation
Resolver-Level Supplier Scoping
```

## Round 14 Completion Status

Round 14 implements event-driven supplier compliance access enforcement.

The consumer uses:

```text
Topic:
compliance.supplier.status_changed

Consumer Group:
supplier-portal-service

DLQ:
compliance.supplier.status_changed.dlq
```

Implemented capabilities include:

```text
CLEAR → cleared
REVIEW → needs_review
BLOCK → suspended

event_id Idempotency
occurred_at Ordering Protection
Manual Kafka Offset Management
Invalid-Event / DLQ Handling
Unknown-Supplier Validation

REST Compliance Enforcement
GraphQL Compliance Enforcement
MinIO Document-Access Enforcement

SQLite-Backed Compliance State
SQLite-Backed Event-Processing Records
SQLite-Backed Compliance Audit History
```

The architecture is:

```text
Compliance Service
       |
       v
      Kafka
       |
       v
Supplier Portal Consumer
       |
       v
SQLite Compliance State and Audit Records
       |
       v
REST / GraphQL / MinIO Access Enforcement
```

Round 14 introduces SQLite-backed persistence for its compliance state and processing records. It does not introduce a persistent database for all Supplier Portal business data.

---

# 28. Known Limitations

The current implementation is designed for development, functional validation, and automated testing. The defined R5, R6–8, R9–11, Round 12, Round 13, and Round 14 functional scopes are implemented, subject to the limitations documented below.
- Suppliers are matched by name until the compliance event carries a `supplier_id`. Two suppliers with the same name are both affected, which fails safe.
- An event that still fails after `KAFKA_MAX_RETRIES` attempts goes to the DLQ without being applied. A `BLOCK` that ends up there must be replayed once the underlying cause is fixed.

## In-Memory Business Storage

Purchase Orders, invoices, P2P workflow data, supplier onboarding metadata, contract records, contract history, and other business data held in in-memory stores are not durable across application restarts.

```text
Application Running
        |
        v
In-Memory Business Data Exists
        |
        v
Application Restart
        |
        v
In-Memory Business Data Cleared
```

This limitation does not describe the R14 SQLite-backed compliance records or MinIO document binaries, which use separate storage mechanisms.

## R14 Compliance State Durability and Recovery

R14 persists compliance access state, processed-event records, ordering metadata, and audit history in SQLite.

These records can survive application restarts if the SQLite database file is retained, accessible, and correctly configured.

Production hardening should still address:

```text
SQLite Database Backup
Database File Retention
Transaction and Failure Recovery
Database Integrity Monitoring
Event Replay Procedures
Kafka Offset / Database Consistency
Recovery Testing
```

A production deployment must coordinate database updates and Kafka offset commits carefully. A database write and Kafka offset commit are not one atomic transaction. Idempotency records and recovery procedures are important for handling redelivery and restart scenarios safely.

## Partial Invoice Lifecycle

The current P2P state machine supports the transition to `invoiced` after the applicable receipt and invoice validations.

Partial invoice validation exists at the invoice-service level, but the P2P state model does not yet provide a complete repeated-partial-invoice lifecycle for a single Purchase Order.

For example:

```text
PO Quantity = 10
        |
        v
Invoice 1 = 5
        |
        v
Remaining Quantity = 5
        |
        v
Invoice 2 = 5
        |
        v
Fully Invoiced
```

The repeated-invoice accounting, remaining quantity, duplicate prevention, cumulative matching, and final completion behavior require additional lifecycle support.

## Kafka Runtime Dependency

Round 14 requires Kafka for live compliance status-change consumption.

The local development configuration uses:

```text
Kafka:
localhost:9092

Topic:
compliance.supplier.status_changed

DLQ:
compliance.supplier.status_changed.dlq
```

If Kafka is unavailable, the background consumer cannot process new compliance status events until connectivity is restored.

REST and GraphQL continue to rely on the compliance state available to the application; they do not replace the ongoing event-driven update mechanism. If the consumer cannot receive a new event, the stored state may not yet reflect the latest decision made by the Compliance Service.

Production deployment should monitor consumer health, event lag, DLQ volume, and the age of the last successfully processed event.

## External Compliance Producer Contract

The Supplier Portal consumer expects the agreed R14 event contract, including:

```text
payload.supplier_id
```

The Compliance Service producer is a separately owned integration dependency. The Supplier Portal does not infer supplier identity from `supplier_name` or `country`.

If the producer omits required fields, the consumer rejects the event according to its validation and dead-letter handling rules rather than guessing the supplier identity.

Producer and consumer contract tests should be maintained together as the event schema evolves.

## Document Storage and Recovery

Round 12 uses MinIO for active invoice PDF and supplier onboarding document storage. Local `uploads/` storage is not the active document-binary storage mechanism.

Production considerations include:

```text
MinIO Backup and Recovery
Object Retention
Encryption at Rest
Object Lifecycle Management
Disaster Recovery
Production Access Policies
Presigned URL Expiry
```

A previously issued presigned URL may remain usable until expiry. Immediate revocation should not be assumed unless an explicit revocation mechanism is implemented.

## Authentication Dependency

Authentication relies on the centralized Platform Service at the configured authentication URL.

If the Platform Service is unavailable or validation times out, protected endpoints may return:

```text
503 Service Unavailable
```

This dependency is intentional: the Platform Service remains the centralized authentication provider. The Supplier Portal should continue to delegate token validation rather than introduce a separate, conflicting token-validation implementation.

## Compliance Service Dependency

Supplier activation depends on the Compliance Service.

If Compliance is unavailable or its response cannot be safely interpreted, activation is blocked. This fail-closed behavior prevents the onboarding flow from treating an unavailable compliance check as a clearance.

## Automatic Contract Renewal

The contract model supports an `auto_renew` configuration value, but the current implementation does not include a background scheduler or automatic renewal worker.

The current behavior requires an explicit renewal operation. It does not automatically perform:

```text
Renewal Scheduling
Renewal Eligibility Evaluation
Automatic Contract Renewal
Automatic Contract-Version Generation
```

## Contract Versioning

Contract renewal updates the existing contract record and records renewal history. The current implementation does not provide a complete immutable, versioned contract repository from which every historical contract version can be reconstructed independently.

## Historical Dispute Suggestions

The dispute-resolution suggestion feature is advisory. It does not automatically:

```text
Resolve Disputes
Adjust Invoices
Create Credit Notes
Approve Payments
Change Match Status
```

Any actual resolution or financial adjustment must follow the applicable authorization and approval workflow.

## GraphQL Expansion

The defined Round 13 GraphQL scope covers:

```text
Purchase Orders
Invoices
Documents
Cursor Pagination
Acknowledge-PO Mutation
Supplier Scoping
```

Potential future enhancements include:

```text
Additional Mutations
Additional Business Domains
Richer Pagination Metadata
Subscriptions
More Granular Permissions
Query Complexity Controls
Production Observability
```

These are future enhancements rather than missing requirements in the defined Round 13 scope.

## Production Persistence

A production deployment should introduce durable persistence for business data, including:

- Purchase Orders and PO events
- Invoices and invoice lifecycle records
- Supplier onboarding and supplier metadata
- Shipments and Goods Receipts
- P2P state and match decisions
- Contracts, renewal records, and contract history
- Supplier analytics source data
- Business audit records

The migration should preserve existing authentication, role authorization, supplier ownership checks, and compliance access controls.

---

# 29. Future Enhancements

The following items are future production or scope expansions beyond the defined R5, R6–8, R9–11, Round 12, Round 13, and Round 14 functionality.

## Persistent Business Database

Replace in-memory business stores with a persistent database.

Potential entities include:

```text
Suppliers
Purchase Orders
PO Events
Invoices
P2P State
Goods Receipts
Shipments
Supplier Onboarding
Supplier Statistics
Scorecards
Contracts
Contract Versions
Contract History
Business Audit Records
```

The existing SQLite-backed R14 compliance state should be considered as part of the broader persistence architecture. A future design may retain SQLite for a suitable deployment or migrate compliance and business data to a shared production database, provided transaction, durability, and operational requirements are met.

## Advanced Document Storage Operations

MinIO is already used for active document storage. Future enhancements may include:

- Encryption-at-rest configuration and verification
- Object lifecycle policies
- Retention policies
- Backup and recovery automation
- Object versioning
- Malware scanning
- Document classification
- Disaster recovery procedures

## Complete Multi-Invoice P2P Lifecycle

Extend the P2P state model to support repeated partial invoicing against one Purchase Order.

Potential behavior:

```text
PO Quantity = 10
       |
       v
Invoice 1 = 5
       |
       v
Remaining Quantity = 5
       |
       v
Invoice 2 = 5
       |
       v
Fully Invoiced
```

The implementation should include cumulative quantity and price validation, duplicate invoice prevention, remaining quantity tracking, and correct final state transitions.

## Automatic Contract Renewal

Extend the existing `auto_renew` configuration into a scheduled or worker-based renewal mechanism.

Potential architecture:

```text
Contract
   |
   v
Renewal Notice Window
   |
   v
Scheduler / Worker
   |
   v
Renewal Eligibility Check
   |
   v
Automatic or Approval-Based Renewal
   |
   v
New Contract Version
   |
   v
Audit History
```

The design should define notice periods, eligibility conditions, approval requirements, idempotency, failure recovery, and audit behavior.

## Explicit Contract Versioning

Introduce immutable contract versions so that previous terms can be reconstructed and audited independently of the current contract record.

## Production Supplier Verification

Replace mock supplier verification with an approved external supplier-verification integration, including dependency failure handling, audit records, and authorization checks.

## Payment Service Integration

The current payment approval workflow is represented in the Supplier Portal P2P state model. A future implementation could integrate the workflow with a dedicated payment or finance service.

The integration should distinguish approval of a payment from actual payment execution and settlement.

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

Event publication should account for delivery guarantees, duplicate handling, event schema evolution, and consistency between database transactions and message delivery.

## Durable Event-Driven Compliance Processing

R14 already persists compliance state and event-processing records in SQLite. Future production improvements may include:

```text
Database Backup and Recovery
Consumer Offset Reconciliation
Event Replay Tooling
DLQ Reprocessing
Event Retention Policies
Consumer Lag Monitoring
Retry / Backoff Policies
Poison-Message Management
Cross-Instance Coordination
```

The design should preserve idempotency and event-ordering protections when multiple consumer instances or recovery workflows are introduced.

## Advanced Supplier Analytics

Potential future analytics capabilities include:

- Supplier trend dashboards
- Delivery-risk indicators
- Invoice anomaly detection
- Supplier benchmarking
- Historical scorecard trends
- Predictive supplier performance analytics

New metrics should be defined with explicit formulas, data-quality requirements, and clear treatment of incomplete or missing records.

## Advanced Dispute Intelligence

The existing historical dispute-resolution feature is advisory. Future improvements may include:

- More detailed historical classifications
- Larger and higher-quality historical datasets
- Confidence indicators
- Explainable recommendation evidence
- Additional resolution-action categories
- Human feedback capture
- Resolution-effectiveness tracking

Suggestions should remain separate from the authority to resolve disputes, change invoice amounts, or approve payments.

## Expanded GraphQL API

Potential future GraphQL capabilities include:

```text
Additional Queries
Additional Mutations
Contract APIs
Shipment APIs
Goods Receipt APIs
Scorecard APIs
GraphQL Subscriptions
Richer Connection Metadata
Query Complexity Protection
GraphQL Observability
```

Any new resolvers must retain authentication, role authorization, supplier ownership checks, and compliance access enforcement.

## Expanded Integration Testing

A future end-to-end test could exercise the full onboarding and P2P workflow:

```text
Supplier Registration
        |
        v
Document Collection
        |
        v
MinIO Document Storage
        |
        v
Compliance CLEAR
        |
        v
Supplier Activation
        |
        v
Create PO
        |
        v
Send PO
        |
        v
Supplier Acknowledgement
        |
        v
Shipment
        |
        v
Goods Receipt
        |
        v
Invoice
        |
        v
Three-Way Match
        |
        v
Payment Approval
```

The R14 extension could verify:

```text
Compliance Status Event
        |
        v
Kafka
        |
        v
Supplier Portal Consumer
        |
        v
BLOCK
        |
        v
Supplier Access Suspended
        |
        v
REST / GraphQL / Document Access Rejected
        |
        v
CLEAR
        |
        v
Supplier Access Restored
```

Additional restart and recovery tests should verify SQLite persistence, event redelivery, idempotency, offset management, and preservation of compliance audit history.

These tests would complement the existing focused service, REST API, MinIO, Kafka consumer, and GraphQL tests.

## Production Observability

Future production deployments should introduce:

- Centralized logging
- Application and dependency metrics
- Distributed tracing
- Health and readiness checks
- Platform authentication dependency monitoring
- Compliance dependency monitoring
- MinIO availability monitoring
- Kafka broker and consumer monitoring
- Kafka consumer-lag and DLQ monitoring
- P2P workflow monitoring
- Contract expiry monitoring
- GraphQL request monitoring
- Compliance status-change monitoring
- Operational alerting

## Advanced Authorization

Potential future authorization enhancements include:

```text
Fine-Grained Permissions
        |
        v
Segregation of Duties
        |
        v
Workflow-Specific Permissions
        |
        v
Compliance-State-Aware Permissions
        |
        v
Auditable Administrative Controls
```

The existing supplier ownership model should remain a core security boundary.

## Audit and Compliance Enhancements

Future versions may expand persistent audit coverage for:

- PO transitions
- Supplier onboarding transitions
- Compliance decisions and status-change events
- Invoice transitions
- Goods Receipt creation
- Shipment events
- Three-way match decisions
- Payment approvals
- Contract term changes
- Contract renewals
- Document access events
- GraphQL mutations
- Administrative maintenance operations

Audit records should identify the actor or service, the affected resource, the operation, the timestamp, and the relevant outcome, while avoiding unnecessary sensitive data.

## Kafka Event Contract Governance

Future production integration should formalize the producer/consumer contract through:

```text
Schema Versioning
Schema Registry
Backward-Compatible Event Evolution
Producer Contract Tests
Consumer Contract Tests
Event Compatibility Validation
```

The `supplier_id` field should remain a required identifier for supplier-specific compliance status events. Supplier identity must not be guessed from a supplier name or country.

## Summary of Future Scope

The defined functional scope covers:

```text
R5
R6–8
R9–11
Round 12
Round 13
Round 14
```

Future work primarily concerns:

```text
Persistent Business Database
Advanced MinIO Operations
Complete Multi-Invoice Lifecycle
Automatic Contract Renewal
Explicit Contract Versioning
External Supplier Verification
Payment-Service Integration
Event-Driven P2P Processing
Compliance Recovery and Operations
Kafka Observability
Advanced Analytics
Advanced Dispute Intelligence
Expanded GraphQL API
Expanded Integration Testing
Production Observability
Advanced Authorization
Persistent Business Audit Controls
Event Contract Governance
```

These enhancements build on the existing authentication, supplier-scoping, P2P, Compliance integration, contract, dispute-suggestion, supplier analytics, MinIO document-storage, GraphQL, and event-driven supplier compliance functionality.
