# FastAPI API Gateway

## Overview

The **API Gateway** is a production-ready FastAPI application that serves as the single entry point for all incoming client requests in the EAICSP microservices platform.

It provides:

- Dynamic Reverse Proxy
- Centralized Health Monitoring
- Global Rate Limiting
- Automatic Retry Mechanism
- Structured Request Logging
- High Performance Asynchronous Routing

---

# Features

- FastAPI-based API Gateway
- Dynamic Reverse Proxy using HTTPX
- Automatic Retry using Tenacity
- Global Rate Limiting using SlowAPI
- Centralized Health Monitoring
- Structured Access Logging
- OpenAPI (Swagger) Documentation
- Fully Asynchronous Architecture
- Unit & Integration Testing

---

# Project Structure

```text
services/api-gateway/
│
├── app/
│   ├── core/
│   │   └── config.py
│   │
│   ├── middleware/
│   │   ├── logging.py
│   │   └── ratelimit.py
│   │
│   ├── routes/
│   │   ├── gateway.py
│   │   └── health.py
│   │
│   ├── schemas/
│   │   └── responses.py
│   │
│   ├── services/
│   │   ├── health.py
│   │   └── proxy.py
│   │
│   ├── __init__.py
│   └── main.py
│
├── tests/
│   ├── test_api.py
│   ├── test_integration.py
│   └── __init__.py
│
├── dummy_services.py
├── requirements.txt
├── .env.example
└── README.md
```

---

# Technology Stack

- Python 3.11+
- FastAPI
- Uvicorn
- HTTPX
- Tenacity
- SlowAPI
- Pydantic
- Pytest

---

# Installation

## 1. Navigate to the project

```bash
cd services/api-gateway
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a local environment file.

```bash
cp .env.example .env
```

The gateway uses **Pydantic Settings** to load configuration values.

The downstream services are configured through the `SERVICE_ROUTES` mapping located in:

```text
app/core/config.py
```

---

# Run the Application

Start the API Gateway:

```bash
uvicorn app.main:app --reload
```

---

# API Documentation

Swagger UI

```
http://127.0.0.1:8000/docs
```

OpenAPI JSON

```
http://127.0.0.1:8000/api/v1/openapi.json
```

---

# API Endpoints

| Method | Endpoint       | Description                              |
| ------ | -------------- | ---------------------------------------- |
| GET    | `/`            | Gateway status                           |
| GET    | `/health`      | Health status of all downstream services |
| ALL    | `/{path:path}` | Reverse proxy endpoint                   |

---

# Reverse Proxy Flow

The gateway forwards requests dynamically using **HTTPX AsyncClient**.

### Request Flow

1. Client sends a request.
2. Gateway matches the request path using `SERVICE_ROUTES`.
3. Hop-by-hop headers are removed.
4. Request is forwarded to the appropriate microservice.
5. Failed requests are automatically retried using **Tenacity**.
6. If the downstream service times out, the gateway returns **504 Gateway Timeout**.
7. If the downstream service is unavailable, the gateway returns **503 Service Unavailable**.
8. The original downstream response is streamed back to the client.

---

# Rate Limiting

The gateway uses **SlowAPI** for global rate limiting.

Default configuration:

- Limit: **100 requests per minute per IP**
- Response: **429 Too Many Requests**
- Supports **X-Forwarded-For** for reverse proxies and load balancers.

---

# Health Monitoring

The `/health` endpoint asynchronously checks every configured downstream service.

Example Response

```json
{
  "inventory": "UP",
  "shipments": "UP",
  "compliance": "DOWN",
  "supplier-risk": "UP"
}
```

Any timeout or connection failure automatically marks the service as **DOWN**.

---

# Logging

Every request is logged with:

- HTTP Method
- Request Path
- Status Code
- Response Time
- Client IP Address

The middleware also records failed requests that result in **500 Internal Server Error**.

---

# Testing

The project includes:

- Unit Tests
- Integration Tests
- Reverse Proxy Tests
- Health Endpoint Tests
- Timeout Tests
- Service Unavailable Tests

Run all tests:

```bash
pytest tests/
```

---

# Author

EAICSP Platform

FastAPI API Gateway
