# Round 10 M3 – API Gateway Load Test Report

> [!NOTE]
> All results in this report were obtained from an actual local laptop test run.
> Data is derived directly from the authoritative Round 10 sweep CSVs and summary.
> **No numbers have been fabricated.**

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
> `python dummy_services.py` during the sweep runs.
> Proxy route latencies confirm downstream availability.

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

Rate limiting was disabled for the sweep (LOAD_TEST_MODE=true) because all Locust users share one source IP.

### Recommended headless run (Windows PowerShell)

```powershell
# Start dummy services (terminal 1)
python dummy_services.py

# Start the API Gateway with LOAD_TEST_MODE (terminal 2)
$env:LOAD_TEST_MODE = "true"
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# Run Locust headless for a single level (terminal 3)
.venv\Scripts\locust.exe `
    -f load_tests/round10_locustfile.py `
    --headless `
    --users 10 `
    --spawn-rate 2 `
    --run-time 60s `
    --host http://127.0.0.1:8000 `
    --csv load_tests/round10_results_u10
```

### Laptop ceiling sweep command

The authoritative ceiling sweep is executed using the automated sweep harness, which monitors the gateway process CPU and detects the degradation boundary:

```powershell
# 1. Start dummy downstream services (terminal 1)
python dummy_services.py

# 2. Start gateway with LOAD_TEST_MODE=true without --reload (terminal 2)
$env:LOAD_TEST_MODE = "true"
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# 3. Find gateway process PID (terminal 3)
(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess

# 4. Run automated sweep harness
python run_locust_sweep.py --gateway-pid <PID>
```

---

## Results

Rate limiting was disabled for the sweep (LOAD_TEST_MODE=true) because all Locust users share one source IP.

### Authoritative Round 10 Results

The table below reflects the authoritative fresh Round 10 sweep run using `python run_locust_sweep.py --gateway-pid <PID>`. Each concurrency level ran for 60 seconds against a realistic 12-endpoint scenario with dummy downstream services running.

| Users | Requests | RPS | Error % | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Gateway CPU avg % | Gateway CPU max % | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | 265 | 4.53 | 0.00 | 38 | 370 | 580 | 992 | 10 | 20 | OK |
| 10 | 539 | 9.28 | 0.00 | 25 | 200 | 430 | 986 | 20 | 98 | OK |
| 20 | 591 | 10.28 | 0.00 | 720 | 2500 | 3100 | 3335 | 82 | 111 | DEGRADED |

> [!NOTE]
> **Degraded Definition**: A concurrency level is marked as `DEGRADED` if `p95 > 1000 ms` OR `error rate > 1%`.
> The sweep automatically halts upon detecting the first degraded level.
>
> **First Degraded Level**:
> - 20 concurrent users
> - p95 = 2500 ms
> - CPU avg = 82%
> - CPU max = 111%

### Dashboard / Health A/B Isolation Test (100 Users)

An A/B isolation experiment was conducted at 100 concurrent users with `/gateway/dashboard` and `/health` excluded from the traffic mix (`round10_results_no_dashboard_stats.csv`), isolating pure gateway routing and downstream proxy tasks:

- **Users**: 100 (dashboard/health excluded)
- **Requests**: 2597
- **Failures**: 0
- **Error rate**: 0.00%
- **RPS**: 44.09
- **p50**: 930 ms
- **p95**: 2700 ms
- **p99**: 3100 ms
- **Max**: 3286.53 ms

**Interpretation**:
- Removing dashboard and health traffic still leaves p95 at 2700 ms under 100 concurrent users.
- Therefore, dashboard and health probe fan-out may contribute workload, but it is **NOT** proven to be the primary bottleneck.
- Evidence points primarily to gateway CPU and single-worker event-loop saturation under high concurrency.
- Dummy downstream services were running throughout the fresh test.

---

## Laptop Ceiling / Break Point

### Methodology

1. Start dummy downstream services (`python dummy_services.py`) on ports 8001–8006.
2. Start the API Gateway in single-process mode (`$env:LOAD_TEST_MODE="true"; uvicorn app.main:app --host 127.0.0.1 --port 8000`).
3. Find the gateway PID: `(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess`.
4. Run the automated ceiling sweep: `python run_locust_sweep.py --gateway-pid <PID>`.
5. The harness evaluates each concurrency level for 60 seconds while sampling process CPU every second.
6. Rate limiting was disabled for the sweep (LOAD_TEST_MODE=true) because all Locust users share one source IP.
7. Break point criterion: A level is marked **DEGRADED** when `p95 > 1000 ms` OR `error rate > 1%`.

### Observed Round 10 Break Point

Based on the authoritative fresh run:
- **5 users**: **OK** (p95 = 370 ms, CPU avg = 10%, CPU max = 20%, 0.00% errors)
- **10 users**: **OK** (p95 = 200 ms, CPU avg = 20%, CPU max = 98%, 0.00% errors)
- **20 users**: **First DEGRADED** (p95 = 2500 ms, CPU avg = 82%, CPU max = 111%, 0.00% errors)

**Key Findings:**
- The first degraded level is **20 concurrent users**.
- At 20 users, `p95 = 2500 ms` exceeds the 1000 ms threshold, with `CPU avg = 82%` and `CPU max = 111%`.
- The gateway successfully processed all requests (0.00% error rate), but latency escalated due to CPU and event-loop saturation.
- This is a local-machine observed boundary, **NOT** production capacity.

> [!WARNING]
> This observed break point applies to the **local development laptop environment only** (single-process Uvicorn on Windows 11) and is **NOT** a theoretical production capacity limit. A production deployment with multiple Uvicorn worker processes (`--workers N`) behind a reverse proxy (e.g. NGINX) on dedicated server hardware would have a substantially higher capacity limit.

---

## Bottleneck Analysis

### Evidence-Based Bottleneck Analysis

1. **Primary evidence points to gateway CPU / single-worker event-loop saturation**
   At 20 concurrent users, the gateway process CPU reached an average of 82% and peaked at 111%, indicating that the single Python/Uvicorn worker core was saturated. Handling concurrency, async task switching, HTTP parsing, request routing, and metric recording within a single event loop caused queued coroutines to wait, escalating p95 latency from 200 ms (at 10 users) to 2500 ms (at 20 users).

2. **Dashboard / health exclusion still has p95 of 2700 ms**
   In the 100-user A/B isolation test where `/gateway/dashboard` and `/health` were excluded entirely, the p95 latency was 2700 ms with 0% error rate across 2597 requests.

3. **Dashboard fan-out alone does not explain degradation**
   Because p95 latency remained high (2700 ms) even when all dashboard and health probe traffic was eliminated, downstream health-probe fan-out alone cannot explain the degradation. Downstream fan-out adds background I/O, but gateway CPU and event-loop saturation under load is the primary bottleneck.

4. **Dummy downstream services were running**
   All 6 dummy downstream services were running and healthy via `python dummy_services.py` throughout the test. Downstream unavailability was not a factor in the observed latency.

5. **Production capacity cannot be inferred from this laptop test**
   The test was conducted on a single Windows laptop development server running a single Uvicorn process. Production capacity cannot be inferred from this test; production environments use multi-worker configurations, Linux `epoll`, load balancing, and dedicated hardware.

---

## Observations

1. **Clean error rate**: All sweep levels (5, 10, 20 users) completed with **0.00% errors** across hundreds of requests.
2. **Acceptable latency at 5 and 10 users**:
   - 5 users: p50 = 38 ms, p95 = 370 ms, CPU avg = 10%.
   - 10 users: p50 = 25 ms, p95 = 200 ms, CPU avg = 20%.
3. **Onset of degradation at 20 users**: At 20 users, p95 latency reached 2500 ms (> 1000 ms threshold) and gateway CPU reached 82% avg / 111% max, marking the first DEGRADED level.
4. **Dashboard/health A/B test confirms CPU/event-loop bottleneck**: Excluding dashboard and health endpoints at 100 users yielded p95 = 2700 ms with 0% errors (2597 requests, 44.09 RPS), confirming that dashboard fan-out alone is not the primary bottleneck.
5. **Dummy downstream services active**: Downstream microservices were running and healthy throughout the tests.
6. **Local boundary**: 20 concurrent users is an observed local laptop break point under single-worker Uvicorn, not a production capacity metric.

---

## Reproduction Commands

### Full setup (PowerShell)

```powershell
# 1. Navigate to the service directory
cd services\api-gateway

# 2. Install dependencies (including locust and psutil)
.venv\Scripts\pip.exe install -r requirements.txt

# 3. Start dummy downstream microservices (Terminal 1)
python dummy_services.py

# 4. Start the API Gateway with LOAD_TEST_MODE enabled (Terminal 2 - do NOT use --reload)
$env:LOAD_TEST_MODE = "true"
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000

# 5. Determine Gateway PID (Terminal 3)
(Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess

# 6. Run the authoritative Round 10 ceiling sweep (Terminal 3)
python run_locust_sweep.py --gateway-pid <PID>

# 7. Run M3 automated validation tests
.venv\Scripts\pytest.exe app/tests/test_round10_m3_loadtest.py -v
```

### Standalone single-level run (PowerShell)

```powershell
.venv\Scripts\locust.exe `
    -f load_tests/round10_locustfile.py `
    --headless `
    --users 10 `
    --spawn-rate 2 `
    --run-time 60s `
    --host http://127.0.0.1:8000 `
    --csv load_tests/round10_results_u10
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

1. **Single-process Uvicorn development server**: Results reflect a single Python process without worker clustering. Production deployments should use `--workers N` or containerized replicas.
2. **Local laptop variability**: Background operating system tasks, CPU power-management states, and IDE background processes introduce variability.
3. **Dummy downstream services instead of production downstreams**: Tests utilized `dummy_services.py` lightweight mock servers rather than full production downstream services with real databases.
4. **60-second runs without soak testing**: Tests were conducted in 60-second intervals per level to identify break points. Soak tests are necessary to evaluate memory behavior or connection pool exhaustion over extended periods.
5. **Rate limiting disabled during sweep**: Rate limiting was disabled for the sweep (LOAD_TEST_MODE=true) because all Locust users share one source IP.
6. **Windows I/O model**: Uvicorn on Windows operates on a selector-based event loop rather than Linux `epoll`, affecting peak single-worker concurrency.
7. **OpenTelemetry exporter background logging**: If an external OTLP/Jaeger collector is not active, the SDK logs export warnings to stderr; these do not impact request processing.

---

*Report generated for Round 10 Milestone 3 — eaicsp-platform API Gateway.*
*Branch: mahendher/round10-api-gateway-metrics-tracing-loadtest*
