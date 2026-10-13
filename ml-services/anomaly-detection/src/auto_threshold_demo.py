"""
Milestone 2 demo: fixed vs auto-tuned threshold on the project's data.

Run from ml-services/anomaly-detection:

    python -m src.auto_threshold_demo

Writes output/auto_threshold_demo.csv
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Imported so joblib can unpickle the model wrappers.
from src.isolation_forest_model import IsolationForestModel  # noqa: F401
from src.lof_model import LOFModel  # noqa: F401
from src.one_class_svm_model import OneClassSVMModel  # noqa: F401

from src.auto_threshold import DEFAULT_PERCENTILES, SignificanceThresholdTuner
from src.data import generate_seasonal_normal_data, inject_temperature_spikes

models_dir = project_root / "models"
output_dir = project_root / "output"

FEATURES = ["temperature", "humidity", "stock_count"]
MODEL_FILES = {
    "iforest": "isolation_forest_model.joblib",
    "lof": "lof_model.joblib",
    "ocsvm": "one_class_svm_model.joblib",
}
WINDOW = 200


def score(model, df):
    """Project convention: higher = more anomalous."""
    return -np.asarray(model.score(df[FEATURES].to_numpy()), dtype=float)


def run_windows(tuner, scores):
    actions = []

    for start in range(0, len(scores) - WINDOW + 1, WINDOW):
        actions.append(tuner.evaluate_window(scores[start:start + WINDOW])["action"])

    return actions


def main():
    calibration = pd.read_csv(output_dir / "calibration_normal.csv")
    seasonal_fit = pd.read_csv(output_dir / "test_seasonal_normal.csv")
    drift = pd.read_csv(output_dir / "test_temperature_drift.csv")

    # Fresh data the tuner never saw.
    seasonal_eval = generate_seasonal_normal_data(n=5000, seed=790)
    seasonal_spikes = inject_temperature_spikes(
        seasonal_eval, n_anomalies=20, seed=2024
    )

    rows = []

    for name, filename in MODEL_FILES.items():
        model = joblib.load(models_dir / filename)

        reference = score(model, calibration)
        percentile = DEFAULT_PERCENTILES[name]

        # Scenario 1: legitimate seasonal regime.
        tuner = SignificanceThresholdTuner(reference, percentile=percentile)
        fixed = tuner.initial_threshold

        run_windows(tuner, score(model, seasonal_fit))
        tuned = tuner.threshold

        normal_scores = score(model, seasonal_eval)
        spike_scores = score(model, seasonal_spikes)
        y = seasonal_spikes["is_anomaly"].to_numpy()

        rows.append({
            "model": name,
            "scenario": "seasonal_regime",
            "fixed_threshold": fixed,
            "tuned_threshold": tuned,
            "adaptations": tuner.adaptations,
            "refinements": tuner.refinements,
            "freezes": tuner.freezes,
            "fixed_false_alarm_rate": float(np.mean(normal_scores >= fixed)),
            "tuned_false_alarm_rate": float(np.mean(normal_scores >= tuned)),
            "fixed_spike_recall": float(np.mean(spike_scores[y == 1] >= fixed)),
            "tuned_spike_recall": float(np.mean(spike_scores[y == 1] >= tuned)),
        })

        # Scenario 2: temperature drift must not be learned.
        drift_tuner = SignificanceThresholdTuner(reference, percentile=percentile)
        run_windows(drift_tuner, score(model, drift))

        rows.append({
            "model": name,
            "scenario": "temperature_drift",
            "fixed_threshold": drift_tuner.initial_threshold,
            "tuned_threshold": drift_tuner.threshold,
            "adaptations": drift_tuner.adaptations,
            "refinements": drift_tuner.refinements,
            "freezes": drift_tuner.freezes,
        })

    result = pd.DataFrame(rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_dir / "auto_threshold_demo.csv", index=False)

    print(result.to_string(index=False))
    print("\nSaved: output/auto_threshold_demo.csv")


if __name__ == "__main__":
    main()