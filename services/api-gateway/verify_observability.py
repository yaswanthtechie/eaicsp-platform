"""
Round 10 observability verification (definition-of-done evidence).

Needs the stack running:
  docker compose -f docker-compose.dev.yml up -d
  # Grafana UI: http://localhost:3000 (anonymous read-only Viewer; admin login from .env)
  python dummy_services.py
  uvicorn app.main:app --host 0.0.0.0 --port 8000    (OTEL_ENABLED=true; 0.0.0.0 so
                                                      the Prometheus container can scrape it)


Checks, and exits 1 if any fails:
  1. After a fixed burst, request/error deltas are identical in
     /gateway/dashboard, the Prometheus SERVER (PromQL), and Grafana
     (querying the provisioned Prometheus datasource), and equal the burst.
  2. One request through the gateway produces ONE trace in Jaeger containing
     spans from both the gateway and the downstream service; the gateway
     records its own span; X-Request-ID still works alongside traceparent.

OBSERVABILITY_EVIDENCE.md is written from the measured values only.
"""

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://127.0.0.1:3000")
JAEGER_URL = os.getenv("JAEGER_URL", "http://127.0.0.1:16686")

# Optional: only needed if anonymous Grafana access is turned off.
GRAFANA_USER = os.getenv("GRAFANA_ADMIN_USER", "")
GRAFANA_PASSWORD = os.getenv("GRAFANA_ADMIN_PASSWORD", "")
GRAFANA_PROM_UID = "prometheus"  # uid in grafana/provisioning/datasources/datasources.yml

GATEWAY_SERVICE = os.getenv("OTEL_SERVICE_NAME", "api-gateway")
DOWNSTREAM_SERVICE = "Inventory Service"  # SERVICE_NAME used by dummy_services.py

OUTPUT_FILE = Path(__file__).resolve().parent / "OBSERVABILITY_EVIDENCE.md"

# Reading a source must not change the numbers being compared, so the
# routes this script itself calls are excluded everywhere.
EXCLUDED_ROUTES = {"/gateway/dashboard", "/gateway/status", "/metrics"}
PROMQL_FILTER = 'route!~"/gateway/dashboard|/gateway/status|/metrics"'
PROMQL_REQUESTS = f"sum(gateway_requests_total{{{PROMQL_FILTER}}})"
PROMQL_ERRORS = f"sum(gateway_errors_total{{{PROMQL_FILTER}}})"
SCRAPE_WAIT_SECONDS = 6  # prometheus.yml scrapes every 2 s

BURST_PLAN = [
    ("GET", "/", 5),
    ("GET", "/health", 5),
    ("GET", "/api/v1/inventory/items", 5),
    ("POST", "/api/v1/purchase-orders", 5),
    ("GET", "/unknown-unmapped-route", 3),
    ("GET", "/api/v1/inventory/error", 2),  # dummy returns 500
]
EXPECTED_REQUESTS = sum(count for _, _, count in BURST_PLAN)
EXPECTED_ERRORS = 2


# ---------------------------------------------------------------------------
# Metric sources
# ---------------------------------------------------------------------------

def _promql(base_url: str, query: str, auth=None) -> int:
    response = httpx.get(
        f"{base_url}/api/v1/query",
        params={"query": query},
        auth=auth,
        timeout=5.0,
    )
    response.raise_for_status()
    result = response.json()["data"]["result"]
    return int(float(result[0]["value"][1])) if result else 0


def prometheus_counts() -> tuple[int, int]:
    return (
        _promql(PROMETHEUS_URL, PROMQL_REQUESTS),
        _promql(PROMETHEUS_URL, PROMQL_ERRORS),
    )


def grafana_counts() -> tuple[int, int]:
    base = f"{GRAFANA_URL}/api/datasources/proxy/uid/{GRAFANA_PROM_UID}"
    auth = (GRAFANA_USER, GRAFANA_PASSWORD) if GRAFANA_USER else None
    return (
        _promql(base, PROMQL_REQUESTS, auth),
        _promql(base, PROMQL_ERRORS, auth),
    )


def dashboard_counts(client: httpx.Client) -> tuple[int, int]:
    routes = client.get("/gateway/dashboard").json().get("routes", {})
    kept = [m for route, m in routes.items() if route not in EXCLUDED_ROUTES]
    return (
        sum(m.get("requests", 0) for m in kept),
        sum(m.get("errors", 0) for m in kept),
    )


def snapshot(client: httpx.Client) -> dict[str, tuple[int, int]]:
    return {
        "Gateway dashboard (/gateway/dashboard)": dashboard_counts(client),
        "Prometheus server (PromQL)": prometheus_counts(),
        "Grafana (Prometheus datasource)": grafana_counts(),
    }


def check_metrics(client: httpx.Client) -> dict:
    time.sleep(SCRAPE_WAIT_SECONDS)  # make sure Prometheus is current
    before = snapshot(client)

    for method, path, count in BURST_PLAN:
        for _ in range(count):
            if method == "POST":
                client.post(path, json={"item": "verify", "quantity": 1})
            else:
                client.get(path)

    time.sleep(SCRAPE_WAIT_SECONDS)  # wait for at least two scrapes
    after = snapshot(client)

    deltas = {
        source: (after[source][0] - before[source][0], after[source][1] - before[source][1])
        for source in before
    }
    passed = all(d == (EXPECTED_REQUESTS, EXPECTED_ERRORS) for d in deltas.values())
    return {"deltas": deltas, "passed": passed}


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------

def check_trace(client: httpx.Client) -> dict:
    trace_id = uuid.uuid4().hex
    sent_span_id = uuid.uuid4().hex[:16]
    request_id = f"verify-{uuid.uuid4().hex[:8]}"

    response = client.get(
        "/api/v1/inventory/items",
        headers={
            "traceparent": f"00-{trace_id}-{sent_span_id}-01",
            "X-Request-ID": request_id,
        },
    )

    returned = response.headers.get("traceparent", "")
    parts = returned.split("-")
    same_trace = len(parts) == 4 and parts[1] == trace_id
    # A RECORDING gateway span puts its OWN span id here. Getting the
    # caller's span id back means no span was recorded/exported.
    gateway_span_recorded = same_trace and parts[2] != sent_span_id
    request_id_kept = response.headers.get("x-request-id") == request_id

    services: set[str] = set()
    span_count = 0
    for _ in range(15):  # BatchSpanProcessor exports every ~5 s
        r = httpx.get(f"{JAEGER_URL}/api/traces/{trace_id}", timeout=3.0)
        if r.status_code == 200 and r.json().get("data"):
            trace = r.json()["data"][0]
            services = {p["serviceName"] for p in trace["processes"].values()}
            span_count = len(trace["spans"])
            if {GATEWAY_SERVICE, DOWNSTREAM_SERVICE} <= services:
                break
        time.sleep(1.0)

    passed = (
        response.status_code == 200
        and gateway_span_recorded
        and request_id_kept
        and {GATEWAY_SERVICE, DOWNSTREAM_SERVICE} <= services
    )
    return {
        "trace_id": trace_id,
        "status_code": response.status_code,
        "sent_traceparent": f"00-{trace_id}-{sent_span_id}-01",
        "returned_traceparent": returned,
        "gateway_span_recorded": gateway_span_recorded,
        "request_id_kept": request_id_kept,
        "jaeger_services": sorted(services),
        "jaeger_span_count": span_count,
        "passed": passed,
    }


# ---------------------------------------------------------------------------
# Evidence file
# ---------------------------------------------------------------------------

def write_evidence(metrics: dict, trace: dict) -> None:
    def verdict(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    rows = "\n".join(
        f"| {source} | {req} | {err} |"
        for source, (req, err) in metrics["deltas"].items()
    )
    OUTPUT_FILE.write_text(
        f"""# Round 10 Observability Evidence

Generated by `verify_observability.py` at {datetime.now(timezone.utc).isoformat()}.
Every value below was measured by the script; nothing is hardcoded.

## 1. Metrics agreement: {verdict(metrics["passed"])}

Burst: {EXPECTED_REQUESTS} requests, {EXPECTED_ERRORS} expected 5xx errors.
Deltas (excluding `{", ".join(sorted(EXCLUDED_ROUTES))}`):

| Source | Requests delta | 5xx errors delta |
|---|---|---|
{rows}

## 2. Distributed trace: {verdict(trace["passed"])}

- Trace ID: `{trace["trace_id"]}` (open it at {JAEGER_URL}/trace/{trace["trace_id"]})
- Sent `traceparent`: `{trace["sent_traceparent"]}`
- Returned `traceparent`: `{trace["returned_traceparent"]}`
- Gateway recorded its own span: {trace["gateway_span_recorded"]}
- `X-Request-ID` preserved alongside `traceparent`: {trace["request_id_kept"]}
- Services in the Jaeger trace: {", ".join(trace["jaeger_services"]) or "none"} ({trace["jaeger_span_count"]} spans)

Screenshots: `docs/evidence/jaeger_trace.png`, `docs/evidence/grafana_dashboard.png`.
Stack endpoints:
- Prometheus UI: {PROMETHEUS_URL}
- Grafana UI: {GRAFANA_URL} (anonymous read-only Viewer; admin login from .env)
- Jaeger UI: {JAEGER_URL}
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_FILE}")


def main() -> int:
    with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
        client.get("/health").raise_for_status()
        metrics = check_metrics(client)
        trace = check_trace(client)

    print("Metrics deltas:", metrics["deltas"], "->", "PASS" if metrics["passed"] else "FAIL")
    print("Trace:", trace)
    write_evidence(metrics, trace)
    return 0 if metrics["passed"] and trace["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
