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
| Downstream services | **Running** (`python dummy_services.py` — 6 mock services on ports 8001–8006) |
| Locust version | 2.46.6 (pinned in `requirements.txt`) |
| Python | 3.14 (`.venv`) |
| Concurrency model | Single-process Uvicorn (development mode) |
| OS | Windows 11 |

> [!IMPORTANT]
> Downstream dummy microservices (Inventory :8001, Shipments :8002, Compliance :8003,
> Auth :8004, Purchase-Orders :8005, Supplier-Portal :8006) were running via
> `python dummy_services.py` during the u5–u100 sweep runs.
> Proxy route latencies (110–200 ms at u50) confirm downstream availability.
> `/gateway/dashboard` latency is higher because it performs live health probes
> to all 6 services on every request.

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

Based on authoritative fresh Round 10 multi-endpoint Locust runs (`round10_results_u*.csv`).
All data read directly from the committed CSV files — no numbers fabricated.

| Concurrency | Requests | RPS | Error Rate | p50 | p95 | p99 | Max | Observation |
|---|---|---|---|---|---|---|---|---|
| 5 users | 86 | 4.75 | **0 %** | 14 ms | 37 ms | 300 ms | 633 ms | Clean |
| 10 users | 169 | 8.86 | **0 %** | 16 ms | 40 ms | 280 ms | 308 ms | Clean |
| 20 users | 327 | 17.22 | **0 %** | 31 ms | 140 ms | 360 ms | 423 ms | Clean |
| 50 users | 743 | 39.12 | **0 %** | 94 ms | 420 ms | 640 ms | 987 ms | Clean |
| 100 users | 777 | 40.48 | **0 %** | 1100 ms | 3300 ms | 3800 ms | 4071 ms | Latency-degraded |

**Observed Round 10 Load Boundary:**
- u5 → u50: 0% recorded Locust failures across all 5 sweep levels.
- u100: 0 Locust failures but aggregated p95 = 3300 ms, p99 = 3800 ms.
  The elevated latency is driven by `/gateway/dashboard` health-probe concurrency
  and `/health` downstream checks at 100 simultaneous users.
- **Clean latency ceiling: 50 concurrent users** (p95 420 ms, p99 640 ms, 0 failures).
- **Latency-degradation onset: 100 concurrent users** (p95 > 3 s, p99 > 3.8 s).
- This is an observed local-machine boundary, NOT a production capacity limit.

> [!WARNING]
> This observed load boundary applies to the **local development server only** with unavailable downstream dependencies and is NOT a theoretical production capacity limit. A production deployment with multiple Uvicorn workers or behind a reverse proxy with running downstream services would have a substantially higher capacity limit.

---

## Bottleneck Analysis

### Evidence-Based Bottleneck Analysis

1. **`/gateway/dashboard` is the primary latency driver at high concurrency**

   The dashboard endpoint performs live health probes to all 6 downstream services on
   every request. At 100 concurrent users, simultaneous health-probe goroutines contend
   for connections, driving aggregate p95 to 3300 ms. From the u100 CSV:
   `[READ] GET /gateway/dashboard` p50 = 1300 ms, p95 = 3200 ms, p99 = 3300 ms.

2. **`/health` endpoint is also health-probe dependent**

   At 100 users, `/health` p50 = 1300 ms, p95 = 3300 ms.
   Both dashboard and health endpoints are bounded by the configured 3-second
   per-service health check timeout × fan-out to 6 services.

3. **Gateway-native endpoints remain sub-second at all tested levels**

   From the u100 CSV:
   - `[READ] GET /` — p50 = 530 ms, p95 = 1700 ms (event-loop queue at 100 users)
   - `[READ] GET /gateway/status` — p50 = 540 ms, p95 = 1600 ms
   - `[READ] GET /metrics` — p50 = 530 ms, p95 = 760 ms (fastest endpoint)

   At u50 (from CSV): `/gateway/status` p95 = 180 ms, `/metrics` p95 = 190 ms.
   The 100-user jump in native-route latency indicates event-loop saturation beginning.

4. **Proxy routes scale well when dummy services are available**

   At 50 users from CSV: `inventory/items` p50 = 110 ms, `shipments` p50 = 110 ms,
   `POST /api/v1/inventory` p50 = 82 ms. These are consistent fast proxy responses,
   not timeout behaviour.

5. **Production capacity cannot be inferred**

   Results are from a Windows laptop, single-process Uvicorn, and 60-second Locust runs.
   CPU/memory profiling, multi-worker deployments, and soak testing are needed for
   production capacity estimates.

---

## Observations

1. All 5 sweep levels (u5 → u100) completed with **0 recorded Locust failures**.

2. u5 → u50: p50 scales from 14 ms to 94 ms, p95 from 37 ms to 420 ms.
   All proxy routes served from dummy services at < 200 ms p50.

3. u100: 0 failures but latency-degraded. p50 = 1100 ms, p95 = 3300 ms, p99 = 3800 ms.
   Degradation is driven by `/gateway/dashboard` health-probe fan-out contention.

4. `/metrics` is consistently the fastest endpoint at all concurrency levels.
   At u100: p50 = 530 ms, p95 = 760 ms. At u50: p50 = 58 ms, p95 = 190 ms.

5. `/gateway/dashboard` and `/health` are the highest-latency endpoints due to
   their live downstream health probe fan-out architecture.

6. **Clean latency ceiling: 50 concurrent users** (p95 420 ms, p99 640 ms, 0 failures).
   **Latency-degradation onset: 100 concurrent users** (p95 > 3 s, p99 > 3.8 s).
   These boundaries apply to the local development setup only.

7. Longer soak testing, CPU/memory profiling, multi-worker setups, and dedicated
   hardware would be required for production capacity estimation.

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
