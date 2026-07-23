# Compliance Service

## Overview

The Compliance Service is a FastAPI-based microservice that screens individuals or organizations against sanctions lists.

The service checks whether an entity exists in the OFAC sanctions list by using exact matching and fuzzy matching with RapidFuzz. It exposes REST APIs, records every screening request in an audit log, and returns the screening result in JSON format.

---

## Features

- Load OFAC sanctions data from CSV
- Load UN Consolidated sanctions list
- Exact name matching
- Fuzzy name matching using RapidFuzz
- Configurable threshold-based screening
- REST API using FastAPI
- Automatic Swagger documentation
- Pydantic request and response validation
- Audit logging for every screening request
- Unit testing using Pytest

---

## Project Structure

```text
compliance-service/
│
├── app/
│   ├── main.py
│   ├── audit.log
│   ├── routes/
│   │   └── compliance.py
│   ├── schemas/
│   │   └── compliance.py
│   ├── services/
│   │   └── sanctions_service.py
│   ├── core/
│   └── models/
│
├── data/
│   ├── ofac.csv
│   └── un.csv      
├── tests/
│   └── test_compliance.py
│
├── requirements.txt
└── README.md
```

---

## Technologies Used

- Python 3.x
- FastAPI
- Uvicorn
- Pydantic
- RapidFuzz
- Pytest

---

## Installation



### Navigate to the project

bash
cd compliance-service


### Create a virtual environment

bash
python -m venv venv


### Activate the virtual environment

Windows

bash
venv\Scripts\activate


### Install dependencies

bash
pip install -r requirements.txt



## Running the Application

Start the server

bash
python -m uvicorn app.main:app --reload


Application URL


http://127.0.0.1:8000


Swagger UI


http://127.0.0.1:8000/docs




## API Endpoint

### POST


/api/v1/compliance/check


---

## Request

```json
{
  "entity_name": "HAMAS",
  "entity_type": "organization",
  "country": "Palestine"
}
```

---

## Response (Flagged)

```json
{
  "is_flagged": true,
  "matched_lists": [
    "OFAC SDN"
  ],
  "match_score": 100,
  "checked_at": "2026-07-17T12:00:00"
}
```

---

## Response (Not Flagged)

```json
{
  "is_flagged": false,
  "matched_lists": [],
  "match_score": 72,
  "checked_at": "2026-07-17T12:00:00"
}
```

---

## How It Works

1. FastAPI starts the application.
2. The OFAC sanctions CSV file is loaded into memory.
3. (Optional) The UN sanctions CSV file is also loaded.
4. The client sends a screening request.
5. The service first checks for an exact match.
6. If no exact match is found, RapidFuzz performs fuzzy matching.
7. The highest similarity score is compared with the threshold (85).
8. The screening result is returned as JSON.
9. An audit log entry is written for every request.

---

## Audit Log

Every screening request is recorded in:

```
app/audit.log
```

Example:

```
2026-07-17 12:30:15
Input : HAMAS
Matched : HAMAS
Score : 100
Flagged : True
```

---

## Testing

Run all tests

```bash
python -m pytest
```

Verbose mode

```bash
python -m pytest -v
```

### Test Cases

- Exact Match
- Fuzzy Match
- Clean Name
- Empty String
- Special Characters
- Long Input Names

---

## Future Enhancements

- Database integration
- Multiple sanctions list support
- Country-based compliance rules
- Entity type validation
- Authentication and Authorization
- Docker support
- Kubernetes deployment

---

## Author

Developed as part of the Compliance Service backend assignment using FastAPI.