# Compliance Screening Service

A **FastAPI-based Compliance Screening Service** for screening suppliers and customers against sanctions lists, internal watchlists, and PEP data.

The service provides:

* Multi-source sanctions screening
* Exact and fuzzy name matching
* Risk-based screening tiers
* Country and transaction-value risk assessment
* Compliance case management
* Audit history and reporting
* False-positive overrides
* Sanctions-data refresh
* Scheduled re-screening
* Newly flagged detection
* Human authentication and role-based authorization
* Service-to-service authentication
* Internal compliance checks
* Internal compliance caching
* SLA and latency monitoring
* SLA alerting
* Regulatory reporting
* Jurisdiction-specific compliance rules
* PostgreSQL persistence
* Alembic database migrations
* Kafka event publishing
* GraphQL read API
* Fixture-based testing
* Integration testing

---

# 1. Overview

The Compliance Service identifies potentially risky suppliers and customers before or during business operations.

The service screens entities against:

```text
OFAC
UN
EU
Internal Watchlist
PEP
```

The general screening flow is:

```text
Request
   ↓
Validate Input
   ↓
Normalize Entity Name
   ↓
Calculate Screening Tier
   ↓
Select Matching Threshold
   ↓
Search Sanctions / Watchlists / PEP
   ↓
Exact + Fuzzy Matching
   ↓
Deduplicate Matches
   ↓
Calculate Confidence
   ↓
Calculate Risk
   ↓
Check False-Positive Override
   ↓
Create Case if Flagged
   ↓
Save Audit Record
   ↓
Return Response
```

---

# 2. Technology Stack

The Compliance Service currently uses:

```text
Python
FastAPI
SQLAlchemy
PostgreSQL
Alembic
RapidFuzz
APScheduler
HTTPX
Pydantic
JWT authentication
Service API-key authentication
Kafka
confluent-kafka
GraphQL
Strawberry GraphQL
Pytest
Docker
```

Supporting infrastructure includes:

```text
PostgreSQL
Redis
Kafka
MinIO
GraphQL
Prometheus
Jaeger
Locust
```

The service keeps REST APIs for existing contracts while GraphQL provides a read-oriented API for compliance data.

---

# 3. Features

## Screening

* OFAC screening
* UN screening
* EU screening
* Internal Watchlist screening
* PEP screening
* Source attribution
* Exact name matching
* Fuzzy name matching
* Match deduplication
* Confidence calculation

## Risk Assessment

* Match confidence
* Source coverage
* Listing recency
* Country risk
* Transaction-value risk
* Overall supplier risk
* Risk-based screening tiers
* Tier-specific matching thresholds
* Configurable risk weights

## Compliance Operations

* Compliance case management
* Case assignment
* Case state machine
* Case history
* Resolution reasons
* False-positive overrides
* Bulk screening
* Audit history
* Audit analytics
* Compliance reporting

## Data Management

* Sanctions-data refresh
* Scheduled re-screening
* Newly flagged detection
* Newly flagged case creation

## Integration

* Platform/Auth Service integration
* Human JWT authentication
* Role-based authorization
* Internal service-to-service authentication
* Service API-key authentication
* Internal compliance endpoint
* Internal compliance caching
* Caller-service logging
* Kafka status-change events

## Monitoring

* Request latency tracking
* Request count
* Error tracking
* SLA monitoring
* SLA threshold tracking
* Rate-limited background SLA alerts

## Data Access

* REST API
* GraphQL read API
* Screening filters
* Case filters
* Pagination

---

# 4. Multi-Source Screening

The service combines multiple compliance data sources into a single screening process.

Supported sources:

```text
OFAC
UN
EU
Internal Watchlist
PEP
```

A single entity can match multiple sources.

Example:

```json
{
  "matched_name": "HAMAS",
  "matched_lists": [
    "OFAC",
    "EU"
  ]
}
```

Source attribution is preserved so downstream users can determine which compliance sources contributed to a match.

---

# 5. Matching and Deduplication

## Name Normalization

Entity names are normalized before matching.

Examples:

```text
CORPORATION  → CORP
COMPANY      → CO
LIMITED      → LTD
INCORPORATED → INC
&            → AND
```

Normalization reduces formatting differences between submitted entities and sanctions records.

## Exact Matching

Exact matching is performed after normalization.

## Fuzzy Matching

Fuzzy matching uses:

```text
RapidFuzz WRatio
```

The default matching threshold is configurable:

```env
MATCH_THRESHOLD=90
```

A higher score represents stronger similarity between the submitted entity and a sanctions/watchlist record.

## Deduplication

Matches from different sources may represent the same underlying entity.

The service deduplicates similar records using:

```env
DEDUPE_THRESHOLD=90
```

Source attribution is retained after deduplication.

---

# 6. Risk-Based Screening

The service calculates risk information in addition to the screening result.

Risk factors include:

* Match confidence
* Source coverage
* Listing recency
* Country risk
* Transaction value
* Overall supplier risk

## Risk Source Count

The source-coverage component uses:

```env
TOTAL_SOURCES=5
```

The five configured sources are:

```text
OFAC
UN
EU
Internal Watchlist
PEP
```

---

# 7. Sanctions Risk Score

The sanctions risk score uses configurable weights.

| Risk Factor      | Weight |
| ---------------- | -----: |
| Match confidence |    50% |
| Source coverage  |    30% |
| Listing recency  |    20% |

Configuration:

```env
CONFIDENCE_WEIGHT=0.50
SOURCE_WEIGHT=0.30
RECENCY_WEIGHT=0.20
```

The weights can be changed through environment variables.

---

# 8. Overall Supplier Risk

For supplier screening, sanctions risk can be combined with country risk.

Configuration:

```env
SANCTIONS_WEIGHT=0.80
COUNTRY_RISK_WEIGHT=0.20
UNKNOWN_COUNTRY_RISK=50.0
```

The calculation is:

```text
Overall Supplier Risk =
    Sanctions Risk × 80%
  + Country Risk × 20%
```

---

# 9. Screening Tiers

Screening tiers are calculated using:

* Country risk
* Transaction value

The tier is calculated **before entity matching**.

The higher-risk tier between country risk and transaction value is selected.

## Country Risk Tiers

```text
LOW
    Country risk <= 39

MEDIUM
    Country risk <= 69

HIGH
    Country risk > 69
```

## Transaction-Value Tiers

```text
LOW
    Transaction value < 1,000,000

MEDIUM
    Transaction value <= 5,000,000

HIGH
    Transaction value > 5,000,000
```

---

# 10. Tier-Specific Matching

The selected tier controls the fuzzy matching threshold.

| Tier   | Match Threshold | Screening Action                      |
| ------ | --------------: | ------------------------------------- |
| LOW    |              90 | `STANDARD_SCREENING`                  |
| MEDIUM |              85 | `ADDITIONAL_COMPLIANCE_REVIEW`        |
| HIGH   |              80 | `ENHANCED_REVIEW_AND_MANUAL_APPROVAL` |

Configuration:

```env
LOW_TIER_MATCH_THRESHOLD=90
MEDIUM_TIER_MATCH_THRESHOLD=85
HIGH_TIER_MATCH_THRESHOLD=80
```

The screening result can include:

```text
screening_tier
screening_action
country_risk_score
transaction_value
enhanced_review_required
```

---

# 11. Country Risk

Country risk is calculated for the submitted entity country.

The screening result can contain:

* Country
* Country risk score
* Country risk factors
* Overall supplier risk

Unknown countries use:

```env
UNKNOWN_COUNTRY_RISK=50.0
```

Country risk contributes to overall supplier risk for supplier screening.

---

# 12. Compliance Cases

Flagged screening results can create compliance cases.

Case management supports:

* Creating cases
* Assigning cases
* Starting reviews
* Clearing cases
* Confirming cases
* Recording resolution reasons
* Maintaining case history
* Tracking assignment timestamps
* Tracking resolution timestamps

## Case Workflow

```text
OPEN
  ↓
UNDER_REVIEW
  ↓
CLEARED
```

or:

```text
OPEN
  ↓
UNDER_REVIEW
  ↓
CONFIRMED
```

Invalid transitions are rejected.

## Case Assignment

Open and under-review cases can be assigned to compliance officers.

Closed cases cannot be reassigned.

Closed statuses are:

```text
CLEARED
CONFIRMED
```

## Case Resolution

A resolution reason is required when closing a case.

The following transitions require a reason:

```text
UNDER_REVIEW → CLEARED
UNDER_REVIEW → CONFIRMED
```

## Case History

Case actions are recorded in case history.

History can contain:

* Previous status
* New status
* User/system responsible
* Reason
* Comments
* Timestamp

---

# 13. False-Positive Overrides

Fuzzy matching can produce false positives because similar names do not necessarily represent the same entity.

The service supports approved false-positive overrides.

Override information can include:

* Entity name
* Matched name
* Source
* Reason
* Reviewed by
* Created timestamp

Available endpoints include:

```text
POST   /api/v1/compliance/override
GET    /api/v1/compliance/override
GET    /api/v1/compliance/overrides
DELETE /api/v1/compliance/override
```

Override operations require:

```text
compliance_officer
```

When an override changes, the internal compliance cache is cleared so callers do not continue receiving stale decisions.

---

# 14. Bulk Screening

The service supports screening multiple entities in one request.

Example performance test:

```powershell
python -m pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

The target performance is:

```text
< 100 ms
```

Actual performance depends on:

* Machine hardware
* Python version
* Dataset size
* Database state
* System load

---

# 15. Audit

Each screening request is stored in the audit database.

Audit records can contain:

* Entity name
* Entity type
* Country
* Match status
* Decision
* Matched name
* Matched lists
* Match score
* Confidence
* Sanctions risk score
* Risk factors
* Country risk score
* Overall supplier risk
* Screening type
* Newly flagged status
* Screening run ID
* Service name
* Screening duration
* Created timestamp

The audit database is PostgreSQL.

---

# 16. Screening Decisions

The audit and internal compliance flows use the following decision states:

```text
CLEAR
BLOCK
REVIEW
```

## CLEAR

No compliance concern requiring additional action was identified.

## BLOCK

A strong compliance match requires the protected operation to stop.

## REVIEW

The result is ambiguous or requires human investigation.

`REVIEW` does not mean that the entity has been confirmed as prohibited.

It means the service cannot safely provide an automatic `CLEAR` decision.

---

# 17. Screening Types

The service supports:

```text
INITIAL
RESCREEN
```

Re-screening records can additionally identify whether an entity became newly flagged.

---

# 18. Audit Summary

Endpoint:

```text
GET /api/v1/compliance/audit/summary
```

The endpoint requires:

```text
compliance_officer
```

The summary can provide:

* Total screenings
* Total flagged screenings
* Flag rate
* Newly flagged entities
* Initial screenings
* Re-screenings
* Flag rate over time
* Frequently flagged entities
* Country-level statistics

---

# 19. Compliance Reporting

The service provides a compliance summary report.

Endpoint:

```text
GET /api/v1/compliance/reports/compliance-summary
```

The report can provide:

* Screening volume
* Flagged count
* Flag rate
* Open cases
* Average resolution time

Example:

```json
{
  "screening_volume": 2,
  "flagged_count": 2,
  "flag_rate": 100,
  "open_cases": 1,
  "average_resolution_time_hours": 0.05
}
```

The reporting endpoint requires:

```text
compliance_officer
```

---

# 20. Sanctions Data

The service supports sanctions data from:

```text
OFAC
UN
EU
```

Additional screening sources are:

```text
Internal Watchlist
PEP
```

Local fixture files are stored in:

```text
app/data/fixtures/

├── ofac_sample.csv
├── un_sample.xml
└── eu_sample.xml
```

---

# 21. Sanctions Data Refresh

The refresh flow is:

```text
Download OFAC
      ↓
Download UN
      ↓
Download EU
      ↓
Load Records
      ↓
Deduplicate
      ↓
Build Index
      ↓
Ready for Screening
```

Download URLs are configured through environment variables.

The application is designed to fail when required sanctions data cannot be loaded rather than silently treating missing data as clean.

---

# 22. Re-Screening

The service supports re-screening entities that were previously cleared.

The process is:

```text
Find Latest Audit Result
        ↓
Find Previously Cleared Entities
        ↓
Refresh Sanctions Data
        ↓
Screen Entity Again
        ↓
Compare New Result
        ↓
Save RESCREEN Audit
        ↓
Identify Newly Flagged Entities
        ↓
Create Case if Required
        ↓
Publish Status-Change Event
```

The latest audit result is used when determining whether an entity is currently cleared.

Example:

```text
ABC COMPANY → clean

ABC COMPANY → clean

ABC COMPANY → matched
```

The latest result is `matched`, so the entity is not treated as previously cleared.

---

# 23. Newly Flagged Detection

An entity is newly flagged when:

```text
Previous Result = Clean
Current Result  = Matched
```

The resulting audit record contains:

```text
screening_type = RESCREEN
newly_flagged = true
```

A newly flagged entity can also result in an open compliance case.

---

# 24. Scheduled Re-Screening

The service uses **APScheduler** to run re-screening automatically.

The scheduled process:

1. Authenticates with the Platform/Auth Service.
2. Refreshes sanctions data.
3. Finds previously cleared entities.
4. Re-screens those entities.
5. Saves audit results.
6. Identifies newly flagged entities.
7. Creates cases for newly flagged entities when applicable.
8. Publishes status-change events when the supplier status changes.

The scheduler controls **when** the job runs.

The re-screening service controls **what happens during the job**.

The scheduler uses:

```text
max_instances=1
```

to prevent multiple instances of the same scheduled job from running simultaneously.

---

# 25. Service-to-Service Authentication

Scheduled re-screening is a system process rather than a human-user operation.

Therefore, the scheduled job uses a service API key instead of a human JWT.

The Compliance Service authenticates with the Platform/Auth Service using:

```text
POST /api/v1/auth/service-verify
```

The API key is sent using:

```text
X-API-Key
```

A successful response is expected to contain information similar to:

```json
{
  "authenticated": true,
  "service": "compliance",
  "auth_type": "api_key"
}
```

If authentication fails, the scheduled re-screening process stops.

This provides fail-closed behavior.

---

# 26. Internal Service-to-Service Compliance Contract

The Compliance Service exposes a dedicated lightweight endpoint for internal business services.

The endpoint is intentionally separate from the richer human-facing screening APIs.

## Endpoint

```text
POST /api/v1/compliance/internal-check
```

Typical callers include:

```text
inventory-service
supplier-portal
```

The endpoint provides a quick compliance decision before a protected business operation continues.

---

# 27. Internal Check Authentication

Authorized internal callers provide caller identity and service authentication information.

Headers include:

```http
X-Caller-Service: inventory-service
X-Service-Key: <service-key>
Content-Type: application/json
```

For Supplier Portal:

```http
X-Caller-Service: supplier-portal
X-Service-Key: <service-key>
Content-Type: application/json
```

Service credentials must be stored securely in environment variables or deployment secrets.

Real service keys must never be committed to source control.

---

# 28. Internal Check Request

The current request contract is:

```json
{
  "supplier_id": "SUP001",
  "company_name": "ABC Supplies Pvt Ltd",
  "country": "India"
}
```

The request supports compatible company-name input forms where configured by the API contract.

The service normalizes the supplied information before screening.

---

# 29. Internal Check Response

The response contains:

```text
supplier_id
company_name
country
cleared
decision
reason
```

The decision can be:

```text
CLEAR
BLOCK
REVIEW
```

Example:

```json
{
  "supplier_id": "SUP001",
  "company_name": "ABC Supplies Pvt Ltd",
  "country": "India",
  "cleared": true,
  "decision": "CLEAR",
  "reason": "No sanctions or watchlist match found."
}
```

Blocked result:

```json
{
  "supplier_id": "SUP001",
  "company_name": "ABC Supplies Pvt Ltd",
  "country": "India",
  "cleared": false,
  "decision": "BLOCK",
  "reason": "Entity matched a sanctions or compliance list."
}
```

Review result:

```json
{
  "supplier_id": "SUP001",
  "company_name": "ABC Supplies Pvt Ltd",
  "country": "India",
  "cleared": false,
  "decision": "REVIEW",
  "reason": "Potential compliance match requires human review."
}
```

The `decision` field is the authoritative field for callers.

---

# 30. Internal Decision Semantics

## CLEAR

The screening did not identify a compliance concern requiring further action.

The caller may continue the business operation.

## BLOCK

The screening identified a result that requires the caller to stop or reject the protected operation.

The caller must not continue the protected operation.

## REVIEW

The screening result is ambiguous or requires human investigation.

`REVIEW` does not mean that the entity has been confirmed as prohibited.

It means that the Compliance Service cannot safely provide an automatic `CLEAR` decision.

The entity must be reviewed by an authorized compliance officer.

---

# 31. Caller Behavior

Internal callers must evaluate the `decision` field.

They must **not** interpret:

```text
cleared=false
```

as an automatic block.

Expected behavior:

| Decision | Caller Action                                      |
| -------- | -------------------------------------------------- |
| `CLEAR`  | Continue operation                                 |
| `BLOCK`  | Stop / reject operation                            |
| `REVIEW` | Hold operation and request human compliance review |

Callers must not implement:

```text
cleared == false → BLOCK
```

Instead:

```text
decision == "CLEAR"
decision == "BLOCK"
decision == "REVIEW"
```

---

# 32. Internal Compliance Cache

Internal compliance checks use a short-lived cache.

Default TTL:

```text
300 seconds
```

Configuration:

```env
CACHE_TTL_SECONDS=300
```

The cache key is based on normalized supplier information:

```text
supplier_id
company_name
country
```

Example:

```text
Request 1
   ↓
SUP-001
   ↓
Perform screening
   ↓
Store result

Request 2
   ↓
SUP-001
   ↓
Cache hit
   ↓
Return cached result
```

The cache reduces redundant screening when multiple internal services request the same supplier within a short period.

Per-key locking prevents concurrent requests for the same supplier from unnecessarily performing duplicate screening work.

---

# 33. Internal Cache Invalidation

The cache is cleared when a compliance officer changes a decision through supported officer operations.

Cache invalidation can occur after:

```text
Override changes
Case-status changes
```

This prevents callers from receiving stale:

```text
CLEAR
BLOCK
REVIEW
```

decisions after a compliance decision changes.

---

# 34. Internal Caller Logging

The caller identity from:

```text
X-Caller-Service
```

is recorded in internal compliance request and response logs.

This allows requests to be traced back to the calling service.

Examples:

```text
inventory-service
supplier-portal
```

Service keys themselves are not logged.

---

# 35. Kafka Event Publishing

The Compliance Service publishes supplier status-change events when a re-screening operation changes the compliance status.

Kafka is used for asynchronous event delivery.

Configuration:

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SUPPLIER_STATUS_TOPIC=compliance.supplier.status_changed
```

## Topic

```text
compliance.supplier.status_changed
```

## Event Envelope

Events use a standard envelope containing information such as:

```text
event_id
event_type
source
timestamp
data
```

The event data contains supplier status-change information including:

```text
supplier_id
old_status
new_status
matched_list
reason
```

Conceptual event:

```json
{
  "event_id": "generated-event-id",
  "event_type": "compliance.supplier.status_changed",
  "source": "compliance-service",
  "timestamp": "2026-09-30T12:00:00Z",
  "data": {
    "supplier_id": "SUP-001",
    "old_status": "CLEAR",
    "new_status": "BLOCK",
    "matched_lists": [
      "OFAC",
      "EU"
    ],
    "reason": "Strong compliance match found."
  }
}
```

The event is published only when the supplier compliance status changes.

Repeated re-screening with the same status does not publish another status-change event.

---

# 36. Kafka Producer

Kafka publishing is implemented using:

```text
confluent-kafka
```

The producer is configured for reliable event publishing.

The Kafka producer is separated from the re-screening logic so that the business workflow can remain independently testable.

Unit tests mock the Kafka producer.

Kafka integration testing can use a running Kafka instance.

---

# 37. GraphQL API

The Compliance Service provides a read-only GraphQL API using:

```text
Strawberry GraphQL
```

GraphQL does not replace the existing REST APIs.

Existing REST contracts remain unchanged.

GraphQL is intended for read-oriented access to compliance data.

Endpoint:

```text
POST /api/v1/compliance/graphql
```

GraphQL authentication uses the same compliance role requirement:

```text
compliance_officer
```

Unauthenticated requests are rejected.

Users with an incorrect role are rejected.

---

# 38. GraphQL Screening Queries

The GraphQL API provides access to screening audit information.

Supported filters include:

```text
status
jurisdiction
date
```

The screening status can represent:

```text
CLEAR
BLOCK
REVIEW
```

`jurisdiction` maps to the screening country information.

Pagination uses:

```text
limit
offset
```

Example query:

```graphql
query {
  screenings(
    status: CLEAR
    jurisdiction: "India"
    limit: 10
    offset: 0
  ) {
    items {
      entityName
      country
      status
      matchScore
      decision
      createdAt
    }
    total
  }
}
```

---

# 39. GraphQL Case Queries

The GraphQL API also provides read access to compliance cases.

Case statuses include:

```text
OPEN
UNDER_REVIEW
CLEARED
CONFIRMED
```

Cases support pagination and relevant filtering.

Example:

```graphql
query {
  cases(
    status: OPEN
    limit: 10
    offset: 0
  ) {
    items {
      caseNumber
      entityName
      status
      createdAt
    }
    total
  }
}
```

GraphQL currently provides read operations only.

No GraphQL mutations are required for the compliance read API.

---

# 40. GraphQL Authorization

The GraphQL endpoint follows the same authorization model as protected compliance operations.

Required role:

```text
compliance_officer
```

Typical responses:

```text
Missing authentication token
    → 401 Unauthorized

Invalid authentication
    → 401 Unauthorized

Incorrect role
    → 403 Forbidden
```

---

# 41. SLA Monitoring

Because other internal services depend on the Compliance Service, the service monitors its own performance.

The service tracks:

* Request count
* Request latency
* Request duration
* Errors
* SLA threshold violations

SLA information is available through:

```text
GET /api/v1/compliance/sla
```

The service monitors `/internal-check` latency against the configured threshold.

Default threshold:

```env
SLA_LATENCY_THRESHOLD_MS=500
```

Requests exceeding the threshold are recorded for operational investigation.

---

# 42. SLA Alerting

When `/internal-check` latency exceeds the configured SLA threshold, the service can trigger an SLA alert in the background.

Alerts are rate-limited using a configurable cooldown period.

Configuration:

```env
SLA_LATENCY_THRESHOLD_MS=500
SLA_ALERT_COOLDOWN_SECONDS=300
SLA_ALERT_WEBHOOK_URL=
```

The alert is dispatched in the background so alert delivery does not block the compliance response.

If no webhook URL is configured, SLA degradation continues to be recorded and logged without requiring an external notification system.

---

# 43. Regulatory Reporting and Multi-Jurisdiction Rules

The Compliance Service provides a foundation for country-specific regulatory information instead of assuming identical requirements across all jurisdictions.

Regulatory rules can be retrieved using:

```text
GET /api/v1/compliance/reports/regulatory/{country}
```

Regulatory rules can be evaluated using:

```text
GET /api/v1/compliance/reports/regulatory/{country}/evaluate
```

Conceptually:

```text
Country
   ↓
Identify applicable regulatory rules
   ↓
Evaluate entity/business context
   ↓
Return applicable requirements
```

The regulatory layer should be considered a foundation for jurisdiction-specific compliance rules rather than complete regulatory coverage for every country.

---

# 44. Human Authentication and Authorization

The Compliance Service integrates with the Platform/Auth Service for human authentication and authorization.

Human users authenticate using JWT access tokens.

General flow:

```text
Client
   ↓
Platform Login
   ↓
JWT Access Token
   ↓
Compliance API
   ↓
Platform Token Verification
   ↓
Role Check
   ↓
Allow / Reject
```

The primary protected role is:

```text
compliance_officer
```

---

# 45. Authentication Responses

Typical authentication responses are:

```text
Missing token
    → 401 Unauthorized

Invalid / expired token
    → 401 Unauthorized

Valid token but incorrect role
    → 403 Forbidden

Platform unavailable
    → 503 Service Unavailable
```

---

# 46. Protected Compliance Operations

Role-protected operations use:

```text
compliance_officer
```

This includes protected:

* Screening operations
* Audit operations
* Override operations
* Case-management operations
* Reporting operations
* GraphQL read operations

---

# 47. Authentication Request Logging

Authentication-related requests can include tracing information such as:

```text
Caller service
Caller endpoint
Request ID
HTTP method
Path
Status code
Duration
User ID
Role
```

Service credentials and secret API keys must not be written to logs.

---

# 48. PostgreSQL Database

The Compliance Service uses PostgreSQL for persistent application data.

Example development configuration:

```env
DATABASE_URL=postgresql+psycopg://compliance:compliance_dev@localhost:5433/compliance
```

The database stores:

* Screening audit records
* Re-screening results
* Compliance cases
* Case history
* Override information

PostgreSQL is used for application persistence and test execution.

---

# 49. Alembic Database Migrations

Database schema changes are managed using:

```text
Alembic
```

Alembic allows database schema changes to be versioned and applied consistently.

Common commands:

```powershell
alembic current
```

Check the current migration:

```powershell
alembic current
```

Apply migrations:

```powershell
alembic upgrade head
```

Check whether model changes require a new migration:

```powershell
alembic check
```

Create a migration:

```powershell
alembic revision --autogenerate -m "describe schema change"
```

The current migration chain should be kept synchronized with the SQLAlchemy models.

---

# 50. Database Testing

Tests use a separate PostgreSQL database so that test data does not modify the development database.

Example:

```text
Application database:
compliance

Test database:
compliance_test
```

Example test configuration:

```env
DATABASE_URL=postgresql+psycopg://compliance:compliance_dev@localhost:5433/compliance_test
```

The test suite cleans test data between tests and resets PostgreSQL sequences where deterministic IDs are required.

This prevents test cases from depending on previous test execution order.

---

# 51. Docker Infrastructure

The service can use Docker-based infrastructure for local development and integration testing.

The infrastructure includes services such as:

```text
PostgreSQL
Redis
Kafka
MinIO
```

Each service maintains its own development compose configuration as required by the platform architecture.

Example:

```text
services/compliance/docker-compose.dev.yml
```

Docker is primarily used for infrastructure dependencies.

Unit tests should remain runnable without requiring Docker.

Container-dependent tests are marked as integration tests.

---

# 52. Configuration

Create a `.env` file in the Compliance Service directory.

Example:

```env
DATABASE_URL=postgresql+psycopg://compliance:compliance_dev@localhost:5433/compliance

SERVICE_NAME=compliance-service
ENVIRONMENT=development

MATCH_THRESHOLD=90
DEDUPE_THRESHOLD=90

LOW_TIER_MATCH_THRESHOLD=90
MEDIUM_TIER_MATCH_THRESHOLD=85
HIGH_TIER_MATCH_THRESHOLD=80

CONFIDENCE_WEIGHT=0.50
SOURCE_WEIGHT=0.30
RECENCY_WEIGHT=0.20

SANCTIONS_WEIGHT=0.80
COUNTRY_RISK_WEIGHT=0.20
UNKNOWN_COUNTRY_RISK=50.0

TOTAL_SOURCES=5

LOW_COUNTRY_RISK_MAX=39
MEDIUM_COUNTRY_RISK_MAX=69

LOW_TRANSACTION_VALUE_MAX=1000000
MEDIUM_TRANSACTION_VALUE_MAX=5000000

PLATFORM_AUTH_URL=http://127.0.0.1:8005
PLATFORM_SERVICE_API_KEY=<real-secret>

INTERNAL_SERVICE_KEYS=

CACHE_TTL_SECONDS=300

SLA_LATENCY_THRESHOLD_MS=500
SLA_ALERT_WEBHOOK_URL=
SLA_ALERT_COOLDOWN_SECONDS=300

INTERNAL_BLOCK_MATCH_SCORE=90

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SUPPLIER_STATUS_TOPIC=compliance.supplier.status_changed

USE_FIXTURES=false
```

Do not put real secrets in `.env.example`.

---

# 53. Internal Service Keys

The Compliance Service can store expected service keys for authorized internal callers.

Example structure:

```env
INTERNAL_SERVICE_KEYS=inventory-service:<secret>,supplier-portal:<secret>
```

The actual values must remain in the local `.env` or secure deployment configuration.

Never commit real service keys to Git.

Do not:

* Put real keys in README files
* Put real keys in `.env.example`
* Put real keys in test source
* Print keys in logs
* Include keys in API examples
* Commit keys to Git

---

# 54. Security

Secrets must remain outside source control.

Do not commit:

```text
.env
Real API keys
Passwords
JWT secrets
Production credentials
```

Use placeholders in `.env.example`.

Automated tests should use mocked or dummy credentials rather than production secrets.

If a real credential is accidentally exposed, it should be rotated immediately.

---

# 55. Fixture Mode

Automated tests can use local fixture data.

Fixture mode provides:

* Faster tests
* Stable test results
* No dependency on external sanctions providers
* Reproducible test data

Enable fixture mode in PowerShell:

```powershell
$env:USE_FIXTURES="true"
```

Check the value:

```powershell
$env:USE_FIXTURES
```

Expected:

```text
true
```

---

# 56. Testing

Tests should be run from:

```text
services/compliance
```

## Run All Tests

```powershell
python -m pytest -q
```

## Internal Compliance API Tests

```powershell
python -m pytest tests/test_internal_compliance_api.py -q
```

These tests verify:

* Internal endpoint availability
* Service-key authentication
* `supplier_name` support
* `company_name` compatibility
* Invalid-key rejection
* Missing-key rejection
* `CLEAR`
* `BLOCK`
* `REVIEW`
* Screening failure handling
* Internal caching
* Cache invalidation

## Internal Compliance Service Tests

```powershell
python -m pytest tests/test_internal_compliance.py -q
```

## SLA Alert Tests

```powershell
python -m pytest tests/test_sla_alert_service.py -q
```

## Authentication Tests

```powershell
python -m pytest -q tests/test_auth_integration.py
```

## Scheduled Job Authentication Tests

```powershell
python -m pytest tests/test_rescreen_auth.py -v
```

These tests use mocked service credentials and do not require a real API key.

## Re-Screening Tests

```powershell
python -m pytest tests/test_rescreen.py -v
```

## Risk Configuration Tests

```powershell
python -m pytest -q tests/test_risk_config.py
```

## Reporting Tests

```powershell
python -m pytest tests/test_reporting.py -q
```

## Regulatory Rules Tests

```powershell
python -m pytest -q tests/test_regulatory_rules.py
```

## Audit Tests

```powershell
python -m pytest tests/test_audit_service.py -q
```

## GraphQL Tests

```powershell
python -m pytest tests/test_graphql.py -q
```

GraphQL tests cover:

* Missing authentication
* Incorrect role
* Authorized screening queries
* Authorized case queries
* Screening filters
* Pagination

## Bulk Performance Test

```powershell
python -m pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

## Integration Tests

For live sanctions downloads or container-dependent infrastructure:

```powershell
$env:USE_FIXTURES="false"

python -m pytest -m integration -v -s
```

Integration tests may depend on:

* External sanctions providers
* PostgreSQL
* Kafka
* Docker
* Network availability

## Collect Tests

```powershell
python -m pytest --collect-only -q
```

---

# 57. Local Setup

## Create Virtual Environment

From:

```text
services/compliance
```

run:

```powershell
python -m venv venv
```

## Activate Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

## Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

## Configure Environment

Create:

```text
.env
```

and configure the required values described in the Configuration section.

---

# 58. Running PostgreSQL

The Compliance Service expects PostgreSQL to be available.

A development PostgreSQL instance can be started using the project's Docker configuration.

Verify the database connection before starting the application.

Example database:

```text
Host: localhost
Port: 5433
Database: compliance
User: compliance
```

Test database:

```text
Host: localhost
Port: 5433
Database: compliance_test
User: compliance
```

---

# 59. Running Kafka

Kafka is required when testing supplier status-change event publishing.

Default configuration:

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

Topic:

```text
compliance.supplier.status_changed
```

Kafka should be running before executing live Kafka integration tests.

Unit tests can mock the Kafka producer and therefore do not require Kafka.

---

# 60. Running the Application

Start the Compliance Service:

```powershell
python -m uvicorn app.main:app --reload --port 8003
```

Default local service:

```text
http://127.0.0.1:8003
```

Swagger documentation:

```text
http://127.0.0.1:8003/docs
```

GraphQL endpoint:

```text
http://127.0.0.1:8003/api/v1/compliance/graphql
```

The Platform/Auth Service is expected separately at:

```text
http://127.0.0.1:8005
```

when authentication or scheduled service authentication is being tested.

---

# 61. Running the Scheduler

Run:

```powershell
python -m app.jobs.scheduler
```

The scheduler starts the re-screening process according to its configured schedule.

Example:

```text
Starting scheduled re-screen...
        ↓
Platform authentication
        ↓
Authentication successful
        ↓
Refreshing sanctions data
        ↓
Finding previously cleared entities
        ↓
Re-screening
        ↓
Saving audit results
        ↓
Creating cases for newly flagged entities
        ↓
Publishing status-change events
```

If authentication fails:

```text
Starting scheduled re-screen...
        ↓
Platform authentication failed
        ↓
Job stops
```


# 63. Database Schema Management

SQLAlchemy models define the application data model.

Alembic manages database schema versions.

Typical workflow:

```text
Change SQLAlchemy Model
        ↓
Create Alembic Migration
        ↓
Review Migration
        ↓
alembic upgrade head
        ↓
Run Tests
```

Before committing schema changes:

```powershell
alembic check
```

Expected result when the schema is synchronized:

```text
No new upgrade operations detected.
```

---

# 64. Contract Testing

The service maintains contract tests for important API boundaries.

Contract tests verify that existing integrations do not accidentally change.

Important contracts include:

```text
/internal-check
Human authentication
Service authentication
GraphQL authorization
Kafka event envelope
```

For the internal compliance contract, tests verify:

```text
Request shape
Response shape
CLEAR
BLOCK
REVIEW
Authentication behavior
```

Existing consumers such as Supplier Portal and Inventory Service depend on the internal compliance response contract.

Changes to the request or response shape should therefore be treated as compatibility-sensitive changes.

---

# 65. Integration Testing Strategy

The test suite separates fast unit/API tests from infrastructure-dependent integration tests.

## Unit Tests

Unit tests can run without Docker.

They cover:

* Matching
* Risk calculations
* Case transitions
* Audit logic
* Cache behavior
* SLA logic
* Kafka publishing logic using mocks
* GraphQL schema behavior

## Integration Tests

Integration tests can use:

```text
PostgreSQL
Kafka
External sanctions providers
Docker infrastructure
```

Integration tests are marked:

```python
@pytest.mark.integration
```

Run them using:

```powershell
python -m pytest -m integration -v -s
```

---

# 66. Current Implementation Summary

The current Compliance Service includes:

```text
✓ OFAC screening
✓ UN screening
✓ EU screening
✓ Internal Watchlist screening
✓ PEP screening
✓ Source attribution
✓ Exact matching
✓ Fuzzy matching
✓ Match deduplication
✓ Confidence calculation
✓ Sanctions risk scoring
✓ Country risk
✓ Transaction-value risk
✓ Risk-based screening tiers
✓ Tier-specific matching thresholds
✓ Configurable risk weights

✓ Audit history
✓ Audit analytics
✓ Persisted screening decisions
✓ CLEAR / BLOCK / REVIEW
✓ False-positive overrides
✓ Bulk screening

✓ Compliance case management
✓ Case assignment
✓ Case state machine
✓ Case history
✓ Resolution reasons
✓ Closed-case reassignment protection

✓ Compliance reporting
✓ Regulatory rules foundation

✓ Sanctions data refresh
✓ Re-screening
✓ Newly flagged detection
✓ Newly flagged case creation
✓ Scheduled re-screening

✓ JWT authentication
✓ Role-based authorization
✓ Platform/Auth Service integration
✓ Service API-key authentication
✓ Internal service authentication
✓ Verified caller logging
✓ Fail-closed authentication behavior

✓ Internal /internal-check contract
✓ CLEAR / BLOCK / REVIEW decisions
✓ 5-minute internal compliance cache
✓ Cache invalidation
✓ Per-key cache locking

✓ SLA latency monitoring
✓ SLA error tracking
✓ Rate-limited background SLA alerts

✓ PostgreSQL persistence
✓ Separate PostgreSQL test database
✓ Alembic migrations
✓ Database schema validation

✓ Kafka supplier status-change events
✓ Standard Kafka event envelope
✓ No duplicate status-change events

✓ Strawberry GraphQL read API
✓ GraphQL screening queries
✓ GraphQL case queries
✓ GraphQL filtering
✓ GraphQL pagination
✓ GraphQL role authorization

✓ Fixture-based testing
✓ Authentication testing
✓ Internal API contract testing
✓ Audit testing
✓ GraphQL testing
✓ Re-screening testing
✓ Kafka producer testing
✓ Integration testing
```

---

# 67. Development Guidelines

When modifying the Compliance Service:

1. Preserve existing REST contracts unless a breaking change is explicitly approved.
2. Preserve the `/internal-check` request and response contract.
3. Keep `CLEAR`, `BLOCK`, and `REVIEW` semantics explicit.
4. Do not interpret `cleared=false` as automatically meaning `BLOCK`.
5. Keep secrets outside source control.
6. Add or update tests for behavior changes.
7. Create an Alembic migration for database schema changes.
8. Run `alembic check` before committing schema changes.
9. Keep infrastructure-dependent tests marked as integration tests.
10. Keep Kafka event publishing idempotent at the business-event level.
11. Avoid changing authentication behavior without updating contract tests.
12. Keep GraphQL as a read API unless mutations are explicitly required.
13. Use PostgreSQL for application and integration testing instead of relying on SQLite-specific behavior.
14. Do not commit `.env` files containing credentials.

---

# 68. Git and Secret Safety

Before committing changes:

```powershell
git status
```

Review the changed files:

```powershell
git diff --stat
```

Check that `.env` is ignored:

```powershell
git check-ignore .env
```

The `.env` file should not appear as an untracked file.

Never commit:

```text
.env
API keys
Service keys
Passwords
JWT secrets
Production credentials
```

Use `.env.example` for non-secret configuration examples.

If a real credential is accidentally exposed, rotate it immediately.

---

# 69. Known Limitations

## External Sanctions Providers

OFAC, UN, and EU data depend on external providers.

If a provider is unavailable or changes its format, the refresh process may fail.

The service is designed to fail rather than silently treat missing required sanctions data as clean.

## Fuzzy Matching

Fuzzy matching can produce false positives because similar names do not always represent the same entity.

The service provides:

* Matching thresholds
* Risk-based thresholds
* Deduplication
* False-positive overrides
* Human review through compliance cases

to manage ambiguous matches.

## Re-Screening Data

Re-screening depends on existing audit records.

If there are no previously cleared entities, the job correctly reports zero entities to re-screen.

## Regulatory Coverage

Country-specific regulatory retrieval and evaluation are implemented as a foundation.

This should not be interpreted as complete regulatory coverage for every jurisdiction.

Additional jurisdictions and rules can be added to the regulatory rules layer.

## SLA Alert Delivery

SLA degradation can trigger a background alert when configured.

External notification delivery depends on the configured webhook.

Without a webhook URL, SLA violations continue to be recorded and logged without external notification.

## Infrastructure Availability

Kafka, PostgreSQL, and other infrastructure-dependent functionality requires the corresponding infrastructure to be available during integration testing.

Unit tests remain independently executable using mocks and fixtures where appropriate.

---

# 70. Development Notes


Fixture mode:

```powershell
$env:USE_FIXTURES="true"
```

Live sanctions/integration testing:

```powershell
$env:USE_FIXTURES="false"
python -m pytest -m integration -v -s
```

---

# 71. Quick Reference

## Start Service

```powershell
python -m uvicorn app.main:app --reload --port 8003
```

## Run Tests

```powershell
python -m pytest -q
```

## Run GraphQL Tests

```powershell
python -m pytest tests/test_graphql.py -q
```

## Run Re-Screening Tests

```powershell
python -m pytest tests/test_rescreen.py -v
```

## Run Internal Compliance Tests

```powershell
python -m pytest tests/test_internal_compliance.py -q
python -m pytest tests/test_internal_compliance_api.py -q
```

## Run SLA Tests

```powershell
python -m pytest tests/test_sla_alert_service.py -q
```

## Run Integration Tests

```powershell
python -m pytest -m integration -v -s
```

## Apply Database Migrations

```powershell
alembic upgrade head
```

## Check Database Migrations

```powershell
alembic check
```



---

