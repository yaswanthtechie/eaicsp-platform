"""
Sustained load test for Platform Service /api/v1/auth/verify.

Purpose:
    Measure realistic combined /verify traffic using multiple user tokens
    and the actual caller-service identities.

Simulated callers:
    - supplier-portal
    - compliance
    - api-gateway

The test sends real HTTP requests to the running Platform Service.

Run:
    python scripts/load_test_verify.py

Required environment variable:
    ACCESS_TOKENS

    Provide 5-10 valid access tokens separated by commas.

Example PowerShell:
    $env:ACCESS_TOKENS="token1,token2,token3,token4,token5"

Optional environment variables:
    BASE_URL=http://127.0.0.1:8005
    DURATION_SECONDS=120
    CONCURRENCY=20
    REQUESTS_PER_SECOND=10
    TIMEOUT_SECONDS=10

Example:
    $env:ACCESS_TOKENS="token1,token2,token3,token4,token5"
    $env:DURATION_SECONDS="120"
    $env:CONCURRENCY="20"
    python scripts/load_test_verify.py
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

ACCESS_TOKENS_RAW = os.getenv("ACCESS_TOKENS", "")

ACCESS_TOKENS = [
    token.strip()
    for token in ACCESS_TOKENS_RAW.split(",")
    if token.strip()
]

DURATION_SECONDS = int(
    os.getenv("DURATION_SECONDS", "120")
)

CONCURRENCY = int(
    os.getenv("CONCURRENCY", "20")
)

REQUESTS_PER_SECOND = float(
    os.getenv("REQUESTS_PER_SECOND", "5")
)

TIMEOUT_SECONDS = float(
    os.getenv("TIMEOUT_SECONDS", "10")
)


# ============================================================
# Real caller identities
# ============================================================

CALLER_SERVICES = (
    "supplier-portal",
    "compliance",
    "api-gateway",
)


# ============================================================
# Result model
# ============================================================

@dataclass
class RequestResult:
    request_number: int
    caller_service: str
    token_index: int
    success: bool
    status_code: int | None
    latency_ms: float
    elapsed_seconds: float
    error: str | None = None


# ============================================================
# Validation
# ============================================================

def validate_configuration() -> None:
    """Validate load-test configuration before starting."""

    if not ACCESS_TOKENS:
        print(
            "\nERROR: ACCESS_TOKENS environment variable is missing.\n"
        )
        print(
            "Provide 5-10 valid access tokens separated by commas."
        )
        print("\nPowerShell example:")
        print(
            '$env:ACCESS_TOKENS="token1,token2,token3,token4,token5"'
        )
        print()
        sys.exit(1)

    if len(ACCESS_TOKENS) < 5:
        print(
            f"WARNING: Only {len(ACCESS_TOKENS)} token(s) supplied."
        )
        print(
            "For the M5 realistic-load test, use 5-10 different user tokens."
        )

    if len(ACCESS_TOKENS) > 10:
        print(
            "WARNING: More than 10 tokens supplied. "
            "Only the first 10 will be used."
        )

    if DURATION_SECONDS < 120:
        print(
            "WARNING: DURATION_SECONDS is less than 120 seconds."
        )
        print(
            "The M5 test should normally run for at least 2 minutes."
        )

    if CONCURRENCY <= 0:
        print("ERROR: CONCURRENCY must be greater than 0.")
        sys.exit(1)

    if REQUESTS_PER_SECOND <= 0:
        print(
            "ERROR: REQUESTS_PER_SECOND must be greater than 0."
        )
        sys.exit(1)

    if TIMEOUT_SECONDS <= 0:
        print(
            "ERROR: TIMEOUT_SECONDS must be greater than 0."
        )
        sys.exit(1)


# ============================================================
# Single request
# ============================================================

async def send_verify_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    request_number: int,
    token: str,
    token_index: int,
    caller_service: str,
    test_start: float,
) -> RequestResult:

    async with semaphore:

        start = time.perf_counter()

        try:
            response = await client.post(
                VERIFY_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Caller-Service": caller_service,
                },
            )

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            elapsed_seconds = (
                time.perf_counter() - test_start
            )

            success = response.status_code == 200

            error = None

            if not success:
                try:
                    error = response.text[:300]
                except Exception:
                    error = "Unable to read response body"

            return RequestResult(
                request_number=request_number,
                caller_service=caller_service,
                token_index=token_index,
                success=success,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
                elapsed_seconds=elapsed_seconds,
                error=error,
            )

        except Exception as exc:

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            elapsed_seconds = (
                time.perf_counter() - test_start
            )

            return RequestResult(
                request_number=request_number,
                caller_service=caller_service,
                token_index=token_index,
                success=False,
                status_code=None,
                latency_ms=elapsed_ms,
                elapsed_seconds=elapsed_seconds,
                error=str(exc),
            )


# ============================================================
# Sustained load test
# ============================================================

async def run_load_test() -> list[RequestResult]:

    tokens = ACCESS_TOKENS[:10]

    semaphore = asyncio.Semaphore(CONCURRENCY)

    limits = httpx.Limits(
        max_connections=CONCURRENCY,
        max_keepalive_connections=CONCURRENCY,
    )

    timeout = httpx.Timeout(
        TIMEOUT_SECONDS
    )

    print("\nStarting sustained /verify load test...")
    print("----------------------------------------")
    print(f"Platform URL       : {BASE_URL}")
    print(f"Verify endpoint    : {VERIFY_URL}")
    print(f"Duration            : {DURATION_SECONDS} seconds")
    print(f"Concurrency         : {CONCURRENCY}")
    print(f"Target rate         : {REQUESTS_PER_SECOND:.2f} requests/sec")
    print(f"User tokens         : {len(tokens)}")
    print(
        "Caller services     : "
        + ", ".join(CALLER_SERVICES)
    )
    print("----------------------------------------\n")

    results: list[RequestResult] = []

    test_start = time.perf_counter()

    request_number = 0

    next_request_time = test_start

    async with httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
    ) as client:

        pending_tasks = set()

        while (
            time.perf_counter() - test_start
            < DURATION_SECONDS
        ):

            now = time.perf_counter()

            # Keep approximately the requested target rate.
            if now < next_request_time:
                await asyncio.sleep(
                    next_request_time - now
                )

            elapsed = (
                time.perf_counter() - test_start
            )

            if elapsed >= DURATION_SECONDS:
                break

            request_number += 1

            token_index = (
                (request_number - 1)
                % len(tokens)
            )

            caller_service = CALLER_SERVICES[
                (request_number - 1)
                % len(CALLER_SERVICES)
            ]

            task = asyncio.create_task(
                send_verify_request(
                    client=client,
                    semaphore=semaphore,
                    request_number=request_number,
                    token=tokens[token_index],
                    token_index=token_index + 1,
                    caller_service=caller_service,
                    test_start=test_start,
                )
            )

            pending_tasks.add(task)

            # Collect completed tasks.
            completed = {
                task
                for task in pending_tasks
                if task.done()
            }

            for completed_task in completed:
                results.append(
                    await completed_task
                )

            pending_tasks -= completed

            next_request_time += (
                1.0 / REQUESTS_PER_SECOND
            )

        # Finish outstanding requests.
        if pending_tasks:
            completed_results = await asyncio.gather(
                *pending_tasks
            )

            results.extend(
                completed_results
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

    token_counts = Counter(
        result.token_index
        for result in results
    )

    rate_limit_results = [
        result
        for result in results
        if result.status_code == 429
    ]

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
    print("/VERIFY SUSTAINED LOAD TEST REPORT")
    print("=" * 70)

    print("\nTEST CONFIGURATION")
    print("-" * 70)
    print(f"Endpoint              : {VERIFY_URL}")
    print(f"Duration              : {total_elapsed:.2f} seconds")
    print(f"Configured duration   : {DURATION_SECONDS} seconds")
    print(f"Concurrency           : {CONCURRENCY}")
    print(
        f"Target request rate   : "
        f"{REQUESTS_PER_SECOND:.2f} requests/sec"
    )
    print(f"Different tokens      : {len(ACCESS_TOKENS[:10])}")
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
    print(f"Total test time       : {total_elapsed:.2f} seconds")
    print(f"Actual throughput     : {throughput:.2f} requests/sec")

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

    print("\n429 RATE-LIMIT ANALYSIS")
    print("-" * 70)

    print(
        f"Total 429 responses   : "
        f"{len(rate_limit_results)}"
    )

    if rate_limit_results:

        first_429 = min(
            rate_limit_results,
            key=lambda result: result.elapsed_seconds,
        )

        print(
            f"First 429 after       : "
            f"{first_429.elapsed_seconds:.2f} seconds"
        )

        print(
            f"First 429 request     : "
            f"#{first_429.request_number}"
        )

        print(
            f"First 429 caller      : "
            f"{first_429.caller_service}"
        )

        print(
            f"First 429 token       : "
            f"token-{first_429.token_index}"
        )

    else:
        print(
            "No 429 responses were observed."
        )

    print("\nCALLER SERVICE DISTRIBUTION")
    print("-" * 70)

    for service in CALLER_SERVICES:

        total_service = caller_counts[service]

        success_service = (
            caller_success_counts[service]
        )

        failure_service = (
            caller_failure_counts[service]
        )

        service_success_rate = (
            success_service
            / total_service
            * 100
            if total_service
            else 0
        )

        service_429 = sum(
            1
            for result in rate_limit_results
            if result.caller_service == service
        )

        print(
            f"{service:<18} "
            f"requests={total_service:<6} "
            f"success={success_service:<6} "
            f"failed={failure_service:<6} "
            f"429={service_429:<6} "
            f"success_rate={service_success_rate:.2f}%"
        )

    print("\nTOKEN DISTRIBUTION")
    print("-" * 70)

    for token_index in sorted(token_counts):
        print(
            f"token-{token_index:<3} : "
            f"{token_counts[token_index]} requests"
        )

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

    if failed:

        print("\nFAILURE DETAILS")
        print("-" * 70)

        for result in failed[:10]:

            print(
                f"Request #{result.request_number} | "
                f"caller={result.caller_service} | "
                f"token=token-{result.token_index} | "
                f"status={result.status_code} | "
                f"time={result.elapsed_seconds:.2f}s | "
                f"error={result.error}"
            )

        if len(failed) > 10:
            print(
                f"... and {len(failed) - 10} more failures"
            )

    print("\nFINAL RESULT")
    print("-" * 70)

    if rate_limit_results:

        print(
            "ATTENTION: Rate limiting was triggered."
        )

        print(
            "Use the first-429 timing and per-caller "
            "429 counts when evaluating the /verify limit."
        )

    elif len(successful) == total:

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


if __name__ == "__main__":
    main()