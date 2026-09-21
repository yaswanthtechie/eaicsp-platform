"""
Runtime monitoring and metrics storage.

Supports:
    - Request volume
    - Latency metrics
    - p50 / p95 latency
    - Per-model metrics
    - Per-model-version metrics
    - Recent input retrieval for drift detection
    - Backward-compatible R5 metrics

The monitoring database is stored at:

    data/monitoring.db
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "data" / "monitoring.db"

DB_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Thread safety
# ============================================================

_DB_LOCK = Lock()


# ============================================================
# Database initialization
# ============================================================


def _get_connection() -> sqlite3.Connection:
    """
    Create a SQLite connection.

    row_factory is enabled so rows can be accessed by column name.
    """

    connection = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    return connection


def _column_exists(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """
    Return True when a column exists in a SQLite table.
    """

    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in rows
    )


def initialize_database() -> None:
    """
    Create the monitoring database and migrate older R5 databases.

    Older databases did not contain model_name.

    The migration adds:

        model_name TEXT NOT NULL DEFAULT 'iris'
    """

    with _DB_LOCK:

        connection = _get_connection()

        try:

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    request_id TEXT NOT NULL,

                    timestamp TEXT NOT NULL,

                    model_name TEXT NOT NULL DEFAULT 'iris',

                    model_version TEXT NOT NULL,

                    prediction TEXT,

                    latency_ms REAL NOT NULL,

                    input_features TEXT
                )
                """
            )

            # ------------------------------------------------
            # Backward-compatible migration
            # ------------------------------------------------

            if not _column_exists(
                connection,
                "predictions",
                "model_name",
            ):
                connection.execute(
                    """
                    ALTER TABLE predictions
                    ADD COLUMN model_name
                    TEXT NOT NULL
                    DEFAULT 'iris'
                    """
                )

            connection.commit()

        finally:

            connection.close()


# Initialize database when module is imported.
initialize_database()


# ============================================================
# Utility functions
# ============================================================


def _percentile(
    values: List[float],
    percentile: float,
) -> float:
    """
    Calculate a percentile using linear interpolation.

    Example:

        values = [10, 20, 30, 40, 50]

        p50 = 30
        p95 = 48
    """

    if not values:
        return 0.0

    ordered = sorted(
        float(value)
        for value in values
    )

    if len(ordered) == 1:
        return ordered[0]

    rank = (
        percentile / 100.0
    ) * (len(ordered) - 1)

    lower_index = int(rank)

    upper_index = min(
        lower_index + 1,
        len(ordered) - 1,
    )

    fraction = (
        rank - lower_index
    )

    lower_value = ordered[
        lower_index
    ]

    upper_value = ordered[
        upper_index
    ]

    return (
        lower_value
        + (
            upper_value
            - lower_value
        )
        * fraction
    )


def _safe_json_value(
    value: Any,
) -> Any:
    """
    Convert arbitrary values into JSON-safe values.

    This prevents monitoring from failing because a prediction
    or input contains a non-JSON-native object.
    """

    try:

        json.dumps(value)

        return value

    except (
        TypeError,
        ValueError,
    ):

        return str(value)


# ============================================================
# Prediction logging
# ============================================================


def log_prediction(
    prediction: Any,
    request_id: str,
    model_version: str,
    latency_ms: float,
    input_features: Optional[Any] = None,
    model_name: str = "iris",
) -> None:
    """
    Store one prediction event.

    Parameters
    ----------
    prediction:
        Model prediction/result.

    request_id:
        Unique request identifier.

    model_version:
        Version of the model that handled the request.

    latency_ms:
        Prediction latency in milliseconds.

    input_features:
        Optional input payload/features.

    model_name:
        Logical model name.

        Defaults to ``iris`` for backward compatibility.

    Notes
    -----
    Existing R5 callers can continue using:

        log_prediction(
            prediction="setosa",
            request_id="abc",
            model_version="1",
            latency_ms=12.0,
        )

    New multi-model callers can use:

        log_prediction(
            prediction=result,
            request_id="abc",
            model_version="v1",
            latency_ms=15.2,
            input_features=payload,
            model_name="forecast",
        )
    """

    if not isinstance(
        latency_ms,
        (int, float),
    ):
        raise TypeError(
            "latency_ms must be numeric."
        )

    if latency_ms < 0:
        raise ValueError(
            "latency_ms cannot be negative."
        )

    request_id = str(
        request_id
    )

    model_version = str(
        model_version
    )

    model_name = (
        str(model_name)
        .strip()
        .lower()
    )

    if not model_name:
        model_name = "iris"

    timestamp = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    prediction_json = json.dumps(
        _safe_json_value(prediction),
        default=str,
    )

    if input_features is None:

        input_json = None

    else:

        input_json = json.dumps(
            _safe_json_value(
                input_features
            ),
            default=str,
        )

    with _DB_LOCK:

        connection = _get_connection()

        try:

            connection.execute(
                """
                INSERT INTO predictions (
                    request_id,
                    timestamp,
                    model_name,
                    model_version,
                    prediction,
                    latency_ms,
                    input_features
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    timestamp,
                    model_name,
                    model_version,
                    prediction_json,
                    float(latency_ms),
                    input_json,
                ),
            )

            connection.commit()

        finally:

            connection.close()


# ============================================================
# Internal metric calculation
# ============================================================


def _calculate_metrics(
    rows: List[sqlite3.Row],
) -> Dict[str, Any]:
    """
    Calculate metrics from database rows.
    """

    latencies = [
        float(row["latency_ms"])
        for row in rows
    ]

    request_volume = len(rows)

    if not latencies:

        return {
            "request_volume": 0,
            "latency_ms": {
                "p50": 0.0,
                "p95": 0.0,
            },
        }

    return {
        "request_volume": request_volume,
        "latency_ms": {
            "p50": round(
                _percentile(
                    latencies,
                    50,
                ),
                3,
            ),
            "p95": round(
                _percentile(
                    latencies,
                    95,
                ),
                3,
            ),
        },
    }


def _rows_for_model(
    connection: sqlite3.Connection,
    model_name: str,
) -> List[sqlite3.Row]:
    """
    Return all monitoring rows for one logical model.
    """

    return connection.execute(
        """
        SELECT
            request_id,
            timestamp,
            model_name,
            model_version,
            prediction,
            latency_ms,
            input_features
        FROM predictions
        WHERE model_name = ?
        ORDER BY timestamp ASC
        """,
        (model_name,),
    ).fetchall()


def _rows_for_version(
    connection: sqlite3.Connection,
    model_name: str,
    model_version: str,
) -> List[sqlite3.Row]:
    """
    Return monitoring rows for one model version.
    """

    return connection.execute(
        """
        SELECT
            request_id,
            timestamp,
            model_name,
            model_version,
            prediction,
            latency_ms,
            input_features
        FROM predictions
        WHERE model_name = ?
          AND model_version = ?
        ORDER BY timestamp ASC
        """,
        (
            model_name,
            model_version,
        ),
    ).fetchall()


def _volume_over_time(
    rows: List[sqlite3.Row],
) -> Dict[str, int]:
    """
    Group request volume by minute.

    Example:

        {
            "2026-09-15T05:42": 10
        }
    """

    result: Dict[str, int] = {}

    for row in rows:

        timestamp = str(
            row["timestamp"]
        )

        try:

            parsed = datetime.fromisoformat(
                timestamp
            )

            key = parsed.strftime(
                "%Y-%m-%dT%H:%M"
            )

        except ValueError:

            key = timestamp[:16]

        result[key] = (
            result.get(key, 0) + 1
        )

    return result


# ============================================================
# Per-model summary
# ============================================================


def get_model_summary(
    model_name: str,
) -> Dict[str, Any]:
    """
    Return monitoring metrics for one logical model.

    Example:

        get_model_summary("forecast")
    """

    model_name = (
        str(model_name)
        .strip()
        .lower()
    )

    with _DB_LOCK:

        connection = _get_connection()

        try:

            rows = _rows_for_model(
                connection,
                model_name,
            )

            metrics = _calculate_metrics(
                rows
            )

            versions: Dict[
                str,
                int,
            ] = {}

            version_metrics: Dict[
                str,
                Dict[str, Any],
            ] = {}

            for row in rows:

                version = str(
                    row["model_version"]
                )

                versions[version] = (
                    versions.get(
                        version,
                        0,
                    )
                    + 1
                )

            for version in sorted(
                versions.keys()
            ):

                version_rows = (
                    _rows_for_version(
                        connection,
                        model_name,
                        version,
                    )
                )

                version_metrics[
                    version
                ] = _calculate_metrics(
                    version_rows
                )

            return {
                "model_name": model_name,

                "request_volume": (
                    metrics[
                        "request_volume"
                    ]
                ),

                "latency_ms": metrics[
                    "latency_ms"
                ],

                "versions": versions,

                "version_metrics": (
                    version_metrics
                ),

                "volume_over_time": (
                    _volume_over_time(
                        rows
                    )
                ),
            }

        finally:

            connection.close()


# ============================================================
# Global summary
# ============================================================


def get_summary() -> Dict[str, Any]:
    """
    Return monitoring metrics.

    The return structure intentionally supports two contracts.

    ------------------------------------------------------------
    New multi-model contract
    ------------------------------------------------------------

        summary["models"]["iris"]
        summary["models"]["forecast"]
        summary["models"]["eta"]
        summary["models"]["anomaly"]
        summary["models"]["risk"]

    Each logical model contains:

        request_volume
        latency_ms
        versions
        version_metrics
        volume_over_time

    ------------------------------------------------------------
    Backward-compatible R5 contract
    ------------------------------------------------------------

    Existing R5 tests expect:

        summary["models"]["1"]
        summary["models"]["2"]

    Therefore each version is also exposed directly under
    ``summary["models"]`` when it belongs to the legacy Iris
    model.

    This keeps the old API working without removing the new
    multi-model structure.
    """

    with _DB_LOCK:

        connection = _get_connection()

        try:

            model_rows = connection.execute(
                """
                SELECT DISTINCT model_name
                FROM predictions
                ORDER BY model_name
                """
            ).fetchall()

            models: Dict[
                str,
                Dict[str, Any],
            ] = {}

            # ------------------------------------------------
            # New per-model structure
            # ------------------------------------------------

            for row in model_rows:

                model_name = str(
                    row["model_name"]
                )

                rows = _rows_for_model(
                    connection,
                    model_name,
                )

                metrics = _calculate_metrics(
                    rows
                )

                versions: Dict[
                    str,
                    int,
                ] = {}

                version_metrics: Dict[
                    str,
                    Dict[str, Any],
                ] = {}

                for prediction_row in rows:

                    version = str(
                        prediction_row[
                            "model_version"
                        ]
                    )

                    versions[version] = (
                        versions.get(
                            version,
                            0,
                        )
                        + 1
                    )

                for version in sorted(
                    versions.keys()
                ):

                    version_rows = (
                        _rows_for_version(
                            connection,
                            model_name,
                            version,
                        )
                    )

                    version_metrics[
                        version
                    ] = _calculate_metrics(
                        version_rows
                    )

                models[
                    model_name
                ] = {
                    "model_name": model_name,

                    "request_volume": (
                        metrics[
                            "request_volume"
                        ]
                    ),

                    "latency_ms": metrics[
                        "latency_ms"
                    ],

                    "versions": versions,

                    "version_metrics": (
                        version_metrics
                    ),

                    "volume_over_time": (
                        _volume_over_time(
                            rows
                        )
                    ),
                }

            # ------------------------------------------------
            # Backward compatibility for R5
            # ------------------------------------------------
            #
            # Original R5 tests expect:
            #
            #     summary["models"]["1"]
            #
            # instead of:
            #
            #     summary["models"]["iris"]
            #                       ["version_metrics"]["1"]
            #
            # Only Iris versions are exposed this way.
            # ------------------------------------------------

            iris_rows = _rows_for_model(
                connection,
                "iris",
            )

            iris_versions: Dict[
                str,
                int,
            ] = {}

            for row in iris_rows:

                version = str(
                    row["model_version"]
                )

                iris_versions[version] = (
                    iris_versions.get(
                        version,
                        0,
                    )
                    + 1
                )

            for version in sorted(
                iris_versions.keys()
            ):

                version_rows = (
                    _rows_for_version(
                        connection,
                        "iris",
                        version,
                    )
                )

                version_metrics = (
                    _calculate_metrics(
                        version_rows
                    )
                )

                # Do not overwrite a logical model
                # if someone happens to name a model
                # "1", "2", etc.
                if version not in models:

                    models[
                        version
                    ] = {
                        "model_name": "iris",

                        "model_version": (
                            version
                        ),

                        "request_volume": (
                            version_metrics[
                                "request_volume"
                            ]
                        ),

                        "latency_ms": (
                            version_metrics[
                                "latency_ms"
                            ]
                        ),

                        "volume_over_time": (
                            _volume_over_time(
                                version_rows
                            )
                        ),
                    }

            # ------------------------------------------------
            # Global R5 aggregate
            # ------------------------------------------------

            all_rows = connection.execute(
                """
                SELECT
                    request_id,
                    timestamp,
                    model_name,
                    model_version,
                    prediction,
                    latency_ms,
                    input_features
                FROM predictions
                ORDER BY timestamp ASC
                """
            ).fetchall()

            global_metrics = (
                _calculate_metrics(
                    all_rows
                )
            )

            return {
                "request_volume": (
                    global_metrics[
                        "request_volume"
                    ]
                ),

                "latency_ms": (
                    global_metrics[
                        "latency_ms"
                    ]
                ),

                "volume_over_time": (
                    _volume_over_time(
                        all_rows
                    )
                ),

                "models": models,
            }

        finally:

            connection.close()


# ============================================================
# Recent input retrieval
# ============================================================


def get_recent_inputs(
    limit: int = 100,
) -> List[Any]:
    """
    Return recent Iris inputs.

    This function preserves the original R5 behavior.

    Only records with:

        model_name = 'iris'

    are returned.

    This is used by the existing Iris drift/retraining flow.
    """

    if limit <= 0:
        return []

    with _DB_LOCK:

        connection = _get_connection()

        try:

            rows = connection.execute(
                """
                SELECT input_features
                FROM predictions
                WHERE model_name = 'iris'
                  AND input_features IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

            result: List[Any] = []

            for row in rows:

                raw_value = (
                    row["input_features"]
                )

                try:

                    result.append(
                        json.loads(
                            raw_value
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ):

                    result.append(
                        raw_value
                    )

            return result

        finally:

            connection.close()


def get_model_recent_inputs(
    model_name: str,
    limit: int = 100,
) -> List[Any]:
    """
    Return recent inputs for a specific logical model.

    This is used by multi-model drift detection.

    Example:

        get_model_recent_inputs(
            "forecast",
            limit=100,
        )
    """

    model_name = (
        str(model_name)
        .strip()
        .lower()
    )

    if not model_name:
        return []

    if limit <= 0:
        return []

    with _DB_LOCK:

        connection = _get_connection()

        try:

            rows = connection.execute(
                """
                SELECT input_features
                FROM predictions
                WHERE model_name = ?
                  AND input_features IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    model_name,
                    int(limit),
                ),
            ).fetchall()

            result: List[Any] = []

            for row in rows:

                raw_value = (
                    row["input_features"]
                )

                try:

                    result.append(
                        json.loads(
                            raw_value
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                    json.JSONDecodeError,
                ):

                    result.append(
                        raw_value
                    )

            return result

        finally:

            connection.close()


# ============================================================
# Per-model summary helper
# ============================================================


def get_model_metrics(
    model_name: str,
) -> Dict[str, Any]:
    """
    Alias for get_model_summary().

    This provides a simple API for dashboard/orchestrator
    integrations.
    """

    return get_model_summary(
        model_name
    )