import asyncio
import statistics
import time
from collections import Counter
from pathlib import Path

# pyrefly: ignore [missing-import]
import httpx


BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/api/v2/status"

# Increase gradually to find the degradation point.
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50, 100]

# Requests generated for each concurrency level.
REQUESTS_PER_LEVEL = 200

TIMEOUT = 10.0


async def make_request(client: httpx.AsyncClient):
    start = time.perf_counter()

    try:
        response = await client.get(
            f"{BASE_URL}{ENDPOINT}",
            headers={"X-Load-Test": "true"},
            timeout=TIMEOUT,
        )

        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }

    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "success": False,
            "status_code": 0,
            "latency_ms": latency_ms,
            "error": str(exc),
        }


async def run_level(concurrency: int):
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:

        async def limited_request():
            async with semaphore:
                return await make_request(client)

        start = time.perf_counter()

        tasks = [
            asyncio.create_task(limited_request())
            for _ in range(REQUESTS_PER_LEVEL)
        ]

        results = await asyncio.gather(*tasks)

        duration = time.perf_counter() - start

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    status_codes = dict(Counter(r["status_code"] for r in results))

    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]

    if latencies:
        sorted_latencies = sorted(latencies)

        p50 = sorted_latencies[
            min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.50))
        ]

        p95 = sorted_latencies[
            min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))
        ]

        p99 = sorted_latencies[
            min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.99))
        ]

        average = statistics.mean(latencies)
    else:
        average = 0
        p50 = 0
        p95 = 0
        p99 = 0

    throughput = REQUESTS_PER_LEVEL / duration

    return {
        "concurrency": concurrency,
        "requests": REQUESTS_PER_LEVEL,
        "successful": len(successful),
        "failed": len(failed),
        "status_codes": status_codes,
        "success_rate": (len(successful) / REQUESTS_PER_LEVEL) * 100,
        "avg_ms": average,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "throughput_rps": throughput,
        "duration_s": duration,
    }


def is_degraded(result):
    """
    Definition used for this load test.

    Gateway is considered degraded when:
    - success rate falls below 99%, OR
    - p95 latency exceeds 500 ms.
    """

    return (
        result["success_rate"] < 99
        or result["p95_ms"] > 500
    )


async def main():

    print("=" * 80)
    print("API GATEWAY LOAD TEST")
    print("=" * 80)
    print(f"Target      : {BASE_URL}{ENDPOINT}")
    print(f"Requests    : {REQUESTS_PER_LEVEL} per level")
    print(f"Levels      : {CONCURRENCY_LEVELS}")
    print("=" * 80)

    results = []

    for concurrency in CONCURRENCY_LEVELS:

        print(
            f"\nRunning concurrency={concurrency} "
            f"({REQUESTS_PER_LEVEL} requests)..."
        )

        result = await run_level(concurrency)

        results.append(result)

        print(
            f"Success      : {result['successful']}/{result['requests']}"
        )
        print(
            f"Success rate : {result['success_rate']:.2f}%"
        )
        print(
            f"Status codes : {result['status_codes']}"
        )
        print(
            f"Avg latency  : {result['avg_ms']:.2f} ms"
        )
        print(
            f"P50 latency  : {result['p50_ms']:.2f} ms"
        )
        print(
            f"P95 latency  : {result['p95_ms']:.2f} ms"
        )
        print(
            f"P99 latency  : {result['p99_ms']:.2f} ms"
        )
        print(
            f"Throughput   : {result['throughput_rps']:.2f} req/s"
        )

        if is_degraded(result):
            print("STATUS       : DEGRADED")
        else:
            print("STATUS       : HEALTHY")

    print("\n" + "=" * 80)
    print("LOAD TEST SUMMARY")
    print("=" * 80)

    degradation_point = None

    for result in results:
        status = "DEGRADED" if is_degraded(result) else "HEALTHY"

        print(
            f"Concurrency={result['concurrency']:>3} | "
            f"Success={result['success_rate']:>6.2f}% | "
            f"Status={result['status_codes']} | "
            f"P95={result['p95_ms']:>8.2f} ms | "
            f"RPS={result['throughput_rps']:>8.2f} | "
            f"{status}"
        )

        if degradation_point is None and is_degraded(result):
            degradation_point = result["concurrency"]

    print("\n" + "=" * 80)

    if degradation_point is not None:
        print(
            f"DEGRADATION POINT: "
            f"Gateway starts degrading at approximately "
            f"{degradation_point} concurrent requests."
        )
    else:
        print(
            "DEGRADATION POINT: "
            "Not reached within the tested concurrency levels."
        )

    print("=" * 80)

    # Save results
    output_dir = Path("load_tests")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "load_test_results.txt"

    with output_file.open("w", encoding="utf-8") as file:

        file.write("API Gateway Load Test Results\n")
        file.write("=" * 80 + "\n")
        file.write(f"Target: {BASE_URL}{ENDPOINT}\n")
        file.write(f"Requests per level: {REQUESTS_PER_LEVEL}\n\n")

        for result in results:
            file.write(
                f"Concurrency: {result['concurrency']}\n"
            )
            file.write(
                f"Success rate: {result['success_rate']:.2f}%\n"
            )
            file.write(
                f"Status codes: {result['status_codes']}\n"
            )
            file.write(
                f"Average latency: {result['avg_ms']:.2f} ms\n"
            )
            file.write(
                f"P50 latency: {result['p50_ms']:.2f} ms\n"
            )
            file.write(
                f"P95 latency: {result['p95_ms']:.2f} ms\n"
            )
            file.write(
                f"P99 latency: {result['p99_ms']:.2f} ms\n"
            )
            file.write(
                f"Throughput: {result['throughput_rps']:.2f} req/s\n"
            )
            file.write(
                f"Status: "
                f"{'DEGRADED' if is_degraded(result) else 'HEALTHY'}\n"
            )
            file.write("-" * 80 + "\n")

        if degradation_point is not None:
            file.write(
                f"\nDEGRADATION POINT: "
                f"{degradation_point} concurrent requests\n"
            )
        else:
            file.write(
                "\nDEGRADATION POINT: "
                "Not reached in tested levels\n"
            )

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())