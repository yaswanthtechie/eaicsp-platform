# API Gateway

## Overview

The API Gateway is the entry point for client requests in the EAICSP platform. It sits in front of the downstream services, applies gateway-level checks, forwards requests, and exposes a few operational endpoints for status and metrics.

The current implementation includes:

- catch-all proxy routing to configured downstream services
- gateway-level authentication pre-check against Platform
- per-user and per-role in-memory rate limiting with IP fallback
- global SlowAPI IP limiter
- per-service circuit breaker state
- aggregated dashboard summary for inventory, compliance, and logistics
- basic metrics dashboard with per-route and per-service data
- request ID propagation and downstream header normalization

---

## Project Structure

```text
services/api-gateway/
├── app/
│   ├── core/
│   │   └── config.py
│   ├── middleware/
│   │   ├── logging.py
│   │   ├── rate_limit.py
│   │   ├── ratelimit.py
│   │   ├── request_id.py
│   │   └── tracing.py
│   ├── routes/
│   │   ├── aggregation.py
│   │   ├── dashboard.py
│   │   ├── gateway.py
│   │   ├── health.py
│   │   └── v2.py
│   ├── schemas/
│   │   └── responses.py
│   ├── services/
│   │   ├── aggregation.py
│   │   ├── auth.py
│   │   ├── cache.py
│   │   ├── circuit_breaker.py
│   │   ├── health.py
│   │   ├── metrics.py
│   │   └── proxy.py
│   ├── tests/
│   │   ├── test_cache.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_cross_service_integration.py
│   │   ├── test_dashboard.py
│   │   ├── test_jwt_config.py
│   │   ├── test_rate_limit.py
│   │   └── test_versioning.py
│   ├── main.py
│   └── __init__.py
├── tests/
│   ├── test_aggregation.py
│   ├── test_api.py
│   ├── test_integration.py
│   ├── test_m3_gateway.py
│   ├── test_m4_gateway.py
│   ├── test_m5_gateway.py
│   ├── test_real_inventory_integration.py
│   ├── test_real_platform_integration.py
│   ├── test_round5_auth_forwarding.py
│   ├── test_round5_gateway_integration.py
│   └── __init__.py
├── .env.example
├── dummy_services.py
├── load_test.py
├── load_tests/
├── pyproject.toml
├── pytest.ini
├── README.md
├── requirements.txt
└── .gitignore
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Gateway status response (`message`, `status`, `version`) |
| GET | `/health` | Health check for all configured downstream services |
| GET | `/gateway/status` | Operational status endpoint without exposing secrets |
| GET | `/gateway/dashboard` | Gateway metrics dashboard |
| GET | `/api/v1/dashboard/summary` | Aggregated dashboard summary across inventory, compliance, and logistics |
| GET | `/api/v1/openapi.json` | OpenAPI schema |
| GET | `/api/v2/status` | API v2 status stub |
| GET | `/api/v2/inventory/items` | API v2 inventory response-envelope stub |
| GET | `/api/v1/auth/...` | Platform auth routes; exempt from gateway pre-check |
| GET/POST/PUT/DELETE/PATCH/OPTIONS/HEAD | `/{path}` | Catch-all proxy to configured downstream services |

The gateway routes are configured via `SERVICE_ROUTES` in `app/core/config.py`.

### Current downstream route mapping

| Prefix | Target |
|--------|--------|
| `/api/v1/inventory` | `http://localhost:8001` |
| `/api/v1/shipments` | `http://localhost:8002` |
| `/api/v1/compliance` | `http://localhost:8003` |
| `/api/v1/purchase-orders` | `http://localhost:8004` |
| `/api/v1/auth` | `http://localhost:8005` |
| `/api/v1/supplier-risk` | `http://localhost:8006` |

The code names the shipments route as `shipments` in the gateway config, even though the underlying service is the Logistics service. The gateway uses the `shipments` path as the public route and forwards to the configured shipments/logistics URL.

---

## Features

### Dynamic Reverse Proxy

`ProxyService` in `app/services/proxy.py` forwards requests to the configured downstream service using the matching route prefix. A route matches exactly or when the path starts with `<prefix>/`; an unmatched path returns `404`.

The proxy:

- strips hop-by-hop headers before forwarding and before returning downstream response headers
- sets `X-Forwarded-For` and `X-Forwarded-Proto`
- preserves or generates `X-Request-ID` and forwards it downstream
- forwards request bodies and query strings without changing their content
- streams downstream response bodies through `StreamingResponse` and closes the upstream response after streaming
- retries only safe methods: `GET`, `HEAD`, `OPTIONS`, `PUT`, and `DELETE`
- does not retry `POST` or `PATCH`
- retries only timeout and connection errors, with exponential backoff from `0.5` seconds up to `5` seconds

Downstream timeout errors return `504`, connection/request errors return `503`, and an open circuit breaker fails fast with `503`.

### Circuit Breaker

`CircuitBreakerManager` maintains a thread-safe, in-memory breaker per downstream service:

- **CLOSED**: requests pass through and outcomes are recorded in a rolling window.
- **OPEN**: requests fail fast with `503`. After `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`, the breaker permits a trial request.
- **HALF-OPEN**: a successful trial returns the breaker to CLOSED and clears its window; a failed trial returns it to OPEN.

The default trip condition is a failure rate greater than `0.50` within the `60`-second rolling window. `CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD`, `CIRCUIT_BREAKER_WINDOW_SECONDS`, and `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` control these values. Downstream `401` and `403` responses are passed through and are not counted as infrastructure failures for the breaker.

### In-Memory Cache

`InMemoryCache` is a thread-safe, process-local cache. Entries may have an optional TTL and expire lazily on read. Individual keys can be deleted, and `invalidate_pattern()` removes keys matching an `fnmatch` pattern or string prefix. Cache reads update hit/miss metrics and the dashboard reports the aggregate cache hit rate.

### Health Monitoring

`GET /health` checks every configured downstream service concurrently with `asyncio.gather`. Each service is queried at `<base_url>/health` with a 3-second timeout. A 2xx response is reported as `UP`; a non-2xx response or connection/timeout error is reported as `DOWN`. One failed check does not prevent the remaining checks from completing, and health checks do not consume normal rate-limit quotas.

### Structured Logging and Request IDs

`RequestIDMiddleware` preserves a client `X-Request-ID` after removing CR/LF characters, or generates a UUID4 when the header is absent or empty. The ID is echoed in the response and forwarded downstream. `LoggingMiddleware` records the request ID, method, path, status, duration, and resolved client IP for each request.

### API Versioning

The gateway serves the existing `/api/v1/*` surface and includes `/api/v2/status` plus `/api/v2/inventory/items` demonstration stubs. The v2 routes show a versioned response envelope without changing v1 behavior.

---

## Configuration

The gateway loads settings from `.env` or environment variables using `pydantic-settings`. Required settings are noted below. Secrets must not be committed to source control.

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `APP_NAME` | No | `API Gateway` | FastAPI app name |
| `VERSION` | No | `1.0.0` | App version |
| `DEBUG` | No | `False` | Debug flag |
| `LOAD_TEST_MODE` | No | `False` | Server-side bypass for per-user/per-role rate limiting |
| `PLATFORM_SERVICE_URL` | No | `http://localhost:8005` | Base URL for Platform verification |
| `INVENTORY_SERVICE_URL` | No | `http://localhost:8001` | Inventory service URL |
| `SHIPMENTS_SERVICE_URL` | No | `http://localhost:8002` | Shipments/logistics service URL |
| `COMPLIANCE_SERVICE_URL` | No | `http://localhost:8003` | Compliance service URL |
| `PURCHASE_ORDERS_SERVICE_URL` | No | `http://localhost:8004` | Purchase orders service URL |
| `SUPPLIER_RISK_SERVICE_URL` | No | `http://localhost:8006` | Supplier risk service URL |
| `API_GATEWAY_SERVICE_API_KEY` | No | `None` | Optional gateway-to-service API key |
| `SERVICE_ROUTES` | No | See config | Route-to-base-url map |
| `TIMEOUT_SECONDS` | No | `5` | Default downstream HTTP timeout |
| `MAX_RETRIES` | No | `2` | Retry attempts for retryable methods |
| `SECRET_KEY` | Yes | none | Required for JWT validation |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `TRUSTED_PROXIES` | No | `[]` | Proxy IPs allowed to override client IP via `X-Forwarded-For` |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Window size used by in-memory rate limiter |
| `ROLE_RATE_LIMITS` | No | see config | Per-role quota map |
| `ROUTE_RATE_LIMITS` | No | `/health` exempt, `/api/v1/dashboard` = 60, `/api/v1/auth` = 30 | Route-specific quotas |
| `CIRCUIT_BREAKER_FAILURE_RATE_THRESHOLD` | No | `0.50` | Open breaker if failure rate exceeds this threshold |
| `CIRCUIT_BREAKER_WINDOW_SECONDS` | No | `60` | Rolling failure-rate window |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | No | `30.0` | Time before OPEN transitions to HALF-OPEN |
| `LATENCY_HISTOGRAM_BUCKETS` | No | `[10, 25, 50, 100, 250, 500, 1000]` | Metric bucket boundaries |
| `AUTH_PRECHECK_ENABLED` | No | `False` | Enables gateway-level auth pre-check |
| `AUTH_PRECHECK_TIMEOUT_SECONDS` | No | `3.0` | Timeout used for Platform verification request |

### Role quotas used by the gateway

`ROLE_RATE_LIMITS` in `app/core/config.py` currently includes:

| Role | Requests per `RATE_LIMIT_WINDOW_SECONDS` |
|------|-------------------------------------------|
| `ceo` | `200` |
| `vp_operations` | `200` |
| `procurement_manager` | `100` |
| `logistics_manager` | `100` |
| `compliance_officer` | `100` |
| `warehouse_manager` | `100` |
| `analyst` | `60` |
| `supplier` | `60` |
| `default` | `60` |

Unknown or missing roles fall back to the `default` quota.

---

## Proxy Behavior

The main proxy implementation is in `app/services/proxy.py`.

### M1 - Full request/response transformation

The gateway forwards requests to the matching downstream service by prefix. It strips hop-by-hop request headers before forwarding, including:

- `connection`
- `keep-alive`
- `proxy-authenticate`
- `proxy-authorization`
- `te`
- `trailer`
- `transfer-encoding`
- `upgrade`
- `host`

The same response filtering is applied when the gateway builds the outbound response stream. The gateway also removes:

- `content-length`
- `content-encoding`
- `date`
- `server`

The proxy adds headers for client tracking and downstream service auth when configured:

- `X-Forwarded-For` is added using the socket peer or the trusted proxy chain when `TRUSTED_PROXIES` matches
- `X-Forwarded-Proto` is set from the incoming request scheme
- `X-Request-ID` is preserved or generated by middleware and forwarded downstream
- `X-Caller-Service` is set to `api-gateway` by default, and any caller-supplied value is dropped
- `X-API-Key` and `X-Service-Name` are added when `API_GATEWAY_SERVICE_API_KEY` is configured

The request body is forwarded exactly as sent; the gateway reads the body once and then constructs the downstream request from it. For streaming, it uses `httpx.AsyncClient.send(..., stream=True)` and then returns a FastAPI `StreamingResponse` that yields bytes from the upstream stream while closing the response in a final block.

Retry behavior is limited to safe methods:

- retryable: `GET`, `HEAD`, `OPTIONS`, `PUT`, `DELETE`
- not retried: `POST`, `PATCH`

Retry is triggered only for connection and timeout errors defined by `httpx`. The retry timing uses a wait strategy with exponential backoff, starting at 0.5s and capped at 5s.

Timeout and connection failures are returned as gateway errors:

- downstream timeout -> `504` with `{"error": "<service> service timeout"}`
- downstream connection/request error -> `503` with `{"error": "<service> service unavailable"}`

If the circuit breaker is open, the request fails fast with `503` before the downstream call is attempted.

---

## Aggregation Endpoint

### M2 - Aggregation endpoint / BFF pattern

The aggregation endpoint is exposed at:

- `GET /api/v1/dashboard/summary`

This route is defined in `app/routes/aggregation.py` and handled by `AggregationService.get_dashboard_summary()` in `app/services/aggregation.py`.

The gateway fans out in parallel to:

- inventory: `GET {INVENTORY_SERVICE_URL}/api/v1/inventory`
- compliance: `GET {COMPLIANCE_SERVICE_URL}/api/v1/compliance/audit/summary`
- logistics/shipments: `GET {SHIPMENTS_SERVICE_URL}/api/v1/shipments/`

It uses `asyncio.gather` so the requests run concurrently. A single downstream failure does not block the other requests.

The response shape is:

```json
{
  "status": "complete|partial|unavailable",
  "inventory": { "status": "ok|unavailable", "data": ..., "error": ... },
  "compliance": { "status": "ok|unavailable", "data": ..., "error": ... },
  "logistics": { "status": "ok|unavailable", "data": ..., "error": ... }
}
```

The aggregator sets the overall status as:

- `complete` when all three downstream calls succeed
- `partial` when one or more succeed and at least one fails
- `unavailable` when all three fail or are unavailable

The individual service entries include a status and either data or an error string. The gateway does not raise an exception for partial or unavailable aggregation results; it returns an HTTP 200 for the summary itself.

---

## Traffic Management and Rate Limiting

### M3 - Advanced traffic management

The gateway uses two main rate limiting layers:

#### 1. Global SlowAPI IP limiter

`app/middleware/ratelimit.py` creates a `Limiter` using the real client IP from `get_real_ip()`. The default limit is `100/minute`.

`get_real_ip()` does not trust `X-Forwarded-For` unless the immediate peer is in `TRUSTED_PROXIES`. This prevents a client from spoofing another IP by sending a forged forwarded IP header.

#### 2. Per-user / per-role limiter

`app/middleware/rate_limit.py` implements `PerUserRoleRateLimitMiddleware` with an in-memory fixed-window limiter.

The middleware:

- skips health checks entirely
- bypasses per-user/per-role quotas when `LOAD_TEST_MODE` is enabled on the server side
- checks `Authorization: Bearer <token>`
- validates the JWT using `SECRET_KEY` and `JWT_ALGORITHM`
- uses user or role claims when valid
- falls back to IP-based limiting when the token is missing, malformed, or invalid

Bucket rules are:

- authenticated user: `user:<user_id>`
- authenticated role: `role:<role>`
- no valid JWT: `ip:<client_ip>`
- route-scoped isolation: `user:<user_id>:<route_pattern>` or `role:<role>:<route_pattern>`

The route-specific quotas defined in config are:

- `/health`: exempt
- `/api/v1/dashboard`: `60`
- `/api/v1/auth`: `30`

When the limit is reached, the gateway returns `429 Too Many Requests` with:

- `Retry-After`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining: 0`

The gateway also sets those response headers on allowed requests.

### Graceful degradation

The gateway uses graceful degradation in the limit checks and downstream aggregation flow:

- a single downstream aggregation failure does not stop the other service calls
- auth pre-check can reject a request early without sending it to downstream business services
- health checks are exempt and never consume normal request quotas

---

## Observability and Metrics

### M4 - Full observability

Metrics are collected in `app/services/metrics.py` via `MetricsCollector`.

The collector tracks:

- request counts per service and per route
- latency histogram buckets
- p50 and p95 latency per service
- error counts and error rates per route
- circuit breaker states per service
- cache hits and misses
- cache hit rate
- top callers by service name
- caller tracking based on `X-Caller-Service`
- route normalization for dynamic endpoints

The latency histogram buckets are configured in `LATENCY_HISTOGRAM_BUCKETS` and currently use:

- `<= 10ms`
- `<= 25ms`
- `<= 50ms`
- `<= 100ms`
- `<= 250ms`
- `<= 500ms`
- `<= 1s`
- `> 1s`

Route normalization folds dynamic paths to canonical gateway routes such as:

- `/api/v1/inventory/123` -> `/api/v1/inventory`
- `/api/v1/compliance/abc` -> `/api/v1/compliance`
- health exemptions are strict matches, although metrics normalization maps paths beginning with `/health` to `/health`

Error counting is designed to separate real backend failures from client auth outcomes:

- `5xx`, request errors, and timeout failures count as route errors
- `401` and `403` are not treated as service failures for the circuit breaker

The dashboard route `/gateway/dashboard` returns a structure with both current and compatibility-friendly fields:

```json
{
  "status": "healthy",
  "timestamp": "...",
  "services": {...},
  "metrics": {
    "routes": {...},
    "circuit_breakers": {...},
    "cache": {...},
    "top_callers": [...]
  },
  "routes": {...},
  "circuit_breakers": {...},
  "cache": {...},
  "top_callers": [...]
}
```

The `Gateway Status` endpoint at `/gateway/status` does not expose secrets or config values.

---

## Gateway-level Authentication Pre-check

### M5 - Gateway authentication pre-check

The gateway includes an authentication pre-check service in `app/services/auth.py`.

This feature is controlled by:

- `AUTH_PRECHECK_ENABLED`
- `AUTH_PRECHECK_TIMEOUT_SECONDS`

When enabled, the gateway checks the incoming request before proxying it to a protected downstream route. It calls the Platform verification endpoint:

- `POST {PLATFORM_SERVICE_URL}/api/v1/auth/verify`

The pre-check is only used for protected paths. Exact and prefix exemptions are defined as:

- exact: `/`, `/api/v1/openapi.json`, `/docs`, `/redoc`
- prefixes: `/health`, `/api/v1/auth`, `/gateway`

Flow:

1. Client sends `Authorization: Bearer <token>`
2. Gateway checks the request path and pre-check settings
3. Gateway validates the Authorization header format
4. Gateway calls Platform `/api/v1/auth/verify`
5. Platform returns `200` for a valid token; the request continues downstream
6. Platform returns `401` for invalid, expired, or malformed auth; the gateway rejects the request
7. Platform returns `5xx` or fails to respond; the gateway returns a gateway-side `503` or `504`

The gateway does not replace downstream authorization. Business service role checks remain the responsibility of the downstream service. This pre-check is an additional early validation layer only.

Auth pre-check behavior matches the implementation:

- missing Authorization header -> `401 {"detail": "Not authenticated"}`
- malformed Authorization header -> `401 {"detail": "Invalid or expired token"}`
- Platform `401` -> `401` with Platform error body
- Platform timeout -> `504 {"detail": "Authentication service timeout"}`
- Platform connect/error or `5xx` -> `503 {"detail": "Authentication service unavailable"}`

```text
Client
  |
  | Authorization: Bearer <token>
  v
API Gateway :8000
  |
  | POST /api/v1/auth/verify
  v
Platform :8005
  |
  +---- 200 ----> Gateway continues to downstream service
  |
  +---- 401 ----> Gateway rejects request
```

---

## Round 6-7-8 milestone notes

The gateway includes the milestones implemented in the current repository.

### M1 - Full request/response transformation

Implemented in `app/services/proxy.py`.

This includes prefix-based route matching, hop-by-hop stripping, `X-Forwarded-For`, `X-Forwarded-Proto`, request ID propagation, service auth headers, response header normalization, body forwarding, streaming, and safe retry behavior for `GET`, `HEAD`, `OPTIONS`, `PUT`, and `DELETE`.

### M2 - Aggregation endpoint / BFF pattern

Implemented in `app/services/aggregation.py` and `app/routes/aggregation.py`.

The gateway performs parallel calls to inventory, compliance, and logistics using `asyncio.gather` and returns a combined status object.

### M3 - Advanced traffic management

Implemented in `app/middleware/ratelimit.py` and `app/middleware/rate_limit.py`.

This includes global SlowAPI limits, per-user/per-role quotas, IP fallback, route-specific quotas, health bypass and route isolation, and `Retry-After` plus the standard rate-limit headers.

### M4 - Full observability

Implemented in `app/services/metrics.py` and `app/routes/dashboard.py`.

The dashboard exposes per-route metrics, latency buckets, cache metrics, circuit breaker state, and top callers.

### M5 - Gateway-level authentication pre-check

Implemented in `app/services/auth.py`.

This is a pre-validation step against Platform before the request is sent downstream. It does not replace downstream business authorization.

---

## Testing

The gateway test suite includes the current round-based tests as well as the earlier route and forwarding checks.

### Current test organization

| Test file | What it covers |
|-----------|---------------|
| `tests/test_aggregation.py` | Aggregation success and partial/unavailable cases |
| `tests/test_m3_gateway.py` | Rate limiting, health exemptions, route-specific limits, IP fallback |
| `tests/test_m4_gateway.py` | Metrics, histograms, circuit breaker state, top callers, cache metrics |
| `tests/test_m5_gateway.py` | Authentication pre-check, Platform verification flow, 401/503/504 handling |
| `tests/test_round5_auth_forwarding.py` | Authorization header passthrough and downstream 401/403 behavior |
| `tests/test_round5_gateway_integration.py` | Gateway integration error handling with mocked services |
| `tests/test_real_platform_integration.py` | Live verification against Platform |
| `tests/test_real_inventory_integration.py` | Live verification against Inventory |

The existing unit and service tests remain under `app/tests/`:

| Test file | What it covers |
|-----------|---------------|
| `app/tests/test_cache.py` | Cache TTL, invalidation, and metrics integration |
| `app/tests/test_circuit_breaker.py` | CLOSED, OPEN, and HALF-OPEN transitions and recovery |
| `app/tests/test_cross_service_integration.py` | Cross-service gateway behavior |
| `app/tests/test_dashboard.py` | Dashboard aggregation and compatibility fields |
| `app/tests/test_jwt_config.py` | JWT configuration and validation settings |
| `app/tests/test_rate_limit.py` | User, role, IP fallback, and load-test rate limiting |
| `app/tests/test_versioning.py` | `/api/v2/*` response stubs |

Run the suite with:

```bash
cd services/api-gateway
python -m pytest -v
```

No claim is made here that all tests pass in every environment; the suite depends on the configured services and environment variables being present.

---

## Live verification

The Round 5 live integration architecture uses three services:

```text
Platform Service (:8005)
  ^
  | authentication verification and forwarded requests
  |
Client -> API Gateway (:8000) -> Inventory Service (:8001)
```

The gateway runs on port `8000`, Platform runs on `8005`, and Inventory runs on `8001`.

Start each service separately as needed:

```bash
# Platform
cd services/platform
uvicorn app.main:app --host 127.0.0.1 --port 8005

# Inventory
cd services/inventory
uvicorn app.main:app --host 127.0.0.1 --port 8001

# Gateway
cd services/api-gateway
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The full downstream integration tests require the services to be running. The M5 auth flow can still be verified with Platform and the Gateway even when Inventory is unavailable because the pre-check occurs before the downstream business request is sent.

Run the live integration suites with:

```bash
python -m pytest tests/test_real_platform_integration.py -v
python -m pytest tests/test_real_inventory_integration.py -v
```

---

## Known limitations

- `InMemoryRateLimiter` and the circuit breaker state are process-local. They are not shared across multiple gateway instances.
- `InMemoryCache` is not shared across instances or processes.
- `X-Forwarded-For` is only trusted when the immediate peer is in `TRUSTED_PROXIES`.
- `LOAD_TEST_MODE` is a server-side feature and should not be enabled in production.
- The gateway does not replace downstream authorization; business-service authorization remains downstream.
- The gateway-level auth pre-check is additional validation, not a full authorization engine.

---

## Security notes

- `SECRET_KEY` must not be committed to source control.
- Platform auth signing configuration and Gateway JWT validation must stay aligned.
- `LOAD_TEST_MODE` is server-side only and should be set intentionally.
- `X-Forwarded-For` must not be trusted blindly when the direct peer is not in `TRUSTED_PROXIES`.
- Hop-by-hop headers are stripped before forwarding.
- Invalid or missing authentication is rejected by the M5 pre-check when that feature is enabled.

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

**Prerequisite:** seed the platform database before running the live suites:

```bash
cd services/platform
python -m app.seed
```

Without this, the four login-based tests fail with `401`; this is missing
fixture data, not a gateway failure.

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

### 4. PR Verification

The baseline gateway suite reports `139 passed, 11 skipped (live tests skip
when downstream services are not running)`; with the new regression test, this
checkout reports `140 passed, 11 skipped`. The skipped count is expected when
the live downstream services are unavailable; a green suite alone does not
prove that the live demo ran.

```bash
cd services/api-gateway
pytest -q
```

For the auth circuit-breaker check, with Platform on port `8005` and the
gateway on port `8000`, send 20 invalid-token requests and inspect the
dashboard:

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null -X POST http://localhost:8000/api/v1/auth/verify -H "Authorization: Bearer bad"
done
curl -s http://localhost:8000/gateway/dashboard | grep -i "circuit\|failure"
```

The auth service's breaker stats should show zero requests recorded. `401`
responses are excluded from breaker accounting, so the 20 invalid-token calls
must not be counted as successful requests.

**PR scope note:** Includes a one-line unblock in `services/inventory` (adds
the missing `InventoryOperationError`), agreed with the owner as required for
the Round 5 live demo.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `pydantic` | Validation and schemas |
| `pydantic-settings` | Environment-based settings |
| `httpx` | Async HTTP client for proxy and verification calls |
| `tenacity` | Retry loop for safe methods |
| `slowapi` | Global IP-based rate limiting |
| `PyJWT` | JWT validation |
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |

---

## Installation

```bash
cd services/api-gateway
python -m venv .venv
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then configure `SECRET_KEY` and any required service URLs before running the gateway.

---

## Running the gateway

```bash
cd services/api-gateway
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The local endpoints are then available at:

- http://localhost:8000/
- http://localhost:8000/health
- http://localhost:8000/gateway/status
- http://localhost:8000/gateway/dashboard
- http://localhost:8000/docs

---

## Notes

This README reflects the current gateway implementation in the repository. It is intentionally limited to what is actually present in the source and tests, and it does not describe capabilities that are not implemented in the code.

---

## Author

EAICSP Platform -- Mahendher
