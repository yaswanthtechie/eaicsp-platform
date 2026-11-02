"""
Tests for JWT token redaction in Uvicorn logs (PR #279 Fix 2).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from app.core.log_redaction import (
    REDACTED,
    UVICORN_LOGGERS,
    TokenQueryRedactionFilter,
    install_token_redaction,
    redact_token_query,
)


def test_websocket_url_token_redacted():
    """1. WebSocket URL containing ?token=abc.def gets redacted."""
    raw = "/api/v1/analytics/kpis/real-time?token=abc.def"
    redacted = redact_token_query(raw)
    assert "abc.def" not in redacted
    assert f"?token={REDACTED}" in redacted


def test_http_url_access_token_redacted():
    """2. HTTP URL containing ?access_token=secret123 gets redacted."""
    raw = "/api/v1/resource?access_token=secret123"
    redacted = redact_token_query(raw)
    assert "secret123" not in redacted
    assert f"?access_token={REDACTED}" in redacted


def test_other_query_parameters_remain_unchanged():
    """3. Other query parameters such as status=active remain unchanged."""
    raw = "/api/v1/orders?status=active&limit=50"
    redacted = redact_token_query(raw)
    assert redacted == raw

    # Verify other parameters remain intact when token is also present
    mixed = "/api/v1/orders?status=active&token=xyz987&limit=50"
    redacted_mixed = redact_token_query(mixed)
    assert "xyz987" not in redacted_mixed
    assert f"status=active&token={REDACTED}&limit=50" in redacted_mixed


def test_multiple_token_parameters_all_redacted():
    """4. Multiple token parameters are all redacted."""
    raw = "/api/v1/test?token=jwt1&other=val&access_token=jwt2"
    redacted = redact_token_query(raw)
    assert "jwt1" not in redacted
    assert "jwt2" not in redacted
    assert f"/api/v1/test?token={REDACTED}&other=val&access_token={REDACTED}" == redacted


def test_token_query_redaction_filter_record():
    """Verify TokenQueryRedactionFilter redacts record.msg and record.args."""
    flt = TokenQueryRedactionFilter()

    # Message string redaction
    rec_msg = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET /api/v1/analytics/kpis/real-time?token=sensitive_token HTTP/1.1",
        args=(),
        exc_info=None,
    )
    flt.filter(rec_msg)
    assert "sensitive_token" not in rec_msg.msg
    assert f"?token={REDACTED}" in rec_msg.msg

    # Arguments tuple redaction
    rec_args = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1", "GET", "/api/v1/resource?access_token=secret_abc", "1.1", 200),
        exc_info=None,
    )
    flt.filter(rec_args)
    assert "secret_abc" not in rec_args.args[2]
    assert f"?access_token={REDACTED}" in rec_args.args[2]


def test_install_token_redaction_idempotent():
    """5. Calling install_token_redaction() multiple times does not install duplicate filters."""
    install_token_redaction()
    install_token_redaction()

    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        redaction_filters = [
            f for f in logger.filters if isinstance(f, TokenQueryRedactionFilter)
        ]
        assert len(redaction_filters) == 1


def test_importing_main_installs_filter_subprocess():
    """6. Importing app.main installs the filter. Verify this in a fresh Python subprocess."""
    gateway_root = str(Path(__file__).resolve().parents[1])
    code = (
        "import sys, logging\n"
        f"sys.path.insert(0, {gateway_root!r})\n"
        "from app.core.log_redaction import TokenQueryRedactionFilter, UVICORN_LOGGERS\n"
        "import app.main\n"
        "for name in UVICORN_LOGGERS:\n"
        "    logger = logging.getLogger(name)\n"
        "    filters = [f for f in logger.filters if isinstance(f, TokenQueryRedactionFilter)]\n"
        "    assert len(filters) == 1, f'Expected 1 filter for {name}, got {len(filters)}'\n"
        "print('FILTERS_OK')\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "FILTERS_OK" in res.stdout
