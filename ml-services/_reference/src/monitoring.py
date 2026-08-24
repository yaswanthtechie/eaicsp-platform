import sqlite3
import statistics
from datetime import datetime,timezone
from pathlib import Path
from threading import Lock


# Project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Local monitoring database
DB_PATH = BASE_DIR / "data" / "monitoring.db"

# Make sure data directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DB_LOCK = Lock()


def initialize_database() -> None:
    """Create monitoring database and predictions table."""

    with _DB_LOCK:
        connection = sqlite3.connect(DB_PATH)

        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    prediction TEXT NOT NULL
                )
                """
            )

            connection.commit()

        finally:
            connection.close()


def log_prediction(
    request_id: str,
    model_version: str,
    latency_ms: float,
    prediction: str,
) -> None:
    """Store one prediction monitoring record."""

    with _DB_LOCK:
        connection = sqlite3.connect(DB_PATH)

        try:
            connection.execute(
                """
                INSERT INTO predictions (
                    request_id,
                    timestamp,
                    model_version,
                    latency_ms,
                    prediction
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    datetime.now(timezone.utc).isoformat(),
                    model_version,
                    latency_ms,
                    prediction,
                ),
            )

            connection.commit()

        finally:
            connection.close()


def _percentile(values: list[float], percentile: float) -> float:
    """Calculate percentile without requiring NumPy."""

    if not values:
        return 0.0

    values = sorted(values)

    index = (len(values) - 1) * percentile / 100

    lower = int(index)
    upper = min(lower + 1, len(values) - 1)

    weight = index - lower

    return (
        values[lower]
        + (values[upper] - values[lower]) * weight
    )


def get_summary() -> dict:
    """Return real latency and request-volume metrics."""

    with _DB_LOCK:
        connection = sqlite3.connect(DB_PATH)

        try:
            cursor = connection.execute(
                """
                SELECT
                    timestamp,
                    latency_ms
                FROM predictions
                ORDER BY timestamp ASC
                """
            )

            rows = cursor.fetchall()

        finally:
            connection.close()

    latencies = [
        float(row[1])
        for row in rows
    ]

    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)

    volume_by_time = {}

    for timestamp, _latency in rows:

        # Example: 2026-08-11T15:30
        minute = timestamp[:16]

        volume_by_time[minute] = (
            volume_by_time.get(minute, 0) + 1
        )

    return {
        "request_volume": len(rows),
        "latency_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
        },
        "volume_over_time": volume_by_time,
    }


# Initialize database when module is loaded
initialize_database()