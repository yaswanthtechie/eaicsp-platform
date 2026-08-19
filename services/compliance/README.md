# Compliance Screening Service

A FastAPI-based sanctions compliance service for screening suppliers and customers against multiple sanctions lists, calculating risk scores, maintaining audit history, supporting overrides, and periodically re-screening previously cleared entities.

 Features

 1. Sanctions Screening

The service screens entity names against:

* OFAC sanctions data
* UN sanctions data
* EU sanctions data

It supports:

* Exact name matching
* Normalized name matching
* Fuzzy name matching using RapidFuzz
* Matched-list identification
* Match confidence scoring
* Multiple sanctions-source matching

### 2. Sanctions Data Refresh

The service can download and reload the latest available sanctions data before a re-screening run.

The refresh flow is:

```text
Download OFAC
      ↓
Download UN
      ↓
Download EU
      ↓
Load sanctions records
      ↓
Deduplicate entities
      ↓
Build search indexes
      ↓
Ready for screening
```

The implementation uses configurable download URLs through environment variables.

### 3. Weighted Risk Score

The service calculates a weighted risk score from **0–100** instead of relying only on a binary flagged/clean result.

The configured weighting is:

| Risk factor      | Weight |
| ---------------- | -----: |
| Match confidence |    50% |
| Source coverage  |    30% |
| Listing recency  |    20% |

The risk score combines:

* Match confidence
* Number of sanctions sources that matched
* Recency of the sanctions listing

Example:

```text
Match confidence = 90
Source coverage  = 2/3
Recency score    = 80

Weighted risk score ≈ 81
```

Therefore, two entities can both be flagged but have different risk scores depending on the strength and supporting evidence of the match.



### 4. Country Risk and Overall Supplier Risk

The screening response can also include:

* Country risk score
* Overall supplier risk
* Risk-factor breakdown

These values can be stored together with the sanctions screening result in the audit database.

### 5. Audit Logging

Screening results are stored in a SQLite database using SQLAlchemy.

Audit records contain information such as:

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
* Creation timestamp

The service supports both:

```text
INITIAL
```

and:

```text
RESCREEN
```

screening types.

### 6. Audit Analytics

The service provides audit summary information including:

* Total screenings
* Total flagged screenings
* Overall flag rate
* Newly flagged count
* Initial screening count
* Re-screening count
* Flag rate over time
* Most frequently flagged entities
* Country-level screening statistics

### 7. False-Positive Overrides

The service supports overrides for entities that have been identified as false positives.

An override can affect the screening result so that an approved false positive does not continue to be treated as a sanctions match.

### 8. Ongoing Re-Screening

The service supports re-screening of entities that were previously cleared.

The re-screening flow is:

```text
Find latest audit status
        ↓
Select previously cleared entities
        ↓
Refresh sanctions lists
        ↓
Reload sanctions index
        ↓
Re-screen cleared entities
        ↓
Detect newly flagged entities
        ↓
Save RESCREEN audit information
```

Only the latest audit result for an entity is considered when determining whether the entity is currently cleared.

For example:

```text
ABC COMPANY → clean
ABC COMPANY → clean
ABC COMPANY → matched
```

The entity is **not** considered cleared because its latest status is matched.

If:

```text
ABC COMPANY → clean
ABC COMPANY → clean
```

the entity can be selected for re-screening.

### 9. Scheduled Re-Screening

A scheduler is included for automated re-screening.

The current configuration uses a **30-second interval as a mock/simulated scheduler**, which is useful for development and testing.

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

 10 .Fixture Data vs Live Data

The project supports both fixture-based testing and live sanctions-data testing.

Fixture Data

Local fixture files are used by the normal automated test suite because they are:

Small
Fast
Deterministic
Independent of external network availability

Fixture files are stored under:

app/data/fixtures/

Example:

app/data/fixtures/
├── ofac_sample.csv
├── un_sample.xml
└── eu_sample.xml
Live Data

The live integration test uses the configured external URLs.

Run:

pytest -m integration -v -s

The live test downloads:

OFAC → ofac.csv
UN   → un.xml
EU   → eu.xml

The live download test does not rely on the local fixture records for its download verification.

For production deployment, the interval can be changed to an appropriate nightly schedule.

## Technology Stack

* Python
* FastAPI
* Uvicorn
* SQLAlchemy
* SQLite
* Pydantic
* RapidFuzz
* Requests
* XMLtodict
* APScheduler
* python-dotenv
* Pytest
* HTTPX


## 500 entities

Bulk screening is optimized for high-volume screening.

Using the committed sanctions fixture dataset, the automated performance
test screened 500 entities in **26.35 ms**.

The performance test enforces a limit of **<100 ms** for screening 500 entities.

Run the benchmark with:

pytest tests/test_sanctions.py::test_bulk_screen_500_entities -s -v

## ofac recency

OFAC records without a listing date contribute to risk scoring through match confidence and source coverage; the recency component is neutral when the listing date is unavailable.

pytest tests/test_sanctions.py::test_ofac_missing_listing_date_is_handled -s -v


## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root.

Example:

```env
DATABASE_URL=sqlite:///./compliance.db

SERVICE_NAME=compliance-service

MATCH_THRESHOLD=90
DEDUPE_THRESHOLD=90

OFAC_DOWNLOAD_URL=https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV

UN_DOWNLOAD_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml

EU_DOWNLOAD_URL=https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=n002gggg
```

Do not put square brackets or parentheses around URLs in `.env`.

## Running the Application

Start the FastAPI application:

```bash
python -m uvicorn app.main:app --reload
```

The application runs at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

OpenAPI specification:

```text
http://127.0.0.1:8000/openapi.json
```

## Running the Re-Screening Scheduler

Run:

```bash
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
1 checked,
0 newly flagged,
1 still clean.
```

## Screening Flow

A typical screening request follows this flow:

```text
API Request
    ↓
Validate request
    ↓
Normalize entity name
    ↓
Exact matching
    ↓
Fuzzy matching
    ↓
Identify matched sanctions sources
    ↓
Calculate match confidence
    ↓
Calculate weighted risk score
    ↓
Apply override if applicable
    ↓
Save audit record
    ↓
Return screening response
```

## Re-Screening Flow

```text
Scheduler
    ↓
Find latest audit record for each entity
    ↓
Select entities whose latest result is clean
    ↓
Download refreshed sanctions lists
    ↓
Reload sanctions data
    ↓
Re-screen previously cleared entities
    ↓
Still clean?
   /     \
 Yes      No
 ↓         ↓
No new    Newly flagged
audit     RESCREEN audit
           ↓
        newly_flagged = true
```

## Testing

The current test suite contains tests covering:

* API behavior
* Compliance screening
* Exact and fuzzy sanctions matching
* Cross-source deduplication
* Risk scoring
* Country risk scoring
* Audit functionality
* False-positive overrides
* Bulk screening
* Re-screening
* Sanctions data refresh
* Scheduler behavior

Run the complete test suite:

```bash
pytest
```

Run the live sanctions download integration test separately:

pytest -v tests/test_live_download.py -s
Latest live-download result:

1 passed, 1 warning

Collect tests without executing them:

pytest --collect-only -q

app/data/fixtures/
├── ofac_sample.csv
├── un_sample.xml
└── eu_sample.xml


To explicitly enable fixture-based screening in the current PowerShell session:

```powershell
$env:USE_FIXTURES="true"
```

Verify the setting:

```powershell
$env:USE_FIXTURES
```

Expected output:
true

Run a sanctions test:

```powershell
pytest -v tests/test_sanctions.py::test_exact_match -s
```

The test output should contain:


Using local sanctions fixtures
Loading OFAC fixture
Loaded 9 OFAC fixture records
Loading UN fixture
Loaded 11 UN fixture records
Loading EU fixture
Loaded 10 EU fixture records
Total fixture records: 30
...
PASSED
```

This confirms that the application is loading the local OFAC, UN, and EU fixture datasets correctly.

### Live Sanctions Download Testing

The project also includes a separate integration test that verifies the current OFAC, UN, and EU sanctions lists can be downloaded successfully.

The live test is marked with:

```python
@pytest.mark.integration
```

The integration test is excluded from the normal fixture-loading setup in `tests/conftest.py`, allowing it to test the real download path independently.

Before running the live-download test, disable fixture mode:

```powershell
$env:USE_FIXTURES="false"
```

Verify:

```powershell
$env:USE_FIXTURES
```

Expected output:

false

Run:

powershell
pytest -v tests/test_live_download.py -s


A successful live test loads the current sanctions data and downloads:


ofac.csv
un.xml
eu.xml


Example output:

Loading OFAC
Loaded 19202 OFAC records
Loading UN
Loaded 736 UN records
Loading EU
Loaded 6234 EU records

Downloading ofac.csv...
Downloaded ofac.csv
Downloading un.xml...
Downloaded un.xml
Downloading eu.xml...
Downloaded eu.xml

All sanctions lists downloaded successfully.
PASSED





## Database

The service uses SQLite through SQLAlchemy.

The configured database is:

compliance.db


The database stores compliance audit history, including both initial screenings and re-screening results.

To inspect the audit table using Python:

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


## Important Implementation Notes

### Latest Audit Status

The re-screening process does not simply search for records where `matched=False`.

It first identifies the latest audit record for each entity.

This prevents an entity that was previously clean but later matched from being incorrectly selected for re-screening.

### Newly Flagged Entity

An entity is considered newly flagged when:

```text
Previous latest result = clean
Current re-screening result = matched
```

The resulting audit record is stored with:

```text
screening_type = RESCREEN
newly_flagged = true
```

### Clean Re-Screen

If a previously cleared entity is still clean during re-screening, the re-screening result is reported as still clean.

### Scheduler Concurrency

The scheduler uses:

```text
max_instances = 1
```

to prevent overlapping re-screening jobs.

If a refresh takes longer than the configured interval, the next scheduled execution can be skipped until the existing execution finishes.

## Requirements

The project dependencies are pinned in `requirements.txt`.

The current environment includes packages such as:

```text
fastapi==0.141.1
uvicorn==0.52.2
SQLAlchemy==2.0.52
pydantic==2.13.4
RapidFuzz==3.14.5
xmltodict==1.0.4
requests==2.34.2
httpx==0.28.1
pytest==9.1.1
python-dotenv==1.2.2
APScheduler==3.11.3
```



# Blockers / Known Limitations

The following items are current blockers or limitations of the Compliance Service implementation:

1. **Sanctions source availability**

   * OFAC, UN, and EU sanctions lists are downloaded from external sources.
   * If any source is unavailable, returns an error, or changes its format/API, the refresh process may fail.
   * The EU sanctions source may require a valid access token/configuration depending on the endpoint being used.

2. **Database migration**

   * The project currently uses SQLite for development/testing.
   * Changes to the `ComplianceAudit` model require the database schema to be updated accordingly.
   * Existing databases may need to be recreated or migrated when new columns are added.

3. **Scheduler is a mock scheduled job**

   * The re-screening scheduler currently runs using APScheduler with a short interval for testing.
   * Production deployment should use an appropriate daily/nightly schedule.
   * Only one scheduler instance should run at a time to avoid duplicate re-screening jobs.

4. **Re-screening depends on existing audit data**

   * Only entities with a latest clean audit record can be selected for re-screening.
   * If there are no previously-cleared entities in the database, the re-screening job correctly reports zero entities to process.

5. **External sanctions refresh can take time**

   * A re-screening run first downloads and reloads the sanctions lists.
   * Because this is an external network operation, the scheduler may take longer than the configured interval.
   * APScheduler can therefore report that a subsequent execution was skipped because the previous instance is still running.

6. **Risk score depends on sanctions metadata**

   * The weighted risk score combines match confidence, source coverage, and listing recency.
   * The quality of the score depends on the availability and correctness of these fields in the sanctions data.
   * Missing data may result in a lower/default contribution for that factor.

7. **Fuzzy matching can produce false positives**

   * RapidFuzz improves matching of similar names but cannot guarantee that two similar names represent the same entity.
   * The configured matching threshold and override mechanism are therefore important for handling potential false positives.

8. **Country-risk data**

   * The overall supplier risk calculation can include country risk when country-risk data is available.
   
9. **Development database only**

   * SQLite is suitable for the current development/testing setup.
   * A production deployment should use the project's intended production database configuration and proper migration management.


