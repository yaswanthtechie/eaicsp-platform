# Compliance Screening Service

This project is a **Compliance Screening Service** developed using **FastAPI**.

The main purpose of this service is to check supplier or customer names against sanctions lists such as **OFAC, UN, and EU**.

The service also provides:

* Exact and fuzzy name matching
* Risk score calculation
* Country risk assessment
* Audit history and analytics
* False-positive overrides
* Bulk screening
* Re-screening of previously cleared entities
* Sanctions data refresh
* Scheduled re-screening
* JWT authentication and role-based authorization

The service uses **SQLite with SQLAlchemy** to store audit information.

---

## Features

### 1. Sanctions Screening

The service checks entity names against three sanctions sources:

```text
OFAC
UN
EU
```

The matching process first normalizes the entity name and performs an exact match. If an exact match is not found, fuzzy matching is performed using **RapidFuzz WRatio**.

The screening flow is:

```text
Request
   ↓
Validate input
   ↓
Normalize entity name
   ↓
Exact match
   ↓
Fuzzy match
   ↓
Find matching sanctions lists
   ↓
Calculate confidence
   ↓
Calculate sanctions risk score
   ↓
Calculate country/overall supplier risk
   ↓
Check override
   ↓
Save audit record
   ↓
Return response
```

The matching threshold is configurable through the environment.

Current value:

```env
MATCH_THRESHOLD=90
```

---

## 2. Sanctions Data

The service supports sanctions data from:

```text
OFAC
UN
EU
```

Sanctions data can be loaded either from local fixture files or from configured live download URLs.

For local testing, fixture files are stored in:

```text
app/data/fixtures/

├── ofac_sample.csv
├── un_sample.xml
└── eu_sample.xml
```

---

## 3. Sanctions Data Refresh

Before a re-screening run, the service can refresh the sanctions data.

The refresh flow is:

```text
Download OFAC
      ↓
Download UN
      ↓
Download EU
      ↓
Load records
      ↓
Remove duplicates
      ↓
Build indexes
      ↓
Ready for screening
```

The download URLs are configured through the `.env` file rather than being hardcoded in the application.

---

## 4. Risk Score

The service calculates a **sanctions risk score from 0 to 100** instead of returning only `flagged` or `clean`.

### Sanctions Risk Score

The sanctions risk score uses three factors:

| Risk Factor      | Weight |
| ---------------- | -----: |
| Match confidence |    50% |
| Source coverage  |    30% |
| Listing recency  |    20% |

The weights are configurable through environment variables:

```env
CONFIDENCE_WEIGHT=0.50
SOURCE_WEIGHT=0.30
RECENCY_WEIGHT=0.20
```

The calculation is:

```text
Sanctions Risk Score =

    Match Confidence × 50%
  + Source Coverage × 30%
  + Listing Recency × 20%
```

For example:

```text
Match confidence = 80
Source coverage  = 66.67
Recency          = 50

Risk score ≈ 70
```

Therefore, two entities can both be flagged while having different risk scores.

### Overall Supplier Risk

The service can also combine the sanctions risk score with the country risk score.

The current configuration is:

```env
SANCTIONS_WEIGHT=0.80
COUNTRY_RISK_WEIGHT=0.20
UNKNOWN_COUNTRY_RISK=50.0
```

The overall supplier risk is calculated as:

```text
Overall Supplier Risk =

    Sanctions Risk × 80%
  + Country Risk × 20%
```

Both the sanctions risk weights and the overall supplier risk weights are configurable through environment variables.

---

## 5. Country Risk

The screening result can also contain country-related risk information.

The response and audit record can include:

* Country
* Country risk score
* Risk-factor details
* Overall supplier risk

Country risk can be combined with the sanctions risk score to produce the overall supplier risk.

---

## 6. Audit

Each screening request is recorded in the audit database.

The service currently uses:

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
* Matched sanctions lists
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

There are two main screening types:

```text
INITIAL
RESCREEN
```

---

## 7. Audit Summary

The service provides an audit summary endpoint for compliance analytics.

It can return information such as:

* Total screenings
* Total flagged screenings
* Overall flag rate
* Newly flagged entities
* Initial screenings
* Re-screenings
* Flag rate over time
* Frequently flagged entities
* Country-level statistics

The endpoint is protected and requires the:

```text
compliance_officer
```

role.

Endpoint:

```text
GET /api/v1/compliance/audit/summary
```

---

## 8. False-Positive Override

Fuzzy matching can sometimes identify an entity that is not actually the sanctioned entity.

To handle approved false positives, the service supports **false-positive overrides**.

An approved override can prevent a known false positive from continuing to be treated as a sanctions match.

Override information includes:

* Entity name
* Matched name
* Source
* Reason
* Reviewed by
* Created timestamp

The override endpoints require the `compliance_officer` role.

Available endpoints:

```text
POST   /api/v1/compliance/override
GET    /api/v1/compliance/override
GET    /api/v1/compliance/overrides
DELETE /api/v1/compliance/override
```

The delete operation is also protected because removing an override can change a compliance screening outcome.

---

## 9. Re-Screening

The service supports re-screening entities that were previously cleared.

The basic process is:

```text
Find latest audit result
        ↓
Identify previously cleared entities
        ↓
Refresh sanctions data
        ↓
Reload sanctions index
        ↓
Screen the entity again
        ↓
Compare the new result
        ↓
Save RESCREEN audit
```

The implementation uses the **latest audit result** for an entity when deciding whether it should be re-screened.

For example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
ABC COMPANY → matched
```

The entity is currently matched because its latest result is matched.

Therefore, it should not be selected as a previously-cleared entity.

Another example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
```

The latest result is clean, so the entity can be selected for re-screening.

### Newly Flagged Entity

An entity is considered newly flagged when:

```text
Previous latest result = clean
Current re-screening result = matched
```

The new audit record is stored as:

```text
screening_type = RESCREEN
newly_flagged = true
```

If the entity remains clean after re-screening, the result is recorded as still clean.

---

## 10. Scheduled Re-Screening Job

A scheduled re-screening job is provided using **APScheduler**.

The current development/test configuration uses a 30-second interval to simulate a nightly re-screening process.

The scheduled job:

1. Runs inside the Compliance Service process.
2. Refreshes the sanctions data.
3. Re-screens previously cleared entities.
4. Stores the new results in the audit database.
5. Identifies newly flagged entities.

### Scheduled Job Authentication

The nightly re-screening job runs **in-process through APScheduler**.

It directly calls:

```python
nightly_rescreen_job()
```

from the service layer.

It does **not** make an HTTP request to the Compliance API.

Therefore:

* It does not call the Compliance API endpoints.
* It does not pass through `verify_token`.
* It does not use a JWT.
* It does not require a separate credential.
* It is treated as a trusted internal process because it runs inside the Compliance Service itself.

This is an intentional design decision for the current architecture.

If the scheduled job is moved to a separate worker, container, or external cron service in the future, it will need its own authenticated identity before calling protected APIs.

Possible approaches include:

```text
Service account registered in Platform Service
```

or, if introduced by the platform architecture:

```text
API key
```

---

## 11. Scheduler

The current scheduler configuration uses a short interval for development and testing:

```python
scheduler.add_job(
    nightly_rescreen_job,
    "interval",
    seconds=30,
    id="nightly_rescreen",
    max_instances=1,
    replace_existing=True,
)
```

`max_instances=1` prevents multiple re-screening jobs from running simultaneously.

The current 30-second interval is only a simulation of a nightly job.

For production, the scheduler should use an appropriate daily/nightly schedule.

---

## 12. Authentication and Authorization

The Compliance Service is integrated with the **Platform Service** for authentication and authorization.

The Platform Service is responsible for:

* User login
* JWT creation
* Token verification
* User roles

The authentication flow is:

```text
Client
  ↓
Compliance API
  ↓
Send JWT to Platform Service
  ↓
Platform verifies token
  ↓
Compliance checks user role
  ↓
Allow / Reject request
```

The Platform Service currently runs on:

```text
http://127.0.0.1:8005
```

The Compliance Service uses:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

### Required Role

Protected Compliance API endpoints require:

```text
compliance_officer
```

### Protected Endpoints

All current Compliance API endpoints require authentication and the `compliance_officer` role:

```text
POST   /api/v1/compliance/screen
POST   /api/v1/compliance/screen-bulk

GET    /api/v1/compliance/audit
GET    /api/v1/compliance/audit/summary

POST   /api/v1/compliance/override
GET    /api/v1/compliance/override
GET    /api/v1/compliance/overrides
DELETE /api/v1/compliance/override
```

### Authentication Responses

If the authentication token is missing:

```text
401 Unauthorized
```

If the token is invalid or expired:

```text
401 Unauthorized
```

If the token is valid but the user does not have the required role:

```text
403 Forbidden
```

If the Platform Service is unavailable or times out:

```text
503 Service Unavailable
```

The Compliance Service sends the JWT to the Platform Service for verification and includes request tracing information.

---

## 13. Authentication Request Logging

The Compliance Service sends request metadata to the Platform Service when requesting token verification.

The request information can include:

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

The Compliance Service sends headers such as:

```text
X-Caller-Service
X-Caller-Endpoint
X-Request-ID
```

This makes it easier to trace authentication requests between the Compliance Service and Platform Service.

---

## 14. Fixture Data

Normal automated tests use local fixture data.

This makes the tests:

* Faster
* Stable
* Independent of external internet access
* Easier to reproduce

Fixture mode can be enabled in PowerShell:

```powershell
$env:USE_FIXTURES="true"
```

To check the value:

```powershell
$env:USE_FIXTURES
```

Expected value:

```text
true
```

---

## 15. Live Sanctions Download Test

A separate integration test is available for checking live sanctions downloads.

The test is marked with:

```python
@pytest.mark.integration
```

To run the integration test:

```powershell
$env:USE_FIXTURES="false"
pytest -m integration -v -s
```

The live test checks the configured downloads for:

```text
OFAC
UN
EU
```

Live download tests depend on the external sanctions providers being available.

---

## 16. Bulk Screening

The service supports screening multiple entities in a single request.

Bulk screening is also tested for performance.

The current performance test screens **500 entities** using the committed fixture dataset.

Run the performance test with:

```powershell
pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

The performance target is:

```text
< 100 ms
```

The latest local test run completed in approximately:

```text
26.35 ms
```

Actual performance can vary depending on the machine, Python environment, dataset, and system load.

---

# Technology Stack

The main technologies used in this project are:

```text
Python
FastAPI
Uvicorn
SQLAlchemy
SQLite
Pydantic
RapidFuzz
Requests
XMLtodict
APScheduler
python-dotenv
Pytest
HTTPX
python-jose
```

---

# Installation

## 1. Create a Virtual Environment

```powershell
python -m venv venv
```

## 2. Activate the Virtual Environment

```powershell
.\venv\Scripts\Activate.ps1
```

## 3. Install Dependencies

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

MATCH_THRESHOLD=90
DEDUPE_THRESHOLD=90

CONFIDENCE_WEIGHT=0.50
SOURCE_WEIGHT=0.30
RECENCY_WEIGHT=0.20

SANCTIONS_WEIGHT=0.80
COUNTRY_RISK_WEIGHT=0.20
UNKNOWN_COUNTRY_RISK=50.0

PLATFORM_AUTH_URL=http://127.0.0.1:8005

OFAC_DOWNLOAD_URL=https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV

UN_DOWNLOAD_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml

EU_DOWNLOAD_URL=
```

### EU Download URL

The EU sanctions source may require a configured access token depending on the source endpoint.

Do not commit access tokens or other credentials to the repository.

If an EU download URL requires a token, configure the complete URL locally in `.env`:

```env
EU_DOWNLOAD_URL=<your-configured-eu-download-url>
```

Keep `.env` out of source control.

### URL Formatting

URLs inside `.env` files should be written directly.

Do not add Markdown formatting such as:

```text
[URL](URL)
```

---

# Running the Application

Start the FastAPI server:

```powershell
python -m uvicorn app.main:app --reload
```

The Compliance Service will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

The Platform Service should also be running separately on:

```text
http://127.0.0.1:8005
```

when testing protected endpoints.

---

# Running the Scheduler

Run the scheduler with:

```powershell
python -m app.jobs.scheduler
```

Example output:

```text
Rescreen scheduler started...

Starting nightly re-screen...

Downloading ofac.csv...
Downloaded ofac.csv

Downloading un.xml...
Downloaded un.xml

Downloading eu.xml...
Downloaded eu.xml

All sanctions lists downloaded successfully.

Re-screen completed:

1 checked
0 newly flagged
1 still clean
```

The exact output depends on the available sanctions data and current audit records.

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

The audit table stores both initial screening and re-screening results.

For example, the audit table can be inspected using Python:

```python
import sqlite3

connection = sqlite3.connect("compliance.db")

rows = connection.execute(
    """
    SELECT
        id,
        entity_name,
        matched,
        screening_type,
        newly_flagged
    FROM compliance_audit
    ORDER BY id
    """
).fetchall()

for row in rows:
    print(row)

connection.close()
```

---

# Testing

## Run All Tests

```powershell
pytest -v
```


## Run Authentication Tests

```powershell
pytest -q tests/test_auth_integration.py
```

Authentication coverage includes:

```text
Missing token              → 401
Invalid token              → 401
Compliance officer         → Success
Wrong role                 → 403
Authentication timeout     → 503
Authentication unavailable → 503
```

## Run Risk Configuration Tests

```powershell
pytest -q tests/test_risk_config.py
```

## Run Live Download Tests

```powershell
pytest -m integration -v -s
```

## Collect Tests Without Running

```powershell
pytest --collect-only -q
```

---

# Known Limitations

### 1. External Sanctions Sources

OFAC, UN, and EU data are downloaded from external sources.

If an external source is unavailable or changes its format, the refresh process may fail.

The EU source may also require the correct URL or access-token configuration.

Credentials or tokens should be configured locally and should not be committed to the repository.

### 2. SQLite

SQLite is currently used for development and testing.

For production deployment, a production-grade database and proper migration process should be used.

### 3. Scheduler

The current scheduler uses a short 30-second interval for development and testing.

A proper nightly schedule should be used in production.

### 4. Re-Screening Data

Re-screening depends on existing audit records.

If there are no previously cleared entities, the job correctly reports that there are no entities to re-screen.

### 5. Fuzzy Matching

Fuzzy matching can sometimes produce false positives because similar names do not always represent the same entity.

The matching threshold and false-positive override mechanism are therefore important.

### 6. Missing Sanctions Metadata

Risk scoring depends on the information available in the sanctions data.

If listing dates or other metadata are missing, the corresponding risk factor may use a neutral or default value.

### 7. Database Schema Changes

If the audit model is changed by adding or removing columns, the existing SQLite database may need to be recreated or migrated.

### 8. Scheduled Job Authentication

The current scheduled re-screening job is an internal in-process operation and therefore does not use JWT authentication.

If the job is moved outside the Compliance Service and starts calling protected HTTP endpoints, an explicit service identity and authentication mechanism will be required.

---

# Current Status

The Compliance Screening Service currently supports:

```text
✓ OFAC screening

✓ UN screening

✓ EU screening

✓ Exact matching

✓ Fuzzy matching using RapidFuzz

✓ Deduplication

✓ Weighted sanctions risk scoring

✓ Configurable risk weights

✓ Country risk

✓ Overall supplier risk

✓ Audit history

✓ Audit analytics

✓ False-positive overrides

✓ Bulk screening

✓ Re-screening

✓ Newly flagged detection

✓ Sanctions data refresh

✓ Scheduled re-screening

✓ Fixture-based testing

✓ Live download testing

✓ JWT authentication integration

✓ Platform Service token verification

✓ Role-based authorization

✓ Protected compliance endpoints

✓ Authentication request logging

✓ 500-entity performance testing

✓ Authentication timeout/unavailable handling
```

