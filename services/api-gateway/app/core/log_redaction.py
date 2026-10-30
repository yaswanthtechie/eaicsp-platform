"""Redact credentials from Uvicorn log lines."""

from __future__ import annotations

import logging
import re

_TOKEN_QUERY_RE = re.compile(
    r"(?i)([?&](?:token|access_token)=)[^&\s\"]+"
)

REDACTED = "[REDACTED]"
UVICORN_LOGGERS = ("uvicorn.access", "uvicorn.error")


def redact_token_query(value: str) -> str:
    return _TOKEN_QUERY_RE.sub(rf"\g<1>{REDACTED}", value)


class TokenQueryRedactionFilter(logging.Filter):
    """Redact token values from log messages and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_token_query(record.msg)

        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_token_query(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )

        return True


def install_token_redaction() -> None:
    """Install the filter on Uvicorn loggers only once."""

    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)

        if not any(
            isinstance(f, TokenQueryRedactionFilter)
            for f in logger.filters
        ):
            logger.addFilter(TokenQueryRedactionFilter())
