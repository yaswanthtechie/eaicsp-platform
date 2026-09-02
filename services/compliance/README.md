# Compliance Screening Service

This project is a **Compliance Screening Service** developed using **FastAPI**.

The main purpose of this service is to check supplier or customer names against different sanctions lists such as **OFAC, UN, and EU**.

Along with screening, the service also handles:

* Exact and fuzzy name matching
* Risk score calculation
* Country risk
* Audit history
* False-positive overrides
* Bulk screening
* Re-screening of previously cleared entities
* Sanctions data refresh
* Scheduled re-screening

The service runs on **FastAPI** and stores audit information in **SQLite using SQLAlchemy**.

---

## Features

### 1. Sanctions Screening

The service checks entity names against three sanctions sources:

* OFAC
* UN
* EU

The matching process first normalizes the name and then checks for an exact match. If an exact match is not found, fuzzy matching is performed using **RapidFuzz WRatio**.

The screening process is basically:

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
Calculate risk score
   ↓
Check override
   ↓
Save audit record
   ↓
Return response
```

The matching threshold can be changed through configuration.

Current value:

```text
MATCH_THRESHOLD=90
```

---

### 2. Sanctions Data

The service supports sanctions data from:

```text
OFAC
UN
EU
```

The data can either come from local fixture files or from the configured live download URLs.

For local testing, the fixture files are stored in:

```text
app/data/fixtures/
├── ofac_sample.csv
├── un_sample.xml
└── eu_sample.xml
```

---

### 3. Sanctions Data Refresh

Before a re-screening run, the service can refresh the sanctions data.

The flow is:

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

The download URLs are configured through the `.env` file, so they do not need to be hardcoded in the application.

---

## 4. Risk Score

Instead of only returning `flagged` or `clean`, the service calculates a **risk score from 0 to 100**.

The current configuration is:

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

The calculation uses:

```text
Risk Score =
    Match Confidence × 50%
  + Source Coverage × 30%
  + Recency × 20%
```

For example:

```text
Match confidence = 80
Source coverage  = 66.67
Recency          = 50

Risk score ≈ 70
```

This means two entities can both be flagged but still have different risk scores.

---

## 5. Country Risk

The screening result can also contain country-related risk information.

The response can include:

* Country risk score
* Overall supplier risk
* Risk-factor details

These values can also be stored in the audit database along with the screening result.

---

## 6. Audit

Every screening result can be stored in the audit database.

The database currently uses:

```text
SQLite
SQLAlchemy
```

Audit information includes things such as:

* Entity name
* Country
* Match status
* Matched name
* Matched sanctions lists
* Match score
* Risk score
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

The service also provides an audit summary endpoint.

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

The audit summary endpoint is protected and requires the:

```text
compliance_officer
```

role.

---

## 8. False-Positive Override

Sometimes a fuzzy match may identify an entity that is actually not the sanctioned entity.

For this reason, the service supports **false-positive overrides**.

An approved override can prevent the same known false positive from continuing to be treated as a sanctions match.

Override information includes:

* Entity name
* Matched name
* Source
* Reason
* Reviewed by
* Created timestamp

The override creation and lookup endpoints are protected using the `compliance_officer` role.

---

## 9. Re-Screening

The service supports re-screening entities that were previously cleared.

The basic process is:

```text
Find latest audit result
        ↓
Check whether entity is currently clean
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

An important part of the implementation is that the service looks at the **latest audit result** for an entity.

For example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
ABC COMPANY → matched
```

The entity is considered **matched**, because the latest result is matched.

It should not be selected as a previously-cleared entity.

Another example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
```

The latest result is clean, so the entity can be selected for re-screening.

---

## 10. Newly Flagged Entity

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

If the entity is still clean after re-screening, it is recorded as still clean.

---

## 11. Scheduler

A scheduler is included for testing the re-screening process.

The current setup uses a **30-second interval** as a mock/simulated nightly scheduler.

```python
scheduler.add_job(
    nightly_rescreen_job,
    "interval",
    seconds=30,
    id="nightly_rescreen",
    max_instances=1,
    replace_existing=True,
)


`max_instances=1` is used so that two re-screening jobs do not run at the same time.

For production, this should be changed to a proper daily/nightly schedule.



## 12. Authentication

The Compliance Service is integrated with the **Platform Service** for authentication.

The Platform Service is responsible for:

* User login
* JWT creation
* Token verification
* User roles

The Compliance Service sends the access token to the Platform Service for verification.

The flow is:

```text
Client
  ↓
Compliance API
  ↓
Send JWT to Platform Service
  ↓
Verify token
  ↓
Check user role
  ↓
Allow / Reject request
```

The Platform Service is currently running on:

```text
http://127.0.0.1:8005
```

The Compliance Service uses:

```env
PLATFORM_SERVICE_URL=http://127.0.0.1:8005
```

The following endpoints currently require the `compliance_officer` role:

```text
GET  /api/v1/compliance/audit/summary
POST /api/v1/compliance/override
GET  /api/v1/compliance/override
```

If the token is missing, the service returns `401`.

If the token is valid but the user does not have the required role, the service returns `403`.

---

## 13. Request Logging

The Platform Service also logs authentication requests coming from the Compliance Service.

The request information includes:

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

This makes it easier to trace authentication requests between the two services.

---

## 14. Fixture Data

For normal automated tests, the project uses local fixture data.

This makes the tests:

* Faster
* Stable
* Independent of the internet
* Easier to reproduce

Fixture mode can be enabled in PowerShell using:

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



## 15. Live Sanctions Download Test

There is also a separate integration test for checking the live sanctions download.

The test is marked with:

```python
@pytest.mark.integration
```

To run it:

```powershell
$env:USE_FIXTURES="false"
```

Then:

run:
pytest -m integration -v -s


The live test checks downloading:

```text
ofac.csv
un.xml
eu.xml
```



---

## 16. Bulk Screening

The service supports screening multiple entities in one request.

Bulk screening is also tested for performance.

The current performance test screens **500 entities** using the committed fixture dataset.

The test can be run using:

```powershell
pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v
```

The performance test has a limit of:

```text
< 100 ms
```

The measured result in the current test run was approximately:

```text
26.35 ms
```


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


# Installation

Create a virtual environment:

```bash
python -m venv venv
```
activate environment:
.\venv\Scripts\Activate.ps1

Install the dependencies:

pip install -r requirements.txt



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

PLATFORM_SERVICE_URL=http://127.0.0.1:8005

OFAC_DOWNLOAD_URL=https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV

UN_DOWNLOAD_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml

EU_DOWNLOAD_URL=https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=n002gggg
```

URLs in `.env` should be written directly. Do not add Markdown formatting such as `[]` or `()` around them.

---

# Running the Application

Start the FastAPI server:

```powershell
python -m uvicorn app.main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```


The Platform Service should be running separately on:

```text
http://127.0.0.1:8005
```

when testing the protected endpoints.

---

# Running the Scheduler

Run:

```powershell
python -m app.jobs.scheduler
```

Example:

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

For example, the audit table can be checked using Python:

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

The test suite covers:

* API endpoints
* Exact matching
* Fuzzy matching
* Name normalization
* OFAC matching
* UN matching
* EU matching
* Cross-source matching
* Deduplication
* Risk scoring
* Configurable risk weights
* Country risk
* Audit records
* Audit summary
* False-positive overrides
* Authentication
* Role authorization
* Bulk screening
* Re-screening
* Sanctions refresh
* Scheduler behavior
* Live sanctions downloads

Run all tests:

```powershell
pytest -q
```

Run the authentication tests:

```powershell
pytest -q tests/test_auth_integration.py
```

Run the risk configuration tests:

```powershell
pytest -q tests/test_risk_config.py
```

Run the live download test:

```powershell
pytest -m integration -v -s
```

Collect tests without running them:

```powershell
pytest --collect-only -q
```

---



# Known Limitations

### 1. External Sanctions Sources

OFAC, UN, and EU data are downloaded from external sources.

If a source is unavailable or changes its format, the refresh process may fail.

The EU source may also require the correct access token or configuration.

### 2. SQLite

SQLite is currently used for development and testing.

For a production deployment, a production database and proper migration process should be used.

### 3. Scheduler

The current scheduler uses a short 30-second interval for development/testing.

A proper nightly schedule should be used in production.

### 4. Re-Screening Data

Re-screening depends on existing audit records.

If there are no previously cleared entities, the job will correctly report that there are no entities to re-screen.

### 5. Fuzzy Matching

Fuzzy matching can sometimes produce false positives because similar names do not always represent the same entity.

The matching threshold and false-positive override mechanism are therefore important.

### 6. Missing Sanctions Metadata

Risk scoring depends on the information available in the sanctions data.

If listing dates or other metadata are missing, the corresponding risk factor may use a neutral/default value.

### 7. Database Schema Changes

If the audit model is changed by adding or removing columns, the existing SQLite database may need to be recreated or migrated.

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
✓ Weighted risk scoring
✓ Country risk
✓ Audit history
✓ Audit analytics
✓ False-positive overrides
✓ Bulk screening
✓ Re-screening
✓ Sanctions data refresh
✓ Scheduled re-screening
✓ Fixture-based testing
✓ Live download testing
✓ JWT authentication integration
✓ Role-based authorization
✓ Authentication request logging
✓ 500-entity performance testing

