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
| `METRICS_BEARER_TOKEN`                  | `""`                     | Bearer token required for Prometheus to scrape `/metrics` |
| `METRICS_ALLOW_ANONYMOUS`               | `false`                  | When `false` (default), `/metrics` returns 503 if token is unset; set `true` only for unauthenticated local development |

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

| File                                       | What it covers                                                       |
|--------------------------------------------|----------------------------------------------------------------------|
| `app/tests/test_cache.py`                  | InMemoryCache TTL, invalidation, metrics integration                 |
| `app/tests/test_circuit_breaker.py`        | CLOSED/OPEN/HALF-OPEN transitions, fail-fast, recovery              |
| `app/tests/test_dashboard.py`              | /gateway/dashboard metrics aggregation                               |
| `app/tests/test_rate_limit.py`             | Per-user, per-role, IP fallback, JWT identity, LOAD_TEST_MODE        |
| `app/tests/test_versioning.py`             | /api/v2/* stub responses                                             |
| `tests/test_api.py`                        | Root, health, proxy success/timeout/503, request ID security        |
| `tests/test_integration.py`                | Live proxy routing via real dummy downstream services                |
| `tests/test_round5_auth_forwarding.py`     | Mocked unit tests for Authorization forwarding & 401/403 passthrough |
| `tests/test_round5_gateway_integration.py` | Mocked error handling (401, 403, 404, 422, 500, 503, 504) & dummy isolation |
| `tests/test_real_platform_integration.py`  | Live end-to-end integration test against real Rahul Platform service |
| `tests/test_real_inventory_integration.py` | Live end-to-end integration test against real Balaji Inventory service|

### Running Tests

```bash
python -m pytest -v
```

---

## Round 5 Real Microservice Integration & Verification

### 1. Architecture

```text
Client
  |
  | HTTP (Authorization: Bearer <token>)
  v
API Gateway (:8000)
  |
  +---------------------------------------+
  |                                       |
  | HTTP (Forwarded Authorization)        | HTTP (Forwarded Authorization)
  v                                       v
Rahul Platform (:8005)                  Balaji Inventory (:8001)
  |                                       |
  | Token verification                    | POST /api/v1/auth/verify (HTTP)
  v                                       v
Platform DB                             Rahul Platform (:8005)
                                          |
                                          | Token & Role verification
                                          v
                                        Inventory DB
```

### 2. Live Services Requirement

> [!IMPORTANT]
> **Live integration testing requires all three services running concurrently on their designated ports:**
> - **Rahul Platform Service**: port `8005` (`uvicorn app.main:app --port 8005` from `services/platform`)
> - **Balaji Inventory Service**: port `8001` (`uvicorn app.main:app --port 8001` from `services/inventory`)
> - **API Gateway**: port `8000` (`uvicorn app.main:app --port 8000` from `services/api-gateway`)
>
> If any downstream service is not running, the corresponding live integration tests skip with an explicit message detailing the missing prerequisite.
>
> *Note: Live integration tests are not currently executed in CI.*

### 3. Running Live Integration Tests

Start the services in three separate terminals:

```powershell
# Terminal 1: Platform Service
cd services/platform
uvicorn app.main:app --host 127.0.0.1 --port 8005

# Terminal 2: Inventory Service
cd services/inventory
uvicorn app.main:app --host 127.0.0.1 --port 8001

# Terminal 3: API Gateway
cd services/api-gateway
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Execute the live integration suites:

```powershell
# Live Platform Integration
python -m pytest tests/test_real_platform_integration.py -v

# Live Inventory Integration
python -m pytest tests/test_real_inventory_integration.py -v
```

---

## Round 10 Observability Stack

### Round 10 status

| Milestone | Status | Evidence |
|---|---|---|
| M1 Prometheus + Grafana | Done when `verify_observability.py` passes | `OBSERVABILITY_EVIDENCE.md` §1 (dashboard = Prometheus = Grafana), `docs/evidence/grafana_dashboard.png` |
| M2 OpenTelemetry + Jaeger | Done when `verify_observability.py` passes | `OBSERVABILITY_EVIDENCE.md` §2 (trace with gateway + Inventory spans), `docs/evidence/jaeger_trace.png` |
| M3 Locust | Done | `load_tests/round10_summary.md` (generated), `ROUND10_M3_LOAD_TEST_REPORT.md` |

Not done / known limits: single Uvicorn worker on one laptop; downstreams are
`dummy_services.py`, not the real services; rate limiting disabled during the sweep.

### Running the tests

```powershell
python -m pytest -m "not integration" -q          # unit tests, no Docker needed
docker compose -f docker-compose.dev.yml up -d     # then dummy_services + gateway (see above)
python -m pytest -m integration -q                 # real Prometheus / Grafana / Jaeger
```

### Overview

The API Gateway is fully instrumented for production observability:

| Component | Version | Purpose |
|---|---|---|
| **Prometheus** | `prom/prometheus:v2.53.0` | Scrapes `/metrics` every 2 s |
| **Grafana** | `grafana/grafana:11.1.0` | Dashboards (provisioned from source) |
| **Jaeger** | `jaegertracing/all-in-one:1.57.0` | Distributed trace collection (OTLP HTTP) |

### Start the Observability Stack

```powershell
# From services/api-gateway/
docker compose -f docker-compose.dev.yml up -d
```

Services start automatically with:
- **Prometheus** → [http://localhost:9090](http://localhost:9090)
- **Grafana** → [http://localhost:3000](http://localhost:3000) (anonymous read-only Viewer; admin login from .env)
- **Jaeger** → [http://localhost:16686](http://localhost:16686) (OTLP HTTP on port 4318)


### Prometheus Scraping & Token Configuration

> [!IMPORTANT]
> **Prometheus Scrape Token Setup (`prometheus/metrics_token`)**:
> On a fresh clone, `prometheus/metrics_token` does not exist because secret files are git-ignored.
> You **must** create `prometheus/metrics_token` as a file before launching Docker Compose:
> ```bash
> # Linux / macOS
> echo "your-bearer-token" > prometheus/metrics_token
> # Windows PowerShell
> Set-Content -Path prometheus/metrics_token -Value "your-bearer-token" -NoNewline
> ```
> Ensure `METRICS_BEARER_TOKEN` in `.env` matches the token inside `prometheus/metrics_token`.
> If this file is missing when starting Docker, Docker will automatically create a **directory** named `prometheus/metrics_token` for the volume mount, causing Prometheus scrape authentication to fail.
>
> **Security Warning**: Never commit real tokens or credentials to version control. Both `prometheus/metrics_token` and `.env` are git-ignored.

The `/metrics` endpoint is **fail-closed by default**:
- **Authentication**: When `METRICS_BEARER_TOKEN` is configured, callers (including Prometheus) must provide a matching `Authorization: Bearer <token>` header. Missing or invalid bearer tokens are rejected with HTTP `401 Unauthorized` (`Invalid metrics token`).
- **Fail-Closed Default**: A missing or unconfigured `METRICS_BEARER_TOKEN` does **not** silently expose `/metrics`. With `METRICS_ALLOW_ANONYMOUS=false` (the default), `/metrics` refuses requests and returns HTTP `503 Service Unavailable` (`Metrics token not configured`).
- **Opt-In Anonymous Access**: Explicit unauthenticated access is permitted **only** when `METRICS_ALLOW_ANONYMOUS=true` is set (strictly intended for local development convenience).

| Environment Variable | Default | Description |
|---|---|---|
| `METRICS_BEARER_TOKEN` | `""` | Bearer token required for Prometheus to scrape `/metrics`. |
| `METRICS_ALLOW_ANONYMOUS` | `false` | Default `false` (fail-closed, returns 503 if token is unset). Set `true` only for unauthenticated local development. |

`prometheus/prometheus.yml` configures Prometheus to scrape the API Gateway `/metrics` endpoint
at `host.docker.internal:8000` every 2 seconds:

```yaml
scrape_configs:
  - job_name: "api-gateway"
    metrics_path: "/metrics"
    scrape_interval: 2s
    scrape_timeout: 2s
    authorization:
      type: Bearer
      credentials_file: /etc/prometheus/metrics_token
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

Exposed metrics:
- `gateway_requests_total{method, route, status_code}` — request counter
- `gateway_request_duration_seconds{method, route}` — latency histogram
- `gateway_errors_total{method, route}` — error counter

Unknown routes are always mapped to the bounded label `route="other"` to prevent
label cardinality explosion.

### Grafana Dashboard

`grafana/round10_api_gateway_dashboard.json` is auto-provisioned by
`grafana/provisioning/dashboards/dashboards.yml` into the **Observability** folder.

Panels include: Request Rate, Error Rate, Latency (p50/p95/p99), Top Routes, Circuit Breaker States.

### Distributed Tracing (Jaeger)

The gateway uses OpenTelemetry W3C Trace Context propagation:
- Incoming `traceparent` headers are extracted and used as parent span context.
- Every request generates a `gateway <METHOD> <route>` SERVER span.
- Proxy calls generate child CLIENT spans that are injected into downstream headers.
- Query strings are **stripped** from `http.url` span attributes before export to Jaeger to prevent sensitive data leakage.

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `OTEL_ENABLED` | `true` | Set `false` to disable tracing entirely |
| `OTEL_SERVICE_NAME` | `api-gateway` | Jaeger service name |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318` | Jaeger OTLP/HTTP collector |

### Full Observability Verification

```powershell
# 1. Start observability stack (Grafana: anonymous read-only Viewer; admin login from .env)
docker compose -f docker-compose.dev.yml up -d

# 2. Start downstream dummy services
python dummy_services.py

# 3. Start gateway
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# 4. Run verification script (generates 25 requests, compares Prometheus vs /gateway/dashboard)
python verify_observability.py
```

Grafana UI is available at [http://localhost:3000](http://localhost:3000) (anonymous read-only Viewer; admin login from .env).
See `OBSERVABILITY_EVIDENCE.md` for the definition-of-done evidence report.


### Round 10 Load Test Results

Load tests were executed with Locust against the API Gateway with a realistic 12-endpoint mixed scenario and dummy downstream services running.
Rate limiting was disabled for the sweep (LOAD_TEST_MODE=true) because all Locust users share one source IP.

Run time per level: 60s. Degraded = p95 > 1000 ms or error rate > 1 %.

| Users | Requests | RPS | Error % | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Gateway CPU avg % | Gateway CPU max % | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 286 | 4.88 | 0.00 | 16 | 38 | 270 | 301 | 7 | 16 | OK |
| 10 | 547 | 9.37 | 0.00 | 15 | 37 | 290 | 329 | 12 | 20 | OK |
| 20 | 1087 | 18.60 | 0.00 | 19 | 65 | 280 | 323 | 26 | 54 | OK |
| 50 | 2336 | 39.94 | 0.00 | 130 | 800 | 1200 | 1391 | 78 | 105 | OK |
| 100 | 2093 | 35.09 | 0.00 | 1700 | 3200 | 3500 | 3815 | 93 | 112 | DEGRADED |

A/B at 100 users, dashboard/health tasks excluded (same gateway, same run):

| Users | Requests | RPS | Error % | p50 (ms) | p95 (ms) | p99 (ms) | CPU avg % | CPU max % |
|---|---|---|---|---|---|---|---|---|
| 100 | 3221 | 56.01 | 0.00 | 610 | 1500 | 1800 | 81 | 100 |

> [!NOTE]
> **Observed Break Point**: 100 concurrent users is the first DEGRADED level (`p95 = 3200 ms` > 1000 ms threshold, `Gateway CPU avg = 93%`, `Gateway CPU max = 112%`). Error rate was 0.00%.
>
> **Bottleneck Analysis**: Primary evidence points to gateway CPU and single-worker event-loop saturation (measured CPU avg 93%, max 112% at 100 users). In the A/B isolation test at 100 users with `/gateway/dashboard` and `/health` excluded, throughput rose to 56.01 RPS and p95 improved to 1500 ms (0.00% errors across 3221 requests), but p95 remained above the 1000 ms threshold with CPU avg at 81% (max 100%), confirming that single-worker CPU/event-loop saturation is the primary ceiling.
>
> This observed break point reflects a single-process Uvicorn server on a local development laptop and is not a production capacity limit.

Run the sweep yourself:

```powershell
python dummy_services.py   # terminal 1

# terminal 2 — gateway with LOAD_TEST_MODE (do NOT use --reload)
$env:LOAD_TEST_MODE = "true"
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# terminal 3 — automated sweep harness
$PID = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
python run_locust_sweep.py --gateway-pid $PID
```

Authoritative summary: `load_tests/round10_summary.md`
CSV result files: `load_tests/round10_results_u{5,10,20,50,100}_stats.csv`, `load_tests/round10_results_ab_u100_stats.csv`

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

## Round 9-11 Status

| Milestone | Status | Notes |
|---|---|---|
| M1 Dependency chain on dashboard | In progress | `GET /gateway/dashboard` now includes `dependency_chains` and `affected_by_dependency` (see below). |
| M2 Canary / blue-green routing | Not started | |
| M3 Edge security hardening | Not started | |
| M4 Chaos test (kill Compliance) | Not started | |
| M5 Observability incl. dependency chain | Partial | Per-route latency and error rates already exist; chain health is included via M1. |

### Dependency chain health

`GET /gateway/dashboard` includes two chains: `inventory_to_compliance` and
`supplier_portal_to_compliance`. For each chain:

- `dependency_status`: `healthy`, `degraded` (Compliance answers `/health` but its circuit
  breaker is not closed, or its error rate is at least 20%), `down` (failed its health check),
  or `unknown` (the gateway could not run health checks; this is never reported as an outage).
- `upstream_status`: `affected` when Compliance is degraded or down; otherwise the upstream's
  own health (`healthy` / `down`), or `unknown`.
- `reason`: a short explanation when the chain is not healthy.

`affected_by_dependency` lists, for each struggling dependency, every service it is hurting,
e.g. `{"compliance": ["inventory", "supplier-portal"]}`. That is the "TWO services affected,
not one generic downstream issue" view the spec asks for.

Note: each dashboard call pings all 6 services live (3s timeout each), so a hung service
slows the dashboard by up to 3s. Caching health results is a planned improvement.

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
