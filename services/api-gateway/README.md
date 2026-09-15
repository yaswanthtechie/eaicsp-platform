# API Gateway

## Overview

The **API Gateway** is a production-ready FastAPI service that acts as the single entry
point for all client requests in the EAICSP microservices platform.

It provides:

- Dynamic reverse proxy to downstream microservices
- Per-user and per-role rate limiting with IP-based fallback
- Circuit breaker with CLOSED -> OPEN -> HALF-OPEN state machine
- In-memory response caching with TTL and pattern invalidation
- Centralized health monitoring of all downstream services
- Aggregated metrics dashboard (request volume, p50/p95 latency, cache hit rate)
- Structured access logging with request IDs
- Automatic retry on safe/idempotent methods
- OpenAPI (Swagger) documentation

---

## Project Structure

```
api-gateway/
|-- app/
|   |-- core/
|   |   `-- config.py            # Settings (pydantic-settings, loads .env)
|   |-- middleware/
|   |   |-- logging.py           # Access log middleware
|   |   |-- rate_limit.py        # Per-user / per-role rate limiter
|   |   |-- ratelimit.py         # SlowAPI global limiter + get_real_ip()
|   |   `-- request_id.py        # X-Request-ID propagation
|   |-- routes/
|   |   |-- dashboard.py         # GET /gateway/dashboard
|   |   |-- gateway.py           # Catch-all proxy route
|   |   |-- health.py            # GET /health
|   |   `-- v2.py                # /api/v2/* stub routes
|   |-- schemas/
|   |   `-- responses.py         # Pydantic response models
|   |-- services/
|   |   |-- cache.py             # InMemoryCache (TTL, pattern invalidation)
|   |   |-- circuit_breaker.py   # CircuitBreakerManager
|   |   |-- health.py            # Async downstream health pinger
|   |   |-- metrics.py           # MetricsCollector (p50/p95, cache rates)
|   |   `-- proxy.py             # ProxyService (HTTPX, retry, streaming)
|   |-- tests/
|   |   |-- test_cache.py
|   |   |-- test_circuit_breaker.py
|   |   |-- test_dashboard.py
|   |   |-- test_rate_limit.py
|   |   `-- test_versioning.py
|   `-- main.py                  # FastAPI application factory
|-- tests/
|   |-- test_api.py              # HTTP-level gateway tests
|   `-- test_integration.py      # Live proxy integration tests
|-- load_tests/
|   `-- load_test_results.txt
|-- .env.example
|-- dummy_services.py
|-- load_test.py
|-- pyproject.toml
|-- pytest.ini
`-- requirements.txt
```

---

## Features

### Dynamic Reverse Proxy

`ProxyService` (in `app/services/proxy.py`) proxies all requests to downstream
microservices using a shared `httpx.AsyncClient` initialized at startup and
closed on shutdown.

Behaviour:

- **Route matching**: exact prefix or `<prefix>/...` match against `SERVICE_ROUTES`.
  Paths that match no prefix receive `404 Service not found`.
- **Hop-by-hop header stripping**: `Connection`, `Keep-Alive`, `Transfer-Encoding`,
  `TE`, `Trailer`, `Proxy-Authenticate`, `Proxy-Authorization`, `Upgrade` are
  removed before forwarding and before returning downstream headers.
- **X-Forwarded-For / X-Forwarded-Proto** headers are appended to every forwarded
  request.
- **X-Request-ID** is propagated to downstream services.
- **Streaming response**: the downstream body is streamed back without loading it into
  gateway memory; the response and its resources are closed in a `finally` block after
  streaming completes.
- **Retry policy**: retries are attempted only for idempotent/safe methods:
  `GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`. `POST` and `PATCH` are intentionally
  excluded to prevent duplicate business operations. Retryable exceptions are
  connection and timeout errors. Retry timing uses exponential back-off
  (multiplier 0.5 s, min 0.5 s, max 5 s).
- **Circuit breaker fail-fast**: when the circuit breaker for a service is OPEN, the
  request is rejected immediately with `503` without attempting a downstream call.
- **Error responses**:
  - `504` -- downstream timeout
  - `503` -- connection failure or circuit breaker OPEN

### Rate Limiting

Two rate limiting layers work in combination:

#### 1. Global IP-based limiter (SlowAPI)

`ratelimit.py` configures a SlowAPI `Limiter` with a default limit of
**100 requests per minute per IP**. The IP resolution uses `get_real_ip()` (see
*Trusted Proxies* below).

#### 2. Per-user / per-role limiter (`PerUserRoleRateLimitMiddleware`)

`rate_limit.py` implements a fixed-window, thread-safe, in-memory rate limiter
(`InMemoryRateLimiter`) that applies quotas based on JWT identity:

| Identity source              | Rate limit bucket key | Default quota         |
|------------------------------|-----------------------|-----------------------|
| Authenticated user (JWT)     | `user:<user_id>`      | Role-based (see below)|
| Role only (no user_id claim) | `role:<role>`         | Role-based            |
| Unauthenticated (no JWT)     | `ip:<client_ip>`      | 60 req/min (default)  |

**Per-role quotas (requests per `RATE_LIMIT_WINDOW_SECONDS`):**

| Role                  | Requests | Category / Purpose                       |
|-----------------------|----------|------------------------------------------|
| `ceo`                 | 200      | Executive tier                           |
| `vp_operations`       | 200      | Executive tier                           |
| `procurement_manager` | 100      | Operations & Management tier             |
| `logistics_manager`   | 100      | Operations & Management tier             |
| `compliance_officer`  | 100      | Operations & Management tier             |
| `warehouse_manager`   | 100      | Operations & Management tier             |
| `analyst`             | 60       | Operational & Analytical tier            |
| `supplier`            | 60       | External partner tier                    |
| `default`             | 60       | Unauthenticated fallback / unknown role  |

Roles match the platform source of truth (`services/platform/app/schemas/user.py:Role`).
Roles are normalised to lowercase with spaces replaced by `_` before lookup.
Unknown or missing roles fall back to the `default` quota (60 req/min).

**JWT identity extraction:**

The middleware reads the `Authorization: Bearer <token>` header and decodes the
JWT using the server-side secret (`SECRET_KEY`) and algorithm (`JWT_ALGORITHM`)
via PyJWT. Claims `user_id` / `sub` (user identity) and `role` / `roles`
(quota tier) are extracted only after **signature validation succeeds**.

If the token is absent, malformed, or the signature is invalid, the middleware
falls back to IP-based rate limiting. It does **not** accept identity claims
from an untrusted or unsigned token.

**Response headers on every allowed request:**

```
X-RateLimit-Limit: <quota>
X-RateLimit-Remaining: <remaining>
```

**Response on limit exceeded:**

```
HTTP/1.1 429 Too Many Requests
Retry-After: <seconds>
X-RateLimit-Limit: <quota>
X-RateLimit-Remaining: 0

{"detail": "Too Many Requests", "error": "Rate limit exceeded"}
```

#### LOAD_TEST_MODE

When `LOAD_TEST_MODE=True` is set in the **server-side** configuration (`.env`
or environment variable), `PerUserRoleRateLimitMiddleware` bypasses its quota
check and forwards every request unconditionally. This is a **server-side-only**
control. A client cannot enable this bypass by sending any header.

#### Trusted Proxies and X-Forwarded-For

`get_real_ip()` resolves the client IP for rate limiting and logging:

1. If the immediate connection peer (`request.client.host`) is listed in
   `TRUSTED_PROXIES`, the first value from the `X-Forwarded-For` header is used
   as the real client IP.
2. Otherwise `request.client.host` is used directly.

This prevents rate-limit spoofing: an untrusted client cannot manipulate
`X-Forwarded-For` to masquerade as a different IP.

`TRUSTED_PROXIES` defaults to an empty list -- forwarded IP information is
**ignored by default** unless explicitly configured.

### Circuit Breaker

`CircuitBreakerManager` (in `app/services/circuit_breaker.py`) maintains a
thread-safe per-service state machine:

| State         | Behaviour                                                                      |
|---------------|--------------------------------------------------------------------------------|
| **CLOSED**    | Requests pass through. Failures and total requests tracked in a rolling 60s window. |
| **OPEN**      | Requests are rejected immediately (fail-fast with HTTP 503). After `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` (30s), transitions to HALF-OPEN. |
| **HALF-OPEN** | One trial request is allowed. Success -> CLOSED (window reset); failure -> OPEN again (30s). |

**Trip condition**: When request failure rate within the rolling 60-second window
exceeds 50% (`failure_rate > 0.50`), the breaker transitions CLOSED to OPEN.
A service with <= 50% failure rate (e.g. 40%) will not trip.

### In-Memory Cache

`InMemoryCache` (in `app/services/cache.py`) is a thread-safe, in-process cache:

- Optional TTL per entry (entries expire lazily on next read)
- Pattern-based invalidation using `fnmatch` or string prefix
- Integrates with `MetricsCollector` to record cache hits and misses

> **Note**: cache state is not shared across multiple gateway processes or instances.

### Metrics and Dashboard

`MetricsCollector` (in `app/services/metrics.py`) collects per-service metrics
in memory:

- Request volume
- Latency percentiles (p50, p95) using the nearest-rank method
- Cache hit rate
- Circuit breaker state

The dashboard endpoint (`GET /gateway/dashboard`) returns a JSON snapshot for
all known downstream services.

### Health Monitoring

`GET /health` pings all configured downstream services concurrently
(`asyncio.gather`) by calling `<base_url>/health` with a 3-second timeout.

- HTTP status 2xx (200-299) -> `"UP"`
- HTTP status 4xx, 5xx, or any network/timeout error -> `"DOWN"`
- All checks run in parallel; a single service failure does not affect others.

### Structured Logging and Request IDs

`RequestIDMiddleware` ensures every request has an `X-Request-ID`:

- If the client provides `X-Request-ID`, it is sanitised (CR/LF characters
  stripped to prevent log injection) and reused.
- If the header is absent or becomes empty after sanitisation, a new UUID4 is
  generated.
- The header is echoed back in the response.

`LoggingMiddleware` logs each request on completion:

```
request_id=<id> method=<METHOD> path=<path> status=<code> duration=<ms>ms ip=<ip>
```

### API Versioning

`/api/v2/*` routes demonstrate a versioned API surface alongside the existing
`/api/v1/*` routes served through the proxy. v1 clients are unaffected.

---

## API Endpoints

| Method | Path                      | Description                                  |
|--------|---------------------------|----------------------------------------------|
| GET    | `/`                       | Gateway root status (message, status, version)|
| GET    | `/gateway/status`         | Gateway operational status (no secrets)      |
| GET    | `/health`                 | Health status of all downstream services     |
| GET    | `/gateway/dashboard`      | Aggregated metrics for all services          |
| GET    | `/api/v1/openapi.json`    | OpenAPI schema                               |
| GET    | `/api/v2/status`          | API v2 status stub                           |
| GET    | `/api/v2/inventory/items` | API v2 inventory stub (breaking schema demo) |
| *      | `/{path}`                 | Catch-all proxy to downstream microservice   |

Supported proxy methods: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `OPTIONS`, `HEAD`.

### Default Downstream Service Routes

| Prefix                    | Default Target          |
|---------------------------|-------------------------|
| `/api/v1/inventory`       | http://localhost:8001   |
| `/api/v1/shipments`       | http://localhost:8002   |
| `/api/v1/compliance`      | http://localhost:8003   |
| `/api/v1/purchase-orders` | http://localhost:8004   |
| `/api/v1/auth`            | http://localhost:8005   |
| `/api/v1/supplier-risk`   | http://localhost:8006   |

---

## Configuration

Copy `.env.example` to `.env` and adjust values for your environment.
All settings are loaded by `pydantic-settings` from `.env` or real environment
variables. Unknown variables are silently ignored.

| Variable                                | Default                  | Description                                            |
|-----------------------------------------|--------------------------|--------------------------------------------------------|
| `APP_NAME`                              | `API Gateway`            | Application name shown in OpenAPI docs                 |
| `VERSION`                               | `1.0.0`                  | Application version                                    |
| `DEBUG`                                 | `False`                  | Enable debug mode                                      |
| `LOAD_TEST_MODE`                        | `False`                  | Bypass per-user/role rate limiter (server-side only)   |
| `TIMEOUT_SECONDS`                       | `5`                      | Downstream HTTP request timeout in seconds             |
| `MAX_RETRIES`                           | `2`                      | Number of retries for safe methods on failure          |
| `SECRET_KEY`                            | **(REQUIRED)**           | Secret key for JWT signature verification — must match the platform token issuer exactly |
| `JWT_ALGORITHM`                         | `HS256`                  | JWT signing algorithm                                  |
| `TRUSTED_PROXIES`                       | `[]`                     | Trusted proxy IPs for X-Forwarded-For resolution       |
| `RATE_LIMIT_WINDOW_SECONDS`             | `60`                     | Fixed window size for per-user/role rate limiter       |
| `CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD`| `0.50`                   | Failure rate threshold (>50%) before breaker trips OPEN|
| `CIRCUIT_BREAKER_WINDOW_SECONDS`        | `60`                     | Rolling time window in seconds for failure rate        |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`      | `30.0`                   | Seconds in OPEN before transitioning to HALF-OPEN      |

> **Security**: Never commit a real `SECRET_KEY` or credentials to version control.
> Use environment-specific secrets management in production.
> `SECRET_KEY` is **required** — the gateway will fail to start if it is not set.

---

## Installation

### Prerequisites

- Python 3.11+

### Setup

**Linux / macOS**

```bash
cd services/api-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env -- at minimum set SECRET_KEY to match the platform token issuer
```

**Windows (PowerShell)**

```powershell
cd services\api-gateway
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env -- at minimum set SECRET_KEY to match the platform token issuer
```

---

## Running the Gateway

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The gateway will be available at:

- API root: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/api/v1/openapi.json

---

## Testing

Tests are discovered from two directories as configured in `pytest.ini`:

- `app/tests/` -- unit tests for middleware and services
- `tests/` -- HTTP-level and live integration tests

### Test Categories

| File                                | What it covers                                                       |
|-------------------------------------|----------------------------------------------------------------------|
| `app/tests/test_cache.py`           | InMemoryCache TTL, invalidation, metrics integration                 |
| `app/tests/test_circuit_breaker.py` | CLOSED/OPEN/HALF-OPEN transitions, fail-fast, recovery              |
| `app/tests/test_dashboard.py`       | /gateway/dashboard metrics aggregation                               |
| `app/tests/test_rate_limit.py`      | Per-user, per-role, IP fallback, JWT identity, LOAD_TEST_MODE        |
| `app/tests/test_versioning.py`      | /api/v2/* stub responses                                             |
| `tests/test_api.py`                 | Root, health, proxy success/timeout/503, request ID security         |
| `tests/test_integration.py`         | Live proxy routing via real dummy downstream services                |

### Running Tests

```bash
python -m pytest -v
```

---

## Dependencies

| Package             | Purpose                                    |
|---------------------|--------------------------------------------|
| `fastapi`           | Web framework                              |
| `uvicorn[standard]` | ASGI server                                |
| `pydantic`          | Data validation and response models        |
| `pydantic-settings` | Environment variable configuration         |
| `httpx`             | Async HTTP client for downstream requests  |
| `tenacity`          | Retry logic with exponential back-off      |
| `slowapi`           | Global IP-based rate limiting (SlowAPI)    |
| `PyJWT`             | JWT signature verification                 |
| `websockets`        | WebSocket transport support for uvicorn    |
| `pytest`            | Test framework                             |
| `pytest-asyncio`    | Async test support                         |

---

## Known Limitations

1. **In-Memory Rate Limiter Scope**:
   `InMemoryRateLimiter` maintains rate limit counters in the local memory of a single API Gateway process. In a multi-replica or clustered deployment, rate limit state is not shared across instances; a distributed store (e.g. Redis) should be used for clustered rate limiting.

2. **In-Memory Circuit Breaker Scope**:
   Circuit breaker state (CLOSED / OPEN / HALF-OPEN) is tracked per gateway instance. A downstream service outage trips the breaker independently for each gateway worker.

3. **Trusted Proxy Single-Hop Forwarding**:
   `get_real_ip()` trusts `X-Forwarded-For` only when the immediate peer IP matches `TRUSTED_PROXIES`. Multi-hop chained proxy setups require explicit CIDR / list configuration.

4. **Unauthenticated Request Fallback**:
   Requests without a valid JWT or with an invalid/expired token fall back to IP-based rate limiting using the default unauthenticated quota (60 req/min). They do not receive privileged role quotas.

5. **`LOAD_TEST_MODE` Server-Side Bypass**:
   `LOAD_TEST_MODE` disables rate limiting for performance testing. It is strictly a server-side setting and logs a warning on activation. It must remain `False` in production environments.

---

## Author

EAICSP Platform -- Mahendher
