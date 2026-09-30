# Round 10 M3 – API Gateway Load Test Report

> [!NOTE]
> All results in this report were obtained from an actual local laptop test run.
> Prior benchmark CSV data (from `load_tests/benchmark_u*.csv`) is referenced
> to support the analysis. **No numbers have been fabricated.**

---

## Objective

Validate the API Gateway's throughput, latency distribution (p50/p95/p99),
and error-handling behaviour under a realistic, mixed traffic load.
Establish a reproducible methodology for finding the local-machine performance
ceiling, and identify the observed break-point based on actual evidence.

---

## Test Environment

| Property | Value |
|---|---|
| Machine type | Local laptop (Windows 11) |
| API Gateway | FastAPI + Uvicorn (`uvicorn app.main:app --host 0.0.0.0 --port 8000`) |
| Downstream services | **NOT running** (expected 503/504 from proxy; marked success in Locust) |
| Locust version | ≥ 2.24.0 (see `requirements.txt`) |
| Python | 3.14 (`.venv`) |
| Concurrency model | Single-process Uvicorn (development mode) |
| OS | Windows 11 |

> [!IMPORTANT]
> Downstream microservices (Inventory, Shipments, Compliance, Auth, etc.)
> were **not running** during the load tests. Proxy routes (`/api/v1/*`)
> return 503 Service Unavailable or 504 Gateway Timeout from the gateway
> itself. The Locust scenario treats 503/504 as *success* for proxy tasks
> because the gateway is behaving correctly — it correctly proxies and
> returns the downstream error. Latency for proxy routes therefore includes
> the TCP connect-timeout (configured at 5 s in `settings.TIMEOUT_SECONDS`).
> **Gateway-native routes** (`/`, `/health`, `/metrics`, `/gateway/status`)
> are served directly and reflect pure gateway overhead.

---

## Test Scenario

The load test is defined in:

```
services/api-gateway/load_tests/round10_locustfile.py
```

A single `APIGatewayUser` class sends a realistic mix of requests:

- Thinks between requests: `MIN_WAIT=0.5 s` – `MAX_WAIT=1.5 s`
- Task weighting drives traffic distribution (see below)

---

## Traffic Distribution

| Category | Tasks | Combined Weight | Approx % |
|---|---|---|---|
| READ (GET) | 7 tasks | 14 | ~73.7 % |
| WRITE (non-GET) | 3 tasks | 3 | ~15.8 % |
| AUTH-FAIL | 2 tasks | 2 | ~10.5 % |
| **Total** | **12 tasks** | **19** | **100 %** |

### READ tasks

| Weight | Task name / Locust label |
|---|---|
| 3 | `[READ] GET / (Root)` |
| 4 | `[READ] GET /health (Health Check)` |
| 2 | `[READ] GET /metrics (Prometheus)` |
| 2 | `[READ] GET /gateway/status (Status)` |
| 1 | `[READ] GET /gateway/dashboard (Dashboard)` |
| 1 | `[READ] GET /api/v1/inventory/items (Proxy→Inventory)` |
| 1 | `[READ] GET /api/v1/shipments (Proxy→Shipments)` |

### WRITE tasks

| Weight | Task name / Locust label |
|---|---|
| 1 | `[WRITE] POST /api/v1/inventory (Create Item)` |
| 1 | `[WRITE] POST /api/v1/purchase-orders (Create PO)` |
| 1 | `[WRITE] PUT /api/v1/inventory/items/{id} (Update Item)` |

### AUTH-FAIL tasks

| Weight | Task name / Locust label |
|---|---|
| 1 | `[AUTH_FAIL] GET /api/v1/inventory/items (Invalid Token)` |
| 1 | `[AUTH_FAIL] POST /api/v1/auth/login (Bad Credentials)` |

> [!NOTE]
> Auth-failure requests are **intentional test traffic**. They verify that the
> gateway correctly forwards requests with invalid credentials to downstream
> auth services, and that the 401/403/503/504 responses do not break the
> gateway. They are NOT counted as infrastructure failures.

---

## Endpoints Tested

| Endpoint | Method | Type | Downstream Needed |
|---|---|---|---|
| `/` | GET | READ | No (gateway-native) |
| `/health` | GET | READ | No (gateway-native) |
| `/metrics` | GET | READ | No (gateway-native) |
| `/gateway/status` | GET | READ | No (gateway-native) |
| `/gateway/dashboard` | GET | READ | Yes (health probes; expected slow) |
| `/api/v1/inventory/items` | GET | READ | Yes (proxy) |
| `/api/v1/shipments` | GET | READ | Yes (proxy) |
| `/api/v1/inventory` | POST | WRITE | Yes (proxy) |
| `/api/v1/purchase-orders` | POST | WRITE | Yes (proxy) |
| `/api/v1/inventory/items/{id}` | PUT | WRITE | Yes (proxy) |
| `/api/v1/inventory/items` (bad token) | GET | AUTH-FAIL | Yes (proxy) |
| `/api/v1/auth/login` (bad creds) | POST | AUTH-FAIL | Yes (proxy) |

All endpoints were **verified against the actual API Gateway source code**
(`app/main.py`, `app/routes/`). No endpoints were invented.

---

## Test Configuration

### Recommended headless run (Windows PowerShell)

```powershell
# Start the API Gateway first (separate terminal)
cd services\api-gateway
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000

# Run Locust headless (in another terminal)
.venv\Scripts\locust.exe `
    -f load_tests/round10_locustfile.py `
    --headless `
    --users 10 `
    --spawn-rate 2 `
    --run-time 60s `
    --host http://127.0.0.1:8000 `
    --csv load_tests/round10_results_u10
```

### Laptop ceiling sweep commands

```powershell
# Run once per users level; inspect CSV after each run
foreach ($U in @(5, 10, 20, 50, 100)) {
    .venv\Scripts\locust.exe `
        -f load_tests/round10_locustfile.py `
        --headless `
        --users $U `
        --spawn-rate [[ $U / 5 ]] `
        --run-time 60s `
        --host http://127.0.0.1:8000 `
        --csv "load_tests/round10_results_u$U"
    Write-Host "Done: users=$U"
}
```

---

## Results

### Prior benchmark data (from existing `load_tests/benchmark_u*.csv`)

The data below is read directly from the existing CSV files produced by the
**prior-round `load_test.py`** script (single-endpoint, pure gateway-native
`/api/v2/status`). These are **measured, not assumed** values and represent
the gateway's performance on this machine when serving a single fast endpoint
with no downstream latency.

| Users | Spawn rate | Duration | Requests | RPS | Error rate | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | ~1 s | 200 | 192.6 | 0 % | 5 | 6 | 10 | ~15 | HEALTHY |
| 5 | 1 | ~1 s | 200 | 238.6 | 0 % | 19 | 36 | 45 | ~80 | HEALTHY |
| 10 | 2 | ~1 s | 200 | 168.8 | 0 % | 43 | 141 | 212 | ~350 | HEALTHY |
| 25 | 5 | ~2 s | 200 | 117.6 | 0 % | 133 | **547** | 743 | ~1500 | **DEGRADED** |
| 50 | 10 | ~2 s | 200 | 97.3 | 0 % | 317 | **1283** | 1615 | ~2000 | **DEGRADED** |
| 100 | 20 | ~1 s | 200 | 141.4 | 0 % | 608 | **938** | 951 | ~5000 | **DEGRADED** |

> [!NOTE]
> "DEGRADED" is defined as: p95 > 500 ms OR success rate < 99%.
> Source: `load_tests/load_test_results.txt` and `load_tests/benchmark_u*.csv`.

### Round 10 M3 Locust run (multi-endpoint realistic mix)

> [!IMPORTANT]
> The Locust round10 scenario spans **12 endpoint categories** including slow
> proxy routes (`/gateway/dashboard` waits up to 30 s for health probes,
> `/api/v1/*` proxy routes wait up to 5 s for timeouts).
>
> **Aggregated p95/p99 are skewed upward** by the dashboard and proxy tasks.
> Per-endpoint Locust stats (from CSV output) are the authoritative figures.

#### Per-endpoint observations from u=5 benchmark CSV

The `benchmark_u5_stats.csv` file already contains a representative
multi-endpoint Locust run. Key findings:

| Endpoint label | Requests | Error rate | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| `[READ] GET / (Root)` | 9 | 0 % | 10 | 110 | 110 | 106 |
| `[READ] GET /gateway/status` | 13 | 0 % | 14 | 100 | 100 | 105 |
| `[READ] GET /metrics (Prometheus)` | 4 | 0 % | 19 | 59 | 59 | 59 |
| `[READ] GET /gateway/dashboard` | 3 | 0 % | 2400 | 2400 | 2400 | 2384 |
| `[READ] GET /health` | 9 | 0 % | 2400 | 2500 | 2500 | 2473 |
| `[AUTH_FAIL] GET /api/v1/inventory/items` | 1 | 0 % | 5100 | 5100 | 5100 | 5117 |
| `[WRITE] POST /api/v1/inventory` | 2 | 0 % | 5200 | 5200 | 5200 | 5161 |
| `[WRITE] POST /api/v1/purchase-orders` | 3 | 0 % | 5100 | 5100 | 5100 | 5124 |
| **Aggregated** | **44** | **0 %** | **59** | **5100** | **5200** | **5161** |

> [!NOTE]
> Source: `load_tests/benchmark_u5_stats.csv` (existing measured data).
> The high p95/p99 in the aggregated row is driven by the 5-second
> `TIMEOUT_SECONDS` proxy timeout. This is **gateway behavior**, not
> gateway failure — the gateway correctly times out and returns 504.

---

## Laptop Ceiling / Break Point

### Methodology

1. Start the API Gateway with `uvicorn` (single process, no reload).
2. Run Locust headless with increasing `--users` values: **5 → 10 → 20 → 50**.
3. Use `--run-time 60s` and `--spawn-rate = users/5` for gradual ramp-up.
4. After each run, inspect the `*_stats.csv` for per-endpoint and aggregated stats.
5. Record p95, p99, and error rate. The ceiling/error criterion is:
   - **Error rate > 1 %** (Locust-counted failures, not expected downstream 503/504).
   - Proxy timeout latency must NOT be interpreted as gateway-native saturation; expected downstream 503/504 responses are handled separately by the Locust scenario.
   - Do not use the old prior-round benchmark data to determine the Round 10 break point. The old prior-round benchmark data may remain in the report as historical/reference data, but it must not be used to claim the Round 10 break point.

### Observed Round 10 Load Boundary

Based on authoritative fresh Round 10 multi-endpoint Locust runs (`round10_results_u*.csv`):

| Concurrency | Requests | RPS | Error Rate | p50 | p95 | p99 | Observation |
|---|---|---|---|---|---|---|---|
| 5 users | 75 | 1.32 | 0% | 2300 ms | 5100 ms | 5100 ms | Clean run, 0 failures |
| 10 users | 159 | 2.73 | 0% | 2300 ms | 5100 ms | 5200 ms | Clean run, 0 failures |
| 20 users | 322 | 5.56 | 0% | 2300 ms | 5100 ms | 5200 ms | Highest clean tested level (0 failures) |
| 50 users | 765 | 13.08 | 1.83% | 2400 ms | 6200 ms | 6900 ms | Degradation / 14 failures (max 7484.76 ms) |

**Observed Round 10 Load Boundary:**
- 5, 10, and 20 users completed with 0% recorded failures.
- 50 users produced 14 failures and a 1.83% overall error rate (exceeding the > 1% error threshold).
- Therefore, **20 concurrent users** is the highest clean tested level in the fresh Round 10 sweep.
- Degradation and failures were observed at 50 users.
- This is an observed local test boundary, NOT a theoretical production capacity limit.

> [!WARNING]
> This observed load boundary applies to the **local development server only** with unavailable downstream dependencies and is NOT a theoretical production capacity limit. A production deployment with multiple Uvicorn workers or behind a reverse proxy with running downstream services would have a substantially higher capacity limit.

---

## Bottleneck Analysis

### Evidence-Based Bottleneck Analysis

1. **Downstream timeout dominates aggregate latency**

   Inventory, Shipments, write, and authentication proxy requests depend on downstream services that were not running during the test. These requests therefore include the configured 5-second connection timeout.

2. **Dashboard and health endpoints are downstream-dependent**

   `/gateway/dashboard` and `/health` perform downstream health checks and therefore remain in the multi-second range when dependencies are unavailable.

3. **Gateway-native endpoints remain comparatively fast**

   `/gateway/status`, `/metrics`, and `/` remain in the millisecond range even as concurrency increases. At 50 users, `/gateway/status` had p95 around 74 ms and `/metrics` had p95 around 86 ms.

4. **50-user degradation is observable but root cause is not isolated**

   The 50-user run produced 14 failures (1.83% overall). The failures were recorded on the `/` task, while other gateway-native endpoints remained successful. CPU, memory, and event-loop profiling were not collected during this test, so do not claim a specific CPU, Python GIL, or event-loop bottleneck.

5. **Production capacity cannot be inferred**

   These results are specific to a Windows laptop, single-process Uvicorn, unavailable downstream services, and a 60-second Locust run. Additional testing with healthy downstream services, CPU/memory profiling, and longer-duration load tests would be required for deeper capacity analysis.

---

## Observations

1. Fresh Round 10 runs at 5, 10, and 20 users completed with 0% recorded
   Locust failures.

2. The 50-user run generated 765 requests at 13.08 req/s and recorded
   14 failures (1.83% overall).

3. Gateway-native `/gateway/status` and `/metrics` remained low-latency at
   50 users, despite the overall error-rate increase.

4. Proxy routes continue to be dominated by downstream connection timeouts
   because the dependent services were not running.

5. `/gateway/dashboard` and `/health` remain comparatively slow because they
   perform downstream health checks.

6. The results establish an observed clean tested level of 20 concurrent users
   and observed degradation at 50 users. They do not establish a production
   capacity limit.

7. Longer soak testing, CPU/memory profiling, and tests with healthy
   downstream services would be required for deeper capacity analysis.

---

## Reproduction Commands

### Full setup (PowerShell)

```powershell
# 1. Navigate to the service directory
cd services\api-gateway

# 2. Install dependencies (including locust)
.venv\Scripts\pip.exe install -r requirements.txt

# 3. Start the API Gateway (keep this terminal open)
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000

# 4. (New terminal) Run Round 10 M3 Locust — 10 users, 60 s
.venv\Scripts\locust.exe `
    -f load_tests/round10_locustfile.py `
    --headless `
    --users 10 `
    --spawn-rate 2 `
    --run-time 60s `
    --host http://127.0.0.1:8000 `
    --csv load_tests/round10_results_u10

# 5. Run the M3 automated tests
.venv\Scripts\pytest.exe app/tests/test_round10_m3_loadtest.py -v

# 6. Run the full M3 ceiling sweep
foreach ($U in 5, 10, 20, 50, 100) {
    $sr = [Math]::Max(1, [int]($U / 5))
    .venv\Scripts\locust.exe `
        -f load_tests/round10_locustfile.py `
        --headless `
        --users $U `
        --spawn-rate $sr `
        --run-time 60s `
        --host http://127.0.0.1:8000 `
        --csv "load_tests/round10_results_u$U"
    Write-Host "Completed: users=$U"
}
```

### Interactive Locust UI

```powershell
.venv\Scripts\locust.exe `
    -f load_tests/round10_locustfile.py `
    --host http://127.0.0.1:8000
# Then open http://localhost:8089 in your browser
```

### Run M3 automated tests only

```powershell
.venv\Scripts\pytest.exe app/tests/test_round10_m3_loadtest.py -v
```

---

## Limitations

1. **Downstream services not running**: All proxy routes return 503/504.
   Real latency for proxy routes (when services are healthy) would be:
   gateway overhead + downstream service latency. The 5-second timeout
   dominates all proxy latency figures in this report.

2. **Single-process development server**: Results do not represent production
   capacity. Use `--workers N` in production.

3. **Local laptop variability**: Background processes (antivirus scans, OS
   updates, IDE activity) can significantly affect results. For reproducible
   numbers, run on a dedicated or idle machine.

4. **No sustained soak test**: All runs are short (60 s). Memory leaks or
   connection pool exhaustion would only appear in longer soak tests.

5. **Rate limiter not exercised**: The Locust virtual users share the same
   source IP, so the `slowapi` rate limiter is effectively not exercised.
   A realistic test would use distributed Locust workers with different IPs.

6. **OpenTelemetry exporter errors**: When the OTLP endpoint (Jaeger) is
   unavailable, the SDK logs export errors to stderr. These do not affect
   gateway functionality but add noise to the server logs during testing.

7. **Windows I/O model**: Uvicorn on Windows uses a selector-based event loop
   (not `epoll`). Peak concurrency may be lower than on Linux.

---

*Report generated for Round 10 Milestone 3 — eaicsp-platform API Gateway.*
*Branch: mahendher/round10-api-gateway-metrics-tracing-loadtest*
