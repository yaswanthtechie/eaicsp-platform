# Compliance Service

A FastAPI-based Compliance Screening Service that screens suppliers and customers against multiple international sanctions lists using exact matching, fuzzy matching, alias matching, and cross-source deduplication.

The service automatically downloads sanctions data, maintains an indexed search engine for fast lookups, stores audit history in SQLite, and supports snapshot-based refresh detection.

---

# Features

- Single entity sanctions screening
- Bulk entity screening
- Exact name matching
- Alias matching
- RapidFuzz fuzzy matching
- Cross-source entity deduplication
- Automatic sanctions list download
- Sanctions refresh and snapshot comparison
- SQLite audit history
- REST API with Swagger documentation
- Performance-tested screening
- Comprehensive unit tests

---

# Technology Stack

- Python 3.14+
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- RapidFuzz
- Requests
- Pytest
- python-dotenv

---

# Project Structure

```
compliance-service/
│
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   │
│   ├── data/
│   │   ├── archive/
│   │   ├── downloads/
│   │   ├── logs/
│   │   └── snapshots/
│   │
│   ├── jobs/
│   │   └── refresh_job.py
│   │
│   ├── models/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   │   └── sources/
│   │
│   └── main.py
│
├── tests/
│
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

---

# Installation

## 1. Clone the repository

```bash
git clone <repository-url>

cd compliance-service
```

---

## 2. Create a virtual environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux/macOS

```bash
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file.

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

---

# Running the Application

Start the FastAPI server.

```bash
python -m uvicorn app.main:app --reload
```

The service automatically:

- Creates SQLite database tables
- Checks for sanctions datasets
- Downloads missing sanctions files
- Loads OFAC, UN and EU sanctions lists
- Performs cross-source deduplication
- Builds the in-memory search index

Swagger UI:

```
http://127.0.0.1:8000/docs
```

OpenAPI:

```
http://127.0.0.1:8000/openapi.json
```

---

# API Endpoints

## Screen Single Entity

**POST**

```
/api/v1/compliance/screen
```

Request

```json
{
  "entity_name": "HAMAS",
  "entity_type": "supplier",
  "country": "India"
}
```

Response

```json
{
  "entity_name": "HAMAS",
  "entity_type": "supplier",
  "country": "India",
  "is_flagged": true,
  "matched_lists": [
    "OFAC",
    "UN"
  ],
  "matched_name": "HAMAS",
  "match_score": 100,
  "confidence": 1.0,
  "duration_ms": 2.84
}
```

---

## Bulk Screening

**POST**

```
/api/v1/compliance/screen-bulk
```

Request

```json
{
  "entity_names": [
    "HAMAS",
    "OpenAI"
  ],
  "entity_type": "supplier",
  "country": "India"
}
```

---

## Audit History

**GET**

```
/api/v1/compliance/audit/{entity_name}
```

Example

```
GET /api/v1/compliance/audit/HAMAS
```

---

# Sanctions Sources

The service loads sanctions data from:

- Office of Foreign Assets Control (OFAC)
- United Nations (UN)
- European Union (EU)

If the datasets are not available locally, the service automatically downloads the latest versions during startup.

---

# Matching Pipeline

Each screening request follows these steps:

1. Normalize entity name
2. Exact match lookup
3. Alias lookup
4. RapidFuzz fuzzy matching
5. Cross-source deduplication
6. Confidence calculation
7. Return matching sanctions sources

---

# Cross-Source Deduplication

Duplicate entities appearing across multiple sanctions lists are merged into a single record.

The deduplication process:

- Normalizes names
- Buckets similar entities
- Performs fuzzy comparison within buckets
- Merges aliases
- Combines sanctions sources
- Maintains confidence scores

This reduces duplicate search results while preserving the originating sanctions lists.

---

# Audit Logging

Every screening request is stored in the SQLite audit database.

Audit records include:

- Entity name
- Matched sanctions entity
- Match score
- Confidence
- Matched sanctions lists
- Screening duration
- Timestamp

Audit history can be retrieved through the audit endpoint.

---

# Refresh Job

The project includes a refresh job for updating sanctions data.

Run:

```bash
python app/jobs/refresh_job.py
```

The refresh process:

1. Archives previous downloads
2. Downloads latest sanctions lists
3. Reloads sanctions data
4. Creates a snapshot
5. Compares changes
6. Logs added and removed entities
7. Updates the in-memory search index

Refresh logs are written to:

```
app/data/logs/refresh.log
```

Archived datasets are stored in:

```
app/data/archive/
```

Snapshots are stored in:

```
app/data/snapshots/
```

---

# Database

SQLite is used for storing audit history.

Default database:

```
compliance.db
```

Database tables are created automatically during application startup.

---

# Testing

Run the complete test suite:

```bash
python -m pytest -v
```

Current Status

```
26 passed
0 failed
```

The test suite covers:

- API endpoints
- Exact matching
- Fuzzy matching
- Alias matching
- Cross-source deduplication
- Audit history
- Refresh logic
- Performance
- Input validation

---

# Performance

The project includes automated performance tests.

Performance goals include:

- Fast exact match lookups
- Efficient fuzzy matching
- Optimized bulk screening
- Bucket-based deduplication

---

# Dependencies

Major packages:

- FastAPI
- SQLAlchemy
- SQLite
- RapidFuzz
- Requests
- Pydantic
- Pytest
- python-dotenv

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Future Improvements

- Scheduled daily sanctions refresh
- Manual refresh REST endpoint
- Redis caching
- Docker support
- CI/CD pipeline
- PostgreSQL support
- Background task scheduling
- Metrics and monitoring

---



