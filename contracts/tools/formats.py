from datetime import datetime
import uuid
from jsonschema import FormatChecker


def build_format_checker() -> FormatChecker:
    """Return a FormatChecker that always enforces uuid and RFC-3339 date-time
    without relying on optional third-party jsonschema format extras."""
    checker = FormatChecker()

    @checker.checks("uuid", ValueError)
    def _check_uuid(instance: object) -> bool:
        if not isinstance(instance, str):
            return True
        uuid.UUID(instance)
        return True

    @checker.checks("date-time", ValueError)
    def _check_date_time(instance: object) -> bool:
        if not isinstance(instance, str):
            return True
        if "T" not in instance and "t" not in instance:
            raise ValueError("Missing 'T' time separator in date-time")
        normalized = instance[:-1] + "+00:00" if instance.endswith(("Z", "z")) else instance
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            raise ValueError("Missing timezone offset in date-time")
        return True

    return checker