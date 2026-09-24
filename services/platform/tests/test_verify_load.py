"""
Load test for Platform Service /api/v1/auth/verify

Purpose:
    Test /verify under the current combined service call graph.

Simulated callers:
    - Inventory Service
    - Supplier Service
    - Compliance Service

The test sends real HTTP requests to the running Platform Service.

Run:
    python tests/load_test_verify.py

Optional environment variables:

    PLATFORM_BASE_URL=http://127.0.0.1:8005
    ACCESS_TOKEN=<valid access token>
    TOTAL_REQUESTS=150
    CONCURRENCY=20

Example:

    set ACCESS_TOKEN=eyJ...
    set TOTAL_REQUESTS=150
    set CONCURRENCY=20

    python tests/load_test_verify.py
"""

import asyncio
import os
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass

import httpx
# ============================================================
# Configuration
# ============================================================

BASE_URL = os.getenv(
    "BASE_URL",
    "http://127.0.0.1:8005",
).rstrip("/")

VERIFY_URL = f"{BASE_URL}/api/v1/auth/verify"

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

TOTAL_REQUESTS = int(
    os.getenv("TOTAL_REQUESTS", "150")
)

CONCURRENCY = int(
    os.getenv("CONCURRENCY", "20")
)

TIMEOUT_SECONDS = float(
    os.getenv("TIMEOUT_SECONDS", "10")
)

# Simulate the current real caller services.
CALLER_SERVICES = (
    "inventory",
    "supplier",
    "compliance",
)

# ============================================================
# Result model
# ============================================================

@dataclass
class RequestResult:
    request_number: int
    caller_service: str
    success: bool
    status_code: int | None
    latency_ms: float
    error: str | None = None

# ============================================================
# Validation
# ============================================================

def validate_configuration() -> None:
    """Validate load-test configuration before starting."""

    if not ACCESS_TOKEN:
        print(
            "\nERROR: ACCESS_TOKEN environment variable is missing.\n"
        )
        print("First obtain a valid access token from the MFA login flow.")
        print("\nWindows CMD:")
        print("    set ACCESS_TOKEN=<your_access_token>")
        print("\nPowerShell:")
        print("    $env:ACCESS_TOKEN=\"<your_access_token>\"")
        print()
        sys.exit(1)

    if TOTAL_REQUESTS <= 0:
        print("ERROR: TOTAL_REQUESTS must be greater than 0.")
        sys.exit(1)

    if CONCURRENCY <= 0:
        print("ERROR: CONCURRENCY must be greater than 0.")
        sys.exit(1)

    if CONCURRENCY > TOTAL_REQUESTS:
        print(
            "WARNING: CONCURRENCY is greater than TOTAL_REQUESTS. "
            "Reducing concurrency to TOTAL_REQUESTS."
        )

# ============================================================
# Single request
# ============================================================

async def send_verify_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    request_number: int,
) -> RequestResult:

    caller_service = CALLER_SERVICES[
        (request_number - 1) % len(CALLER_SERVICES)
    ]

    async with semaphore:

        start = time.perf_counter()

        try:
            response = await client.post(
                VERIFY_URL,
                headers={
                    "Authorization": f"Bearer {ACCESS_TOKEN}",
                    "X-Caller-Service": caller_service,
                },
            )

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            success = (
                response.status_code == 200
            )

            error = None

            if not success:
                try:
                    error_body = response.text[:300]
                except Exception:
                    error_body = "Unable to read response body"

                error = error_body

            return RequestResult(
                request_number=request_number,
                caller_service=caller_service,
                success=success,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
                error=error,
            )

        except Exception as exc:

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            return RequestResult(
                request_number=request_number,
                caller_service=caller_service,
                success=False,
                status_code=None,
                latency_ms=elapsed_ms,
                error=str(exc),
            )

# ============================================================
# Load test
# ============================================================

async def run_load_test() -> list[RequestResult]:

    effective_concurrency = min(
        CONCURRENCY,
        TOTAL_REQUESTS,
    )

    semaphore = asyncio.Semaphore(
        effective_concurrency
    )

    limits = httpx.Limits(
        max_connections=effective_concurrency,
        max_keepalive_connections=effective_concurrency,
    )

    timeout = httpx.Timeout(
        TIMEOUT_SECONDS
    )

    print("\nStarting /verify load test...")
    print("----------------------------------------")
    print(f"Platform URL       : {BASE_URL}")
    print(f"Verify endpoint    : {VERIFY_URL}")
    print(f"Total requests     : {TOTAL_REQUESTS}")
    print(f"Concurrency        : {effective_concurrency}")
    print(f"Timeout            : {TIMEOUT_SECONDS}s")
    print(
        "Caller services    : "
        + ", ".join(CALLER_SERVICES)
    )
    print("----------------------------------------\n")

    test_start = time.perf_counter()

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
    ) as client:

        tasks = [
            send_verify_request(
                client,
                semaphore,
                request_number,
            )
            for request_number in range(
                1,
                TOTAL_REQUESTS + 1,
            )
        ]

        results = await asyncio.gather(
            *tasks
        )

    total_elapsed = (
        time.perf_counter() - test_start
    )

    print_report(
        results,
        total_elapsed,
    )

    return results

# ============================================================
# Percentile calculation
# ============================================================

def percentile(
    values: list[float],
    percent: float,
) -> float:

    if not values:
        return 0.0

    sorted_values = sorted(values)

    index = (
        (len(sorted_values) - 1)
        * percent
        / 100
    )

    lower = int(index)
    upper = min(
        lower + 1,
        len(sorted_values) - 1,
    )

    fraction = index - lower

    return (
        sorted_values[lower]
        + (
            sorted_values[upper]
            - sorted_values[lower]
        )
        * fraction
    )

# ============================================================
# Report
# ============================================================

def print_report(
    results: list[RequestResult],
    total_elapsed: float,
) -> None:

    total = len(results)

    successful = [
        result
        for result in results
        if result.success
    ]

    failed = [
        result
        for result in results
        if not result.success
    ]

    latencies = [
        result.latency_ms
        for result in results
    ]

    successful_latencies = [
        result.latency_ms
        for result in successful
    ]

    status_counts = Counter(
        result.status_code
        for result in results
    )

    caller_counts = Counter(
        result.caller_service
        for result in results
    )

    caller_success_counts = Counter(
        result.caller_service
        for result in successful
    )

    caller_failure_counts = Counter(
        result.caller_service
        for result in failed
    )

    throughput = (
        total / total_elapsed
        if total_elapsed > 0
        else 0
    )

    success_rate = (
        len(successful) / total * 100
        if total
        else 0
    )

    failure_rate = (
        len(failed) / total * 100
        if total
        else 0
    )

    print("\n")
    print("=" * 70)
    print("                 /VERIFY LOAD TEST REPORT")
    print("=" * 70)

    print("\nTEST CONFIGURATION")
    print("-" * 70)
    print(f"Endpoint              : {VERIFY_URL}")
    print(f"Total requests        : {total}")
    print(f"Concurrency           : {min(CONCURRENCY, TOTAL_REQUESTS)}")
    print(
        "Caller services       : "
        + ", ".join(CALLER_SERVICES)
    )

    print("\nOVERALL RESULTS")
    print("-" * 70)
    print(f"Total requests        : {total}")
    print(f"Successful requests   : {len(successful)}")
    print(f"Failed requests       : {len(failed)}")
    print(f"Success rate          : {success_rate:.2f}%")
    print(f"Failure rate          : {failure_rate:.2f}%")
    print(f"Total test time       : {total_elapsed:.3f} seconds")
    print(f"Throughput            : {throughput:.2f} requests/sec")

    print("\nLATENCY")
    print("-" * 70)

    if latencies:
        print(
            f"Min latency           : "
            f"{min(latencies):.2f} ms"
        )

        print(
            f"Average latency       : "
            f"{statistics.mean(latencies):.2f} ms"
        )

        print(
            f"Median latency        : "
            f"{statistics.median(latencies):.2f} ms"
        )

        print(
            f"P95 latency           : "
            f"{percentile(latencies, 95):.2f} ms"
        )

        print(
            f"P99 latency           : "
            f"{percentile(latencies, 99):.2f} ms"
        )

        print(
            f"Max latency           : "
            f"{max(latencies):.2f} ms"
        )

    if successful_latencies:
        print("\nSUCCESSFUL REQUEST LATENCY")
        print("-" * 70)

        print(
            f"Average successful    : "
            f"{statistics.mean(successful_latencies):.2f} ms"
        )

        print(
            f"P95 successful       : "
            f"{percentile(successful_latencies, 95):.2f} ms"
        )

        print(
            f"P99 successful       : "
            f"{percentile(successful_latencies, 99):.2f} ms"
        )

    print("\nCALLER SERVICE DISTRIBUTION")
    print("-" * 70)

    for service in CALLER_SERVICES:

        total_service = caller_counts[service]
        success_service = caller_success_counts[service]
        failure_service = caller_failure_counts[service]

        service_success_rate = (
            success_service / total_service * 100
            if total_service
            else 0
        )

        print(
            f"{service:<15} "
            f"requests={total_service:<5} "
            f"success={success_service:<5} "
            f"failed={failure_service:<5} "
            f"success_rate={service_success_rate:.2f}%"
        )

    print("\nHTTP STATUS CODES")
    print("-" * 70)

    for status_code, count in sorted(
        status_counts.items(),
        key=lambda item: (
            item[0] is None,
            item[0] or 0,
        ),
    ):
        print(
            f"{str(status_code):<10} : {count}"
        )

    if failed:

        print("\nFAILURE DETAILS")
        print("-" * 70)

        # Show at most 10 failures so the report stays readable.
        for result in failed[:10]:

            print(
                f"Request #{result.request_number} | "
                f"caller={result.caller_service} | "
                f"status={result.status_code} | "
                f"error={result.error}"
            )

        if len(failed) > 10:
            print(
                f"... and {len(failed) - 10} more failures"
            )

    print("\nFINAL RESULT")
    print("-" * 70)

    if len(successful) == total:
        print(
            "PASS: All /verify requests completed successfully."
        )
    else:
        print(
            "ATTENTION: Some /verify requests failed."
        )

    print("=" * 70)
    print()

# ============================================================
# Entry point
# ============================================================

def main() -> None:

    validate_configuration()

    try:
        asyncio.run(
            run_load_test()
        )

    except KeyboardInterrupt:
        print(
            "\nLoad test interrupted by user."
        )
        sys.exit(130)

    except Exception as exc:
        print(
            f"\nLoad test failed to execute: {exc}"
        )
        sys.exit(1)


if __name__ =="__main__":
    main()