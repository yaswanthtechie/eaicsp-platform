
import argparse
import json
import time
import urllib.request
import urllib.error


DEFAULT_PAYLOAD = {
    "request": {
        "features": [5.1, 3.5, 1.4, 0.2]
    }
}


def send_request(url: str, payload: dict, timeout: float) -> bool:
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate load against the Kubernetes Iris prediction service."
    )

    parser.add_argument(
        "--url",
        default="http://localhost:3000/predict",
        help="Prediction endpoint URL",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Load duration in seconds",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=10,
        help="Requests per second",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5,
        help="HTTP request timeout in seconds",
    )

    args = parser.parse_args()

    interval = 1.0 / args.rate

    total = 0
    successful = 0
    failed = 0

    start_time = time.monotonic()
    next_request = start_time

    print("=" * 60)
    print("Kubernetes Load Test")
    print("=" * 60)
    print(f"URL       : {args.url}")
    print(f"Duration  : {args.duration}s")
    print(f"Rate      : {args.rate} requests/sec")
    print("=" * 60)

    while time.monotonic() - start_time < args.duration:
        current_time = time.monotonic()

        if current_time < next_request:
            time.sleep(next_request - current_time)

        success = send_request(
            args.url,
            DEFAULT_PAYLOAD,
            args.timeout,
        )

        total += 1

        if success:
            successful += 1
        else:
            failed += 1

        next_request += interval

    elapsed = time.monotonic() - start_time

    print()
    print("=" * 60)
    print("Load Test Result")
    print("=" * 60)
    print(f"Total Requests : {total}")
    print(f"Successful     : {successful}")
    print(f"Failed         : {failed}")
    print(f"Elapsed        : {elapsed:.2f}s")

    if total:
        success_rate = successful / total * 100
        print(f"Success Rate   : {success_rate:.2f}%")

    print("=" * 60)


if __name__ == "__main__":
    main()

