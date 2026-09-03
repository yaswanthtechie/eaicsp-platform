import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from src.config import MONITORING_INPUT_LIMIT


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "monitoring.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DB_LOCK = Lock()


def initialize_database() -> None:
    """Create monitoring database and upgrade R4 database if required."""

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
                    prediction TEXT NOT NULL,
                    input_features TEXT
                )
                """
            )

            # Upgrade an existing R4 database.
            columns = connection.execute(
                "PRAGMA table_info(predictions)"
            ).fetchall()

            column_names = {
                column[1]
                for column in columns
            }

            if "input_features" not in column_names:
                connection.execute(
                    """
                    ALTER TABLE predictions
                    ADD COLUMN input_features TEXT
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
    input_features=None,
) -> None:
    """
    Store one prediction monitoring record.

    R5 additionally stores input features so that the
    scheduler can calculate drift.
    """

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
                    prediction,
                    input_features
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    datetime.now(timezone.utc).isoformat(),
                    model_version,
                    latency_ms,
                    prediction,
                    json.dumps(input_features)
                    if input_features is not None
                    else None,
                ),
            )

            connection.commit()

        finally:
            connection.close()


def _percentile(
    values: list[float],
    percentile: float,
) -> float:
    """Calculate percentile without NumPy."""

    if not values:
        return 0.0

    values = sorted(values)

    index = (
        (len(values) - 1)
        * percentile
        / 100
    )

    lower = int(index)

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    weight = index - lower

    return (
        values[lower]
        + (
            values[upper]
            - values[lower]
        )
        * weight
    )


def get_summary() -> dict:
    """
    Return aggregate and per-model metrics.

    R5:
        - request volume by model
        - p50 latency by model
        - p95 latency by model
    """

    with _DB_LOCK:
        connection = sqlite3.connect(DB_PATH)

        try:
            rows = connection.execute(
                """
                SELECT
                    timestamp,
                    model_version,
                    latency_ms
                FROM predictions
                ORDER BY timestamp DESC
                limit 1000
                """
            ).fetchall()

        finally:
            connection.close()

    all_latencies = [
        float(row[2])
        for row in rows
    ]

    # Aggregate volume by minute.
    volume_by_time = {}

    for timestamp, _model_version, _latency in rows:

        minute = timestamp[:16]

        volume_by_time[minute] = (
            volume_by_time.get(
                minute,
                0,
            )
            + 1
        )

    # --------------------------------------------------
    # R5: Per-model metrics
    # --------------------------------------------------

    models = {}

    for row in rows:

        timestamp = row[0]
        model_version = str(row[1])
        latency = float(row[2])

        if model_version not in models:
            models[model_version] = {
                "request_volume": 0,
                "latencies": [],
                "volume_over_time": {},
            }

        models[model_version]["request_volume"] += 1
        models[model_version]["latencies"].append(
            latency
        )

        minute = timestamp[:16]

        models[model_version][
            "volume_over_time"
        ][minute] = (
            models[model_version][
                "volume_over_time"
            ].get(minute, 0)
            + 1
        )

    model_summary = {}

    for model_version, data in models.items():

        latencies = data["latencies"]

        model_summary[model_version] = {
            "request_volume": data[
                "request_volume"
            ],
            "latency_ms": {
                "p50": round(
                    _percentile(
                        latencies,
                        50,
                    ),
                    2,
                ),
                "p95": round(
                    _percentile(
                        latencies,
                        95,
                    ),
                    2,
                ),
            },
            "volume_over_time": data[
                "volume_over_time"
            ],
        }

    return {
        "request_volume": len(rows),
        "latency_ms": {
            "p50": round(
                _percentile(
                    all_latencies,
                    50,
                ),
                2,
            ),
            "p95": round(
                _percentile(
                    all_latencies,
                    95,
                ),
                2,
            ),
        },
        "volume_over_time": volume_by_time,
        "models": model_summary,
    }


def get_recent_inputs(
    limit: int = MONITORING_INPUT_LIMIT,
) -> list[list[float]]:
    """
    Return recent prediction inputs.

    Used by R5 automated retraining.
    """

    with _DB_LOCK:
        connection = sqlite3.connect(DB_PATH)

        try:
            rows = connection.execute(
                """
                SELECT input_features
                FROM predictions
                WHERE input_features IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        finally:
            connection.close()

    inputs = []

    for row in rows:

        try:
            features = json.loads(row[0])

            if (
                isinstance(features, list)
                and len(features) == 4
            ):
                inputs.append(
                    [
                        float(value)
                        for value in features
                    ]
                )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            continue

    inputs.reverse()

    return inputs


initialize_database()