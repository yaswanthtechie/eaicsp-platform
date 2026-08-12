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

- MAX_RETRIES: number of retries on retryable failures (e.g. 2 → original request + 2 retries).
- The gateway generates or forwards X-Request-ID for tracing. Downstream services should log this header.

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

| Method | Endpoint                 | Description                              |
| ------ | ------------------------ | ---------------------------------------- |
| GET    | `/`                      | Gateway status                           |
| GET    | `/health`                | Health status of all downstream services |
| GET    | `/gateway/dashboard`     | Aggregated Health & Metrics Dashboard    |
| GET    | `/api/v2/status`         | API v2 Gateway Status (Stub)             |
| GET    | `/api/v2/inventory/items`| API v2 Inventory Items (Stub Demo)       |
| ALL    | `/{path:path}`           | Reverse proxy endpoint (`/api/v1/...`)   |

---

# API Versioning

The gateway supports API Versioning to demonstrate backward compatibility and breaking contract migrations:

- **API v1 (`/api/v1/...`)**: Production proxy API forwarding requests to downstream microservices via `SERVICE_ROUTES`.
- **API v2 (`/api/v2/...`)**: Demonstration/stub API showing future breaking contract changes (e.g. envelope-wrapped response format).

> **Important**:
> - v1 remains the existing production proxy API.
> - v2 is currently a demonstration/stub for future breaking changes.
> - v2 does not replace v1.
> - v1 clients remain unaffected.

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

# In-Memory Caching

The gateway provides a thread-safe in-memory caching service (`app/services/cache.py`):

- **TTL Expiration**: Configurable time-to-live per cache entry.
- **Pattern Invalidation**: Support for key prefix or fnmatch pattern invalidation (`invalidate_pattern("inventory:*")`).
- **Metrics Collector Integration**: Tracks `cache_hits` and `cache_misses` per service for real-time hit rate calculation on `/gateway/dashboard`.
- **Thread Safety**: Guarantees lock-protected atomic cache operations under concurrent workloads.

---

# Testing

The gateway features full test coverage across all features and boundary conditions:

- **Circuit Breaker (`app/tests/test_circuit_breaker.py`)**: 10 tests (CLOSED, OPEN, HALF-OPEN transitions, fail-fast, dashboard sync, full dynamic lifecycle, concurrency).
- **Per-User/Role Rate Limiting (`app/tests/test_rate_limit.py`)**: 13 tests (user buckets, role quotas, IP fallback, boundary limits, normalization, concurrency).
- **Aggregated Health Dashboard (`app/tests/test_dashboard.py`)**: 6 tests (structure, volume, percentiles, cache hit rate, circuit breaker state, empty metrics defaults).
- **API Versioning (`app/tests/test_versioning.py`)**: 6 tests (v2 status, v2 stub envelope, v1 proxy preservation, 404 fallthrough, middleware, OpenAPI schema).
- **In-Memory Cache (`app/tests/test_cache.py`)**: 6 tests (set/get, TTL expiration, delete/clear, pattern invalidation, hit rate metrics, concurrency).
- **Integration Tests (`tests/`)**: 10 tests (proxy forwarding, health endpoint, status, service error fallbacks).

Run all unit tests:

```bash
pytest app/tests/ -v
```

Run all integration tests:

```bash
pytest tests/ -v
```

---

# Known Limitations

- **Node-Local State (Single Instance Memory)**:
  - The rate limiter (`InMemoryRateLimiter`), circuit breaker (`CircuitBreakerManager`), metrics collector (`MetricsCollector`), and cache (`InMemoryCache`) maintain thread-safe state in-memory within a single Gateway process.
  - In multi-instance or horizontally scaled cloud deployments, state is not automatically shared across worker processes or separate nodes.
  - **Production Recommendation**: Upgrade backends to distributed data stores (e.g. Redis / Redis Cluster) when running multi-node clusters.

- **Reverse Proxy Trust Boundary**:
  - `X-Forwarded-For` headers are strictly **ignored** unless the immediate peer IP address (`request.client.host`) is explicitly listed in `TRUSTED_PROXIES`.
  - Ensure reverse proxies or load balancers (e.g. NGINX, AWS ALB) are properly configured in `TRUSTED_PROXIES` when deployed behind trusted infrastructure.

- **Route Prefix Matching**:
  - Routing to downstream services relies on exact prefix matching against `SERVICE_ROUTES`.
  - Unmatched request paths fall through to a 404 Not Found error.

---

# Author

EAICSP Platform

FastAPI API Gateway
