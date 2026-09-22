"""
M4 - build the labeled library of past incident types.

TRAINING SIDE. predict.py must NOT import this module; it loads the
saved artifact through model_loader.get_incident_library().

The library is built from a separate "history" dataset (its own
seeds), never from the test datasets, so matching accuracy measured
on the test datasets is honest.
"""

from pathlib import Path

import joblib
import numpy as np

from src.data import (
    generate_normal_data,
    inject_combined_anomalies,
    inject_stock_anomalies,
    inject_temperature_spikes,
)
from src.root_cause import FEATURES, reading_signature


project_root = Path(__file__).resolve().parent.parent
models_dir = project_root / "models"

INCIDENT_LIBRARY_FILE = "incident_library.joblib"

HISTORY_SEED = 2000
HISTORY_INCIDENTS_PER_TYPE = 50

INCIDENT_DESCRIPTIONS = {
    "temperature_spike": (
        "Resembles past temperature spikes - check HVAC / cooling "
        "failure or a door left open."
    ),
    "stock_anomaly": (
        "Resembles past stock-count anomalies - check for an unlogged "
        "bulk receipt or a scanner double-count."
    ),
    "combined_anomaly": (
        "Resembles past combined heat + moisture events - check for a "
        "leak or ventilation failure."
    ),
    "relationship_break": (
        "Values are individually normal but humidity is moving the wrong "
        "way for the temperature - check for a faulty humidity sensor or "
        "a moisture source."
    ),
}


def fit_normal_stats(train_df):
    """Normal-behaviour statistics, fit on TRAINING data only."""

    slope, intercept = np.polyfit(
        train_df["temperature"],
        train_df["humidity"],
        deg=1,
    )

    residual = train_df["humidity"] - (intercept + slope * train_df["temperature"])

    return {
        "mean": train_df[FEATURES].mean().to_dict(),
        "std": train_df[FEATURES].std().to_dict(),
        "humidity_slope": float(slope),
        "humidity_intercept": float(intercept),
        "residual_std": float(residual.std()),
    }


def default_history():
    """
    Labeled historical incidents for the incident types the
    production models currently see.

    relationship_break is left out on purpose: the production models
    are still trained on generate_normal_data(), where temperature and
    humidity are independent. Add it once production moves to
    generate_correlated_normal_data() (see README - M3 next steps).
    """

    base = generate_normal_data(n=5000, seed=HISTORY_SEED)
    n = HISTORY_INCIDENTS_PER_TYPE

    return {
        "temperature_spike": inject_temperature_spikes(base, n, seed=HISTORY_SEED + 1),
        "stock_anomaly": inject_stock_anomalies(base, n, seed=HISTORY_SEED + 2),
        "combined_anomaly": inject_combined_anomalies(base, n, seed=HISTORY_SEED + 3),
    }


def build_incident_library(train_df, labeled_history):
    """
    labeled_history: {incident_type: dataframe with is_anomaly column}
    """

    stats = fit_normal_stats(train_df)

    signatures = []
    labels = []

    for incident_type, df in labeled_history.items():
        incidents = df[df["is_anomaly"] == 1]

        for reading in incidents[FEATURES].to_dict("records"):
            signatures.append(reading_signature(reading, stats))
            labels.append(incident_type)

    return {
        "stats": stats,
        "signatures": np.vstack(signatures),
        "labels": labels,
        "descriptions": {
            t: INCIDENT_DESCRIPTIONS[t] for t in labeled_history
        },
    }


def save_incident_library(library):
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(library, models_dir / INCIDENT_LIBRARY_FILE)