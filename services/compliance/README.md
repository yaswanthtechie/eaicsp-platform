# Compliance Screening Service

A **FastAPI-based Compliance Screening Service** for screening supplier and customer entities against sanctions lists, internal watchlists, and PEP data.

The service supports multi-source screening, exact and fuzzy name matching, risk-based screening tiers, compliance case management, audit history, reporting, sanctions-data refresh, scheduled re-screening, and service-to-service authentication.



# Overview

The Compliance Screening Service is responsible for identifying potentially risky suppliers and customers before or during business operations.

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

The service uses:

* FastAPI
* SQLAlchemy
* SQLite
* RapidFuzz
* APScheduler
* HTTPX
* JWT-based authentication
* Platform Service authentication
* Service API-key authentication

---



# Features

The service currently supports:

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
* Sanctions risk scoring
* Country risk assessment
* Transaction-value risk assessment
* Risk-based screening tiers
* Tier-specific matching thresholds
* False-positive overrides
* Bulk screening
* Audit history
* Audit analytics
* Compliance case management
* Case assignment
* Case state machine
* Case history
* Resolution reasons
* Compliance reporting
* Sanctions data refresh
* Re-screening
* Newly flagged detection
* Scheduled re-screening
* JWT authentication
* Role-based authorization
* Platform Service integration
* Service API-key authentication
* Fixture-based testing
* Integration testing
* Performance testing



# Multi-Source Screening

The service combines multiple compliance data sources into a single screening process.

Supported sources:

```text
OFAC
UN
EU
Internal Watchlist
PEP
```

A single entity can match more than one source.

For example:

```json
{
  "matched_name": "HAMAS",
  "matched_lists": [
    "OFAC",
    "EU"
  ]
}
```

This allows downstream compliance users to understand which sources contributed to the match.

---

# Matching and Deduplication

## Name Normalization

Entity names are normalized before matching.

Examples of normalization include:

```text
CORPORATION → CORP
COMPANY     → CO
LIMITED     → LTD
INCORPORATED → INC
&           → AND
```

Normalization helps reduce formatting differences between user input and sanctions records.

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

A higher score represents a stronger similarity between the submitted entity and a sanctions/watchlist record.

## Deduplication

Matches from different sources can represent the same underlying entity.

The service deduplicates similar records using:

```env
DEDUPE_THRESHOLD=90
```

Source attribution is preserved after deduplication.

This prevents the same entity from being counted as multiple unrelated matches.

---

# Risk-Based Screening

The service calculates risk information in addition to the screening match result.

Risk-related information can include:

* Match confidence
* Source coverage
* Listing recency
* Country risk
* Transaction value
* Overall supplier risk

---

## Sanctions Risk Score

The sanctions risk score uses the following configurable weights:

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

## Overall Supplier Risk

For supplier screening, sanctions risk can be combined with country risk.

Current configuration:

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

# Screening Tiers

The service uses screening tiers to adjust screening behavior according to:

* Country risk
* Transaction value

The tier is calculated **before entity matching**.

The higher-risk tier between country risk and transaction value is selected.



## Tier Rules

Country risk:

```text
LOW
    Country risk <= 39

MEDIUM
    Country risk <= 69

HIGH
    Country risk > 69
```

Transaction value:

```text
LOW
    Transaction value < 1,000,000

MEDIUM
    Transaction value <= 5,000,000

HIGH
    Transaction value > 5,000,000
```

The final screening tier is the higher of the country-risk tier and transaction-value tier.

---

## Tier-Specific Matching

The selected tier affects the fuzzy matching threshold.

| Tier   | Match Threshold | Screening Action                      |
| ------ | --------------: | ------------------------------------- |
| LOW    |              90 | `STANDARD_SCREENING`                  |
| MEDIUM |              85 | `ADDITIONAL_COMPLIANCE_REVIEW`        |
| HIGH   |              80 | `ENHANCED_REVIEW_AND_MANUAL_APPROVAL` |

A lower matching threshold makes screening more sensitive for higher-risk entities.

Configuration:

```env
LOW_TIER_MATCH_THRESHOLD=90
MEDIUM_TIER_MATCH_THRESHOLD=85
HIGH_TIER_MATCH_THRESHOLD=80
```

The selected tier is calculated before screening and its threshold is passed to the matching engine.

The screening result can include:

```text
screening_tier
screening_action
country_risk_score
transaction_value
enhanced_review_required
```

---

# Country Risk

Country risk is calculated for the submitted entity country.

The screening result can contain:

* Country
* Country risk score
* Country risk factors
* Overall supplier risk

Unknown countries use the configured default:

```env
UNKNOWN_COUNTRY_RISK=50.0
```

Country risk contributes to overall supplier risk for supplier screening.

---

# Case Management

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

---

## Case Workflow

Cases follow the state machine:

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

Invalid state transitions are rejected.

---

## Case Assignment

Open and under-review cases can be assigned to compliance officers.

Blank assignments are rejected.

Closed cases cannot be reassigned.

Closed statuses are:

```text
CLEARED
CONFIRMED
```

---

## Case Resolution

A resolution reason is required when closing a case.

The following transitions require a reason:

```text
UNDER_REVIEW → CLEARED
UNDER_REVIEW → CONFIRMED
```

This ensures that the compliance decision contains an explanation.

---

## Case History

Case actions are recorded in case history.

History can contain:

* Previous status
* New status
* User/system responsible
* Reason
* Comments
* Timestamp

The actor is taken from the authenticated request where applicable rather than using a fixed user identity.

---

# Compliance Reporting

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

# Audit

Each screening request is stored in the audit database.

The service uses:

```text
SQLite
SQLAlchemy
```

Audit records can contain:

* Entity name
* Entity type
* Country
* Match status
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

---

## Screening Types

The service supports:

```text
INITIAL
RESCREEN
```

Re-screening records can additionally identify whether the entity became newly flagged.

---

# Audit Summary

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

# False-Positive Overrides

Fuzzy matching can produce false positives because similar names do not always represent the same entity.

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

Override operations require the:

```text
compliance_officer
```

role.

---

# Bulk Screening

The service supports screening multiple entities in one request.

Bulk screening:

* Screens multiple entities
* Preserves input order
* Applies risk-based screening tiers
* Uses the tier-specific matching threshold
* Supports case creation for flagged entities
* Records screening results

Performance testing is included for large batches.

Example:

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

# Sanctions Data

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

# Sanctions Data Refresh

Sanctions data can be refreshed before re-screening.

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

Download URLs are configured using environment variables.

The application should fail when required sanctions data cannot be loaded rather than silently treating missing data as clean.

---

# Re-Screening

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
```

The latest audit result is used when determining whether an entity is currently cleared.

For example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
ABC COMPANY → matched
```

The latest result is `matched`, so the entity is not treated as previously cleared.

If:

```text
ABC COMPANY → clean
ABC COMPANY → clean
```

the entity can be selected for re-screening.

---

## Newly Flagged Detection

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

# Scheduled Re-Screening

The service uses **APScheduler** to run re-screening automatically.

The scheduled process:

1. Authenticates with the Platform Service.
2. Refreshes sanctions data.
3. Finds previously cleared entities.
4. Re-screens those entities.
5. Saves audit results.
6. Identifies newly flagged entities.
7. Creates cases for newly flagged entities when applicable.

The scheduler controls **when** the job runs.

The re-screening service controls **what happens during the job**.

The scheduler uses:

```text
max_instances=1
```

to prevent multiple instances of the same scheduled job from running simultaneously.

For development and testing, a short interval can be configured.

Production deployments should use an appropriate nightly schedule.

---

# Service-to-Service Authentication

Scheduled re-screening is a system process rather than a human user.

Therefore, the scheduled job does not use a human JWT.

Instead, the Compliance Service authenticates with the Platform/Auth Service using a service API key.

The Platform/Auth Service is configured separately.

Default local configuration:

```text
http://127.0.0.1:8005
```

The Compliance Service calls:

```text
POST /api/v1/auth/service-verify
```

The API key is sent using:

```text
X-API-Key
```

---

## Service Authentication Flow

```text
Scheduled Job
      ↓
Read Service API Key
      ↓
Authenticate with Platform
      ↓
Platform verifies API key
      ↓
Authentication successful?
      ↓
   ┌──┴──┐
  Yes    No
   ↓      ↓
Run     Stop Job
Job
```

A successful response is expected to contain information similar to:

```json
{
  "authenticated": true,
  "service": "compliance",
  "auth_type": "api_key"
}
```

If authentication fails, the re-screening process stops.

This provides **fail-closed behavior**.

---

# Service API Key Configuration

The real service API key must be stored outside source control.

Local `.env`:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
PLATFORM_SERVICE_API_KEY=<real-secret>
```

The real API key must **never be committed to Git**.

The `.env.example` file should contain only a placeholder:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
PLATFORM_SERVICE_API_KEY=your-compliance-service-api-key
```

The `.env` file should be included in `.gitignore`.

The API key must not be:

* Printed in logs
* Added to README files
* Added to test source code
* Committed to Git
* Included in API examples

Automated tests use dummy values through mocking rather than requiring the developer's real API key.

---

# Authentication and Authorization

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

The primary role used by protected Compliance operations is:

```text
compliance_officer
```

---

## Authentication Responses

Typical responses are:

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

# Protected Compliance Operations

Role-protected operations use:

```text
compliance_officer
```

This includes protected screening, audit, override, case-management, and reporting operations as configured by the application.

---

# Authentication Request Logging

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

This information helps trace requests between the Compliance Service and Platform Service.

---

# Configuration

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=sqlite:///./compliance.db

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
```

Do not place the real API key in:

```text
.env.example
README.md
Git
Tests
Logs
```

---

# Fixture Data

Automated tests use local fixture data.

Fixture mode provides:

* Faster tests
* Stable test results
* No dependency on external internet access
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

# Testing

## Run All Tests

From:

```text
services/compliance
```

run:

```powershell
python -m pytest -q
```

The Round 6 test suite has been verified successfully.

---

## Authentication Tests

```powershell
python -m pytest -q tests/test_auth_integration.py
```

---

## Scheduled Job Authentication Tests

```powershell
python -m pytest tests/test_rescreen_auth.py -v
```

These tests mock the service API key so they do not depend on a real secret in `.env`.

---

## Re-Screening Tests

```powershell
python -m pytest tests/test_rescreen.py -v
```

---

## Risk Configuration Tests

```powershell
python -m pytest -q tests/test_risk_config.py
```

---

## Reporting Tests

```powershell
python -m pytest tests/test_reporting.py -q
```

---

## Bulk Performance Test

```powershell
python -m pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

---

## Integration Tests

To test live sanctions downloads:

```powershell
$env:USE_FIXTURES="false"

python -m pytest -m integration -v -s
```

Live integration tests depend on external sanctions providers and network availability.

---

## Collect Tests

To see the tests collected by pytest:

```powershell
python -m pytest --collect-only -q
```




```powershell
python -m venv venv
```
```powershell
.\venv\Scripts\Activate.ps1
```
## 4. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## 5. Configure Environment Variables

Create:

```text
.env
```

and configure the required values described in the [Configuration](#configuration) section.

---

# Running the Application

Start the Compliance Service:

```powershell
python -m uvicorn app.main:app --reload
```

The service runs locally on:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

The Platform/Auth Service should run separately on:

```text
http://127.0.0.1:8005
```

when authentication or service-to-service authentication is being tested.

---

# Running the Scheduler

Run:

```powershell
python -m app.jobs.scheduler
```

The scheduler starts the re-screening process according to its configured schedule.

Example flow:

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
```

If authentication fails:

```text
Starting scheduled re-screen...
        ↓
Platform authentication failed
        ↓
Job stops
```

---

# Database

The project currently uses:

```text
SQLite
```

Default database:

```text
compliance.db
```

The database stores:

* Screening audit records
* Re-screening results
* Compliance cases
* Case history
* Override information

SQLite is primarily intended for development and testing.


# Environment and Security

Secrets must remain outside source control.

Recommended local setup:

```text
.env
    ↓
Environment variables
    ↓
Application configuration
```

Do not commit:

```text
.env
Real API keys
Passwords
JWT secrets
Production credentials
```

Use placeholders in `.env.example`.

---

# Known Limitations

## External Sanctions Providers

OFAC, UN, and EU data depend on external providers.

If a provider is unavailable or changes its format, the refresh process may fail.

The service is designed to fail rather than silently treat missing required sanctions data as clean.

---

## SQLite

SQLite is currently used for development and testing.

A production deployment should use a production-grade database and an appropriate migration strategy.

---

## Re-Screening Data

Re-screening depends on existing audit records.

If there are no previously cleared entities, the job correctly reports zero entities to re-screen.

---

## Fuzzy Matching

Fuzzy matching can produce false positives because similar names do not always represent the same entity.

The matching threshold, risk-based thresholds, deduplication, and false-positive override mechanisms help manage these cases.

---

## Service API Key

Scheduled re-screening requires successful authentication with the Platform/Auth Service.

The real service API key must remain outside source control.

Automated tests should use mocked/dummy credentials rather than real secrets.

---

# Development Notes

For local development:

```text
Compliance Service
    ↓
127.0.0.1:8000

Platform/Auth Service
    ↓
127.0.0.1:8005
```

Fixture mode can be used for deterministic local testing:

```powershell
$env:USE_FIXTURES="true"
```

Live sanctions downloads can be tested using:

```powershell
$env:USE_FIXTURES="false"
python -m pytest -m integration -v -s
```

---

# Current Implementation Summary

The current Round 6 implementation includes:

```text
✓ OFAC screening
✓ UN screening
✓ EU screening
✓ Internal Watchlist screening
✓ PEP screening

✓ Source attribution
✓ Match deduplication
✓ Exact matching
✓ Fuzzy matching

✓ Sanctions risk scoring
✓ Country risk
✓ Transaction-value risk
✓ Risk-based screening tiers
✓ Tier-specific matching thresholds
✓ Configurable risk weights

✓ Audit history
✓ Audit analytics
✓ False-positive overrides
✓ Bulk screening

✓ Compliance case management
✓ Case assignment
✓ Case state machine
✓ Case history
✓ Resolution reasons
✓ Closed-case reassignment protection

✓ Compliance reporting

✓ Sanctions data refresh
✓ Re-screening
✓ Newly flagged detection
✓ Newly flagged case creation
✓ Scheduled re-screening

✓ JWT authentication
✓ Role-based authorization
✓ Platform Service integration
✓ Service API-key authentication
✓ Fail-closed authentication

✓ Fixture-based testing
✓ Authentication testing
✓ Re-screening testing
✓ Integration testing
✓ Performance testing
```