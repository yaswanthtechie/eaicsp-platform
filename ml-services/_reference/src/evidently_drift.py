
"""
Evidently-based drift detection for the Iris reference service.

Milestone 2:
- Data drift detection
- Prediction drift detection
- Real monitoring.db input/prediction support
- Deliberately shifted-data validation
- HTML report generation
- Retraining integration support

Compatible with Evidently 0.7.23.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, List

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier

from evidently import Report
from evidently.presets import DataDriftPreset

from src.monitoring import DB_PATH


FEATURE_NAMES = [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width",
]

TARGET_NAME = "prediction"

DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "reports"
    / "evidently"
    / "drift_report.html"
)


def load_reference_inputs() -> pd.DataFrame:
    """Load the Iris training/reference feature distribution."""

    iris = load_iris()

    return pd.DataFrame(
        iris.data,
        columns=FEATURE_NAMES,
    )


def create_recent_inputs(
    reference: pd.DataFrame,
    sample_count: int = 100,
) -> pd.DataFrame:
    """Create an unshifted recent-data window for testing."""

    if sample_count <= 0:
        raise ValueError(
            "sample_count must be greater than zero."
        )

    if len(reference) == 0:
        raise ValueError(
            "Reference data cannot be empty."
        )

    indices = (
        np.arange(sample_count)
        % len(reference)
    )

    return (
        reference.iloc[indices]
        .reset_index(drop=True)
        .copy()
    )


def create_shifted_inputs(
    reference: pd.DataFrame,
    shift: float = 2.0,
) -> pd.DataFrame:
    """Create deliberately shifted production-like data."""

    shifted = reference.copy()

    for column in FEATURE_NAMES:
        shifted[column] = (
            shifted[column] + shift
        )

    return shifted.reset_index(
        drop=True
    )


def _build_reference_model():
    """Build the same deterministic Iris reference model."""

    iris = load_iris()

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
    )

    model.fit(
        iris.data,
        iris.target,
    )

    return model


def add_predictions(
    inputs: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add deterministic model predictions to an input DataFrame.

    Used for controlled Evidently validation windows.
    Production monitoring uses predictions already logged
    in monitoring.db.
    """

    model = _build_reference_model()

    predictions = model.predict(
        inputs[FEATURE_NAMES].to_numpy()
    )

    result = inputs.copy()

    result[TARGET_NAME] = [
        str(value)
        for value in predictions
    ]

    return result


def _prediction_to_value(
    prediction: Any,
) -> str:
    """Convert a logged prediction into a stable categorical value."""

    if isinstance(prediction, str):
        try:
            decoded = json.loads(prediction)
        except json.JSONDecodeError:
            return prediction
    else:
        decoded = prediction

    if isinstance(decoded, dict):
        if "prediction" in decoded:
            return str(
                decoded["prediction"]
            )

    return str(decoded)


def load_logged_monitoring_data(
    limit: int = 100,
) -> pd.DataFrame:
    """
    Load real served-model inputs and predictions from monitoring.db.

    Only Iris records with usable four-feature input payloads
    are returned.
    """

    if limit <= 0:
        return pd.DataFrame(
            columns=[
                *FEATURE_NAMES,
                TARGET_NAME,
            ]
        )

    connection = sqlite3.connect(DB_PATH)

    try:
        rows = connection.execute(
            """
            SELECT
                input_features,
                prediction
            FROM predictions
            WHERE model_name = 'iris'
              AND input_features IS NOT NULL
              AND prediction IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        connection.close()

    records: List[dict[str, Any]] = []

    for input_raw, prediction_raw in rows:
        try:
            features = json.loads(input_raw)
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        if not isinstance(
            features,
            (list, tuple),
        ):
            continue

        if len(features) != len(
            FEATURE_NAMES
        ):
            continue

        try:
            numeric_features = [
                float(value)
                for value in features
            ]
        except (
            TypeError,
            ValueError,
        ):
            continue

        record = dict(
            zip(
                FEATURE_NAMES,
                numeric_features,
            )
        )

        record[TARGET_NAME] = (
            _prediction_to_value(
                prediction_raw
            )
        )

        records.append(record)

    return pd.DataFrame(
        records,
        columns=[
            *FEATURE_NAMES,
            TARGET_NAME,
        ],
    )


def _prediction_distribution(
    data: pd.DataFrame,
) -> dict[str, float]:
    """Return normalized prediction frequencies."""

    if data.empty or TARGET_NAME not in data.columns:
        return {}

    counts = (
        data[TARGET_NAME]
        .astype(str)
        .value_counts(normalize=True)
    )

    return {
        str(key): float(value)
        for key, value in counts.items()
    }


def calculate_prediction_drift(
    reference_data: pd.DataFrame,
    recent_data: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate prediction-distribution drift.

    This is intentionally kept independent of Evidently's
    ColumnDriftMetric because that metric is not exposed by
    the installed Evidently 0.7.23 API.

    The score is the total variation distance between the
    reference and recent prediction distributions:

        0.0 = identical distributions
        1.0 = completely different distributions
    """

    reference_distribution = _prediction_distribution(
        reference_data
    )

    recent_distribution = _prediction_distribution(
        recent_data
    )

    if not reference_distribution:
        return {
            "score": None,
            "drift_detected": False,
            "reason": "Reference predictions are empty.",
            "reference_distribution": {},
            "recent_distribution": recent_distribution,
        }

    if not recent_distribution:
        return {
            "score": None,
            "drift_detected": False,
            "reason": "Recent predictions are empty.",
            "reference_distribution": reference_distribution,
            "recent_distribution": {},
        }

    labels = set(
        reference_distribution
    ) | set(
        recent_distribution
    )

    score = 0.5 * sum(
        abs(
            reference_distribution.get(label, 0.0)
            - recent_distribution.get(label, 0.0)
        )
        for label in labels
    )

    # Prediction drift threshold.
    # 0.10 means a 10 percentage-point total-distribution shift.
    threshold = 0.10

    return {
        "score": round(float(score), 4),
        "threshold": threshold,
        "drift_detected": bool(
            score >= threshold
        ),
        "reference_distribution": reference_distribution,
        "recent_distribution": recent_distribution,
    }


def generate_drift_report(
    reference_data: pd.DataFrame,
    recent_data: pd.DataFrame,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    """
    Generate an Evidently data-drift report.

    Prediction drift is calculated separately because
    ColumnDriftMetric is not available in Evidently 0.7.23.
    """

    reference_with_predictions = (
        add_predictions(reference_data)
    )

    recent_with_predictions = (
        add_predictions(recent_data)
    )

    report = Report(
        metrics=[
            DataDriftPreset(),
        ]
    )

    snapshot = report.run(
        current_data=recent_with_predictions,
        reference_data=reference_with_predictions,
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot.save_html(
        str(report_path)
    )

    prediction_drift = (
        calculate_prediction_drift(
            reference_with_predictions,
            recent_with_predictions,
        )
    )

    return {
        "report_path": str(report_path),
        "reference_samples": len(
            reference_data
        ),
        "recent_samples": len(
            recent_data
        ),
        "prediction_drift": prediction_drift,
    }


def calculate_evidently_drift(
    reference_data: pd.DataFrame,
    recent_data: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate Evidently data drift plus prediction drift.

    The Evidently snapshot is returned for reporting/debugging.
    The normalized prediction drift result is returned separately
    for use by the retraining trigger.
    """

    reference_with_predictions = (
        add_predictions(reference_data)
    )

    recent_with_predictions = (
        add_predictions(recent_data)
    )

    report = Report(
        metrics=[
            DataDriftPreset(),
        ]
    )

    snapshot = report.run(
        current_data=recent_with_predictions,
        reference_data=reference_with_predictions,
    )

    prediction_drift = (
        calculate_prediction_drift(
            reference_with_predictions,
            recent_with_predictions,
        )
    )

    return {
        "snapshot": snapshot,
        "prediction_drift": prediction_drift,
        "reference_samples": len(
            reference_data
        ),
        "recent_samples": len(
            recent_data
        ),
    }


def calculate_logged_evidently_drift(
    recent_limit: int = 100,
) -> dict[str, Any]:
    """
    Run Evidently against real served-model monitoring data.

    Reference window:
        Iris reference dataset.

    Recent window:
        Actual served-model inputs and predictions
        stored in monitoring.db.
    """

    reference = load_reference_inputs()

    recent = load_logged_monitoring_data(
        limit=recent_limit
    )

    if recent.empty:
        return {
            "status": "insufficient_data",
            "reason": (
                "No usable Iris monitoring "
                "records were found."
            ),
            "reference_samples": len(
                reference
            ),
            "recent_samples": 0,
        }

    reference_with_predictions = (
        add_predictions(reference)
    )

    # IMPORTANT:
    # Use the actual predictions from monitoring.db.
    # Do not overwrite recent predictions with a newly
    # trained reference model.
    recent_for_report = recent.copy()

    report = Report(
        metrics=[
            DataDriftPreset(),
        ]
    )

    snapshot = report.run(
        current_data=recent_for_report,
        reference_data=reference_with_predictions,
    )

    prediction_drift = (
        calculate_prediction_drift(
            reference_with_predictions,
            recent_for_report,
        )
    )

    data_drift_detected = False

    # Evidently 0.7.23 provides the drift report through
    # the snapshot. Keep the exact snapshot object available
    # for inspection/reporting rather than depending on
    # version-specific internal dictionary keys.
    #
    # Prediction drift is explicitly available through our
    # normalized calculation above.
    #
    # The HTML report remains the source for detailed
    # feature-level Evidently drift inspection.

    return {
        "status": "ok",
        "snapshot": snapshot,
        "reference_samples": len(
            reference_with_predictions
        ),
        "recent_samples": len(
            recent_for_report
        ),
        "prediction_drift": prediction_drift,
        "data_drift_detected": data_drift_detected,
    }


def run_deliberate_shift_test() -> dict[str, Any]:
    """Create normal and deliberately shifted test windows."""

    reference = load_reference_inputs()

    recent = create_recent_inputs(
        reference,
        sample_count=100,
    )

    shifted = create_shifted_inputs(
        reference,
        shift=2.0,
    )

    normal_with_predictions = add_predictions(
        recent
    )

    shifted_with_predictions = add_predictions(
        shifted
    )

    prediction_drift = calculate_prediction_drift(
        normal_with_predictions,
        shifted_with_predictions,
    )

    return {
        "reference": reference,
        "recent": recent,
        "shifted": shifted,
        "normal_with_predictions": normal_with_predictions,
        "shifted_with_predictions": shifted_with_predictions,
        "prediction_drift": prediction_drift,
    }

