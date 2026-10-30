#!/usr/bin/env python3
"""
Round 15 A5 end-to-end smoke runner.

Runs configured Flow A / Flow B HTTP steps through the API Gateway, then
polls the Purchase Order event endpoint and verifies that configured event
types were persisted. No service is called directly.

Configuration is JSON so request bodies and event names stay aligned with
the actual service contracts in this repository.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class SmokeFailure(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeFailure(f"Cannot read JSON config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SmokeFailure("Config root must be a JSON object.")
    return data


def render(value: Any, context: dict[str, Any]) -> Any:
    """Replace {{name}} placeholders recursively in strings."""
    if isinstance(value, str):
        for key, replacement in context.items():
            value = value.replace("{{" + key + "}}", str(replacement))
        return value
    if isinstance(value, list):
        return [render(item, context) for item in value]
    if isinstance(value, dict):
        return {key: render(item, context) for key, item in value.items()}
    return value


def response_summary(response: requests.Response) -> str:
    try:
        body = response.json()
        body_text = json.dumps(body, ensure_ascii=False)
    except ValueError:
        body_text = response.text
    return body_text[:1200]


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    body: Any = None,
    timeout: float = 20,
) -> tuple[requests.Response, Any]:
    response = session.request(
        method=method.upper(),
        url=url,
        json=body,
        timeout=timeout,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}
    return response, payload


def get_path(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(dotted_path)
    return current


def check_event_types(
    session: requests.Session,
    gateway: str,
    po_number: str,
    expected: list[str],
    *,
    timeout_seconds: int,
    poll_interval: float,
) -> None:
    if not expected:
        raise SmokeFailure(
            "No expected_events configured. Set the exact event type names "
            "from the service event definitions; event verification is required."
        )

    url = (
        gateway.rstrip("/")
        + "/api/v1/purchase-orders/"
        + quote(po_number, safe="")
        + "/events"
    )
    deadline = time.monotonic() + timeout_seconds
    last_events: list[dict[str, Any]] = []

    while time.monotonic() < deadline:
        response, payload = request_json(session, "GET", url)
        if response.ok:
            if isinstance(payload, list):
                last_events = [item for item in payload if isinstance(item, dict)]
            elif isinstance(payload, dict):
                candidate = (
                    payload.get("events")
                    or payload.get("items")
                    or payload.get("data")
                    or []
                )
                if isinstance(candidate, list):
                    last_events = [
                        item for item in candidate if isinstance(item, dict)
                    ]
            found = {
                str(event.get("event_type") or event.get("event_name") or event.get("type") or "")
                for event in last_events
            }
            missing = sorted(set(expected) - found)
            if not missing:
                print(f"  PASS events: {', '.join(expected)}")
                return
        elif response.status_code not in (404, 405):
            raise SmokeFailure(
                f"Event lookup failed ({response.status_code}) at {url}: "
                f"{response_summary(response)}"
            )
        time.sleep(poll_interval)

    found = sorted({
        str(event.get("event_type") or event.get("event_name") or event.get("type") or "")
        for event in last_events
    })
    missing = sorted(set(expected) - set(found))
    raise SmokeFailure(
        "Timed out waiting for PO events. "
        f"Missing={missing}; observed={found}. "
        "Check the configured event endpoint/response shape and Kafka consumer."
    )


def run_step(
    session: requests.Session,
    gateway: str,
    step: dict[str, Any],
    context: dict[str, Any],
    timeout: float,
) -> Any:
    name = str(step.get("name", "unnamed step"))
    method = str(step.get("method", "POST")).upper()
    path = render(step.get("path", ""), context)
    if not isinstance(path, str) or not path.startswith("/"):
        raise SmokeFailure(f"{name}: path must start with '/'.")
    url = gateway.rstrip("/") + path
    body = render(step.get("body"), context)

    try:
        response, payload = request_json(
            session, method, url, body=body, timeout=timeout
        )
    except requests.RequestException as exc:
        raise SmokeFailure(f"{name}: request failed: {exc}") from exc

    expected_status = step.get("expected_status", 200)
    accepted = (
        expected_status
        if isinstance(expected_status, list)
        else [expected_status]
    )
    if response.status_code not in accepted:
        raise SmokeFailure(
            f"{name}: expected HTTP {accepted}, got {response.status_code}. "
            f"URL={url}; response={response_summary(response)}"
        )

    print(f"  PASS {name} (HTTP {response.status_code})")

    save_as = step.get("save_as")
    if save_as:
        source = step.get("save_from", "id")
        try:
            context[str(save_as)] = get_path(payload, str(source))
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise SmokeFailure(
                f"{name}: response did not contain save_from='{source}'. "
                f"Response={response_summary(response)}"
            ) from exc

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Round 15 Flow A and Flow B smoke tests through API Gateway."
    )
    parser.add_argument(
        "--config",
        default="scripts/a5_smoke_config.json",
        help="Path to A5 JSON scenario config.",
    )
    parser.add_argument(
        "--gateway",
        default=os.getenv("A5_GATEWAY_URL", "http://localhost:8000"),
        help="API Gateway base URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("A5_REQUEST_TIMEOUT", "20")),
    )
    parser.add_argument(
        "--event-timeout",
        type=int,
        default=int(os.getenv("A5_EVENT_TIMEOUT", "30")),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
    )
    args = parser.parse_args()

    try:
        config = load_json(Path(args.config))
        token = os.getenv("A5_BEARER_TOKEN")
        api_key = os.getenv("A5_API_KEY")
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})
        if token:
            session.headers["Authorization"] = f"Bearer {token}"
        if api_key:
            session.headers["X-API-Key"] = api_key

        # Optional headers can be supplied in config for separate internal/
        # supplier identities. A step may override them with its own headers.
        context: dict[str, Any] = dict(config.get("variables", {}))
        context.setdefault("supplier_token", os.getenv("A5_SUPPLIER_TOKEN", ""))
        context.setdefault("procurement_token", os.getenv("A5_PROCUREMENT_TOKEN", token or ""))
        all_steps = config.get("steps", [])
        if not isinstance(all_steps, list) or not all_steps:
            raise SmokeFailure("Config must contain a non-empty 'steps' array.")

        print(f"A5 smoke test -> {args.gateway}")
        print(f"Scenario: {config.get('name', 'Round 15 Flow A/B')}")
        print(f"Steps: {len(all_steps)}")

        for step in all_steps:
            if not isinstance(step, dict):
                raise SmokeFailure("Every item in 'steps' must be an object.")
            step_session = requests.Session()
            step_session.headers.update(session.headers)
            for key, value in step.get("headers", {}).items():
                step_session.headers[str(key)] = str(render(value, context))
            payload = run_step(
                step_session, args.gateway, step, context, args.timeout
            )
            if step.get("capture_response_as"):
                context[str(step["capture_response_as"])] = payload

        po_number = context.get("po_number") or config.get("po_number")
        if not po_number:
            raise SmokeFailure(
                "PO number was not captured. Configure a create-PO step with "
                "'save_as': 'po_number' and the correct 'save_from' response path."
            )

        expected_events = config.get("expected_events", [])
        event_session = requests.Session()
        event_session.headers.update(session.headers)
        event_headers = config.get("event_headers", {})
        event_session.headers.update({
            str(key): str(render(value, context))
            for key, value in event_headers.items()
        })

        check_event_types(
            event_session,
            args.gateway,
            str(po_number),
            [str(item) for item in expected_events],
            timeout_seconds=args.event_timeout,
            poll_interval=args.poll_interval,
        )
        print("\nA5 RESULT: PASS")
        return 0

    except SmokeFailure as exc:
        print(f"\nA5 RESULT: FAIL\nFAILED STEP: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nA5 RESULT: ABORTED", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
