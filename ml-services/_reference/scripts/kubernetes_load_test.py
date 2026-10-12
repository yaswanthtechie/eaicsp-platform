"""
Load generator for the Kubernetes Iris service (Round 14).

Sends POST /predict at a fixed rate from a thread pool, so one slow request
does not stall the others. Prints a summary and a single RESULT_JSON line;
with --output it also writes the summary to a file so the numbers can be
committed as evidence.

Exit code is 1 if any request failed.
"""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


DEFAULT_PAYLOAD = {
    "request": {
        "features": [5.1, 3.5, 1.4, 0.2]
    }
}


def send_request(url: str, payload: dict, timeout: float) -> str | None:
    """Return None on success, or a short error label on failure."""
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            if 200 <= response.status < 300:
                return None
            return f"http_{response.status}"
    except urllib.error.HTTPError as exc:
        return f"http_{exc.code}"
    except Exception as exc:
        # Count every failure, including connection resets and malformed responses.
        return type(exc).__name__


def run(url: str, duration: float, rate: float, timeout: float, workers: int) -> dict:
    lock = threading.Lock()
    errors: Counter = Counter()
    counts = {"total": 0, "successful": 0}

    def task() -> None:
        error = send_request(url, DEFAULT_PAYLOAD, timeout)
        with lock:
            counts["total"] += 1
            if error is None:
                counts["successful"] += 1
            else:
                errors[error] += 1

    interval = 1.0 / rate
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    sent = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while sent * interval < duration:
            delay = start + sent * interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            pool.submit(task)
            sent += 1

    elapsed = time.monotonic() - start
    total = counts["total"]

    return {
        "started_at": started_at,
        "url": url,
        "target_rate": rate,
        "achieved_rate": round(total / elapsed, 2) if elapsed else 0.0,
        "elapsed_s": round(elapsed, 2),
        "total": total,
        "successful": counts["successful"],
        "failed": total - counts["successful"],
        "errors": dict(errors),
        "success_rate": (
            round(counts["successful"] / total * 100, 2) if total else 0.0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate load against the Kubernetes Iris prediction service."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:3000/predict",
        help="prediction endpoint URL",
    )
    parser.add_argument("--duration", type=float, default=60, help="seconds")
    parser.add_argument("--rate", type=float, default=10, help="requests per second")
    parser.add_argument("--timeout", type=float, default=5, help="per-request timeout")
    parser.add_argument("--workers", type=int, default=20, help="concurrent requests")
    parser.add_argument("--output", help="write the JSON summary to this file")
    args = parser.parse_args()

    if args.duration <= 0:
        parser.error("--duration must be greater than 0")
    if args.rate <= 0:
        parser.error("--rate must be greater than 0")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.workers <= 0:
        parser.error("--workers must be greater than 0")

    result = run(args.url, args.duration, args.rate, args.timeout, args.workers)

    print("=" * 60)
    for key, value in result.items():
        print(f"{key:<14}: {value}")
    print("=" * 60)
    print("RESULT_JSON " + json.dumps(result))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            f.write("\n")

    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())