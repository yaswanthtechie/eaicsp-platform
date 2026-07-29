# Compliance Service

A FastAPI-based Compliance Screening Service that checks supplier and customer names against sanctions lists using exact and fuzzy matching.

## Features

- Load OFAC SDN sanctions list on startup
- Load UN Consolidated sanctions list
- Exact match screening
- Fuzzy matching using RapidFuzz (WRatio)
- Configurable match threshold
- JSON audit logging
- UTC timestamps
- REST API using FastAPI
- Pytest unit tests
- Deduplicates entities appearing in multiple sanctions lists

---

## Project Structure


compliance-service/
│
├── app/
│   ├── core/
│   │   └── config.py
│   │
│   ├── routes/
│   │   └── compliance.py
│   │
│   ├── schemas/
│   │   └── compliance.py
│   │
│   ├── services/
│   │   ├── sanctions_service.py
│   │   ├── csv_reader.py
│   │   ├── entity_matching.py
│   │   └── audit_service.py
│   │
│   ├── main.py
│   └── audit.log
│
├── data/
│   ├── ofac.csv
│   └── un.csv
│
├── tests/
│   └── test_compliance.py
│
├── requirements.txt
└── README.md


## Installation

Create a virtual environment.


python -m venv venv


Activate it.

Windows

venv\Scripts\activate


Install dependencies.


pip install -r requirements.txt


---

## Running the Service

Start the FastAPI server.

bash
python -m uvicorn app.main:app --reload


The application starts at

http://127.0.0.1:8000


Swagger documentation

```
http://127.0.0.1:8000/docs
```

---

## API Endpoint

### POST


/api/v1/compliance/screen


### Request

json
{
  "entity_name": "HAMAS",
  "entity_type": "supplier",
  "country": "India"
}


### Response
json
{
  "is_flagged": true,
  "matched_lists": [
    "OFAC SDN"
  ],
  "matched_name": "HAMAS",
  "match_score": 100,
  "checked_at": "2026-07-28T09:30:10.425+00:00"
}


---

## Matching Process

1. Normalize entity names.
2. Perform an exact match.
3. If no exact match is found, perform fuzzy matching using RapidFuzz WRatio.
4. If the score is greater than or equal to the configured threshold (85), the entity is flagged.
5. Every screening request is written to the audit log.


## Audit Logging

Each screening request is stored as a JSON record in


app/audit.log


Example

json
{
  "timestamp": "2026-07-28T09:30:10.425+00:00",
  "input_name": "HAMAS",
  "is_flagged": true,
  "matched_lists": [
    "OFAC SDN"
  ],
  "matched_name": "HAMAS",
  "match_score": 100
}


---

## Running Tests

Run all tests.

bash
pytest -v


Current test coverage includes

- Exact match
- Fuzzy match
- First OFAC record
- UN-only entity
- Duplicate entity across OFAC and UN
- Clean entity
- Empty entity
- Blank spaces
- Special characters
- Case-insensitive matching

---

## Configuration

The following configuration values are defined in

app/core/config.py


- OFAC_CSV_PATH
- UN_CSV_PATH
- AUDIT_LOG_PATH
- MATCH_THRESHOLD

---

## Technologies Used

- Python 3
- FastAPI
- RapidFuzz
- Pydantic
- Pytest
- Uvicorn


## Compliance Workflow


Client Request
      │
      ▼
FastAPI Endpoint
      │
      ▼
Normalize Entity Name
      │
      ▼
Exact Match
      │
      ▼
No Match
      │
      ▼
RapidFuzz WRatio Matching
      │
      ▼
Score ≥ 85 ?
      │
 ┌────┴────┐
 │         │
Yes        No
 │         │
 ▼         ▼
Flag     Clean
 │
 ▼
Write Audit Log
 │
 ▼
Return Response
