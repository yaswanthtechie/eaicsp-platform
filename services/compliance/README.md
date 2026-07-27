# Compliance Service

## Overview

The Compliance Service is a FastAPI-based microservice that screens entities against sanctions lists.

It supports:

- OFAC SDN sanctions list
- United Nations (UN) sanctions list
- Exact name matching
- Fuzzy name matching using RapidFuzz
- REST API for compliance screening
- JSON audit logging
- Automatic API documentation using Swagger

---

# Project Structure

```
compliance-service/
│
├── app/
│   ├── main.py
│   ├── audit.log
│   │
│   ├── core/
│   │   └── config.py
│   │
│   ├── routes/
│   │   └── compliance.py
│   │
│   ├── schemas/
│   │   └── compliance.py
│   │
│   └── services/
│       └── sanctions_service.py
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
```

---

# Features

- Load OFAC sanctions from CSV
- Load UN sanctions from CSV
- Exact name matching
- Fuzzy name matching using RapidFuzz (WRatio)
- Configurable matching threshold
- JSON audit log
- FastAPI REST API
- Pydantic request and response validation
- Automatic Swagger documentation

---

# Technologies Used

- Python 3.x
- FastAPI
- Uvicorn
- Pydantic
- RapidFuzz
- Pytest

---

# Installation

## Clone the repository

```bash
git clone <repository-url>
```

---

## Navigate to the project

```bash
cd compliance-service
```

---

## Create Virtual Environment

Windows

```bash
python -m venv venv
```

Activate

```bash
venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Running the Application

Start the FastAPI server

```bash
python -m uvicorn app.main:app --reload
```

---

## Application URL

```
http://127.0.0.1:8000
```

---

## Swagger Documentation

```
http://127.0.0.1:8000/docs
```

---

# API Endpoint

## Screen Entity

**POST**

```
/api/v1/compliance/screen
```

---

# Sample Request

```json
{
    "entity_name": "HAMAS",
    "entity_type": "supplier",
    "country": "Palestine"
}
```

---

# Sample Response (Flagged)

```json
{
    "is_flagged": true,
    "matched_lists": [
        "OFAC SDN"
    ],
    "matched_name": "HAMAS",
    "match_score": 100,
    "checked_at": "2026-07-27T08:30:00+00:00"
}
```

---

# Sample Response (Not Flagged)

```json
{
    "is_flagged": false,
    "matched_lists": [],
    "matched_name": "",
    "match_score": 0,
    "checked_at": "2026-07-27T08:30:00+00:00"
}
```

---

# Project Workflow

1. FastAPI starts the application.
2. The service loads OFAC and UN sanction lists into memory.
3. Startup fails if no sanctions are loaded.
4. The client sends a screening request.
5. The service first performs an exact match.
6. If no exact match exists, RapidFuzz performs fuzzy matching.
7. The best matching entity is selected.
8. If the score is greater than or equal to the configured threshold, the entity is flagged.
9. The screening result is written to a JSON audit log.
10. The API returns the screening result.

---

# Matching Logic

### Exact Match

```
HAMAS
```

CSV

```
HAMAS
```

Result

```
Score = 100
Flagged = True
```

---

### Fuzzy Match

Input

```
Acme Corp
```

CSV

```
ACME Corporation Ltd
```

RapidFuzz calculates the similarity score using **WRatio**.

If

```
Score >= 85
```

Result

```
Flagged = True
```

Otherwise

```
Flagged = False
```

---

# Audit Logging

Every screening request is stored in

```
app/audit.log
```

Example

```json
{
  "timestamp":"2026-07-27T08:30:00+00:00",
  "input_name":"HAMAS",
  "matched_name":"HAMAS",
  "match_score":100,
  "is_flagged":true,
  "matched_lists":["OFAC SDN"]
}
```

---

# Running Tests

Run all tests

```bash
python -m pytest -v
```

Run a single test file

```bash
python -m pytest tests/test_compliance.py -v
```

---

# Configuration

Application configuration is stored in

```
app/core/config.py
```

This includes:

- OFAC CSV path
- UN CSV path
- Audit log path
- Matching threshold

---

# Future Enhancements

- Database integration
- Authentication and Authorization
- Multiple sanctions providers
- Country-specific screening rules
- Docker support
- Kubernetes deployment
- CI/CD pipeline
- Bulk entity screening
- Performance optimization using indexed search

---

