"""
Unit tests for scripts/verify_elk_correlation.py.
Validates correlation logic, timeouts, connection error handling, schema resilience,
token privacy, and evidence creation rules without requiring Docker or live services.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.verify_elk_correlation import (
    check_token_absent,
    es_search,
    extract_logged_status,
    generate_jaeger_url,
    generate_kibana_url,
    generate_request_id,
    poll_elasticsearch_for_request,
    send_gateway_request,
    validate_trace_id,
    verify_correlation,
    write_evidence,
)

VALID_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"


def test_generate_request_id_format():
    rid = generate_request_id()
    assert isinstance(rid, str)
    assert rid.startswith("r14-elk-")
    uuid_part = rid[len("r14-elk-"):]
    assert len(uuid_part) == 36


@pytest.mark.parametrize(
    "trace_id,expected",
    [
        (VALID_TRACE_ID, True),
        (VALID_TRACE_ID.upper(), True),
        ("0" * 32, False),
        (None, False),
        (12345, False),
        (["list"], False),
        ("short", False),
        ("4bf92f3577b34da6a3ce929d0e0e473", False),  # 31 chars
        ("4bf92f3577b34da6a3ce929d0e0e47360", False),  # 33 chars
        ("4bf92f3577b34da6a3ce929d0e0e473g", False),  # Non-hex 'g'
    ],
)
def test_validate_trace_id(trace_id, expected):
    assert validate_trace_id(trace_id) is expected


@pytest.mark.parametrize(
    "log_entry,expected",
    [
        ({"http.status_code": 200}, 200),
        ({"http": {"status_code": 404}}, 404),
        ({"status_code": 500}, 500),
        ({"http": {"status_code": "502"}}, 502),
        ({"http.status_code": "201"}, 201),
        ({"http": "not-a-dict"}, None),
        ({"http": {}}, None),
        ({"http.status_code": "not-an-int"}, None),
        ({}, None),
        (None, None),
        ("invalid-type", None),
    ],
)
def test_extract_logged_status_schemata(log_entry, expected):
    assert extract_logged_status(log_entry) == expected


def test_generate_urls():
    jaeger_url = generate_jaeger_url("http://localhost:16686/", VALID_TRACE_ID)
    assert jaeger_url == f"http://localhost:16686/trace/{VALID_TRACE_ID}"

    assert generate_jaeger_url("http://localhost:16686", None) is None
    assert generate_jaeger_url("http://localhost:16686", "invalid") is None

    kibana_url = generate_kibana_url("http://127.0.0.1:5601/", "req-123")
    assert kibana_url.startswith("http://127.0.0.1:5601/app/discover#/view/1e6adbaa-1f7b-426c-bad0-d483bfff6c5c")
    assert "request_id:\"req-123\"" in kibana_url


def test_send_gateway_request_success():
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        status, err = send_gateway_request("http://localhost:8000", "/api/v1/items", "req-1")
        assert status == 200
        assert err is None


def test_send_gateway_request_http_error():
    http_error = urllib.error.HTTPError(
        url="http://localhost:8000/api/v1/items",
        code=502,
        msg="Bad Gateway",
        hdrs=None,
        fp=io.BytesIO(b"Downstream offline"),
    )
    with patch("urllib.request.urlopen", side_effect=http_error):
        status, err = send_gateway_request("http://localhost:8000", "/api/v1/items", "req-1")
        assert status == 502
        assert err is None


def test_send_gateway_request_connection_failure():
    url_error = urllib.error.URLError("Connection refused")
    with patch("urllib.request.urlopen", side_effect=url_error):
        status, err = send_gateway_request("http://localhost:8000", "/api/v1/items", "req-1")
        assert status is None
        assert "Gateway connection failed" in err


def test_send_gateway_request_timeout():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        status, err = send_gateway_request("http://localhost:8000", "/api/v1/items", "req-1")
        assert status is None
        assert "timed out" in err


def test_send_gateway_request_token_header_and_privacy():
    captured_reqs = []

    def mock_urlopen(req, timeout):
        captured_reqs.append(req)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    secret_token = "secret-super-sensitive-token-12345"
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        status, err = send_gateway_request(
            "http://localhost:8000",
            "/api/v1/items",
            "req-1",
            token=secret_token,
        )
        assert status == 200
        assert err is None
        assert len(captured_reqs) == 1
        assert captured_reqs[0].get_header("Authorization") == f"Bearer {secret_token}"
        assert captured_reqs[0].get_header("X-request-id") == "req-1"


def test_es_search_success():
    payload = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "request_id": "r14-elk-test",
                        "trace_id": VALID_TRACE_ID,
                        "http.status_code": 200,
                    }
                }
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = io.BytesIO(json.dumps(payload).encode("utf-8"))

    with patch("urllib.request.urlopen", return_value=mock_resp.__enter__.return_value):
        ok, hits, err = es_search("http://127.0.0.1:9200", {"query": {"match_all": {}}})
        assert ok is True
        assert len(hits) == 1
        assert hits[0]["request_id"] == "r14-elk-test"
        assert err is None


def test_es_search_missing_index_404():
    http_error = urllib.error.HTTPError(
        url="http://127.0.0.1:9200/gateway-logs-*/_search",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"index_not_found_exception"}'),
    )
    with patch("urllib.request.urlopen", side_effect=http_error):
        ok, hits, err = es_search("http://127.0.0.1:9200", {"query": {"match_all": {}}})
        assert ok is True
        assert hits == []
        assert err == "index_not_found"


def test_es_search_connection_failure():
    url_error = urllib.error.URLError("Connection refused")
    with patch("urllib.request.urlopen", side_effect=url_error):
        ok, hits, err = es_search("http://127.0.0.1:9200", {"query": {"match_all": {}}})
        assert ok is False
        assert hits == []
        assert "Elasticsearch connection failed" in err


def test_es_search_malformed_response():
    with patch("urllib.request.urlopen", return_value=io.BytesIO(b"not-json")):
        ok, hits, err = es_search("http://127.0.0.1:9200", {"query": {"match_all": {}}})
        assert ok is False
        assert hits == []
        assert "Failed to parse Elasticsearch response as JSON" in err


def test_poll_elasticsearch_for_request_success():
    expected_hit = {"request_id": "req-1", "trace_id": VALID_TRACE_ID}
    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, [expected_hit], None)):
        log_line, err = poll_elasticsearch_for_request(
            "http://127.0.0.1:9200",
            "req-1",
            timeout=1.0,
            interval=0.1,
        )
        assert log_line == expected_hit
        assert err is None


def test_poll_elasticsearch_for_request_timeout():
    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, [], None)):
        log_line, err = poll_elasticsearch_for_request(
            "http://127.0.0.1:9200",
            "req-1",
            timeout=0.05,
            interval=0.01,
        )
        assert log_line is None
        assert "within 0.05s" in err


def test_check_token_absent_clean_and_leaked():
    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, [], None)):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "my-secret-token")
        assert ok is True
        assert leaked is False
        assert err is None

    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, [{"_source": {}}], None)):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "my-secret-token")
        assert ok is True
        assert leaked is True
        assert err is None


def test_check_token_absent_es_down():
    with patch("scripts.verify_elk_correlation.es_search", return_value=(False, [], "ES down")):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "my-secret-token")
        assert ok is False
        assert leaked is False
        assert "Token check search failed" in err


def test_check_token_absent_query_structure():
    """Verify query includes fields: ['*'] and lenient: True."""
    captured_queries = []

    def mock_search(es_base, query, index_pattern=None, timeout=None):
        captured_queries.append(query)
        return True, [], None

    with patch("scripts.verify_elk_correlation.es_search", side_effect=mock_search):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "bearer-test-token")
        assert ok is True
        assert leaked is False
        assert err is None
        assert len(captured_queries) == 1
        qs = captured_queries[0]["query"]["query_string"]
        assert qs["fields"] == ["*"]
        assert qs["lenient"] is True
        assert qs["query"] == '"bearer-test-token"'


def test_check_token_absent_escaping_backslash_and_quotes():
    """Verify tokens with backslashes and double quotes are escaped correctly (backslash first)."""
    captured_queries = []

    def mock_search(es_base, query, index_pattern=None, timeout=None):
        captured_queries.append(query)
        return True, [], None

    with patch("scripts.verify_elk_correlation.es_search", side_effect=mock_search):
        test_token = 'token\\with\\backslashes"and"quotes'
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", test_token)
        assert ok is True
        assert len(captured_queries) == 1
        expected_query = '"token\\\\with\\\\backslashes\\"and\\"quotes"'
        assert captured_queries[0]["query"]["query_string"]["query"] == expected_query


def test_check_token_absent_detects_leak_in_custom_fields():
    """Verify token in fields like request_id, route, or any custom field is detected as a leak."""
    leak_in_request_id = [{"_source": {"request_id": "r14-leak-token-1234"}}]
    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, leak_in_request_id, None)):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "leak-token")
        assert ok is True
        assert leaked is True
        assert err is None

    leak_in_route = [{"_source": {"route": "/api/v1/inventory?token=secret123"}}]
    with patch("scripts.verify_elk_correlation.es_search", return_value=(True, leak_in_route, None)):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "secret123")
        assert ok is True
        assert leaked is True
        assert err is None


def test_check_token_absent_es_error_does_not_produce_false_success():
    """Verify ES connection or query errors produce ok=False and do not report token as absent."""
    with patch("scripts.verify_elk_correlation.es_search", return_value=(False, [], "Elasticsearch 500 Internal Server Error")):
        ok, leaked, err = check_token_absent("http://127.0.0.1:9200", "some-token")
        assert ok is False
        assert leaked is False
        assert err is not None
        assert "Token check search failed" in err


def test_verify_correlation_all_pass_writes_evidence(tmp_path):
    mock_log = {
        "@timestamp": "2026-10-13T12:00:00.000Z",
        "level": "ERROR",
        "service.name": "api-gateway",
        "http": {"status_code": 502},
        "latency_ms": 12.34,
        "request_id": "r14-elk-mock",
        "trace_id": VALID_TRACE_ID,
    }

    with (
        patch("scripts.verify_elk_correlation.send_gateway_request", return_value=(502, None)),
        patch("scripts.verify_elk_correlation.poll_elasticsearch_for_request", return_value=(mock_log, None)),
        patch("scripts.verify_elk_correlation.check_token_absent", return_value=(True, False, None)),
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            path="/api/v1/inventory/items",
            es_base="http://127.0.0.1:9200",
            kibana_base="http://127.0.0.1:5601",
            jaeger_base="http://localhost:16686",
            token="dummy-test-token",
            wait_seconds=1.0,
            interval_seconds=0.1,
            evidence_dir=tmp_path,
        )

        assert success is True
        assert result is not None
        assert result["http_status_returned"] == 502
        assert result["http_status_logged"] == 502
        assert result["trace_id"] == VALID_TRACE_ID
        assert result["token_found_in_elasticsearch"] is False
        assert result["jaeger_url"] == f"http://localhost:16686/trace/{VALID_TRACE_ID}"
        assert "request_id:\"r14-elk-" in result["kibana_url"]

        evidence_file = tmp_path / "elk_correlation.json"
        assert evidence_file.exists()
        raw_evidence = evidence_file.read_text(encoding="utf-8")
        saved = json.loads(raw_evidence)
        assert saved["http_status_returned"] == 502
        assert saved["token_found_in_elasticsearch"] is False
        assert '"token_found_in_elasticsearch": false' in raw_evidence
        # Ensure secret token is not written into evidence
        assert "dummy-test-token" not in raw_evidence


def test_verify_correlation_without_token_sets_token_found_to_null(tmp_path):
    mock_log = {
        "@timestamp": "2026-10-13T12:00:00.000Z",
        "level": "INFO",
        "service.name": "api-gateway",
        "http": {"status_code": 200},
        "latency_ms": 10.5,
        "request_id": "r14-elk-notoken",
        "trace_id": VALID_TRACE_ID,
    }

    with (
        patch("scripts.verify_elk_correlation.send_gateway_request", return_value=(200, None)),
        patch("scripts.verify_elk_correlation.poll_elasticsearch_for_request", return_value=(mock_log, None)),
        patch("scripts.verify_elk_correlation.check_token_absent") as mock_check,
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            path="/health",
            token=None,
            wait_seconds=1.0,
            interval_seconds=0.1,
            evidence_dir=tmp_path,
        )

        assert success is True
        assert result is not None
        assert result["token_found_in_elasticsearch"] is None
        mock_check.assert_not_called()

        evidence_file = tmp_path / "elk_correlation.json"
        assert evidence_file.exists()
        raw_evidence = evidence_file.read_text(encoding="utf-8")
        saved = json.loads(raw_evidence)
        assert saved["token_found_in_elasticsearch"] is None
        assert '"token_found_in_elasticsearch": null' in raw_evidence


def test_verify_correlation_gateway_down_no_evidence_written(tmp_path):
    with patch(
        "scripts.verify_elk_correlation.send_gateway_request",
        return_value=(None, "Gateway connection failed: Connection refused"),
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            evidence_dir=tmp_path,
        )
        assert success is False
        assert result is None
        assert "Gateway request failed" in msg

        evidence_file = tmp_path / "elk_correlation.json"
        assert not evidence_file.exists()


def test_verify_correlation_status_mismatch_no_evidence_written(tmp_path):
    mock_log = {
        "http.status_code": 500,
        "request_id": "r14-elk-mock",
        "trace_id": VALID_TRACE_ID,
    }

    with (
        patch("scripts.verify_elk_correlation.send_gateway_request", return_value=(200, None)),
        patch("scripts.verify_elk_correlation.poll_elasticsearch_for_request", return_value=(mock_log, None)),
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            evidence_dir=tmp_path,
        )
        assert success is False
        assert result is None
        assert "Status code mismatch" in msg

        evidence_file = tmp_path / "elk_correlation.json"
        assert not evidence_file.exists()


def test_verify_correlation_invalid_trace_id_no_evidence_written(tmp_path):
    mock_log = {
        "http.status_code": 200,
        "request_id": "r14-elk-mock",
        "trace_id": "0" * 32,  # Invalid: all zeroes
    }

    with (
        patch("scripts.verify_elk_correlation.send_gateway_request", return_value=(200, None)),
        patch("scripts.verify_elk_correlation.poll_elasticsearch_for_request", return_value=(mock_log, None)),
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            evidence_dir=tmp_path,
        )
        assert success is False
        assert result is None
        assert "Invalid or missing trace_id" in msg

        evidence_file = tmp_path / "elk_correlation.json"
        assert not evidence_file.exists()


def test_verify_correlation_token_leak_fails_no_evidence_written(tmp_path):
    mock_log = {
        "http.status_code": 200,
        "request_id": "r14-elk-mock",
        "trace_id": VALID_TRACE_ID,
    }

    with (
        patch("scripts.verify_elk_correlation.send_gateway_request", return_value=(200, None)),
        patch("scripts.verify_elk_correlation.poll_elasticsearch_for_request", return_value=(mock_log, None)),
        patch("scripts.verify_elk_correlation.check_token_absent", return_value=(True, True, None)),  # Leaked!
    ):
        success, result, msg = verify_correlation(
            gateway_base="http://localhost:8000",
            token="leaked-token",
            evidence_dir=tmp_path,
        )
        assert success is False
        assert result is None
        assert "SECURITY FAILURE" in msg

        evidence_file = tmp_path / "elk_correlation.json"
        assert not evidence_file.exists()
