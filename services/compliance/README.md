# Compliance Screening Service

A **FastAPI-based Compliance Screening Service** for screening suppliers and customers against sanctions lists, internal watchlists, and PEP data.

The service provides:

* Multi-source sanctions screening
* Exact and fuzzy name matching
* Country and transaction-value risk assessment
* Risk-based screening
* Compliance case management
* Audit history
* False-positive overrides
* Bulk screening
* Sanctions-data refresh
* Nightly re-screening
* Internal service-to-service compliance checks
* Kafka status-change events
* Strawberry GraphQL read APIs
* SLA monitoring
* Regulatory-rule management
* PostgreSQL persistence with Alembic migrations

---

# Current Round Status

Round 12+13 status

| Milestone | Status | Notes |
|---|---|---|
| M1 Postgres + Alembic + /internal-check contract | Done | `tests/test_contract.py`; `alembic upgrade head` verified by integration test |
| M2 `compliance.supplier.status_changed` on Kafka | Done | Published after commit; Kafka outage is logged, never rolls back the re-screen |
| M3 Strawberry GraphQL | Done | `/api/v1/compliance/graphql`, compliance_officer only   |



---

# Technology Stack

## Application

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* PostgreSQL
* Strawberry GraphQL

## Compliance

* OFAC
* United Nations sanctions data
* European Union sanctions data
* Internal watchlist
* PEP data
* RapidFuzz for fuzzy matching

## Messaging

* Apache Kafka
* `confluent-kafka`

## Scheduling

* APScheduler

## Testing

* Pytest
* HTTPX
* SQLite for normal unit/API tests
* PostgreSQL and Kafka for integration tests

## Development Infrastructure

* Docker
* Docker Compose

---
# Screening Flow

A normal screening request follows this flow:

```text
Client
  |
  v
FastAPI Compliance Endpoint
  |
  v
Request Validation
  |
  v
Compliance Screening
  |
  +--> OFAC
  +--> UN
  +--> EU
  +--> Internal Watchlist
  +--> PEP
  |
  v
Exact/Fuzzy Matching
  |
  v
Risk Calculation
  |
  v
Decision
  |
  +--> CLEAR
  +--> REVIEW
  +--> BLOCK
  |
  v
Audit Record
  |
  +--> Case when required
  |
  v
Response
```

---

# Screening Sources

The service supports the following sources:

| Source             | Purpose                               |
| ------------------ | ------------------------------------- |
| OFAC               | U.S. sanctions screening              |
| UN                 | United Nations sanctions screening    |
| EU                 | European Union sanctions screening    |
| Internal Watchlist | Organization-specific watchlist       |
| PEP                | Politically Exposed Persons screening |

The application loads the available sanctions data during startup.

The exact source record counts can change when source data is refreshed.

---

# Matching

The service supports:

* Exact matching
* Fuzzy name matching
* Normalized-name comparison
* Match confidence scoring
* Duplicate/deduplication handling

Fuzzy matching uses `rapidfuzz`.

The configured match threshold is controlled through environment configuration.

Example:

```text
MATCH_THRESHOLD=90
DEDUPE_THRESHOLD=90
```

These values are configuration settings and may be changed between environments.

---

# Decision Rules

The service uses a centralized decision function.

The current decision rules are:

```text
No match
    |
    +--> CLEAR

Match found
    |
    +--> score >= INTERNAL_BLOCK_MATCH_SCORE
    |        |
    |        +--> BLOCK
    |
    +--> score below threshold
             |
             +--> REVIEW
```

Current default:

```text
INTERNAL_BLOCK_MATCH_SCORE=90
```

The effective decision is therefore:

| Match | Score | Decision |
| ----- | ----: | -------- |
| No    |   Any | CLEAR    |
| Yes   |  < 90 | REVIEW   |
| Yes   | >= 90 | BLOCK    |

The threshold is configurable.

---

# Internal Compliance Check

Other internal services can use:

```text
POST /api/v1/compliance/internal-check
```

Request:

```json
{
  "supplier_id": "SUP-003",
  "supplier_name": "HAMAS TRADING",
  "country": "India"
}
```

The endpoint returns:

```json
{
  "supplier_id": "SUP-003",
  "company_name": "HAMAS TRADING",
  "country": "India",
  "cleared": false,
  "decision": "BLOCK",
  "reason": "Strong compliance match found on EU, OFAC"
}
```

Supported decisions:

```text
CLEAR
REVIEW
BLOCK
```

`cleared` is:

```text
true  -> CLEAR
false -> REVIEW or BLOCK
```

The internal contract is covered by an explicit contract test.

---

# Internal Check Contract

The contract test verifies:

* Request structure
* Required headers
* Authentication failure
* CLEAR response
* REVIEW response
* BLOCK response
* Exact response keys

The contract test is located at:

```text
tests/test_contract.py
```

Run it with:

```powershell
python -m pytest tests\test_contract.py -q
```

---

# REST API

The main REST API prefix is:

```text
/api/v1/compliance
```

Important operations include:

```text
POST   /api/v1/compliance/screen
POST   /api/v1/compliance/bulk
POST   /api/v1/compliance/internal-check
GET    /api/v1/compliance/audit
GET    /api/v1/compliance/audit/summary
GET    /api/v1/compliance/sla
```

Additional routes support cases, overrides, regulatory rules, and re-screening functionality.

---

# Screening Endpoint

Primary screening endpoint:

```text
POST /api/v1/compliance/screen
```

Typical request fields include:

```json
{
  "entity_name": "Example Supplier",
  "entity_type": "supplier",
  "country": "India",
  "transaction_value": 100000
}
```

The screening result contains the applicable compliance decision and screening information.

---
# Audit Trail

Every screening can create an audit record containing information such as:

* Entity name
* Entity type
* Country
* Match status
* Match score
* Decision
* Screening date/time
* Source information
* Screening metadata

The audit trail is persisted using SQLAlchemy.

Production persistence is PostgreSQL.

---

# Compliance Cases

Compliance cases can be created for screenings requiring human review or investigation.

Typical case lifecycle:

```text
OPEN
  |
  v
UNDER_REVIEW
  |
  +--> CLEARED
  |
  +--> CONFIRMED
```

Closing a case requires a resolution reason.

Case history is maintained separately from the current case state.

---

# False-Positive Overrides

Authorized compliance users can create overrides for confirmed false positives.

Overrides can prevent repeated false-positive matches from unnecessarily generating compliance cases.

Overrides are persisted in the compliance database.

---

# Re-screening

The service supports re-screening of previously cleared entities.

The re-screening flow:

```text
Previously Cleared Entity
        |
        v
Run Current Screening
        |
        v
Calculate New Decision
        |
        v
Compare Old vs New Decision
        |
        +--> Same status
        |       |
        |       +--> No status-change event
        |
        +--> Different status
                |
                +--> Commit database changes
                |
                +--> Publish Kafka event
```

The old decision is read from the existing audit/entity state.

The new decision is calculated using the centralized decision logic.

---

# Re-screening Status Changes

A Kafka status-change event is generated only when:

```text
old_status != new_status
```

For example:

```text
CLEAR -> REVIEW
```

or:

```text
CLEAR -> BLOCK
```

No status-change event is generated when:

```text
CLEAR -> CLEAR
```

The database transaction is committed before the Kafka event is published.

Therefore:

```text
Database failure
    -> database transaction fails

Kafka failure
    -> database change remains committed
    -> failure is logged
```

This prevents a Kafka outage from rolling back a successful compliance status update.


# Kafka Integration

Kafka is used for supplier compliance status-change events.

Current event type:

```text
compliance.supplier.status_changed
```

---

# Kafka Event Envelope

The current implementation publishes this structure:

```json
{
  "event_id": "uuid",
  "event_type": "compliance.supplier.status_changed",
  "event_version": 1,
  "occurred_at": "2026-10-05T10:00:00+00:00",
  "producer": "compliance-service",
  "payload": {
    "supplier_name": "Example Supplier",
    "country": "India",
    "old_status": "CLEAR",
    "new_status": "BLOCK",
    "matched_list": [
      "OFAC"
    ],
    "reason": "Strong compliance match found",
    "screening_run_id": "run-123"
  }
}
```

The actual envelope fields are:

```text
event_id
event_type
event_version
occurred_at
producer
payload
```

The payload contains:

```text
supplier_name
country
old_status
new_status
matched_list
reason
screening_run_id
```
---

# Kafka Event Topic

The topic is:

```text
compliance.supplier.status_changed
```

The producer sets:

```text
topic = event_type
```

Therefore the current event is published to:

```text
compliance.supplier.status_changed
```

# Kafka Duplicate Behavior

The re-screening code checks:

```text
old_status != new_status
```

before preparing a status-change event.

Therefore repeated screening runs with the same status do not intentionally create another status-change event.

Example:

```text
Run 1:
CLEAR -> BLOCK
    -> event published

Run 2:
BLOCK -> BLOCK
    -> no event

Run 3:
BLOCK -> BLOCK
    -> no event
```

This is application-level status-change suppression.

The service does **not** claim full distributed exactly-once delivery semantics.

---

# Kafka Testing

Producer unit tests cover:

* Event envelope
* Event type
* Topic
* UTC timestamp
* Payload
* Kafka outage behavior
* Unacknowledged delivery
* Idempotent producer configuration

Run:

```powershell
python -m pytest tests\test_kafka_producer.py -q
```

A Kafka integration test also verifies that an event reaches a real Kafka broker.

Run:

```powershell
python -m pytest tests\test_integration_infra.py::test_status_changed_event_reaches_real_kafka -m integration -q
```

---

# GraphQL

The service provides a Strawberry GraphQL read API.

Endpoint:

```text
/api/v1/compliance/graphql
```

GraphQL is intended for compliance read/query operations.

REST APIs remain available and are not replaced by GraphQL.

---

# GraphQL Authorization

GraphQL access uses the same compliance role protection as the protected REST operations.

The required role is:

```text
compliance_officer
```

An authorized compliance officer can access GraphQL.

An analyst without the required role is rejected.

Requests without the required authentication context are also rejected.

---

# GraphQL Screening Queries

The GraphQL screening API supports:

* Screening retrieval
* Status filtering
* Jurisdiction/country filtering
* Date filtering
* Pagination

Example conceptual query:

```graphql
query {
  screenings(
    status: BLOCK
    page: 1
    pageSize: 20
  ) {
    items {
      entityName
      country
      status
    }
    total
    page
    pageSize
  }
}
```

The exact GraphQL schema should be treated as the source of truth for available fields.

---

# GraphQL Case Queries

Compliance cases can also be queried through GraphQL.

The API supports case retrieval for authorized compliance users.

GraphQL tests verify that unauthorized users cannot access the protected query.

---

# GraphQL REVIEW Status

The GraphQL screening status filter supports:

```text
CLEAR
REVIEW
BLOCK
```

`REVIEW` is calculated using the same decision logic as the compliance service when an explicit persisted decision is not available.

This avoids treating every matched screening as `BLOCK`.

---

# GraphQL Pagination

GraphQL screening queries support pagination.

Pagination allows clients to request a limited page rather than retrieving the complete screening dataset.

The response includes pagination metadata such as:

```text
items
total
page
pageSize
```

---

# SLA Monitoring

The service tracks screening latency.

The default threshold is:

```text
SLA_LATENCY_THRESHOLD_MS=500
```

SLA metrics are exposed through the compliance service.

The service also supports SLA alert handling.

---

# Regulatory Rules

The service includes regulatory-rule management.

Rules can be used to represent compliance requirements relevant to the screening service.

Regulatory reporting schemas and services are included separately from the core screening logic.

---

# Authentication and Authorization

Protected compliance operations require the appropriate authentication context and role.

The main compliance role used by protected operations is:

```text
compliance_officer
```
The service also supports internal service authentication for internal compliance checks.

Secrets must be supplied through environment configuration.

Secrets must not be committed to Git.

---

# Database

The service uses:

```text
PostgreSQL
```

for application persistence.

The database includes entities such as:

```text
compliance_audit
compliance_case
case_history
compliance_override
regulatory_rules
```

Alembic maintains the database schema.

---

# Alembic

Database schema changes are managed using Alembic.

Apply migrations with:

```powershell
alembic upgrade head
```

Do not use application startup to create production tables.

The application does not call:

```python
Base.metadata.create_all(...)
```

during normal startup.

Database creation and schema upgrades are intentionally separated from application startup.

---

# Alembic Integration Test

The infrastructure integration test verifies that a clean PostgreSQL database can be migrated to the current Alembic head.

It verifies the expected tables and important columns.

It also verifies that the migration can be downgraded back to the base state.

Run:

```powershell
python -m pytest tests\test_integration_infra.py::test_alembic_upgrade_head_on_empty_database -m integration -q
```

This test requires:

```text
COMPLIANCE_PG_TEST_URL
```

and a running PostgreSQL instance.

---

# Test Database

Normal unit and API tests use SQLite.

This keeps the default test suite:

* Fast
* Deterministic
* Independent of Docker
* Independent of a running PostgreSQL server

PostgreSQL-specific behavior is tested separately through integration tests.

---

# Integration Tests

Integration tests are marked:

```python
@pytest.mark.integration
```

The default test configuration excludes them.

Run normal tests:

```powershell
python -m pytest -m "not integration" -q
```

Run integration tests:

```powershell
python -m pytest -m integration -q
```

Integration tests can require:

* PostgreSQL
* Kafka
* Docker
* Live external compliance data, depending on the specific test

Not every integration test requires every external service.

---

# Pytest Configuration

The project defines the integration marker in `pytest.ini`.

Default behavior:

```text
integration tests are excluded
```

This allows normal development and CI unit tests to run without requiring the complete infrastructure stack.

---

# Docker Compose

Development infrastructure is defined in:

```text
docker-compose.dev.yml
```

The current development stack includes PostgreSQL and Kafka.

Example PostgreSQL mapping:

```text
localhost:5433 -> PostgreSQL container:5432
```

Example Kafka mapping:

```text
localhost:9092 -> Kafka container:9092
```

---

# Environment Configuration

Create a local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Then configure real local development credentials.

Do not commit `.env`.

A safe `.env.example` should contain placeholders rather than real passwords.

Example:

```text
POSTGRES_DB=compliance
POSTGRES_USER=compliance
POSTGRES_PASSWORD=change-me

DATABASE_URL=postgresql+psycopg://compliance:change-me@localhost:5433/compliance

COMPLIANCE_PG_TEST_URL=postgresql+psycopg://compliance:change-me@localhost:5433/compliance_test

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_FLUSH_TIMEOUT_SECONDS=5

INTERNAL_SERVICE_KEYS=inventory-service:change-me,supplier-portal:change-me

SLA_LATENCY_THRESHOLD_MS=500
SLA_ALERT_WEBHOOK_URL=
SLA_ALERT_COOLDOWN_SECONDS=300

INTERNAL_BLOCK_MATCH_SCORE=90
```

Replace placeholder values locally.

---

# Starting Development Infrastructure

From:

```text
services/compliance
```

run:

```powershell
docker compose -f docker-compose.dev.yml --env-file .env up -d
```

Check containers:

```powershell
docker ps
```

Expected development services include:

```text
compliance-postgres
compliance-kafka
```

---

# PostgreSQL Development Database

The development PostgreSQL instance uses a host port of:

```text
5433
```

Therefore a local connection string has the general form:

```text
postgresql+psycopg://USER:PASSWORD@localhost:5433/DATABASE
```

The actual password must come from the local `.env`.

Do not place a real password in the README.

---

# Kafka Development Broker

Kafka is exposed locally on:

```text
localhost:9092
```

The application configuration uses:

```text
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

The exact Kafka container configuration is defined in:

```text
docker-compose.dev.yml
```

---

# 46. Application Startup

After PostgreSQL is available and migrations have been applied:

```powershell
alembic upgrade head
```

Start the FastAPI application:

```powershell
python -m uvicorn app.main:app --reload --port 8003
```

The service will load sanctions data during application startup.

---

# Health Endpoint

Basic service health endpoint:

```text
GET /root
```

Example response:

```json
{
  "service": "compliance"
}
```

---

# Dependency Pinning

Application dependencies are pinned in:

```text
requirements.txt
```

This reduces unexpected dependency changes between development and CI environments.

Install dependencies with:

```powershell
python -m pip install -r requirements.txt
```

---

# Current Dependency Set

The project currently pins dependencies including:

```text
fastapi==0.142.2
uvicorn==0.54.0
sqlalchemy==2.1.3
alembic==1.20.0
psycopg[binary]==3.3.6
python-dotenv==1.2.4
rapidfuzz==3.14.6
requests==2.34.2
apscheduler==3.11.3
pytest==9.1.1
httpx==0.28.1
xmltodict==1.0.4
pydantic==2.13.5
confluent-kafka==2.15.1
strawberry-graphql==0.331.1
```

The exact versions should be changed only through an intentional dependency update.

---

# Running Unit Tests

Run the default test suite:

```powershell
python -m pytest -m "not integration" -q
```

This includes normal unit and API tests.

Integration tests are intentionally excluded by default.

---

# Test Coverage Areas

The test suite covers areas including:

* Screening
* Matching
* Risk calculation
* Decisions
* Internal compliance
* Contract behavior
* Re-screening
* Kafka producer behavior
* GraphQL authorization
* GraphQL filtering
* GraphQL pagination
* SLA logic
* Regulatory rules
* Case behavior
* Audit behavior
* PostgreSQL/Alembic infrastructure
* Kafka integration

---

# Internal Service Contract Compatibility

The `/internal-check` endpoint is intentionally kept compatible with the existing internal consumers.

The request contract remains:

```text
supplier_id
supplier_name
country
```

The response contract remains:

```text
supplier_id
company_name
country
cleared
decision
reason
```

This allows existing service-to-service callers to continue using the compliance endpoint without changing the public contract.

---

# Caching

The internal compliance check supports short-lived caching.

The current cache duration is:

```text
300 seconds
```

Cache keys use normalized supplier information.

Per-key locking is used to reduce duplicate concurrent screening work.

---
#  Security and Secrets

The repository must not contain:

* Production passwords
* Database passwords
* API keys
* Service secrets
* Private credentials
* Real authentication tokens

Use:

```text
.env
```

for local secrets.

Commit:

```text
.env.example
```

with placeholders only.

Before committing changes, check:

```powershell
git status
```

and inspect staged files.

---

# Current Status

The Compliance Screening Service currently provides a working foundation for:

* Sanctions screening
* Risk-based decisions
* Compliance cases
* Audit history
* Internal service screening
* PostgreSQL persistence
* Alembic migrations
* Kafka status-change publishing
* GraphQL read access
* SLA monitoring
* Scheduled re-screening

The Round 12 + 13 implementation has been developed with explicit unit tests and infrastructure integration tests.

The project intentionally documents its remaining limitations rather than presenting incomplete behavior as fully implemented.

The final milestone status should be updated only after the relevant PostgreSQL integration verification passes in the target development/CI environment.
