"""
Round 10 Milestone 3 – API Gateway Load Test (Locust)
======================================================

Realistic traffic mix targeting the API Gateway:

  Category          | Weight | Approx %
  ------------------|--------|----------
  READ (GET)        |   14   |  ~74 %
  WRITE (non-GET)   |    3   |  ~16 %
  AUTH-FAIL         |    2   |  ~10 %
  ------------------|--------|----------
  Total             |   19   | 100 %

The weights are implemented via Locust's @task(n) decorator.
They can be changed by editing the integer argument.

Endpoints used are limited to those verified to exist in the
current API Gateway implementation (app/main.py + app/routes/).

READ endpoints
--------------
  GET /                         – root status
  GET /health                   – health check
  GET /metrics                  – Prometheus scrape
  GET /gateway/status           – operational status (no auth required)
  GET /gateway/dashboard        – aggregated metrics dashboard (may be slow -
                                  hits real health checks to downstream services)
  GET /api/v1/inventory/items   – proxied to Inventory service (expected 503/504
                                  when downstream is unavailable)
  GET /api/v1/shipments         – proxied to Shipments service

WRITE endpoints
---------------
  POST /api/v1/inventory        – create inventory item (proxied)
  POST /api/v1/purchase-orders  – create purchase order (proxied)
  PUT  /api/v1/inventory/items/{id} – update item (proxied stub)

AUTH-FAIL traffic
-----------------
  GET  /api/v1/inventory/items  with header Authorization: Bearer INVALID_TOKEN
  POST /api/v1/auth/login       with deliberately wrong credentials

  These requests are intentional test traffic.
  The gateway returns 401/403/503/504 depending on how the downstream
  auth service handles bad tokens.  They are NOT infrastructure failures;
  the API Gateway is behaving correctly by forwarding them.

Usage
-----
  # Headless (recommended for CI / reproducible results)
  locust -f load_tests/round10_locustfile.py ^
         --headless ^
         --users 10 ^
         --spawn-rate 2 ^
         --run-time 60s ^
         --host http://127.0.0.1:8000 ^
         --csv load_tests/round10_results

  # Interactive web UI (useful for manual exploration)
  locust -f load_tests/round10_locustfile.py ^
         --host http://127.0.0.1:8000

Environment variables / override
---------------------------------
  LOCUST_HOST       – override default host (default: http://127.0.0.1:8000)
  LOCUST_USERS      – max concurrent users
  LOCUST_SPAWN_RATE – users added per second during ramp-up

Laptop ceiling procedure
------------------------
  Run the headless command with increasing --users values:
    5, 10, 20, 50, 100
  After each run inspect the CSV stats (p95, error rate).
  The "ceiling" is identified when:
    a) p95 latency exceeds 500 ms   (latency degradation), OR
    b) error rate exceeds 1 %       (error rate degradation).
  See ROUND10_M3_LOAD_TEST_REPORT.md for detailed methodology.
"""

import os
import random
import uuid

from locust import HttpUser, between, task


# ---------------------------------------------------------------------------
# Configurable constants
# ---------------------------------------------------------------------------

# Default wait time between tasks for each simulated user (seconds).
# Adjust to change overall request rate per user.
MIN_WAIT: float = float(os.getenv("LOCUST_MIN_WAIT", "0.5"))
MAX_WAIT: float = float(os.getenv("LOCUST_MAX_WAIT", "1.5"))

# Intentional auth-failure header/body payloads
INVALID_TOKEN = "Bearer INVALID_TOKEN_FOR_LOAD_TEST"
BAD_LOGIN_PAYLOAD = {"username": "unknown_user", "password": "wrong_password"}

# Proxy-route headers to simulate a realistic browser-like client
BASE_HEADERS = {
    "Accept": "application/json",
    "X-Load-Test": "round10-m3",
    "X-Source": "locust-load-test",
}


# ---------------------------------------------------------------------------
# Helper: generate realistic fake payloads
# ---------------------------------------------------------------------------

def _inventory_payload() -> dict:
    """Generate a minimal inventory item creation payload."""
    return {
        "name": f"LoadTest-Item-{uuid.uuid4().hex[:8]}",
        "quantity": random.randint(1, 500),
        "unit": random.choice(["pcs", "kg", "litre"]),
        "sku": f"SKU-{uuid.uuid4().hex[:6].upper()}",
    }


def _purchase_order_payload() -> dict:
    """Generate a minimal purchase order creation payload."""
    return {
        "supplier": f"Supplier-{random.randint(1, 20)}",
        "item_sku": f"SKU-{uuid.uuid4().hex[:6].upper()}",
        "quantity": random.randint(10, 1000),
        "priority": random.choice(["low", "medium", "high"]),
    }


def _inventory_update_payload() -> dict:
    """Generate a minimal inventory update payload."""
    return {
        "quantity": random.randint(1, 999),
        "status": random.choice(["in_stock", "low_stock", "out_of_stock"]),
    }


# ---------------------------------------------------------------------------
# User class
# ---------------------------------------------------------------------------

class APIGatewayUser(HttpUser):
    """
    Simulates a realistic mix of clients hitting the API Gateway.

    Task weights (total weight = 19):
      READ tasks  : weight 14  -> ~73.7 %
      WRITE tasks : weight  3  -> ~15.8 %
      AUTH-FAIL   : weight  2  -> ~10.5 %
    """

    wait_time = between(MIN_WAIT, MAX_WAIT)

    # ------------------------------------------------------------------
    # READ tasks  (weight 14 combined)
    # ------------------------------------------------------------------

    @task(3)
    def read_root(self):
        """[READ] GET / (Root)"""
        self.client.get(
            "/",
            name="[READ] GET / (Root)",
            headers=BASE_HEADERS,
        )

    @task(4)
    def read_health(self):
        """[READ] GET /health (Health Check)"""
        self.client.get(
            "/health",
            name="[READ] GET /health (Health Check)",
            headers=BASE_HEADERS,
        )

    @task(2)
    def read_metrics(self):
        """[READ] GET /metrics (Prometheus)"""
        self.client.get(
            "/metrics",
            name="[READ] GET /metrics (Prometheus)",
            headers={"Accept": "text/plain", "X-Load-Test": "round10-m3"},
        )

    @task(2)
    def read_gateway_status(self):
        """[READ] GET /gateway/status (Status)"""
        self.client.get(
            "/gateway/status",
            name="[READ] GET /gateway/status (Status)",
            headers=BASE_HEADERS,
        )

    @task(1)
    def read_gateway_dashboard(self):
        """[READ] GET /gateway/dashboard (Dashboard)
        Note: This endpoint fans out to downstream health probes,
        so it has significantly higher latency when services are
        unavailable.  Weight is kept at 1 to avoid skewing averages.
        """
        self.client.get(
            "/gateway/dashboard",
            name="[READ] GET /gateway/dashboard (Dashboard)",
            headers=BASE_HEADERS,
            # Allow up to 30 s for dashboard (health probes can be slow)
            timeout=30,
        )

    @task(1)
    def read_inventory_items(self):
        """[READ] GET /api/v1/inventory/items (Proxy to Inventory)"""
        with self.client.get(
            "/api/v1/inventory/items",
            name="[READ] GET /api/v1/inventory/items (Proxy->Inventory)",
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Expected 200, got status {resp.status_code}")

    @task(1)
    def read_shipments(self):
        """[READ] GET /api/v1/shipments (Proxy to Shipments)"""
        with self.client.get(
            "/api/v1/shipments",
            name="[READ] GET /api/v1/shipments (Proxy->Shipments)",
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Expected 200, got status {resp.status_code}")

    # ------------------------------------------------------------------
    # WRITE tasks  (weight 3 combined)
    # ------------------------------------------------------------------

    @task(1)
    def write_create_inventory_item(self):
        """[WRITE] POST /api/v1/inventory (Create Item)"""
        with self.client.post(
            "/api/v1/inventory",
            name="[WRITE] POST /api/v1/inventory (Create Item)",
            json=_inventory_payload(),
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            else:
                resp.failure(f"Expected 200/201, got status {resp.status_code}")

    @task(1)
    def write_create_purchase_order(self):
        """[WRITE] POST /api/v1/purchase-orders (Create PO)"""
        with self.client.post(
            "/api/v1/purchase-orders",
            name="[WRITE] POST /api/v1/purchase-orders (Create PO)",
            json=_purchase_order_payload(),
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            else:
                resp.failure(f"Expected 200/201, got status {resp.status_code}")

    @task(1)
    def write_update_inventory_item(self):
        """[WRITE] PUT /api/v1/inventory/items/{id} (Update Item)"""
        item_id = f"item-{random.randint(1, 100)}"
        with self.client.put(
            f"/api/v1/inventory/items/{item_id}",
            name="[WRITE] PUT /api/v1/inventory/items/{id} (Update Item)",
            json=_inventory_update_payload(),
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Expected 200, got status {resp.status_code}")

    # ------------------------------------------------------------------
    # AUTH-FAIL tasks  (weight 2 combined)
    # These are intentional "bad credential" requests.
    # They exercise the gateway's auth forwarding path.
    # The gateway proxy correctly forwards these and returns the
    # downstream's rejection (401/403). Unexpected 2xx responses are failures.
    # ------------------------------------------------------------------

    @task(1)
    def auth_fail_invalid_token(self):
        """[AUTH_FAIL] GET /api/v1/inventory/items (Invalid Token)"""
        with self.client.get(
            "/api/v1/inventory/items",
            name="[AUTH_FAIL] GET /api/v1/inventory/items (Invalid Token)",
            headers={**BASE_HEADERS, "Authorization": INVALID_TOKEN},
            catch_response=True,
        ) as resp:
            if resp.status_code in (401, 403):
                resp.success()
            else:
                resp.failure(f"Expected 401/403 for invalid token, got status {resp.status_code}")

    @task(1)
    def auth_fail_bad_login(self):
        """[AUTH_FAIL] POST /api/v1/auth/login (Bad Credentials)"""
        with self.client.post(
            "/api/v1/auth/login",
            name="[AUTH_FAIL] POST /api/v1/auth/login (Bad Credentials)",
            json=BAD_LOGIN_PAYLOAD,
            headers=BASE_HEADERS,
            catch_response=True,
        ) as resp:
            if resp.status_code in (401, 403):
                resp.success()
            else:
                resp.failure(f"Expected 401/403 for bad login, got status {resp.status_code}")
