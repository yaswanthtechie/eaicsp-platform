# Compliance Screening Service

This project is a **Compliance Screening Service** developed using **FastAPI**.

The main purpose of this service is to screen supplier and customer entities against sanctions lists, internal watchlists, and PEP data.

The service provides:

* Sanctions screening
* Internal watchlist and PEP screening
* Exact and fuzzy name matching
* Risk-based screening
* Country risk assessment
* Transaction-value risk assessment
* Audit history and analytics
* False-positive overrides
* Bulk screening
* Case management
* Compliance reporting
* Sanctions data refresh
* Scheduled re-screening
* JWT authentication
* Role-based authorization
* Service-to-service authentication

The service uses **SQLite with SQLAlchemy** for audit and case-management data.

---

# Features

## Sanctions Screening

The service checks entity names against multiple sources:

```text
OFAC
UN
EU
Internal Watchlist
PEP
```

All sources are combined into a single screening process.

The matching process includes:

```text
Request
   ↓
Validate Input
   ↓
Normalize Entity Name
   ↓
Search Sanctions and Watchlists
   ↓
Exact/Fuzzy Matching
   ↓
Deduplicate Matches
   ↓
Calculate Confidence
   ↓
Calculate Risk
   ↓
Check Override
   ↓
Create Case if Flagged
   ↓
Save Audit Record
   ↓
Return Response
```

Fuzzy matching uses **RapidFuzz WRatio**.

The matching threshold is configurable:

```env
MATCH_THRESHOLD=90
```

---

# Source Attribution and Deduplication

When an entity matches more than one source, the response identifies the matching sources.

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

Similar records from different sources are deduplicated using:

```env
DEDUPE_THRESHOLD=90
```

This prevents the same entity from being treated as multiple unrelated matches.

---

# Risk-Based Screening

The service calculates a risk score instead of returning only `matched` or `clean`.

Risk calculation considers factors such as:

* Match confidence
* Source coverage
* Listing recency
* Country risk
* Transaction value

## Sanctions Risk Score

The sanctions risk score uses:

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

The weights are configurable through environment variables.

## Overall Supplier Risk

The sanctions risk can be combined with country risk.

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

# Risk-Based Screening Tiers

The screening process can apply different levels of screening depending on risk.

Risk can be influenced by:

* Country risk
* Transaction value
* Sanctions risk

Configuration:

```env
LOW_COUNTRY_RISK_MAX=39
MEDIUM_COUNTRY_RISK_MAX=69

LOW_TRANSACTION_VALUE_MAX=1000000
MEDIUM_TRANSACTION_VALUE_MAX=5000000
```

The configuration allows risk rules to be changed without modifying application code.

---

# Country Risk

The screening result can contain:

* Country
* Country risk score
* Risk factors
* Overall supplier risk

Country risk is combined with sanctions risk to calculate the overall supplier risk.

---

# Case Management

Flagged screening results can be converted into compliance cases.

Case management allows compliance users to:

* Create cases
* Assign cases
* Start reviews
* Clear cases
* Confirm cases
* Record resolution reasons
* Add comments
* Maintain case history

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

Invalid state transitions are rejected.

## Case History

Important case actions are recorded in the case history.

History can contain:

* Previous status
* New status
* User/system responsible
* Reason
* Comments
* Timestamp

This provides an audit trail for compliance decisions.

---

# Compliance Reporting

The service provides a compliance summary report.

Endpoint:

```text
GET /api/v1/compliance/reports/compliance-summary
```

The report provides information such as:

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

The reporting endpoint requires the:

```text
compliance_officer
```

role.

---

# Audit

Each screening request is stored in the audit database.

The service uses:

```text
SQLite
SQLAlchemy
```

Audit information can include:

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

Screening types include:

```text
INITIAL
RESCREEN
```

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

It can provide:

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

Fuzzy matching can sometimes identify an entity that is not the actual sanctioned entity.

The service supports approved false-positive overrides.

Override information can include:

* Entity name
* Matched name
* Source
* Reason
* Reviewed by
* Created timestamp

Available endpoints:

```text
POST   /api/v1/compliance/override
GET    /api/v1/compliance/override
GET    /api/v1/compliance/overrides
DELETE /api/v1/compliance/override
```

These operations are protected using the `compliance_officer` role.

---

# Bulk Screening

The service supports screening multiple entities in a single request.

Bulk screening preserves the input order.

The service also includes performance testing for large batches.

Example performance test:

```powershell
python -m pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

The target performance is:

```text
< 100 ms
```

Actual performance depends on the machine, Python environment, dataset, and system load.

---

# Sanctions Data

Sanctions data is available from:

```text
OFAC
UN
EU
```

Additional screening data comes from:

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

The service can refresh sanctions data before re-screening.

The refresh process is:

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

The application should fail when required sanctions data cannot be loaded rather than silently approving all entities.

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
```

The latest audit result is used when determining whether an entity is currently cleared.

For example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
ABC COMPANY → matched
```

The latest result is `matched`, so the entity is not considered previously cleared.

If:

```text
ABC COMPANY → clean
ABC COMPANY → clean
```

the entity can be selected for re-screening.

## Newly Flagged

An entity is newly flagged when:

```text
Previous result = clean
Current result = matched
```

The audit record contains:

```text
screening_type = RESCREEN
newly_flagged = true
```

---

# Scheduled Re-Screening

The service uses **APScheduler** to run re-screening automatically.

The scheduled process:

1. Authenticates with the Platform Service.
2. Refreshes sanctions data.
3. Finds previously cleared entities.
4. Re-screens those entities.
5. Saves the results.
6. Identifies newly flagged entities.

The scheduler controls **when** the job runs.

The re-screening service controls **what happens during the job**.

For development/testing, a short interval can be configured.

Production should use an appropriate nightly schedule.

The scheduler uses:

```text
max_instances=1
```

to prevent multiple copies of the same job from running at the same time.

---

# Service-to-Service Authentication

The scheduled re-screening process is a system process rather than a human user.

Therefore, it does not use a human JWT.

Instead, the Compliance Service authenticates with the Platform/Auth Service using a service API key.

The Platform/Auth Service runs on:

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

The flow is:

```text
Scheduled Job
      ↓
Authenticate with Platform
      ↓
Platform verifies API key
      ↓
Authentication successful?
      ↓
   Yes ─────────────→ Run re-screening
      |
     No
      ↓
Stop the job
```

A successful response looks like:

```json
{
  "authenticated": true,
  "service": "compliance",
  "auth_type": "api_key"
}
```

If authentication fails, the re-screening process does not continue.

This provides **fail-closed behavior**.

---

# Service API Key Configuration

The real service API key is stored locally in `.env`:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
PLATFORM_SERVICE_API_KEY=<real-secret>
```

The real API key must **never be committed to Git**.

The `.env.example` file should contain only:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
PLATFORM_SERVICE_API_KEY=your-compliance-service-api-key
```

The `.env` file should be included in `.gitignore`.

The service API key must not be printed in logs or included in documentation.

---

# Authentication and Authorization

The Compliance Service integrates with the Platform/Auth Service for user authentication and authorization.

Human users authenticate using JWT access tokens.

The general flow is:

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

The main role used by the Compliance Service is:

```text
compliance_officer
```

Typical authentication responses are:

```text
Missing token
    → 401 Unauthorized

Invalid/expired token
    → 401 Unauthorized

Valid token but wrong role
    → 403 Forbidden

Platform unavailable
    → 503 Service Unavailable
```

---

# Protected Compliance Operations

Role-protected operations use the:

```text
compliance_officer
```


# Authentication Request Logging

Authentication requests can include tracing information such as:

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

This helps trace requests between the Compliance Service and Platform Service.

---

# Fixture Data

Automated tests use local fixture data.

This makes tests:

* Faster
* Stable
* Independent of external internet access
* Easier to reproduce

Enable fixture mode:

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

```powershell
python -m pytest -q
```

The current test suite has been verified successfully.

## Authentication Tests

```powershell
python -m pytest -q tests/test_auth_integration.py
```

## Scheduled Job Authentication Tests

```powershell
python -m pytest tests/test_rescreen_auth.py -v
```



## Risk Configuration Tests

```powershell
python -m pytest -q tests/test_risk_config.py
```

## Live Download Tests

```powershell
$env:USE_FIXTURES="false"
python -m pytest -m integration -v -s
```

## Collect Tests

```powershell
python -m pytest --collect-only -q
```

---

# Installation

## Create Virtual Environment

```powershell
python -m venv venv
```

## Activate Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

## Install Dependencies

```powershell
pip install -r requirements.txt
```

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

Do not put the real API key in `.env.example`, README files, or Git.

URLs in `.env` must be written directly.

Do not use Markdown formatting around URLs.

---

# Running the Application

Start the Compliance Service:

```powershell
python -m uvicorn app.main:app --reload
```

The service runs on:

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

when authentication testing is required.

---

# Running the Scheduler

Run:

```powershell
python -m app.jobs.scheduler
```

The scheduler starts the re-screening process according to its configured schedule.

Example flow:

```text
Starting nightly re-screen...
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
```

If authentication fails:

```text
Starting nightly re-screen...
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

Database file:

```text
compliance.db
```

The database stores:

* Screening audit records
* Re-screening results
* Case information
* Case history

---

# Known Limitations

### External Sanctions Sources

OFAC, UN, and EU data depend on external providers.

If a provider is unavailable or changes its format, the refresh process may fail.

### SQLite

SQLite is currently used for development and testing.

A production deployment should use a production-grade database and migration strategy.


### Re-Screening Data

Re-screening depends on existing audit records.

If there are no previously cleared entities, the job correctly reports zero entities to re-screen.

### Fuzzy Matching

Fuzzy matching can produce false positives because similar names do not always represent the same entity.

The matching threshold and false-positive override mechanism help manage these cases.

### Service API Key

The scheduled re-screening job requires successful service authentication with Platform/Auth.

The real API key must remain outside source control.




The Compliance Screening Service currently supports:

```text
✓ OFAC screening
✓ UN screening
✓ EU screening
✓ Internal Watchlist screening
✓ PEP screening
✓ Source attribution
✓ Deduplication
✓ Exact matching
✓ Fuzzy matching
✓ Risk-based screening
✓ Country risk
✓ Transaction-value risk
✓ Configurable risk weights
✓ Audit history
✓ Audit analytics
✓ False-positive overrides
✓ Bulk screening
✓ Case management
✓ Case state machine
✓ Case history
✓ Compliance reporting
✓ Sanctions data refresh
✓ Re-screening
✓ Newly flagged detection
✓ Scheduled re-screening
✓ JWT authentication
✓ Role-based authorization
✓ Platform Service integration
✓ Service API-key authentication
✓ Authentication failure handling
✓ Fixture-based testing
✓ Live download testing
✓ Authentication testing
✓ Performance testing
```
