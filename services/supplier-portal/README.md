# Enterprise AI Cognitive Supply Chain Platform

# Supplier Portal Service

A **FastAPI-based microservice** for supplier-facing purchase orders (POs), invoices, document management, supplier onboarding, contracts, performance scorecards, dispute-resolution suggestions, and procure-to-pay (P2P) workflows.

The service integrates with the **Platform Service** for authentication and role-based authorization, the **Compliance Service** for supplier activation checks, **MinIO** for document storage, **Strawberry GraphQL** for portal queries and mutations, and **Apache Kafka** for compliance status changes and approved purchase-order events.

Invoice PDFs and supplier onboarding documents are stored in MinIO. Authorized downloads use short-lived presigned URLs after authentication, authorization, compliance-access, and supplier-ownership checks.

Round 14 adds Kafka-based compliance status processing, event idempotency, out-of-order event protection, audit history, manual offset management, and dead-letter queue (DLQ) handling.

Round 15 adds the Inventory approved-PO consumer, `po_mirror` persistence, supplier-scoped approved-PO access through REST and GraphQL, and supplier PO acknowledgement backed by a transactional outbox.

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
- **Milestone 3:** Strawberry GraphQL queries, cursor pagination, PO acknowledgement mutation, and resolver-level supplier scoping.

**Known limitation:** GraphQL cursors for legacy in-memory collections represent positions in lists. Those positions may change when records are added or removed. Most legacy business records are not durable across application restarts.

## Round 14 Status

**Round 14 – Pod 1: Supplier Compliance Status Event Consumption**

Implemented capabilities:

- Kafka consumer for `compliance.supplier.status_changed`.
- Consumer group `supplier-portal-service`.
- Event schema, type, and version validation.
- `event_id` idempotency and `occurred_at` ordering protection.
- Compliance state mapping and audit history.
- Manual offset management and DLQ handling.
- REST and GraphQL compliance access enforcement.
- Supplier PO, invoice, and document access restrictions.
- Local Kafka development infrastructure and consumer tests.

Compliance state mapping:

| Event decision | Supplier Portal state | Supplier access |
|---|---|---|
| `CLEAR` | `cleared` | Permitted reads and otherwise-authorized writes |
| `REVIEW` | `needs_review` | Reads allowed; protected writes denied |
| `BLOCK` | `suspended` | Supplier-facing protected access denied |

Compliance access state is separate from the supplier onboarding lifecycle status.

The synchronous Compliance Service check during activation remains unchanged:

`approved → Compliance internal-check → CLEAR → active`

Kafka handles ongoing compliance status changes after activation.

**Event contract boundary:** The compliance event does not carry `supplier_id`. Supplier Portal identifies the matching onboarding record using the producer's `payload.supplier_name`, comparing it with `company_name` after normalization. The Kafka key is not treated as the supplier's identity.

## Round 15 Status

**Round 15 – Inventory Approved Purchase Orders and Supplier Acknowledgement**

The Supplier Portal consumes Inventory's `inventory.po.approved` event and persists approved purchase-order data in `po_mirror`. Suppliers can retrieve their authorized approved POs through REST and GraphQL.

When a supplier acknowledges an eligible PO, the acknowledgement service updates the PO mirror and records an outgoing event in the transactional outbox.

Implemented areas:

- Inventory approved-PO Kafka consumer.
- Approved-PO persistence through `po_mirror`.
- Event idempotency and consumer retry/DLQ handling.
- Supplier-scoped REST and GraphQL access.
- Supplier PO acknowledgement service.
- Transactional acknowledgement outbox.
- Automated consumer, API, service, and GraphQL tests.

**Event publication boundary:** Persisting an event in the transactional outbox does not, by itself, prove that it has been published to Kafka. Publication depends on the outbox publisher and its runtime configuration. Compatibility with the Inventory producer's canonical example must be verified against the actual event contract before being marked as confirmed.

---

## Running Locally

Run the commands below from the appropriate directory. Repository-level Docker Compose commands should be executed from the repository root; application and test commands should be executed from `services/supplier-portal`.

Create the local environment file:

```bash
cp .env.example .env
```

Configure valid MinIO credentials and the application settings required by the project. Use the exact environment-variable names defined in `app/core/config.py` and `.env.example`.

Start development dependencies from the repository root:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

Typical local development endpoints:

| Service | Endpoint |
|---|---|
| Supplier Portal | `http://127.0.0.1:8000` |
| MinIO API | `http://127.0.0.1:9000` |
| MinIO Console | `http://127.0.0.1:9001` |
| Kafka broker | `localhost:9092` |
| Platform Service | `http://127.0.0.1:8005` |

Actual endpoints depend on the local environment configuration.

Start the Supplier Portal:

```bash
cd services/supplier-portal
python -m uvicorn app.main:app --reload --port 8000
```

Run the non-integration test suite:

```bash
python -m pytest -m "not integration" -q
```

Run integration tests when the required dependencies are running and configured:

```bash
python -m pytest -m integration -q
```

Run the complete suite:

```bash
python -m pytest -q
```

### MinIO Document Storage — Rounds 12–13

MinIO provides S3-compatible storage for invoice PDFs and supplier onboarding documents. The local development setup uses `docker-compose.dev.yml`.

Typical configuration values are shown below; use the variable names and defaults defined in the current application configuration:

```text
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=<configured-value>
MINIO_SECRET_KEY=<configured-value>
MINIO_BUCKET=supplier-documents
MINIO_SECURE=false
MINIO_PRESIGNED_EXPIRY_SECONDS=300
```

Start or inspect the development services from the repository root:

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker ps
```

If the MinIO container already exists but is stopped:

```bash
docker start supplier-portal-minio
```

### Start Kafka for Round 14 and Round 15

Start Kafka using the development Compose configuration:

```bash
docker compose -f docker-compose.dev.yml up -d kafka
docker ps
```

The application configuration must specify the relevant topics and consumer settings. Before creating topics manually, check whether the development Compose configuration or repository scripts already create them.

The following topics belong to the documented consumer contracts:

- Round 14 input: `compliance.supplier.status_changed`
- Round 14 DLQ: `compliance.supplier.status_changed.dlq`
- Round 15 input: `inventory.po.approved`

Use the exact Round 15 consumer and DLQ settings from `app/core/config.py` and `.env.example`; do not assume that the Round 14 topic or consumer-group settings apply to the Inventory consumer.

Run the Round 14 targeted tests:

```bash
python -m pytest tests/test_kafka_consumer.py tests/test_r14_enforcement.py -q
```

Run the Round 15 targeted tests:

```bash
python -m pytest tests/test_inventory_po_approved_consumer.py -q
python -m pytest tests/test_approved_purchase_orders.py -q
python -m pytest tests/test_po_acknowledgement_service.py -q
python -m pytest tests/test_graphql.py -q
```

These tests can validate consumer, service, API, and GraphQL behavior without claiming that a live Kafka producer-to-consumer integration has been exercised.

### Document access flow

**Upload:** Validate the document, authenticate the caller, check authorization and supplier ownership, then store the object in MinIO.

**Download:** Authenticate the caller, enforce compliance access and supplier ownership, validate the document and object, and generate a short-lived presigned URL.

Cross-supplier access must be denied without generating a presigned URL. A suspended supplier must not obtain a new presigned URL through the protected download flow.

Storage failures must be handled as dependency failures rather than client-validation errors.

Run document-storage tests:

```bash
python -m pytest tests/test_document_storage_service.py tests/test_supplier_document_download.py -q
python -m pytest -m integration -q
```

---

## Supplier Portal–Compliance Integration

Before a supplier moves from `approved` to `active`, Supplier Portal calls the Compliance Service.

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

**Illustrative response**

```json
{
  "decision": "CLEAR",
  "cleared": true,
  "reason": "No sanctions or watchlist match found."
}
```

Activation is permitted only when `decision == "CLEAR"` and `cleared` is `true`. A `BLOCK` or `REVIEW` decision, contradictory response, or unavailable Compliance Service prevents activation.

| Failure or decision | HTTP response |
|---|---:|
| Valid `BLOCK` or `REVIEW` decision | `409 Conflict` |
| Timeout or connection failure | `503 Service Unavailable` |
| Error or unusable Compliance response | `502 Bad Gateway` |

Relevant implementation files:

| File | Responsibility |
|---|---|
| `app/services/compliance_client.py` | Calls Compliance and validates its response |
| `app/services/supplier_onboarding_service.py` | Implements the activation decision |
| `app/routes/supplier_onboarding.py` | Maps service errors to HTTP responses |
| `app/core/config.py` | Configures `COMPLIANCE_SERVICE_URL` |
| `tests/test_compliance_client.py` | Compliance client tests |
| `tests/test_supplier_onboarding.py` | Supplier activation tests |

Run the targeted tests:

```bash
python -m pytest tests/test_compliance_client.py tests/test_supplier_onboarding.py -q
```

Platform Service code remains outside the scope of this integration.

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
2. Resolve the supplier using the producer's supplier-name field and the onboarding record.
3. Check `event_id` for duplicate processing.
4. Compare `occurred_at` to prevent stale events from overwriting newer state.
5. Apply the compliance state and record audit history.
6. Commit the offset after successful processing.

Invalid or unresolvable events are routed to the DLQ. Unexpected processing failures must not commit the original offset, allowing Kafka to redeliver the message.

The consumer uses manual offset management (`enable.auto.commit = false`). Processed event IDs support idempotency.

### Access enforcement

- `cleared`: supplier reads and otherwise-authorized writes are allowed.
- `needs_review`: reads are allowed; protected supplier writes are denied.
- `suspended`: supplier-facing protected operations, including protected document downloads, are denied.

Compliance checks do not replace role authorization or supplier-ownership checks. Internal roles continue to follow their existing authorization rules.

The external compliance event producer is outside the Supplier Portal implementation scope.

---

# 1. Overview

The Supplier Portal Service provides APIs for supplier and procurement workflows, including:

- Purchase orders, approved-PO visibility, supplier acknowledgement, shipment notices, and goods receipts.
- Invoices, three-way matching, discrepancy review, and payment approval.
- Supplier registration, onboarding, and activation.
- Supplier contracts, renewals, and lifecycle history.
- Supplier statistics, performance scorecards, and self-service analytics.
- Historical dispute-resolution suggestions.
- MinIO-backed document storage and secure downloads.
- REST and GraphQL authorization and supplier isolation.
- Synchronous compliance checks during activation.
- Kafka-based compliance status updates and approved-PO consumption.

### Procure-to-pay workflow

```text
Inventory approves a Purchase Order
                 ↓
       inventory.po.approved
                 ↓
       Supplier Portal consumer
                 ↓
             po_mirror
                 ↓
    Supplier REST / GraphQL access
                 ↓
       Supplier acknowledges PO
                 ↓
       PO state + outbox record
                 ↓
  supplierportal.po.acknowledged
```

The final Kafka publication depends on an operational outbox publisher. The persisted outbox record alone is not proof of successful publication.

The wider P2P workflow continues as follows:

```text
Purchase Order → Acknowledgement → Shipment Notice
       → Goods Receipt → Invoice → Three-Way Match
                                     ├── Matched
                                     └── Discrepancy
                                            ↓
                                      Human Review
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

A supplier must satisfy the onboarding and activation requirements before a new PO can be created for that supplier.

### Compliance after activation

Onboarding status and compliance access state are distinct. An active supplier may later be restricted by a Kafka compliance event without changing its onboarding lifecycle state.

| Round | Main deliverables |
|---|---|
| Rounds 5–8 | Supplier scoping, authentication enforcement, PO and invoice workflows |
| Rounds 9–11 | Compliance activation integration, contracts, dispute suggestions, self-service analytics |
| Round 12 | MinIO document storage and presigned downloads |
| Round 13 | GraphQL queries, cursor pagination, acknowledgement mutation, resolver-level scoping |
| Round 14 | Kafka compliance events, idempotency, ordering protection, audit history, offset and DLQ handling |
| Round 15 | Inventory approved-PO consumer, `po_mirror`, supplier-scoped REST/GraphQL access, acknowledgement outbox |

### Storage limitations

- Legacy purchase orders, invoices, P2P records, onboarding records, and contract data use in-memory business storage unless explicitly backed by a database.
- Legacy in-memory business records are not durable across application restarts.
- Round 14 compliance access state, processed-event information, and audit history are SQLite-backed.
- Round 15 approved-PO mirror and acknowledgement outbox use database persistence and migrations.
- Invoice PDFs and onboarding documents are stored in MinIO.
- Authentication depends on Platform Service; supplier activation depends on Compliance Service.
- Local Kafka configuration is intended for development and is not production security configuration.
- External producers must publish events that follow the agreed event contracts.

The service supports development, functional validation, and automated testing. Production deployment requires appropriate database operations, backups, monitoring, security hardening, and durable storage for legacy business records.

---

# 2. Key Features

## Purchase Orders

- Retrieve approved POs received from the Inventory event stream.
- Persist approved-PO data in `po_mirror`.
- Provide supplier-scoped approved-PO access through REST and GraphQL.
- Acknowledge eligible POs and persist acknowledgement events in the transactional outbox.
- Support existing PO workflows, including state transitions, actor tracking, timestamps, and delivery tracking.
- Enforce supplier ownership and applicable compliance restrictions.

Supplier compliance rules:

| State | Supplier PO access |
|---|---|
| `cleared` | View and acknowledge when otherwise authorized |
| `needs_review` | View; acknowledgement blocked |
| `suspended` | Supplier-facing protected access blocked |

The event-consumer flow supplements the existing PO business workflows. Do not assume that every legacy PO record has been migrated into `po_mirror`.

## Invoices

- Create and retrieve invoices with PO, ownership, line-item, and amount validation.
- Support duplicate protection, partial invoices, and multiple line items.
- Manage invoice state transitions, disputes, adjustments, and history.
- Restrict invoice adjustment to authorized compliance roles.
- Support P2P integration and three-way-match discrepancy handling.
- Generate historical dispute-resolution suggestions.

Price differences exceeding the three-way-match tolerance are handled by the matching process; invoice creation does not automatically reject an invoice solely for that reason.

## Invoice Documents

- PDF-only uploads with content-type, signature, and 10 MB size validation.
- MinIO object storage and supplier-scoped object references.
- Object-existence checks and short-lived presigned downloads.
- Compliance and ownership checks before URL generation.
- Cross-supplier protection and storage-failure handling.
- Unit and integration tests.

Documents are stored in MinIO rather than the old local-filesystem upload directory.

**Security rule:** Never generate a presigned URL before authentication, applicable compliance authorization, and supplier-ownership validation.

## Supplier Statistics

- Purchase Order counts and on-time delivery percentage.
- Average invoice cycle time and invoice metrics.
- Date normalization and invalid/missing-date handling.
- Supplier existence validation.
- Exclusion of future-due, cancelled, and undated POs from the on-time denominator.
- Treatment of past-due unfulfilled POs as late.

## Supplier Performance Scorecard

- On-time delivery, invoice accuracy, dispute rate, and overall performance.
- Performance ratings and status.
- PO and invoice performance details.
- Historical dispute tracking and invoice cycle time.
- Monthly trends and supplier-scoped self-service access.

Invoice-related scorecard calculations use the `po_number` stored on invoice line items.

## Procure-to-Pay and Three-Way Match

- PO acknowledgement, shipment notices, and Goods Receipt processing.
- Partial/short receipts and P2P state transitions.
- PO/Receipt/Invoice matching.
- Quantity and price discrepancy detection.
- Human-review handling and prevention of automatic approval when discrepancies exist.
- Payment-approval workflow states.

Historical dispute-resolution suggestions are advisory. They do not automatically modify invoices, approve disputes, or change matching state.

## Supplier Onboarding

- Registration, document collection, mock verification, approval, and activation.
- Supplier-scoped onboarding access and lifecycle-state management.
- Compliance Service activation checks and fail-closed error handling.
- Active-supplier enforcement before PO creation.
- MinIO-backed onboarding documents and presigned downloads.
- Separate Kafka-driven compliance access-state updates after activation.

## Supplier Contract Lifecycle Management

- Create, retrieve, and update supplier contracts.
- Draft-to-active lifecycle and status tracking.
- Expiry detection, renewal processing, and renewal-date validation.
- Renewal reasons, notice periods, and auto-renew configuration.
- Payment terms, delivery terms, pricing terms, and minimum order values.
- Supplier-scoped access and contract history.

Contract records and contract history remain in-memory.

## Supplier Self-Service Analytics

Supplier users can retrieve their own scorecard through:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The service enforces supplier ownership and applicable compliance access. Self-service analytics are read-only.

---

# 3. Architecture

The service uses a layered FastAPI architecture with REST routes, GraphQL operations, authentication and authorization, business services, database-backed components, document storage, and Kafka consumers.

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
  ├── Legacy in-memory business records
  ├── SQLite-backed compliance state/history
  ├── Database-backed approved-PO mirror/outbox
  ├── MinIO document objects
  ├── Platform Service authentication
  ├── Compliance Service activation check
  └── Kafka event consumers
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

## GraphQL

The GraphQL endpoint is `POST /graphql`. Supported query operations include purchase orders, invoices, and supplier documents. Collection operations support cursor pagination using `first`, `after`, `hasNextPage`, and `endCursor`; `first` is limited to 100 records.

The mutation surface includes `acknowledgePurchaseOrder`. Resolvers use the relevant business services and enforce compliance access and supplier ownership.

**Known limitation:** Cursors for legacy in-memory collections are position-based and may not remain stable when the collection changes. Approved-PO persistence and legacy in-memory GraphQL collections should not be treated as the same storage source unless explicitly connected in the implementation.

## MinIO documents

The document storage service handles object uploads, existence checks, missing objects, storage errors, and presigned URL generation. REST endpoints and GraphQL resolvers must authorize requests before exposing protected document information or generating a download URL.

## Kafka compliance processing — Round 14

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

## Inventory approved-PO processing — Round 15

```text
Inventory Producer
       ↓
inventory.po.approved
       ↓
Inventory PO Approved Consumer
       ↓
Event Validation + Idempotency
       ↓
po_mirror Database Persistence
       ↓
Supplier-Scoped REST / GraphQL
       ↓
Supplier Acknowledgement
       ↓
PO Update + Transactional Outbox
       ↓
Outbox Publisher (if configured and running)
       ↓
supplierportal.po.acknowledged
```

The consumer must persist the event's business state before committing the corresponding Kafka offset. Idempotency prevents duplicate delivery from creating duplicate processing effects. Failed processing follows the configured retry/DLQ policy.

The transactional outbox records the outgoing acknowledgement in the same database transaction as the PO update. Kafka publication is a separate step and should be documented as operational only when an outbox publisher is present and verified.

## Contracts and dispute suggestions

Contract management uses a separate business service and an in-memory contract store. The dispute-resolution service analyses historical three-way-match dispute information to produce advisory suggestions.

---

# 4. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| Strawberry GraphQL | GraphQL API |
| Pydantic / Pydantic Settings | Validation and configuration |
| SQLAlchemy / Alembic | Database models, sessions, and migrations for database-backed components |
| Uvicorn | ASGI server |
| HTTPX | HTTP client and API testing |
| Pytest | Automated testing |
| `python-multipart` | Multipart file uploads |
| MinIO / S3-compatible API | Invoice and onboarding document storage |
| Apache Kafka | Compliance status and approved-PO event consumption |
| `confluent-kafka` | Kafka consumption and DLQ publishing |

Dependency versions are maintained in `requirements.txt`. Supplier Portal consumes external compliance and Inventory events; the corresponding producer implementations are outside this service's scope.

---

# 5. Project Structure

The project separates application configuration, authentication, REST routes, GraphQL operations, schemas, business services, storage integrations, Kafka processing, database models, migrations, and tests.

```text
supplier-portal/
├── alembic/
│   └── versions/
│       ├── 002_po_mirror.py
│       └── 003_po_ack_outbox.py
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
│   ├── models/
│   │   ├── __init__.py
│   │   ├── po_mirror.py
│   │   └── po_ack_outbox.py
│   ├── routes/
│   │   ├── purchase_order.py
│   │   ├── approved_purchase_orders.py
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
│       ├── kafka_consumer.py
│       ├── kafka_consumer_runner.py
│       ├── inventory_po_approved_consumer.py
│       ├── inv_po_approved_consumer_runner.py
│       └── po_acknowledgement_service.py
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
│   ├── test_inventory_po_approved_consumer.py
│   ├── test_approved_purchase_orders.py
│   ├── test_po_acknowledgement_service.py
│   └── integration/
│       └── test_minio_document_storage.py
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

This structure reflects the files relevant to the documented workflows. Keep it aligned with the actual repository when files are added, removed, or renamed. The old local `uploads/` directory is not the current document-storage architecture.

## Application and Core

- `app/main.py`: Creates the FastAPI application, registers REST and GraphQL routes, and manages application background tasks.
- `app/core/auth.py`: Handles bearer-token authentication through Platform Service, role authorization, supplier identity, request IDs, and access checks.
- `app/core/config.py`: Loads application, Platform, Compliance, MinIO, and Kafka configuration.
- `alembic/`: Contains database migration configuration and versioned schema changes.

## GraphQL

`app/graphql/` defines the schema, queries, mutations, types, request context, pagination, and resolver-level authorization. Resolvers reuse business services and apply the required supplier-scoping and compliance checks.

`app/graphql/context.py` centralizes GraphQL compliance access checks through `require_graphql_view_access(user)` and `require_graphql_write_access(user)`.

## Routes and Schemas

- `app/routes/`: REST endpoint definitions, dependency injection, access checks, HTTP responses, resource validation, and business-service calls.
- `app/routes/approved_purchase_orders.py`: REST access to persisted approved purchase orders.
- `app/schemas/`: Request/response validation and data models for POs, shipments, receipts, invoices, matching, onboarding, contracts, and events.
- `app/schemas/events.py`: Event payload validation, including the Inventory approved-PO event contract.

## Business Services

`app/services/` contains the workflow and business logic for POs, P2P transitions, shipments, goods receipts, invoices, matching, onboarding, contracts, scorecards, dispute suggestions, compliance integration, and document storage.

### Supplier compliance service

`app/services/supplier_compliance_service.py` maps compliance decisions to access states, rejects stale events, tracks duplicate event IDs, maintains compliance audit history, and exposes state to authorization logic. Round 14 compliance state and event/audit information are SQLite-backed.

### Round 14 Kafka consumer

`app/services/kafka_consumer.py` validates and processes compliance events, applies access-state changes, routes invalid messages to the DLQ, and manages offset commits.

`app/services/kafka_consumer_runner.py` runs the consumer in the application background and handles shutdown.

### Round 15 Inventory approved-PO consumer

`app/services/inventory_po_approved_consumer.py` consumes approved-PO events, validates the event, applies idempotency and retry/DLQ handling, and persists the approved-PO mirror before the original offset is committed.

`app/services/inv_po_approved_consumer_runner.py` manages the approved-PO consumer's application background execution.

`app/models/po_mirror.py` defines the persisted approved-PO mirror. `app/services/po_acknowledgement_service.py` handles supplier acknowledgement and records the outgoing event in the transactional outbox represented by `app/models/po_ack_outbox.py`.

### Document storage

`app/services/document_storage_service.py` provides MinIO object uploads, object-existence checks, presigned URLs, missing-object handling, and storage-failure handling. Callers must complete authentication, compliance authorization, and supplier-ownership checks before requesting a presigned URL.

---

# 6. Authentication and Authorization

Supplier Portal delegates authentication to the **Platform Service**. It does not locally decode or independently validate JWT tokens; it forwards the Bearer token to Platform Service for verification.

Authentication endpoint:

```http
POST /api/v1/auth/verify
```

## 6.1 Authentication flow

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
  ├── Role authorization
  ├── Supplier identity validation
  ├── Compliance access check
  └── Resource ownership check
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

Supplier Portal uses the returned identity for authorization and supplier scoping.

## 6.2 Authentication configuration

The Platform Service URL is configured through:

```text
PLATFORM_AUTH_URL
```

Default development value:

```text
http://127.0.0.1:8005
```

Platform Service remains the authentication provider. Supplier Portal applies its own role, compliance, and resource-level authorization rules.

## 6.3 Authentication and authorization errors

| Situation | Expected response |
|---|---:|
| Missing, invalid, or expired token | `401 Unauthorized` |
| Authenticated user lacks the required role | `403 Forbidden` |
| Supplier identity missing for a supplier-scoped operation | `403 Forbidden` |
| Supplier attempts to access another supplier's resource | `403 Forbidden` |
| Authentication service timeout or unavailability | `503 Service Unavailable` |
| Invalid authentication response from Platform Service | `503 Service Unavailable` |

The exact response also depends on the endpoint and its authorization implementation.

## 6.4 Supplier scoping

For supplier users, the authenticated `supplier_id` must match the supplier associated with the requested resource.

```text
Authenticated supplier: SUP001
Requested resource owner: SUP002
Result: 403 Forbidden
```

This rule applies to supplier-scoped resources, including:

- Purchase orders and PO events.
- Approved purchase orders from `po_mirror`.
- Invoices and invoice documents.
- Supplier statistics and scorecards.
- Shipments and Goods Receipts.
- Three-way-match records.
- Supplier onboarding documents and records.
- Supplier contracts and contract history.
- Supplier-facing GraphQL resources.

Supplier filtering must be applied before returning collection results. GraphQL resolvers enforce ownership independently of REST routes.

For a GraphQL lookup, an unauthorized resource must not be exposed. Depending on the resolver, the result may be `null` or a GraphQL authorization error.

## 6.5 Round 14 compliance access control

Round 14 adds a compliance access state to the existing authentication, role, and ownership checks. This state is maintained separately from the supplier's onboarding lifecycle status.

| Compliance decision | Supplier Portal access state |
|---|---|
| `CLEAR` | `cleared` |
| `REVIEW` | `needs_review` |
| `BLOCK` | `suspended` |

For supplier-facing operations:

| Compliance state | Read operations | Protected writes |
|---|---|---|
| `cleared` | Allowed, subject to authorization | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization | Blocked |
| `suspended` | Blocked | Blocked |

Standard denial messages include:

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

Authentication, role authorization, compliance access, and resource ownership are separate checks. Passing one check does not grant unrestricted access.

## 6.6 MinIO document authorization

Invoice and onboarding document downloads require authorization before a presigned URL is generated.

```text
Authenticated request
        ↓
Role and compliance checks
        ↓
Supplier ownership check
        ↓
Document and object validation
        ↓
Generate presigned URL
        ↓
Return URL to authorized caller
```

A supplier cannot access another supplier's document merely by knowing its document ID, invoice number, supplier ID, or object reference. A suspended supplier must be rejected before a new presigned URL is generated through the protected download flow.

## 6.7 GraphQL authorization

GraphQL authorization is enforced inside the relevant resolver and shared GraphQL access checks, not only at the `/graphql` endpoint.

For supplier users:

- Collection resolvers filter records to the authenticated supplier.
- Resource resolvers check ownership before exposing protected data.
- Protected mutations check compliance write access before modifying data.
- Supplier filtering is applied before cursor pagination for the relevant collections.

The relevant collection operations include:

```text
purchaseOrders
invoices
documents
```

The `acknowledgePurchaseOrder` mutation checks the applicable compliance access and supplier ownership before changing the PO state.

Approved-PO GraphQL access must also enforce supplier scoping for records backed by `po_mirror`.

## 6.8 Role-based authorization

The Supplier Portal uses role-based authorization through helpers such as:

```python
require_roles(...)
```

Important roles include:

```text
ceo
vp_operations
procurement_manager
logistics_manager
compliance_officer
warehouse_manager
analyst
supplier
```

Examples of role-restricted operations:

| Operation | Required role |
|---|---|
| Purchase Order creation and state transitions | `procurement_manager` |
| Bulk PO sending | `procurement_manager` |
| Invoice adjustment | `compliance_officer` |
| Three-way-match dispute resolution | `compliance_officer` |
| Goods Receipt creation | `warehouse_manager` |
| Supplier contract creation, update, activation, and renewal | `procurement_manager` |

Supplier-facing operations additionally enforce supplier ownership and applicable Round 14 compliance access.

## 6.9 Round 5 supplier-scoping requirement

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

SUP001 token → SUP001 approved PO → Allowed, if authorized
SUP001 token → SUP002 approved PO → 403 Forbidden
```

The same principle applies to supplier-scoped statistics, scorecards, contracts, onboarding resources, shipments, Goods Receipts, three-way matches, and GraphQL resources.

Round 14 adds compliance restrictions, and Round 15 adds persisted approved-PO access and acknowledgement. Neither replaces the existing authentication, role-authorization, or supplier-scoping model.
# 7. Purchase Order Management

The Supplier Portal supports legacy Purchase Order (PO) operations and the Round 15 Inventory-approved PO integration. These are separate flows with different data sources and lifecycle rules.

## 7.1 Legacy PO Operations

Legacy PO functionality includes creation, retrieval, updates, cancellation, acknowledgement, state transitions, event history, bulk sending, and delivery tracking.

PO creation is restricted to `procurement_manager`:

```http
POST /api/v1/purchase-orders
```

Before creation, the service validates the supplier, onboarding status, PO number, line items, quantities, prices, totals, and duplicate PO numbers.

The legacy lifecycle is:

```text
draft → sent → acknowledged → fulfilled
  └──────────────┴──────────────→ cancelled
```

| Current state | Allowed next states |
|---|---|
| `draft` | `sent`, `cancelled` |
| `sent` | `acknowledged`, `cancelled` |
| `acknowledged` | `fulfilled`, `cancelled` |
| `fulfilled` | None |
| `cancelled` | None |

Invalid transitions are rejected. Transition history records the actor, previous state, new state, and timestamp. Historical events are stored separately from the PO record.

## 7.2 Legacy PO REST Endpoints

| Operation | Endpoint | Authorization |
|---|---|---|
| Create | `POST /api/v1/purchase-orders` | `procurement_manager` |
| List | `GET /api/v1/purchase-orders` | Authenticated and authorized |
| Retrieve | `GET /api/v1/purchase-orders/{po_number}` | Authenticated and authorized |
| Update | `PUT /api/v1/purchase-orders/{po_number}` | Role and ownership checks |
| Delete | `DELETE /api/v1/purchase-orders/{po_number}` | Role and ownership checks |
| Acknowledge | `POST /api/v1/purchase-orders/{po_number}/acknowledge` | Supplier ownership and write-access checks |
| Transition | `POST /api/v1/purchase-orders/{po_number}/transition` | `procurement_manager` |
| Bulk send | `POST /api/v1/purchase-orders/bulk-send` | `procurement_manager` |
| Event history | `GET /api/v1/purchase-orders/{po_number}/events` | Role, ownership, and compliance checks |

Bulk sending processes each PO independently and reports individual successes and failures.

## 7.3 Round 15: Inventory-Approved POs

The Round 15 integration consumes `inventory.po.approved` events and persists approved PO data in the Supplier Portal's `po_mirror` table.

```text
Inventory
   │ inventory.po.approved
   ▼
Dedicated Supplier Portal consumer
   │
   ├── Validate event
   ├── Handle duplicates and failures
   └── Persist PO mirror
          │
          ▼
   Supplier-scoped REST / GraphQL
          │
          ▼
   Supplier acknowledges PO
          │
          ▼
   Update acknowledgement state
          │
          ▼
   Persist acknowledgement outbox event
```

The implementation includes:

- A dedicated consumer group.
- Persistent `po_mirror` records.
- Duplicate-event handling and retry/DLQ behavior.
- Supplier-scoped REST and GraphQL access.
- PO acknowledgement through the acknowledgement service.
- Transactional persistence of acknowledgement data and its outbox event.
- Automated consumer, API, service, and GraphQL tests.

The Inventory event contract must be checked against the producer's actual example and schema. Passing local tests alone does not establish producer-contract compatibility.

**Outbox note:** Persisting an acknowledgement in the outbox does not, by itself, prove that the event has been published to Kafka. Document publication as implemented only if the corresponding publisher is present and verified.

The mirrored Inventory-approved PO flow is separate from the legacy PO lifecycle described in Section 7.1. Refer to the implemented route and schema definitions for the exact API paths and event fields.

## 7.4 PO and P2P Relationship

The broader procure-to-pay workflow is:

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

The legacy PO lifecycle tracks PO status. The P2P workflow tracks transaction progression, including receipt, invoicing, matching, and payment approval.

## 7.5 Delivery Tracking

Delivery performance uses the expected delivery date and applicable Goods Receipt records. For fulfilled POs, the actual delivery date is derived from the relevant receipt date rather than the current system date.

| PO condition | Treatment |
|---|---|
| Fulfilled | Eligible |
| Unfulfilled and past due | Eligible and counted as late |
| Unfulfilled and not yet due | Excluded |
| Cancelled | Excluded |
| No applicable expected delivery date | Excluded |

These eligibility rules should be consistent across supplier statistics, scorecards, and monthly delivery trends.

---

# 8. Invoice Management

Invoices are associated with suppliers and Purchase Orders. Invoice processing has its own lifecycle, separate from both the legacy PO lifecycle and the broader P2P workflow.

## 8.1 Invoice Data and Lifecycle

Invoice records include the invoice number, supplier, line items, amount, invoice date, status, dispute or adjustment information, document reference, and history.

The invoice lookup key is `(supplier_id, invoice_number)`.

| Current status | Allowed next statuses |
|---|---|
| `submitted` | `approved`, `disputed`, `rejected` |
| `disputed` | `approved`, `adjusted`, `rejected` |
| `adjusted` | `approved`, `rejected` |
| `approved` | None |
| `rejected` | None |

The service validates transitions and rejects invalid state changes.

## 8.2 Invoice REST Endpoints

| Operation | Endpoint |
|---|---|
| Create | `POST /api/v1/invoices` |
| List | `GET /api/v1/invoices` |
| Retrieve | `GET /api/v1/invoices/{supplier_id}/{invoice_number}` |
| Upload PDF | `POST /api/v1/invoices/{supplier_id}/{invoice_number}/document` |
| Download PDF | `GET /api/v1/invoices/{supplier_id}/{invoice_number}/document` |
| Adjust invoice | `POST /api/v1/invoices/{supplier_id}/{invoice_number}/adjust` |
| Transition invoice | `POST /api/v1/invoices/{supplier_id}/{invoice_number}/transition` |

All protected endpoints enforce authentication and their applicable role, supplier ownership, and compliance checks. Invoice adjustment is restricted to `compliance_officer` and requires the invoice to be disputed.

## 8.3 Validation and Three-Way Matching

Invoice creation validates supplier and PO consistency, invoice uniqueness, item codes, positive quantities, remaining PO quantities, and calculated totals.

The legacy PO must be in an eligible state, such as `acknowledged` or `fulfilled`. The P2P invoice transition separately requires the appropriate goods-received state.

The three-way match compares PO, receipt, and invoice information. The configured price tolerance is **5%**.

```text
Invoice validation
       ↓
Three-way match
       ├── Within tolerance → Matched
       └── Outside tolerance → Discrepancy
```

Invoice creation and discrepancy resolution are separate operations. Rejected invoices do not consume PO quantities.

## 8.4 Disputes and Resolution Suggestions

Disputes require a reason and retain relevant history, including actor and timestamp information. Historical dispute information remains available after subsequent adjustment or approval.

The resolution-suggestion endpoint is:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

It is restricted to `compliance_officer`. Suggestions are based on classified historical resolution patterns and are advisory only. They do not automatically adjust or approve invoices or resolve matches.

---

# 9. Document Management

The Supplier Portal uses MinIO, an S3-compatible object store, for invoice PDFs and supplier onboarding documents. The application manages authorization and object references; MinIO stores the document binaries.

## 9.1 Configuration

Relevant settings include:

```text
MINIO_ENDPOINT
MINIO_ACCESS_KEY
MINIO_SECRET_KEY
MINIO_BUCKET
MINIO_SECURE
MINIO_PRESIGNED_EXPIRY_SECONDS
```

Typical local values are:

```text
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_BUCKET=supplier-documents
MINIO_SECURE=false
MINIO_PRESIGNED_EXPIRY_SECONDS=300
```

Use environment variables for credentials. Never commit real secrets.

## 9.2 Upload and Download Security

Invoice PDF uploads validate the declared content type, PDF signature, and file size.

| Validation | Requirement |
|---|---|
| Content type | `application/pdf` |
| Signature | Starts with `%PDF-` |
| Maximum size | 10 MB |

Downloads use short-lived presigned URLs. Before generating a URL, the application checks authentication, authorization, supplier ownership, compliance access, and object availability.

For supplier users:

| Compliance state | Reads and downloads | Protected writes |
|---|---|---|
| `cleared` | Allowed, subject to authorization | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization | Blocked |
| `suspended` | Blocked | Blocked |

A document ID or MinIO object key does not grant access. Suspended suppliers must be rejected before new presigned URLs are generated.

## 9.3 Error Handling and Tests

Document endpoints distinguish authorization failures, missing resources, and storage failures. Exact HTTP responses depend on the endpoint's exception handling.

Run relevant tests from `services/supplier-portal`:

```powershell
python -m pytest tests/test_document_storage_service.py -q
python -m pytest tests/test_supplier_document_download.py -q
python -m pytest tests/integration/test_minio_document_storage.py -q
```

The MinIO integration test requires a configured, running MinIO instance. Unit tests may mock the storage client; integration tests verify actual object-storage behavior.

---

# 10. Supplier Statistics

Supplier statistics are available through:

```http
GET /api/v1/suppliers/{supplier_id}/stats
```

The endpoint returns supplier-level metrics, including PO count, on-time delivery percentage, and average invoice cycle time.

Supplier users can access only their own supplier data. The service applies the existing ownership checks and Round 14 compliance access rules.

| Compliance state | Statistics access |
|---|---|
| `cleared` | Allowed, subject to ownership |
| `needs_review` | Allowed, subject to ownership |
| `suspended` | Blocked |

A missing supplier returns `404 Not Found` when the endpoint cannot identify the requested supplier in its relevant data.

## 10.1 Delivery Metrics

The PO count includes applicable PO states, including draft, sent, acknowledged, fulfilled, and cancelled.

Delivery performance uses the same eligibility rules as the scorecard:

- Fulfilled POs are eligible.
- Past-due, unfulfilled POs are eligible and count as late.
- Future-due, unfulfilled POs are excluded.
- Cancelled POs and POs without an applicable expected delivery date are excluded.

For fulfilled POs, actual delivery is based on the applicable Goods Receipt date. The calculation must not substitute the current date for the receipt date.

```text
On-time percentage =
    On-time eligible POs / Eligible POs × 100
```

When no POs are eligible, the service follows its implemented zero-eligible-record behavior.

## 10.2 Invoice Cycle Time

Invoice cycle time is based on the difference between the invoice date and the associated PO creation date.

PO references can come from invoice line items (`invoice.items[].po_number`) or the supported legacy top-level PO reference. Invalid dates and negative cycle times are excluded according to the implementation.

The GraphQL API exposes PO, invoice, and document operations; supplier statistics are available through REST.

---

# 11. Supplier Performance Scorecard

The Supplier Performance Scorecard provides supplier-level analytics derived from Purchase Orders, Goods Receipts, invoices, and dispute history.

**Endpoint**

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

Supplier users can access only their own scorecard. Existing role-based authorization applies to internal users.

## 11.1 Metrics

The scorecard includes:

- On-time delivery and PO fulfillment metrics.
- Invoice accuracy and invoice status metrics.
- Dispute rate and dispute performance.
- Overall score, rating, and performance status.
- Monthly performance trends.

Round 14 compliance access rules apply:

| Compliance state | Scorecard access |
|---|---|
| `cleared` | Allowed, subject to authorization |
| `needs_review` | Allowed, subject to authorization |
| `suspended` | Blocked |

## 11.2 Calculation Rules

Delivery metrics use the same eligibility rules as Supplier Statistics. Actual delivery dates come from applicable Goods Receipt records.

Invoice accuracy, dispute rate, and dispute performance are calculated from invoice history. An invoice without recorded dispute information may be treated as accurate by the implemented calculation; this does not independently verify invoice correctness.

Historical dispute information remains relevant after an invoice is adjusted or approved.

The documented overall-score formula is:

```text
overall score =
    (on-time delivery × 0.40)
  + (invoice accuracy × 0.40)
  + (dispute performance × 0.20)
```

**Verify these weights and the rating thresholds against the current scorecard service before treating them as confirmed production rules.**

## 11.3 Monthly Trends and Supplier Identification

Monthly trends are grouped by PO creation month and use the shared delivery-eligibility and receipt-date rules.

Where supported by the implementation, supplier identification can use relevant invoice data when a supplier has no POs. This avoids assuming that a supplier must have an existing PO to appear in scorecard results.

The scorecard preserves both supplier ownership checks and compliance enforcement:

```text
Authentication
      ↓
Supplier identity and role
      ↓
Compliance access
      ↓
Supplier ownership
      ↓
Scorecard results
```
# 12. Procure-to-Pay Lifecycle

The Supplier Portal supports the Procure-to-Pay (P2P) workflow from Purchase Order acknowledgement through shipment, Goods Receipt, invoicing, three-way matching, and payment approval.

```text
Acknowledged PO
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

P2P processing state, the legacy Purchase Order lifecycle, and supplier compliance access are separate concerns. Compliance enforcement controls access; it does not make an invalid business-state transition valid.

## 12.1 P2P State Machine

The P2P processing states are:

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

The separate legacy Purchase Order lifecycle uses statuses such as `draft`, `sent`, `acknowledged`, `fulfilled`, and `cancelled`.

Each transition must satisfy the applicable business rules. A discrepancy must be reviewed and resolved before payment approval is permitted.

## 12.2 Shipment and Goods Receipt

Shipment processing advances an acknowledged transaction to `shipped`. Goods Receipt records the goods received against a Purchase Order and advances eligible transactions to `received`.

Receipt information can include:

- `receipt_id`, `po_number`, and `supplier_id`
- `receipt_date`, warehouse, and receiving details
- Received items, quantities, and receipt status

Validation includes PO existence, supplier ownership, valid item codes, positive quantities, duplicate-item detection, and applicable quantity limits.

### Partial Goods Receipt

Partial receiving is supported. For example, a PO for 100 units can have a receipt for 40 units. A partial receipt may include only the items received; included quantities must satisfy the applicable PO quantity rules.

The recorded `receipt_date` is used for actual delivery-date calculations where supported by the supplier performance implementation.

## 12.3 Invoice Integration

P2P invoicing requires the transaction to reach `received` before progressing to `invoiced`. Duplicate or invalid invoice submissions must not advance the P2P state.

The invoice lifecycle is separate from the P2P state machine:

```text
submitted
    ├── approved
    ├── rejected
    └── disputed
           ↓
        adjusted
```

Invoice submission and transitions remain subject to endpoint authorization, supplier ownership, compliance access, and invoice business validation.

## 12.4 Three-Way Match and Payment Approval

Three-way matching compares the Purchase Order, Goods Receipt, and invoice, including applicable item codes, quantities, and prices.

```text
Purchase Order
      +
Goods Receipt
      +
Invoice
      ↓
Three-Way Match
   ├── Matched → Eligible for the next permitted step
   └── Discrepancy → Human review and resolution
```

A successful match does not bypass payment-approval rules. A discrepancy must not automatically progress to payment approval.

## 12.5 Supplier Compliance Enforcement

Round 14 adds event-driven compliance access enforcement to protected supplier-facing operations.

| Supplier compliance state | Permitted reads | Protected supplier writes |
|---|---|---|
| `cleared` | Allowed, subject to authorization | Allowed when business rules permit |
| `needs_review` | Allowed, subject to authorization | Restricted |
| `suspended` | Denied for protected supplier-facing resources | Denied |

Typical protected writes include PO acknowledgement, shipment/P2P updates, and invoice submission. Exact enforcement depends on the endpoint and its implemented authorization checks. Internal users remain subject to their existing role permissions.

The enforcement sequence is:

```text
Authentication
      ↓
Supplier identity and ownership
      ↓
Compliance access check
      ↓
Role and business validation
      ↓
Permitted operation
```

A supplier's onboarding status and compliance access state are independent. An onboarding-active supplier can subsequently become `needs_review` or `suspended` without its onboarding status being overwritten.

## 12.6 Supplier Activation Requirement

Supplier activation is separate from event-driven compliance enforcement. Before activation, the Supplier Portal calls the Compliance Service's internal check. Only a usable `CLEAR` decision with `cleared: true` permits activation.

```text
Approved supplier
      ↓
Compliance activation check
      ├── CLEAR + cleared=true → Active
      └── BLOCK / REVIEW / unavailable → Not activated
```

The later Kafka status-change consumer updates supplier compliance access. It does not replace the onboarding lifecycle or the P2P state machine.

---

# 13. Three-Way Match

Three-way matching evaluates Purchase Order, Goods Receipt, and invoice data to identify quantity or price discrepancies before payment approval.

## 13.1 Quantity Matching

The matching process compares ordered, received, and invoiced quantities.

Example:

```text
PO quantity       = 100
Received quantity = 90
Invoice quantity  = 100
```

This may produce a quantity discrepancy requiring review. Partial Goods Receipt allows the received quantity to be evaluated without requiring the entire PO to have arrived.

## 13.2 Price Matching and Tolerance

The configured price tolerance is:

```text
PRICE_TOLERANCE_PERCENT = 5.0
```

The tolerance is inclusive. For a PO unit price of `100`:

| Invoice unit price | Result |
|---:|---|
| `95` | Within tolerance |
| `100` | Within tolerance |
| `105` | Within tolerance |
| `106` | Outside tolerance |

An invoice unit price of `120` against a PO unit price of `100` is outside the tolerance and can be flagged for review.

The tolerance is a matching rule, not an invoice-creation rejection rule.

## 13.3 Match Results and Discrepancy Handling

The match result reflects the implemented checks for relevant PO, receipt, and invoice data.

```text
Three-Way Match
      ├── Matched → Continue under payment-approval rules
      └── Discrepancy → Review and resolution
```

Quantity and price discrepancies are handled through the applicable review process. Matching does not automatically authorize payment when a discrepancy exists.

## 13.4 Historical Resolution Suggestions

The Supplier Portal provides advisory suggestions based on historical resolved three-way-match disputes.

**Endpoint**

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

**Authorization:** `compliance_officer`

Implemented historical patterns include:

| Discrepancy | Suggested action |
|---|---|
| Price mismatch | `correct_invoice` |
| Quantity mismatch | `credit_note` |

The service uses eligible historical resolved disputes to suggest a possible resolution. Unresolved disputes are not historical evidence, and the current unresolved dispute must not be used as its own example.

Suggestions are advisory only. This endpoint does not automatically modify an invoice, match result, P2P state, or payment approval.

## 13.5 Integration and Review Requirements

Three-way matching operates within the P2P workflow after receipt and invoice processing. The P2P state machine controls permitted transitions; the matching logic evaluates discrepancies; compliance enforcement determines whether a supplier may perform protected operations.

A discrepancy requires the applicable authorized review and resolution before any permitted subsequent transition. A match alone does not bypass business rules or payment authorization.
# 14. Supplier Onboarding

The Supplier Portal manages supplier registration, document collection, verification, approval, and activation.

```text
Registration
     ↓
Document Collection
     ↓
Verification
     ↓
Approval
     ↓
Compliance Check
     ↓
Active
```

Approval does not automatically activate a supplier. Activation requires a successful Compliance Service clearance.

## 14.1 Registration and Documents

Registration creates the supplier onboarding record. Document collection and verification are separate stages and do not independently activate the supplier.

Onboarding documents are stored through the MinIO-backed storage layer. Supported formats and validation rules are defined by the onboarding document validator; the configured maximum file size is 10 MB.

Validation includes the applicable file type, extension, content, size, and supplier authorization checks. Downloads must verify authorization before generating a short-lived MinIO presigned URL.

## 14.2 Verification, Approval, and Activation

The current verification workflow uses mock verification logic for development; it should not be described as an external verification-provider integration.

After verification and approval, the Supplier Portal calls the Compliance Service:

```http
POST /api/v1/compliance/internal-check
```

Local development configuration:

```text
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

The request includes supplier information such as supplier ID, name, and country, together with the configured caller-service header.

## 14.3 Compliance Decisions

| Compliance result | Activation behavior |
|---|---|
| `CLEAR` with `cleared: true` | Activation permitted |
| `BLOCK` | Activation rejected |
| `REVIEW` | Activation rejected |
| Dependency unavailable | Activation fails closed |
| Unusable or unsuccessful response | Activation rejected |

The implemented error mapping distinguishes blocked decisions, unavailable dependencies, and other Compliance Service errors. Verify the active client and route code before relying on specific HTTP status codes.

If clearance cannot be established, the supplier remains approved rather than becoming active.

## 14.4 Activation and Event-Driven Access

The synchronous activation check and Round 14 Kafka consumer serve different purposes:

- **Activation check:** determines whether an approved supplier can become active.
- **Event-driven compliance:** updates supplier access after subsequent compliance status changes.

Onboarding status and compliance access state remain separate. An active supplier can later become `needs_review` or `suspended` without overwriting its onboarding status.

---

# 15. Supplier Contract Lifecycle

The Supplier Portal provides REST-based contract management for contract terms, activation, expiry tracking, renewal, and history.

Supplier contracts are not part of the documented Round 13 GraphQL scope.

## 15.1 Contract Information and Lifecycle

Contract information can include supplier ID, contract number, title, dates, payment and delivery terms, pricing terms, renewal settings, and status.

The documented lifecycle is:

```text
draft → active → renewed / expired
```

Contract status is separate from supplier compliance access. For example, a contract's status does not automatically change when its supplier is suspended.

## 15.2 Contract API

The documented endpoints are:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/supplier-contracts` | Create a contract |
| `GET` | `/api/v1/supplier-contracts` | List contracts |
| `GET` | `/api/v1/supplier-contracts/expiring` | List expiring contracts |
| `GET` | `/api/v1/supplier-contracts/{contract_id}` | Retrieve a contract |
| `PUT` | `/api/v1/supplier-contracts/{contract_id}` | Update contract terms |
| `POST` | `/api/v1/supplier-contracts/{contract_id}/activate` | Activate a draft |
| `POST` | `/api/v1/supplier-contracts/{contract_id}/renew` | Renew a contract |
| `GET` | `/api/v1/supplier-contracts/{contract_id}/history` | Retrieve contract history |

Contract creation, updates, activation, and renewal are documented as procurement-controlled operations. Verify each route's current authorization dependencies before treating this table as the definitive permission specification.

## 15.3 Validation and History

Contract operations validate the applicable supplier, contract identity, dates, and lifecycle state. History records supported contract actions and changes, including actor and timestamp information where implemented.

The renewal operation reuses the existing contract record in the current design; it does not imply separate versioned contract records.

## 15.4 Storage and Limitations

The current contract implementation uses in-memory dictionaries for contract records and history. Therefore, this data is not durable across a full application restart.

The `auto_renew` field represents configuration; it does not mean that an automatic renewal scheduler is running. Renewal remains an explicit operation unless a scheduler is implemented separately.

Supplier-facing access, where supported, must enforce supplier ownership and compliance policy. Internal procurement operations remain subject to role authorization.

---

# 16. API Reference

The Supplier Portal exposes REST APIs under `/api/v1` and a Strawberry GraphQL endpoint at `/graphql`. The root health/message endpoint `/` is outside the `/api/v1` prefix.

Protected requests use the centralized Platform Service authentication mechanism. Authorization can include role checks, supplier ownership, compliance access, and business-state validation.

## 16.1 Root Endpoint

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Service health/message response |

## 16.2 Purchase Order APIs

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/purchase-orders` | Create a Purchase Order |
| `GET` | `/api/v1/purchase-orders` | List Purchase Orders |
| `GET` | `/api/v1/purchase-orders/{po_number}` | Retrieve a Purchase Order |
| `PUT` | `/api/v1/purchase-orders/{po_number}` | Update a Purchase Order |
| `DELETE` | `/api/v1/purchase-orders/{po_number}` | Delete a Purchase Order |
| `POST` | `/api/v1/purchase-orders/{po_number}/acknowledge` | Acknowledge a Purchase Order |
| `POST` | `/api/v1/purchase-orders/{po_number}/transition` | Transition a Purchase Order |
| `GET` | `/api/v1/purchase-orders/{po_number}/events` | Retrieve PO events |
| `POST` | `/api/v1/purchase-orders/bulk-send` | Send Purchase Orders in bulk |

Authorization varies by operation. Supplier requests must be scoped to the authenticated supplier; procurement operations require the appropriate role.

### Inventory-approved Purchase Orders — R15

Round 15 introduces a separate consumer flow for Inventory-approved PO events:

```text
Inventory
    ↓
inventory.po.approved
    ↓
Supplier Portal consumer
    ↓
po_mirror persistence
    ↓
Supplier-scoped PO reads
    ↓
Supplier acknowledgement
    ↓
Acknowledgement outbox
```

The consumer is expected to process events idempotently, handle failures using the configured retry/DLQ behavior, and persist the PO mirror before committing the Kafka offset.

The approved-PO REST paths and GraphQL fields must match the active route and schema implementation. Do not assume that the legacy PO endpoints and the R15 mirror endpoints represent the same storage or lifecycle.

The acknowledgement outbox records acknowledgement work transactionally where implemented. Outbox persistence alone does not prove that an event has been published to Kafka; publication requires a configured publisher and verified delivery behavior.

## 16.3 Invoice APIs

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/invoices` | List invoices |
| `POST` | `/api/v1/invoices` | Create an invoice |
| `GET` | `/api/v1/invoices/{supplier_id}/{invoice_number}` | Retrieve an invoice |
| `POST` | `/api/v1/invoices/{supplier_id}/{invoice_number}/transition` | Transition an invoice |
| `POST` | `/api/v1/invoices/{supplier_id}/{invoice_number}/adjust` | Adjust a disputed invoice |
| `POST` | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Upload an invoice PDF |
| `GET` | `/api/v1/invoices/{supplier_id}/{invoice_number}/document` | Retrieve an invoice document URL |

Invoice identity is scoped by `(supplier_id, invoice_number)`. Supplier access must verify ownership. Invoice operations also apply the configured role, compliance, and business rules.

## 16.4 Document APIs

Invoice documents are PDF-only, with a maximum size of 10 MB. Onboarding documents support the formats allowed by the onboarding validator, also subject to its size and content checks.

Document downloads return short-lived MinIO presigned URLs rather than streaming the object through the Supplier Portal. Authorization and compliance checks must run before generating a URL.

## 16.5 Supplier Onboarding APIs

Onboarding covers registration, document collection, verification, approval, activation, and related document access. Exact route paths should be taken from the active onboarding router.

Activation calls the Compliance Service's internal check. The synchronous check is separate from Round 14's Kafka status-change consumer.

## 16.6 GraphQL API

The GraphQL endpoint is:

```http
POST /graphql
```

The documented GraphQL scope includes Purchase Orders, invoices, supplier documents, cursor pagination, and PO acknowledgement. The exact field names and argument types are defined by the active Strawberry schema.

GraphQL resolvers must enforce authentication, compliance access, role authorization, and supplier ownership. A supplier must not bypass REST restrictions by changing GraphQL arguments or pagination cursors.

R15 approved-PO query support should be documented using the actual schema fields and resolver implementation. Do not assume all REST resources are also available through GraphQL.

## 16.7 Procure-to-Pay and Three-Way Match

The P2P workflow covers shipment, Goods Receipt, invoicing, three-way matching, discrepancy review, and payment approval.

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

The configured price tolerance is 5%, inclusive. Quantity and price discrepancies require the applicable review process; a discrepancy must not automatically approve payment.

The historical resolution-suggestion endpoint is:

```http
GET /api/v1/three-way-matches/{supplier_id}/{invoice_number}/resolution-suggestion
```

Authorization: `compliance_officer`.

The suggestion is advisory and must not automatically modify invoice, matching, or payment state.

## 16.8 Supplier Statistics and Scorecard

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/v1/suppliers/{supplier_id}/stats` | Supplier operational statistics |
| `GET` | `/api/v1/suppliers/{supplier_id}/scorecard` | Supplier performance scorecard |

Supplier users must only access their own supplier-scoped information. The compliance policy and normal authorization rules continue to apply.

## 16.9 Supplier Contract APIs

Contract endpoints are documented in [Section 15](#15-supplier-contract-lifecycle). Contract management remains REST-based unless contract operations are explicitly added to the GraphQL schema.

## 16.10 API Security Summary

Protected API access combines:

```text
Authentication
      +
Role authorization
      +
Supplier ownership
      +
Compliance access enforcement
      +
Business-state validation
```

A valid token alone does not authorize access to another supplier's resources. `needs_review` restricts protected supplier writes, while `suspended` denies protected supplier-facing access, subject to the implemented enforcement rules and internal-role policies.

---

# 17. HTTP Response Codes

The Supplier Portal uses HTTP status codes to distinguish successful operations, authentication and authorization failures, invalid requests, business conflicts, and dependency errors.

| Status | Meaning |
|---|---|
| `200 OK` | Request completed successfully |
| `201 Created` | Resource created successfully |
| `400 Bad Request` | Request or business validation failed |
| `401 Unauthorized` | Authentication is missing or invalid |
| `403 Forbidden` | Authorization, supplier ownership, or compliance policy denies access |
| `404 Not Found` | Requested resource was not found |
| `409 Conflict` | Conflicting state, duplicate resource, or rejected activation decision |
| `422 Unprocessable Entity` | Request schema validation failed |
| `502 Bad Gateway` | Downstream service returned an unusable response |
| `503 Service Unavailable` | Required dependency is unavailable |

Examples include:

| Condition | Typical response |
|---|---|
| Missing or invalid token | `401` |
| Supplier requests another supplier's resource | `403` |
| Suspended supplier requests protected access | `403` |
| Supplier under review attempts a protected write | `403` |
| Resource does not exist | `404` |
| Invalid business-state transition or duplicate operation | `409` or the endpoint's documented validation response |
| Invalid request schema | `422` |
| Compliance dependency unavailable during activation | `503` |
| Compliance response unusable | `502` |

The exact response depends on the endpoint's exception handling and validation rules. Do not assume every business validation error returns the same status code.

Supplier activation follows a fail-closed rule: without a usable clearance decision, the supplier must not be activated.

Kafka consumer failures use retry, offset-commit, and dead-letter handling rather than HTTP response codes.

# 18. Configuration

The Supplier Portal uses environment-based configuration. Use `.env.example` as the starting point for local settings and `app/core/config.py` as the source of truth for supported setting names.

```powershell
Copy-Item .env.example .env
```

Do not commit credentials or environment-specific secrets in `.env`.

## 18.1 Platform Authentication

The Supplier Portal delegates token verification to the Platform Service; it does not independently decode authentication tokens.

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

Verification endpoint:

```http
POST /api/v1/auth/verify
```

The returned identity and role information is used for authorization and supplier scoping. R14/R15 Supplier Portal changes do not require changes to `services/platform`.

## 18.2 Compliance Service

```env
COMPLIANCE_SERVICE_URL=http://127.0.0.1:8003
```

Supplier activation calls:

```http
POST /api/v1/compliance/internal-check
```

The request identifies the caller using `X-Caller-Service: supplier-portal`.

A valid `CLEAR` decision with the required positive clearance field permits activation. `BLOCK`, `REVIEW`, timeouts, connection failures, or unusable responses must not activate the supplier. This synchronous activation check is separate from R14 asynchronous compliance-status processing.

## 18.3 Kafka

Kafka supports two separate workflows:

| Workflow | Purpose |
|---|---|
| R14 compliance events | Consume `compliance.supplier.status_changed` and update compliance access state |
| R15 approved POs | Consume `inventory.po.approved`, persist approved POs in `po_mirror`, and support supplier acknowledgement |

The R14 status topic and DLQ are:

```text
compliance.supplier.status_changed
compliance.supplier.status_changed.dlq
```

The R14 consumer group documented for the current setup is `supplier-portal-service`. Confirm the effective values in `app/core/config.py` and `.env.example` before changing local settings.

The R15 approved-PO consumer has its own processing configuration. Do not assume it uses the R14 consumer group or DLQ.

Consumer processing must validate events, handle duplicates, persist successful changes before committing offsets, and route eligible failures to the configured DLQ. Unexpected processing failures must not be silently acknowledged.

## 18.4 MinIO Document Storage

MinIO provides S3-compatible storage for invoice and supplier-onboarding documents. Configure its endpoint, credentials, bucket, and presigned-URL expiry using the setting names supported by the project.

The document flow is:

```text
Upload/download request
        ↓
Authentication and authorization
        ↓
Supplier ownership and compliance checks
        ↓
MinIO object operation
        ↓
Document reference or presigned URL
```

Authorize downloads before generating a presigned URL. Cross-supplier access and suspended-supplier access must be rejected. Do not silently substitute local filesystem storage for MinIO.

## 18.5 Three-Way Match Tolerance

The configured price tolerance is defined in `app/core/config.py`:

```python
PRICE_TOLERANCE_PERCENT = 5.0
```

For a PO unit price of `100`, the inclusive range is `95`–`105`; `106` is outside the price tolerance. This tolerance is used by matching logic, not as a blanket invoice-creation rejection rule.

## 18.6 Supplier Contracts

The contract feature supports contract terms, lifecycle status, renewal tracking, and history as implemented by the service. The current implementation stores contract records and history in application memory, so this data is not durable across application restarts.

The `auto_renew` field does not itself provide scheduled automatic renewal.

## 18.7 GraphQL

The Strawberry GraphQL API is mounted at:

```text
http://127.0.0.1:8000/graphql
```

GraphQL operations reuse the Supplier Portal's authenticated request context and enforce applicable role permissions, supplier scope, and compliance access rules.

---

# 19. Installation

These commands assume Windows PowerShell and Python are installed.

## Step 1 — Open the service directory

```powershell
cd C:\Users\Lenovo\Desktop\EAICSC\eaicsp-platform\services\supplier-portal
```

## Step 2 — Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If script execution is blocked, follow your organization's approved PowerShell execution policy.

## Step 3 — Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Step 4 — Configure the environment

```powershell
Copy-Item .env.example .env
```

Set the required Platform, Compliance, database, Kafka, and MinIO values using the variable names defined by the project.

## Step 5 — Start required dependencies

Start the dependencies required for the feature being tested:

| Dependency | Purpose |
|---|---|
| Platform Service | Token verification |
| Compliance Service | Supplier activation clearance |
| Database | Persistent application data, including approved PO mirror/outbox data |
| MinIO | Document storage |
| Kafka | R14 compliance events and R15 approved-PO events |

Some isolated tests use mocks and do not require all external services. Integration tests may require the corresponding services to be running.

---

# 20. Running the Services

Start each dependency from its own project directory or configured development environment. Confirm the actual entry point and Compose service names before running service-specific commands.

## 20.1 Start the Supplier Portal

From the Supplier Portal directory:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Local endpoints:

- REST API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- GraphQL: `http://127.0.0.1:8000/graphql`

Check the root endpoint:

```http
GET /
```

## 20.2 Integration Overview

```text
Client
  │
  ▼
Supplier Portal (:8000)
  ├── Platform Service (:8005)
  │     └── Token verification
  │
  ├── Compliance Service (:8003)
  │     └── Synchronous activation check
  │
  ├── Database
  │     └── Approved PO mirror and acknowledgement outbox
  │
  ├── MinIO
  │     └── Document objects
  │
  └── Apache Kafka (:9092)
        ├── R14 compliance-status consumer
        └── R15 approved-PO consumer
```

The actual database URL, Kafka broker address, topics, consumer groups, MinIO settings, and worker startup behavior depend on the effective configuration.

## 20.3 R14 — Compliance Status Events

The Supplier Portal consumes:

```text
compliance.supplier.status_changed
```

The processing flow validates the event, checks idempotency and event ordering, persists compliance state and audit information, and then handles the Kafka offset according to the processing result.

| Compliance state | Supplier access |
|---|---|
| `CLEAR` | Permitted operations remain available |
| `REVIEW` | Permitted reads remain available; protected supplier writes are restricted |
| `BLOCK` | Supplier-facing access is suspended |

The compliance access state is separate from the onboarding lifecycle status. A supplier can retain its historical onboarding status while its current compliance access is suspended.

## 20.4 R15 — Approved Purchase Orders

The approved-PO flow is separate from R14:

```text
Inventory Service
      │
      │ inventory.po.approved
      ▼
Dedicated R15 consumer
      │
      ▼
Validate event and handle duplicates
      │
      ▼
Persist PO in po_mirror
      │
      ▼
Supplier-scoped REST / GraphQL reads
      │
      ▼
Supplier acknowledgement
      │
      ▼
Acknowledgement outbox
```

The consumer must persist the PO before acknowledging the corresponding Kafka offset. Repeated events must be handled idempotently, and eligible failures must follow the configured retry/DLQ policy.

The acknowledgement outbox records the event for reliable publication. Do not claim that the event was delivered to Kafka unless the outbox publisher and delivery behavior are implemented and verified.

Verify compatibility with the Inventory producer's actual `inventory.po.approved` example and schema; do not infer missing identifiers from unrelated fields.

## 20.5 Documents and Supplier Activation

For document operations, the Supplier Portal authorizes the caller, checks supplier ownership and compliance access, and then interacts with MinIO. It must not issue a new presigned URL for an unauthorized or suspended supplier.

For initial supplier activation, the synchronous Compliance check permits activation only when the required positive `CLEAR` response is received. A technical failure or unusable response must fail closed.

---

# 21. Swagger and API Documentation

FastAPI provides interactive REST documentation while the service is running:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- GraphQL endpoint: `http://127.0.0.1:8000/graphql`

Swagger displays registered REST routes. GraphQL queries and mutations are submitted through `/graphql`.

## 21.1 Authentication and Authorization

Use Swagger's **Authorize** control with a valid bearer token accepted by the configured Platform Service.

```text
Request with bearer token
        ↓
Platform token verification
        ↓
Role and supplier-scope checks
        ↓
Compliance access checks
        ↓
Endpoint operation
```

A valid token does not grant access to every supplier's records. A supplier must not read or modify another supplier's resources.

## 21.2 API Coverage

Inspect the running application's registered routes and schemas for the supported operations, which may include:

- Purchase Orders and supplier acknowledgement
- Invoices and invoice documents
- Shipment and Goods Receipt operations
- Supplier onboarding and activation
- Supplier statistics and scorecards
- Supplier contracts
- Three-way matching and dispute resolution
- Compliance-protected supplier operations

R15 approved-PO endpoints and GraphQL fields should be documented according to their actual implementation. Do not assume every business feature has a corresponding REST endpoint.

## 21.3 Compliance-Protected Operations

| Access state | Supplier reads | Protected supplier writes |
|---|---|---|
| `CLEARED` | Allowed when authorized | Allowed when role and business rules permit |
| `NEEDS REVIEW` | Permitted reads remain available | Restricted |
| `SUSPENDED` | Rejected | Rejected |

Existing internal-user role permissions continue to apply. Compliance enforcement does not replace role-based authorization.

## 21.4 Document Endpoints

Use Swagger to confirm the actual registered document routes and request/response schemas. For invoice documents, the implementation may expose routes such as:

```http
POST /api/v1/invoices/{supplier_id}/{invoice_number}/document
GET  /api/v1/invoices/{supplier_id}/{invoice_number}/document
```

Verify these paths against the running application before relying on them. Downloads must authorize the caller and validate supplier ownership and compliance access before generating a presigned URL.

---

# 22. Automated Testing

Run test commands from the Supplier Portal directory with the project's environment activated.

## 22.1 Run Tests

Run the non-integration suite:

```powershell
python -m pytest -m "not integration" -q
```

Run the complete suite:

```powershell
python -m pytest -q
```

The complete suite may require external services for integration tests. Record the actual results from the current run rather than copying a historical test count.

## 22.2 Key Test Modules

Run a focused module when investigating a particular area:

| Area | Test command |
|---|---|
| Purchase Orders | `python -m pytest tests/test_purchase_order.py -q` |
| GraphQL | `python -m pytest tests/test_graphql.py -q` |
| R14 compliance enforcement | `python -m pytest tests/test_r14_enforcement.py -q` |
| R14 Kafka consumer | `python -m pytest tests/test_kafka_consumer.py -q` |
| Kafka consumer runner | `python -m pytest tests/test_kafka_consumer_runner.py -q` |
| R15 approved PO REST | `python -m pytest tests/test_approved_purchase_orders.py -q` |
| R15 approved PO consumer | `python -m pytest tests/test_inventory_po_approved_consumer.py -q` |
| R15 acknowledgement/outbox | `python -m pytest tests/test_po_acknowledgement_service.py -q` |

Check that a test file exists before running a command. Run MinIO integration tests only when the integration environment is configured.

## 22.3 Required Coverage

The regression suite should cover the implemented behavior for:

- Authentication, role authorization, supplier scoping, and cross-supplier access
- Purchase Order lifecycle, acknowledgement, shipments, and Goods Receipts
- Invoice validation, document operations, and three-way matching
- Supplier onboarding and fail-closed Compliance activation
- MinIO object storage and presigned URL authorization
- R14 event validation, idempotency, event ordering, offset handling, DLQ, and audit history
- R15 approved-PO event validation, duplicate handling, persistence, retry/DLQ, and supplier-scoped reads
- R15 acknowledgement authorization and durable outbox records
- GraphQL queries, pagination, mutation authorization, and compliance enforcement
- Supplier statistics, scorecards, and contract lifecycle where supported

## 22.4 R14 Kafka Processing Expectations

The tests should verify:

```text
Valid event applied and persisted
    → Commit original offset

Invalid event successfully published to DLQ
    → Commit original offset

Unexpected processing failure
    → Do not acknowledge the message prematurely
```

They should also cover duplicate event IDs, out-of-order `occurred_at` values, and compliance access enforcement for supplier-facing REST, GraphQL, and document operations.

## 22.5 R15 Approved PO Expectations

The tests should verify:

- Compatibility with the actual Inventory producer event contract
- Idempotent processing of repeated approved-PO events
- Persistence before offset commit
- Retry/DLQ behavior on eligible failures
- Supplier scoping in REST and GraphQL
- Acknowledgement authorization and valid state transitions
- Durable acknowledgement outbox records

An outbox record alone does not prove successful Kafka delivery; test the publisher separately if one is implemented.

## 22.6 Final Verification

Before committing README or application changes, run:

```powershell
git diff --check
python -m pytest -m "not integration" -q
git status --short
```

Review the README against `app/core/config.py`, `.env.example`, the registered routes, GraphQL schema, and the actual test filenames. Run the full suite when the required integration services are available.
# 23. Business Rules

## 23.1 Purchase Orders and Invoices

- A new Purchase Order (PO) starts in `draft`. The primary lifecycle is `draft → sent → acknowledged → fulfilled`; cancellation and other transitions follow the implemented state machine.
- PO creation requires the appropriate procurement role and an eligible supplier.
- Invoice creation requires a valid PO, matching supplier identity, and a unique `supplier_id + invoice_number` combination.
- In the P2P workflow, invoice submission requires the PO to have reached `received`. Invalid or duplicate submissions must not advance the workflow.
- Invoice lifecycle status and supplier compliance access are separate concerns.

## 23.2 Document Validation and Storage

Invoice documents must satisfy the implemented PDF validation rules, including content type, PDF signature, and a maximum size of 10 MB. Onboarding documents support the configured formats, currently documented as PDF, JPG/JPEG, PNG, DOC, and DOCX, with a maximum size of 10 MB.

Document binaries are stored in MinIO. Protected downloads must authenticate the caller, validate resource ownership and compliance access, locate the object, and only then generate a short-lived presigned URL.

Missing objects and storage dependency failures must be handled separately. Previously issued presigned URLs may remain usable until expiry; immediate revocation must not be assumed.

## 23.3 Procure-to-Pay and Three-Way Matching

The P2P workflow is:

```text
Acknowledged → Shipped → Received → Invoiced
                                      ↓
                              Three-Way Match
                                ↙         ↘
                            Matched    Discrepancy
                                ↓         ↓
                         Payment Approval
                                   Human Review
```

The actual transitions depend on the implemented state machine.

Goods Receipt processing supports partial delivery and validates the PO, supplier, item codes, positive quantities, and quantities against the PO. Duplicate receipt items and items not present on the PO are rejected; a partial receipt may omit PO items.

Three-way matching compares the PO, Goods Receipt, and invoice. The configured inclusive price tolerance is 5%: for a unit price of 100, prices from 95 through 105 are within tolerance. Quantity discrepancies are evaluated separately. Unresolved discrepancies must not bypass required review or payment-approval controls.

**Limitation:** Partial invoice validation does not guarantee a complete repeated-partial-invoice lifecycle for a single PO.

## 23.4 Supplier Onboarding and Compliance

The onboarding lifecycle is:

```text
Registration → Documents → Verification → Approval
             → Compliance Check → Active
```

Activation calls `POST /api/v1/compliance/internal-check` and identifies the caller with `X-Caller-Service: supplier-portal`.

Only a valid `CLEAR` decision with the required positive clearance field permits activation. `BLOCK`, `REVIEW`, timeouts, connection failures, and unusable responses must not activate the supplier.

Initial activation and ongoing compliance events are separate processes. R14 maintains a separate compliance access state:

| Compliance decision | Access state | Supplier-facing policy |
|---|---|---|
| `CLEAR` | `cleared` | Normal access, subject to authorization |
| `REVIEW` | `needs_review` | Permitted reads; protected writes restricted |
| `BLOCK` | `suspended` | Supplier-facing access denied |

A compliance event must not silently rewrite the onboarding lifecycle status or the P2P business state.

## 23.5 Supplier Contracts and Audit History

The documented contract lifecycle includes `draft`, `active`, `renewed`, and `expired`.

Contract operations validate applicable supplier eligibility, unique contract numbers, dates, and allowed transitions. The end date must be later than the start date. Renewal validates the new dates and records renewal history.

Meaningful term changes can create history records containing the supported actor, reason, state, terms, and timestamp information. No-op updates should not create unnecessary history.

Contract records and history currently use in-memory storage. Renewal updates the existing record; immutable contract versioning and scheduled automatic renewal are not implied by the lifecycle or the `auto_renew` field.

## 23.6 Dispute Suggestions and Supplier Analytics

Historical dispute-resolution suggestions are advisory. They must not automatically modify invoices, resolve disputes, change match status, or approve payments.

Supplier scorecards are available through the implemented endpoint, documented as:

```http
GET /api/v1/suppliers/{supplier_id}/scorecard
```

The authenticated supplier must match the requested supplier ID. Scorecard metrics and formulas must remain aligned with the actual service implementation and tests.

The configured score weights are:

```text
On-time delivery     40%
Invoice accuracy     40%
Dispute performance  20%
```

The implemented overall score formula is:

```text
overall score =
    (on-time delivery × 0.40)
  + (invoice accuracy × 0.40)
  + (dispute performance × 0.20)
```

Dispute performance is calculated as `100 - dispute rate` where supported by the implementation. For fulfilled POs, actual delivery uses the applicable Goods Receipt `receipt_date`. Eligibility rules exclude cancelled POs, future-due unfulfilled POs, and records without a usable expected-delivery date; past-due unfulfilled POs count as misses where defined by the service.

## 23.7 GraphQL Rules

The Strawberry GraphQL API must preserve REST-equivalent authentication, role authorization, supplier ownership, compliance access, and business validation.

Implemented operations include PO, invoice, and document queries, cursor pagination, and PO acknowledgement. Collection queries must filter supplier-scoped records before returning results. Unauthorized access and invalid-cursor behavior must match the actual resolver contract.

---

# 24. Security Controls

The Supplier Portal uses layered security:

```text
Platform Authentication
        ↓
Role Authorization
        ↓
Supplier Ownership
        ↓
Compliance Access
        ↓
Input and Business Validation
        ↓
Protected Storage / Business Operation
```

## 24.1 Authentication and Roles

Token verification is delegated to the Platform Service. The Supplier Portal uses the returned identity and role information; it must not introduce an independent, conflicting token-validation mechanism.

Restricted operations—including procurement actions, bulk PO sending, invoice adjustments, and contract management—must enforce their implemented role requirements. Role authorization does not replace supplier ownership checks.

## 24.2 Supplier Isolation — R5

Supplier-scoped access must validate:

```text
Authenticated supplier_id == Resource supplier_id
```

Authenticated suppliers must not access another supplier's POs, invoices, documents, shipments, Goods Receipts, matches, scorecards, onboarding resources, contracts, or supported GraphQL resources.

A supplier without the required supplier identity must not gain supplier-scoped access. Collection endpoints must filter results before returning them to the caller.

## 24.3 Compliance Access — R14

The supplier compliance states are `cleared`, `needs_review`, and `suspended`.

- `cleared`: normal access, subject to existing permissions.
- `needs_review`: permitted reads remain available; protected supplier writes are restricted.
- `suspended`: supplier-facing REST, GraphQL, and protected document operations are denied where the enforcement guard is implemented.

Internal users remain subject to their existing role permissions. Compliance access enforcement complements, rather than replaces, role authorization.

## 24.4 Kafka Reliability and Audit

The R14 consumer processes `compliance.supplier.status_changed` and uses `compliance.supplier.status_changed.dlq` for messages routed to the dead-letter topic.

The consumer implements event validation, idempotency, timestamp ordering, persistence, and explicit offset management. The original offset must not be committed before successful processing or successful DLQ handling, according to the implemented path.

**Event identity caveat:** The current producer contract does not include `supplier_id`. The implementation uses supplier name and country to identify the corresponding supplier. This is a limitation: duplicate supplier names or inconsistent country values can make identification ambiguous. The long-term contract should include a stable supplier ID, with producer and consumer contract tests updated together.

Compliance access state, processed-event information, and audit history are persisted in SQLite. This does not mean all Supplier Portal business entities use durable database storage.

## 24.5 Input and Document Security

Validate identifiers, quantities, prices, dates, document content, pagination inputs, and event schemas according to the actual endpoint and model definitions. Do not document a universal identifier regex unless every relevant schema enforces it.

Before issuing a presigned document URL, the service must validate authentication, resource ownership, and applicable compliance access. Object keys and document identifiers are not proof of authorization.

MinIO failures must not be treated as successful document operations. Missing objects and unavailable storage must be handled according to the endpoint's actual exception mapping.

## 24.6 GraphQL and Contract Security

Every protected GraphQL resolver must enforce the applicable ownership and compliance rules. Collection filtering must happen before pagination. GraphQL must not bypass REST-equivalent authorization or business validation.

Contract retrieval and history access must enforce role authorization and supplier scoping. Meaningful changes should record the audit information supported by the implementation.

---

# 25. Storage Architecture

The current application uses different storage mechanisms for business records, document binaries, and R14 compliance processing.

| Data category | Current storage | Restart behavior |
|---|---|---|
| Purchase Orders and PO events | In-memory stores | Not durable across restart |
| Invoices and P2P workflow records | In-memory stores, where implemented | Not durable across restart |
| Onboarding business metadata | In-memory stores, where implemented | Not durable across restart |
| Supplier contracts and history | In-memory stores | Not durable across restart |
| Invoice and onboarding document binaries | MinIO | Persist independently of the application process |
| R14 compliance state | SQLite | Persists if the database file is retained |
| R14 processed-event and audit records | SQLite | Persists if the database file is retained |

## 25.1 MinIO Document Storage

MinIO provides S3-compatible object storage for invoice PDFs and onboarding documents. The application retains the metadata and object references needed to locate the binaries.

The active document-storage implementation uses MinIO rather than the local `uploads/` directory for document binaries. Restarting the Supplier Portal does not, by itself, delete existing MinIO objects.

Protected downloads must authorize the caller before generating a short-lived presigned URL. A previously issued URL may remain usable until it expires.

## 25.2 R14 SQLite Storage

R14 persists compliance access state, processed-event/idempotency information, ordering information, and compliance audit history in SQLite.

Durability depends on retaining and protecting the database file and on correct transaction and deployment configuration. SQLite state and Kafka offsets are not committed as one atomic transaction; recovery and replay must account for possible redelivery.

## 25.3 Production Storage Considerations

Production deployment should provide durable storage for business entities and suitable backup, retention, recovery, and access controls for both SQLite data and MinIO objects.

Replacing the in-memory stores with durable persistence is future work unless implemented separately. Do not describe all business records as database-backed.

---

# 26. End-to-End Workflows

## 26.1 Procure-to-Pay

```text
PO Created → Sent → Acknowledged → Shipment
                                     ↓
                               Goods Receipt
                                     ↓
                                  Invoice
                                     ↓
                              Three-Way Match
                                ↙         ↘
                             Matched   Discrepancy
                                ↓         ↓
                         Payment Approval  Human Review
```

The state machine and endpoint validation govern the allowed transitions. Completing a match does not automatically approve a discrepancy.

## 26.2 Supplier Onboarding

```text
Registration → Documents in MinIO → Verification
             → Approval → Compliance Internal Check
                                  ↓
                       CLEAR / REVIEW / BLOCK
                                  ↓
                        Activation decision
```

Activation is permitted only for a valid clearance response. The initial synchronous check is separate from the ongoing R14 event consumer.

## 26.3 Ongoing Compliance Access — R14

```text
Compliance Service
        ↓
compliance.supplier.status_changed
        ↓
Apache Kafka
        ↓
Supplier Portal Consumer
        ↓
Validate → Idempotency / Ordering → Persist State and Audit
        ↓
REST / GraphQL / Document Access Enforcement
```

The consumer maps `CLEAR` to `cleared`, `REVIEW` to `needs_review`, and `BLOCK` to `suspended`. A valid, newer clearance event can restore access without erasing previous audit records.

The current event contract identifies suppliers using `supplier_name` and `country`; a stable `supplier_id` is a recommended contract improvement.

## 26.4 Document Download

```text
Authenticated Request
        ↓
Resource and Ownership Validation
        ↓
Compliance Access Validation
        ↓
MinIO Object Lookup
        ↓
Short-Lived Presigned URL
        ↓
Client Downloads Document
```

Cross-supplier and suspended-supplier requests must be rejected before a new URL is generated.

## 26.5 GraphQL

```text
Frontend / Apollo Client
        ↓
/graphql
        ↓
Authentication Context
        ↓
Resolver Authorization and Supplier Filtering
        ↓
Compliance Validation
        ↓
Existing Business Logic / Data Access
        ↓
GraphQL Response
```

The documented R13 scope includes PO, invoice, and document queries, cursor pagination, PO acknowledgement, and supplier-level authorization. Pagination is based on the existing collection implementation and should not be described as stable database-backed pagination.

## 26.6 Contracts and Analytics

Contract lifecycle management supports creation, activation, explicit renewal, expiry information, and history according to the implemented service. Renewal updates the existing record and records history; automatic renewal and immutable versioning are not implied.

Supplier analytics derive from available PO, Goods Receipt, invoice, and dispute data. Scorecard access remains subject to authentication, supplier ownership, and compliance access.

---

# 27. Current Implementation Status

The following table summarizes the intended feature scope. It is not a substitute for reviewing the implementation or running the current test suite.

| Capability | Documented scope |
|---|---|
| Purchase Orders and P2P workflow | Implemented scope |
| Shipment and Goods Receipt processing | Implemented scope |
| Three-way matching and discrepancy review | Implemented scope |
| Supplier onboarding and synchronous compliance check | Implemented scope |
| Supplier performance analytics and scorecards | Implemented scope |
| Contract lifecycle, expiry, and explicit renewal | Implemented scope |
| Contract term-change history | Implemented scope |
| Historical dispute suggestions | Advisory feature |
| Supplier-scoping controls | Implemented scope |
| MinIO invoice and onboarding documents | Implemented scope |
| Presigned document URLs | Implemented scope |
| Strawberry GraphQL queries and PO acknowledgement | Implemented scope |
| R14 Kafka compliance consumer and DLQ handling | Implemented scope |
| R14 compliance state and audit persistence in SQLite | Implemented scope |
| Durable persistence for all business entities | Not currently provided by in-memory stores |
| Complete repeated-partial-invoice P2P lifecycle | Limitation |
| Automatic contract renewal scheduler | Not implemented |
| Immutable contract version repository | Not implemented |

## Round Summary

- **R5:** Supplier-scoping and authorization requirements.
- **R6–8:** P2P workflow, three-way matching, onboarding, supplier analytics, and related security controls.
- **R9–11:** Compliance activation integration, contract lifecycle, dispute suggestions, and scorecards.
- **R12:** MinIO-backed document storage and protected download URLs.
- **R13:** Strawberry GraphQL operations, pagination, and resolver-level supplier scoping.
- **R14:** Event-driven compliance access enforcement, SQLite-backed state and audit records, idempotency, ordering protection, and DLQ handling.
- **R15:** Approved-PO consumption and supplier acknowledgement should be documented separately, using the actual event schema, routes, outbox implementation, and test results from the current branch.

Feature status must be confirmed against the current code and test results before describing a feature as verified or production-ready.

---

# 28. Known Limitations

## In-Memory Business Data

POs, invoices, P2P records, onboarding metadata, contracts, contract history, and other business entities held in in-memory stores are not durable across application restarts.

This limitation does not apply to MinIO document binaries or the SQLite-backed R14 compliance records, which use separate storage mechanisms.

## R14 Supplier Identification

The current Compliance producer event does not include `supplier_id`; supplier identification relies on `supplier_name` and `country`. This is less reliable than a stable identifier, particularly when supplier names are duplicated or producer data changes.

A `BLOCK` event that fails processing and is routed to the DLQ is not applied to the compliance access state. It must be investigated and replayed after the cause is resolved. Monitor DLQ messages to avoid an unnoticed stale access state.

## Kafka Availability and Recovery

R14 requires Kafka to receive ongoing status-change events. If the broker or consumer is unavailable, the stored compliance state may not reflect the latest Compliance decision until processing resumes.

Database writes and Kafka offset commits are not one atomic transaction. Idempotency, recovery, replay, and offset reconciliation are important for reliable operation.

## Partial Invoice Lifecycle

Partial invoice validation does not provide a complete repeated-invoice lifecycle with cumulative quantity accounting, remaining-quantity tracking, cumulative matching, and final completion for one PO.

## Document Storage

MinIO is the active document-binary storage implementation. Production deployment still requires appropriate backup, retention, access policies, encryption configuration, and recovery procedures.

A presigned URL already issued to a client may remain valid until expiry. Immediate revocation must not be assumed.

## External Service Dependencies

- Platform Service availability affects centralized token verification.
- Compliance Service availability affects supplier activation; the integration fails closed when clearance cannot be confirmed.
- MinIO availability affects document operations.
- Kafka availability affects ongoing compliance event processing.

The exact HTTP response for each dependency failure depends on the relevant endpoint's exception mapping.

## Contracts and Dispute Suggestions

Automatic contract renewal and immutable contract versioning are not implemented by the current lifecycle alone. Historical dispute suggestions remain advisory and do not execute financial or approval actions.

## GraphQL Scope

The documented GraphQL scope covers the implemented PO, invoice, document, pagination, and acknowledgement operations. Additional domains, subscriptions, and production-grade query-complexity controls are potential future work.

---

# 29. Future Enhancements

The following items extend the documented functional scope or address production hardening.

## Durable Business Persistence

Replace in-memory business stores