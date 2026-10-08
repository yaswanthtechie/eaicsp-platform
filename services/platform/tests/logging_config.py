import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

SERVICE_NAME = "platform-service"

request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="no-request-id",
)

def set_request_id(request_id: str) -> None:
    """
    Store the request ID for the current request context.
    """
    request_id_context.set(request_id)


def get_request_id() -> str:
    """
    Return the request ID for the current request context.
    """
    return request_id_context.get()


class JSONFormatter(logging.Formatter):
    """
    JSON structured logging formatter.

    Every log entry contains:
        timestamp
        level
        service
        request_id
        message

    Additional request fields can be supplied through
    the LogRecord extra dictionary.
    """

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "request_id": get_request_id(),
            "message": record.getMessage(),
        }

        # Preserve additional structured fields.
        structured_fields = (
            "caller",
            "caller_endpoint",
            "method",
            "path",
            "status",
            "duration_ms",
        )

        for field in structured_fields:
            value = getattr(record, field, None)

            if value is not None:
                log_entry[field] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            log_entry,
            ensure_ascii=False,
        )


def configure_logging() -> logging.Logger:
    """
    Configure application-wide structured JSON logging.
    """

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers during reload/tests.
    if logger.handlers:
        for handler in logger.handlers:
            handler.setFormatter(JSONFormatter())

        return logger

    file_handler = logging.FileHandler(
        "logs/auth_requests.log",
        encoding="utf-8",
    )

    console_handler = logging.StreamHandler(
        sys.stdout
    )

    formatter = JSONFormatter()

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger