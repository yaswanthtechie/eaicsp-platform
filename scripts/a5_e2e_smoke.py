
#!/usr/bin/env python3
"""
Round 15 A5 end-to-end smoke runner.

Runs configured Flow A / Flow B HTTP steps through the API Gateway and verifies
configured events directly from Kafka. No service is called directly.

Each step may define an ``expect_event`` object containing:
- topic: Kafka topic to consume
- type: expected event_type in the JSON message
- match: optional fields to match in the message's payload
- save: optional mapping of context variable -> payload field
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from confluent_kafka import Consumer


class SmokeFailure(RuntimeError):
    pass


class EventWatcher:
    """Listen to Kafka from before the first workflow step."""

    def __init__(self, bootstrap: str, topics: list[str]) -> None:
        if not topics:
            raise SmokeFailure(
                "No Kafka topics configured for event verification."
            )

        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": f"a5-smoke-{uuid.uuid4()}",
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
            }
        )
        self.seen: list[dict[str, Any]] = []
        self.consumer.subscribe(topics)

        deadline = time.monotonic() + 15
        while not self.consumer.assignment() and time.monotonic() < deadline:
            self.consumer.poll(0.5)

        if not self.consumer.assignment():
            self.consumer.close()
            raise SmokeFailure(
                f"Kafka: no partitions assigned for topics {topics}. "
                f"Check broker {bootstrap} and topic names."
            )

    def wait_for(
        self,
        event_type: str,
        match: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        def find() -> dict[str, Any] | None:
            for event in self.seen:
                payload = event.get("payload") or {}
                if (
                    event.get("event_type") == event_type
                    and isinstance(payload, dict)
                    and all(
                        payload.get(key) == value
                        for key, value in match.items()
                    )
                ):
                    return event
            return None

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            found = find()
            if found:
                return found

            message = self.consumer.poll(1.0)
            if message is None or message.error():
                continue

            try:
                event = json.loads(message.value())
            except (ValueError, TypeError):
                continue

            if isinstance(event, dict):
                self.seen.append(event)

        seen_types = sorted(
            {str(event.get("event_type", "?")) for event in self.seen}
        )
        raise SmokeFailure(
            f"Timed out after {timeout}s waiting for "
            f"event_type={event_type!r} matching {match}. "
            f"Event types seen: {seen_types}"
        )

    def close(self) -> None:
        self.consumer.close()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SmokeFailure(
            f"Cannot read JSON config {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise SmokeFailure("Config root must be a JSON object.")

    return data


_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(value: Any, context: dict[str, Any]) -> Any:
    """
    Replace {{name}} placeholders recursively.

    A string that is exactly one placeholder keeps the context value's type.
    Any placeholder left unresolved is an error.
    """
    if isinstance(value, str):
        whole = _PLACEHOLDER.fullmatch(value)
        if whole and whole.group(1) in context:
            return context[whole.group(1)]

        for key, replacement in context.items():
            value = value.replace(
                "{{" + key + "}}",
                str(replacement),
            )

        leftover = _PLACEHOLDER.search(value)
        if leftover:
            raise SmokeFailure(
                f"Unresolved placeholder {leftover.group(0)} in {value!r}"
            )

        return value

    if isinstance(value, list):
        return [render(item, context) for item in value]

    if isinstance(value, dict):
        return {
            key: render(item, context)
            for key, item in value.items()
        }

    return value


def collect_topics(steps: list[dict[str, Any]]) -> list[str]:
    """Collect Kafka topics; by default topic names equal event types."""
    return sorted(
        {
            str(
                step["expect_event"].get("topic")
                or step["expect_event"]["type"]
            )
            for step in steps
            if step.get("expect_event")
        }
    )


def response_summary(response: requests.Response) -> str:
    try:
        body_text = json.dumps(
            response.json(),
            ensure_ascii=False,
        )
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
            session,
            method,
            url,
            body=body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise SmokeFailure(
            f"{name}: request failed: {exc}"
        ) from exc

    expected_status = step.get("expected_status", 200)
    accepted = (
        expected_status
        if isinstance(expected_status, list)
        else [expected_status]
    )

    if response.status_code not in accepted:
        raise SmokeFailure(
            f"{name}: expected HTTP {accepted}, "
            f"got {response.status_code}. "
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
                f"{name}: response did not contain "
                f"save_from='{source}'. "
                f"Response={response_summary(response)}"
            ) from exc

    for variable, source in step.get("save", {}).items():
        try:
            context[str(variable)] = get_path(payload, str(source))
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise SmokeFailure(
                f"{name}: response did not contain '{source}'. "
                f"Response={response_summary(response)}"
            ) from exc

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Round 15 Flow A and Flow B smoke tests "
            "through API Gateway."
        )
    )
    parser.add_argument(
        "--config",
        default="scripts/a5_smoke_config.json",
        help="Path to A5 JSON scenario config.",
    )
    parser.add_argument(
        "--gateway",
        default=os.getenv(
            "A5_GATEWAY_URL",
            "http://localhost:8000",
        ),
        help="API Gateway base URL.",
    )
    parser.add_argument(
        "--kafka",
        default=os.getenv(
            "A5_KAFKA_BOOTSTRAP",
            "localhost:29092",
        ),
        help="Kafka bootstrap servers.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("A5_REQUEST_TIMEOUT", "20")),
    )
    parser.add_argument(
        "--event-timeout",
        type=float,
        default=float(os.getenv("A5_EVENT_TIMEOUT", "30")),
        help="Seconds to wait for each expected Kafka event.",
    )
    args = parser.parse_args()

    watcher: EventWatcher | None = None

    try:
        config = load_json(Path(args.config))

        # Shared session contains only non-role-specific headers.
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})

        now = datetime.now(timezone.utc)
        context: dict[str, Any] = {
            "today": date.today().isoformat(),
            "today_plus_7": (
                date.today() + timedelta(days=7)
            ).isoformat(),
            "run_id": now.strftime("%Y%m%d%H%M%S"),
            **config.get("variables", {}),
        }

        # Every role must supply its own token explicitly.
        for name, env_var in (
            ("procurement_token", "A5_PROCUREMENT_TOKEN"),
            ("supplier_token", "A5_SUPPLIER_TOKEN"),
            ("warehouse_token", "A5_WAREHOUSE_TOKEN"),
        ):
            value = os.getenv(env_var)
            if not value:
                raise SmokeFailure(f"{env_var} is not set.")
            context[name] = value

        all_steps = config.get("steps", [])
        if not isinstance(all_steps, list) or not all_steps:
            raise SmokeFailure(
                "Config must contain a non-empty 'steps' array."
            )

        if any(not isinstance(step, dict) for step in all_steps):
            raise SmokeFailure(
                "Every item in 'steps' must be an object."
            )

        topics = collect_topics(all_steps)
        if not topics:
            raise SmokeFailure(
                "No Kafka event expectations configured. "
                "Add expect_event with 'type' to relevant steps "
                "in the JSON config."
            )

        print(f"A5 smoke test -> {args.gateway}")
        print(f"Kafka bootstrap -> {args.kafka}")
        print(
            f"Scenario: {config.get('name', 'Round 15 Flow A/B')}"
        )
        print(f"Steps: {len(all_steps)}")

        # Subscribe before executing workflow steps to avoid missing events.
        watcher = EventWatcher(args.kafka, topics)

        try:
            for step in all_steps:
                name = str(step.get("name", "unnamed step"))
                payload: Any = {}

                if step.get("path"):
                    # Each step gets an isolated session so role headers
                    # cannot leak into subsequent requests.
                    step_session = requests.Session()
                    step_session.headers.update(session.headers)

                    for key, value in step.get("headers", {}).items():
                        step_session.headers[str(key)] = str(
                            render(value, context)
                        )

                    try:
                        payload = run_step(
                            step_session,
                            args.gateway,
                            step,
                            context,
                            args.timeout,
                        )
                    finally:
                        step_session.close()

                if step.get("capture_response_as"):
                    context[str(step["capture_response_as"])] = payload

                expect = step.get("expect_event")
                if expect:
                    event_type = str(expect.get("type", ""))
                    if not event_type:
                        raise SmokeFailure(
                            f"{name}: expect_event.type must be configured."
                        )

                    match = render(expect.get("match", {}), context)
                    if not isinstance(match, dict):
                        raise SmokeFailure(
                            f"{name}: expect_event.match "
                            "must be a JSON object."
                        )

                    try:
                        event = watcher.wait_for(
                            event_type,
                            match,
                            args.event_timeout,
                        )
                    except SmokeFailure as exc:
                        raise SmokeFailure(
                            f"{name}: {exc}"
                        ) from exc

                    event_payload = event.get("payload") or {}
                    for variable, field in expect.get("save", {}).items():
                        if field not in event_payload:
                            raise SmokeFailure(
                                f"{name}: event {event_type} has no "
                                f"payload field '{field}'."
                            )
                        context[str(variable)] = event_payload[field]

                    print(
                        f"  PASS {name}: Kafka event {event_type}"
                    )
        finally:
            watcher.close()
            watcher = None

        print("\nA5 RESULT: PASS")
        return 0

    except SmokeFailure as exc:
        print(
            f"\nA5 RESULT: FAIL\nFAILED STEP: {exc}",
            file=sys.stderr,
        )
        return 1

    except KeyboardInterrupt:
        print("\nA5 RESULT: ABORTED", file=sys.stderr)
        return 130

    finally:
        if watcher is not None:
            watcher.close()


if __name__ == "__main__":
    raise SystemExit(main())
