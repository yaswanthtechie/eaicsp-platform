"""
Round 14 proof: gateway logs reach Elasticsearch and correlate with Jaeger.

1. Sends ONE request through the gateway with a known X-Request-ID.
2. Polls Elasticsearch (gateway-logs-*) until that request's log line arrives.
3. Prints the log line, its trace_id, and ready-to-open Jaeger / Kibana links.
4. Checks the bearer token (if --token is given) never appears in Elasticsearch.
5. Writes docs/evidence/round14/elk_correlation.json ONLY upon real successful live verification.

Exit code 0 = everything found and correlated.
Exit code 1 = service unreachable, verification failed, or timeout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

DEFAULT_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "evidence" / "round14"
HEX_32_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def generate_request_id() -> str:
    """Generate a unique request ID with the round 14 prefix."""
    return f"r14-elk-{uuid.uuid4()}"


def validate_trace_id(trace_id: Any) -> bool:
    """
    Validate that trace_id is a 32-character hexadecimal string and not all zeroes.
    """
    if not isinstance(trace_id, str):
        return False
    if len(trace_id) != 32:
        return False
    if not HEX_32_PATTERN.match(trace_id):
        return False
    if trace_id == "0" * 32:
        return False
    return True


def extract_logged_status(log_line: dict[str, Any]) -> int | None:
    """
    Extract the HTTP status code from a log entry safely, handling
    both raw flat keys ('http.status_code') and Filebeat expanded keys ('http': {'status_code': ...}).
    """
    if not isinstance(log_line, dict):
        return None

    http_obj = log_line.get("http")
    if isinstance(http_obj, dict) and "status_code" in http_obj:
        raw_status = http_obj["status_code"]
    elif "http.status_code" in log_line:
        raw_status = log_line["http.status_code"]
    elif "status_code" in log_line:
        raw_status = log_line["status_code"]
    else:
        return None

    try:
        return int(raw_status)
    except (ValueError, TypeError):
        return None


def generate_jaeger_url(jaeger_base: str, trace_id: str | None) -> str | None:
    """Generate a direct Jaeger trace UI link if trace_id is valid."""
    if not trace_id or not validate_trace_id(trace_id):
        return None
    base = jaeger_base.rstrip("/")
    return f"{base}/trace/{trace_id}"


DEFAULT_SAVED_SEARCH_ID = "1e6adbaa-1f7b-426c-bad0-d483bfff6c5c"


def generate_kibana_url(
    kibana_base: str,
    request_id: str,
    saved_search_id: str = DEFAULT_SAVED_SEARCH_ID,
) -> str:
    """Generate a Kibana Discover link for the saved search filtering by request_id."""
    base = kibana_base.rstrip("/")
    kql = f'request_id:"{request_id}"'
    return (
        f"{base}/app/discover#/view/{saved_search_id}"
        f"?_a=(query:(language:kuery,query:'{kql}'))"
    )


def send_gateway_request(
    gateway_base: str,
    path: str,
    request_id: str,
    token: str | None = None,
    timeout: float = 15.0,
) -> tuple[int | None, str | None]:
    """
    Send a single GET request through the API gateway.
    Returns (status_code, error_message).
    Note: Token is never printed or included in error messages.
    """
    url = f"{gateway_base.rstrip('/')}/{path.lstrip('/')}"
    headers = {"X-Request-ID": request_id}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError as exc:
        return None, f"Gateway connection failed: {exc.reason}"
    except (TimeoutError, OSError) as exc:
        return None, f"Gateway request timed out or failed: {exc}"


def es_search(
    es_base: str,
    body: dict[str, Any],
    index_pattern: str = "gateway-logs-*",
    timeout: float = 10.0,
) -> tuple[bool, list[dict[str, Any]], str | None]:
    """
    Perform a search query against Elasticsearch.
    Returns (success, hits_sources, error_message).
    """
    url = f"{es_base.rstrip('/')}/{index_pattern}/_search"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.load(resp)
            if not isinstance(payload, dict):
                return False, [], "Unexpected Elasticsearch response: payload is not a JSON object"
            hits_block = payload.get("hits")
            if not isinstance(hits_block, dict):
                return False, [], "Unexpected Elasticsearch response: missing or invalid 'hits' object"
            hits_list = hits_block.get("hits")
            if not isinstance(hits_list, list):
                return False, [], "Unexpected Elasticsearch response: 'hits.hits' is not a list"

            sources: list[dict[str, Any]] = []
            for hit in hits_list:
                if isinstance(hit, dict) and "_source" in hit and isinstance(hit["_source"], dict):
                    sources.append(hit["_source"])
            return True, sources, None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # Index not created yet
            return True, [], "index_not_found"
        return False, [], f"Elasticsearch HTTP error {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return False, [], f"Elasticsearch connection failed: {exc.reason}"
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return False, [], f"Failed to parse Elasticsearch response as JSON: {exc}"
    except (TimeoutError, OSError) as exc:
        return False, [], f"Elasticsearch request timed out or failed: {exc}"


def poll_elasticsearch_for_request(
    es_base: str,
    request_id: str,
    timeout: float = 90.0,
    interval: float = 3.0,
    index_pattern: str = "gateway-logs-*",
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Poll Elasticsearch until a log entry matching request_id is found or timeout is reached.
    Returns (log_entry, error_message).
    """
    query = {"query": {"match_phrase": {"request_id": request_id}}}
    deadline = time.monotonic() + timeout
    last_error: str | None = None

    while time.monotonic() < deadline:
        ok, hits, err = es_search(es_base, query, index_pattern=index_pattern, timeout=min(10.0, interval))
        if ok and hits:
            return hits[0], None
        if not ok:
            last_error = err
        time.sleep(interval)

    msg = f"No log line for request_id '{request_id}' found in Elasticsearch within {timeout}s"
    if last_error:
        msg += f" (last error: {last_error})"
    return None, msg


def check_token_absent(
    es_base: str,
    token: str,
    index_pattern: str = "gateway-logs-*",
    timeout: float = 10.0,
) -> tuple[bool, bool, str | None]:
    """
    Verify that the given bearer token never appears in Elasticsearch logs.
    Returns (check_successful, token_found, error_message).
    IMPORTANT: Never prints or logs the token value.
    """
    safe_query_token = token.replace("\\", "\\\\").replace('"', '\\"')
    query = {
        "query": {
            "query_string": {
                "query": f'"{safe_query_token}"',
                "fields": ["*"],
                "lenient": True,
            }
        }
    }
    ok, hits, err = es_search(es_base, query, index_pattern=index_pattern, timeout=timeout)
    if not ok:
        return False, False, f"Token check search failed: {err}"
    return True, len(hits) > 0, None


def write_evidence(
    evidence_dir: Path,
    result_data: dict[str, Any],
) -> Path:
    """
    Write verification results to docs/evidence/round14/elk_correlation.json.
    Must ONLY be called after a successful verification.
    """
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "elk_correlation.json"
    evidence_file.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    return evidence_file


def verify_correlation(
    gateway_base: str = "http://localhost:8000",
    path: str = "/api/v1/inventory/items",
    es_base: str = "http://127.0.0.1:19200",
    kibana_base: str = "http://127.0.0.1:15601",
    jaeger_base: str = "http://localhost:16686",
    token: str | None = None,
    wait_seconds: float = 90.0,
    interval_seconds: float = 3.0,
    evidence_dir: Path | None = DEFAULT_EVIDENCE_DIR,
) -> tuple[bool, dict[str, Any] | None, str]:
    """
    Run full live ELK correlation verification.
    Returns (success, result_dict_or_none, status_message).
    """
    request_id = generate_request_id()
    print(f"Sending gateway request to {path} with X-Request-ID={request_id}...")

    # 1. Send single gateway request
    status, send_err = send_gateway_request(
        gateway_base=gateway_base,
        path=path,
        request_id=request_id,
        token=token,
    )
    if send_err is not None or status is None:
        return False, None, f"Gateway request failed: {send_err}"

    print(f"Gateway responded with HTTP {status}")

    # 2. Poll Elasticsearch for the matching log entry
    print(f"Polling Elasticsearch ({es_base}) for request_id={request_id} (timeout={wait_seconds}s)...")
    log_line, poll_err = poll_elasticsearch_for_request(
        es_base=es_base,
        request_id=request_id,
        timeout=wait_seconds,
        interval=interval_seconds,
    )
    if log_line is None:
        return False, None, f"Elasticsearch log lookup failed: {poll_err}"

    # 3. Verify status code
    logged_status = extract_logged_status(log_line)
    if logged_status is None:
        return False, None, "Failed to extract valid HTTP status code from log entry"
    if logged_status != status:
        return False, None, f"Status code mismatch: gateway returned {status}, but log has {logged_status}"

    # 4. Verify trace ID
    trace_id = log_line.get("trace_id")
    if not validate_trace_id(trace_id):
        return False, None, f"Invalid or missing trace_id in log entry: {trace_id}"

    # 5. Check token absence if token was provided
    token_found: bool | None = None
    if token:
        check_ok, found, token_err = check_token_absent(es_base=es_base, token=token)
        if not check_ok:
            return False, None, f"Token leak check could not be completed: {token_err}"
        if found:
            return False, None, "SECURITY FAILURE: Provided token was discovered in Elasticsearch logs!"
        token_found = found

    # 6. Generate Jaeger and Kibana URLs
    jaeger_url = generate_jaeger_url(jaeger_base, trace_id)
    kibana_url = generate_kibana_url(kibana_base, request_id)

    result_data = {
        "request_id": request_id,
        "http_status_returned": status,
        "http_status_logged": logged_status,
        "log_line": log_line,
        "trace_id": trace_id,
        "jaeger_url": jaeger_url,
        "kibana_url": kibana_url,
        "token_found_in_elasticsearch": token_found,
    }

    # 7. Write evidence ONLY on real successful live verification
    if evidence_dir is not None:
        evidence_file = write_evidence(evidence_dir, result_data)
        print(f"Evidence recorded at {evidence_file}")

    status_msg = "Correlation verified successfully: log found in ES, status matches, trace_id valid"
    if token:
        status_msg += ", token absent"
    return True, result_data, status_msg


def main() -> int:
    p = argparse.ArgumentParser(description="Verify gateway ELK log flow and trace correlation.")
    p.add_argument("--gateway", default="http://localhost:8000", help="Gateway URL")
    p.add_argument("--path", default="/api/v1/inventory/items", help="Gateway route to call")
    p.add_argument("--es", default="http://127.0.0.1:19200", help="Elasticsearch URL")
    p.add_argument("--kibana", default="http://127.0.0.1:15601", help="Kibana URL")
    p.add_argument("--jaeger", default="http://localhost:16686", help="Jaeger URL")
    p.add_argument("--token", help="Optional bearer token (verified absent from ES; never printed/stored)")
    p.add_argument("--wait", type=float, default=90.0, help="Seconds to wait for Filebeat harvesting")
    p.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds")
    a = p.parse_args()

    success, result, msg = verify_correlation(
        gateway_base=a.gateway,
        path=a.path,
        es_base=a.es,
        kibana_base=a.kibana,
        jaeger_base=a.jaeger,
        token=a.token,
        wait_seconds=a.wait,
        interval_seconds=a.interval,
        evidence_dir=DEFAULT_EVIDENCE_DIR,
    )

    if success and result is not None:
        print("\n" + json.dumps(result, indent=2))
        print(f"\nPASS: {msg}")
        return 0
    else:
        print(f"\nBLOCKED / FAIL: {msg}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
