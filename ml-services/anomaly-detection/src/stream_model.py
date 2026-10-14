"""
Streaming model for the 4 warehouse features.

Separate from the production 3-feature models. Reuses the existing
IsolationForestModel wrapper (train/score only).

Score convention: anomaly_score = -model.score(X), higher = more anomalous.
SHAP explains the NEGATED score, so a positive SHAP value pushes toward
"anomaly". Contributions are abs-normalized (same format as predict.py);
direction says whether the feature is above or below its training mean.
"""

from pathlib import Path

import joblib
import numpy as np
import shap

from .isolation_forest_model import IsolationForestModel
from .stream_simulator import (
    CALIBRATION_SEED,
    FEATURES,
    TRAIN_SEED,
    generate_normal_frame,
    reading_to_array,
)


MODEL_VERSION = "stream-1.0"

project_root = Path(__file__).resolve().parent.parent
models_dir = project_root / "models"
MODEL_PATH = models_dir / "stream_model.joblib"


class StreamModel:

    def __init__(
        self,
        model,
        calibration_scores,
        background,
        version=MODEL_VERSION,
    ):
        self.model = model
        self.calibration_scores = np.asarray(calibration_scores, dtype=float)
        self.background = np.asarray(background, dtype=float)
        self.feature_means = self.background.mean(axis=0)
        self.version = version
        self._explainer = None

    def __getstate__(self):

        state = self.__dict__.copy()
        state["_explainer"] = None

        return state

    def score_batch(self, X):
        """Project anomaly score: higher = more anomalous."""

        return -np.asarray(self.model.score(np.asarray(X)), dtype=float)

    def score_one(self, reading):

        return float(self.score_batch(reading_to_array(reading))[0])

    def _get_explainer(self):

        if self._explainer is None:
            self._explainer = shap.Explainer(
                self.score_batch,
                shap.maskers.Independent(self.background, max_samples=len(self.background)),
                feature_names=FEATURES,
            )

        return self._explainer

    def explain(self, reading, top_k=3):

        X = reading_to_array(reading)

        values = self._get_explainer()(X, silent=True)

        contributions = np.abs(np.asarray(values.values[0], dtype=float))
        total = contributions.sum()

        if total > 0:
            contributions = contributions / total

        order = np.argsort(-contributions, kind="stable")[:top_k]

        return [
            {
                "feature": FEATURES[i],
                "contribution": round(float(contributions[i]), 4),
                "direction": (
                    "high" if X[0, i] >= self.feature_means[i] else "low"
                ),
            }
            for i in order
        ]


def train_stream_model(train_n=5000, calibration_n=2000, background_n=200):

    train = generate_normal_frame(train_n, TRAIN_SEED)
    calibration = generate_normal_frame(calibration_n, CALIBRATION_SEED)

    model = IsolationForestModel(n_estimators=200)
    model.train(train)

    calibration_scores = -np.asarray(model.score(calibration), dtype=float)

    background = train.sample(
        n=background_n, random_state=TRAIN_SEED
    ).to_numpy()

    return StreamModel(model, calibration_scores, background)


def save_stream_model(stream_model, path=MODEL_PATH):

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(stream_model, path)

    return path


def load_stream_model(path=MODEL_PATH):

    return joblib.load(Path(path))


def load_or_train(path=MODEL_PATH):

    if Path(path).is_file():
        return load_stream_model(path)

    stream_model = train_stream_model()
    save_stream_model(stream_model, path)

    return stream_model