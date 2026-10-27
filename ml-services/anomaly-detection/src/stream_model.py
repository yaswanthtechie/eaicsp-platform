"""
Streaming model for the 4 warehouse features.

Separate from the production 3-feature models. Reuses the existing
IsolationForestModel wrapper (train/score only).

Score convention: anomaly_score = -model.score(X), higher = more anomalous.
SHAP explains the NEGATED score, so a positive SHAP value pushes toward
"anomaly". Only features that push toward anomaly are listed.

Production loads a saved model and never trains. Train with:
    python -m src.train_stream_model
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
                shap.maskers.Independent(
                    self.background, max_samples=len(self.background)
                ),
                feature_names=FEATURES,
            )

        return self._explainer

    def explain(self, reading, top_k=3):
        """
        Top features pushing this reading toward "anomaly".

        shap_value > 0 means the feature raises the anomaly score.
        contribution = that feature's share of all positive pushes (0..1).
        Features that push toward "normal" are never listed.
        """

        X = reading_to_array(reading)
        values = np.asarray(
            self._get_explainer()(X, silent=True).values[0], dtype=float
        )

        positive = np.clip(values, 0.0, None)
        total = positive.sum()

        if total <= 0:
            # Nothing pushes toward anomaly. Report the least-normal
            # feature with a 0 share.
            i = int(np.argmax(values))
            order, shares = [i], np.zeros_like(values)
        else:
            shares = positive / total
            order = [
                int(i)
                for i in np.argsort(-positive, kind="stable")
                if positive[i] > 0
            ][:top_k]

        return [
            {
                "feature": FEATURES[i],
                "contribution": round(float(shares[i]), 4),
                "shap_value": round(float(values[i]), 6),
                "direction": (
                    "high" if X[0, i] > self.feature_means[i] else "low"
                ),
            }
            for i in order
        ]

    def warm_up(self):
        """Build the SHAP explainer now so the first event is not slow."""

        self.explain(dict(zip(FEATURES, self.feature_means.tolist())))


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

    joblib.dump(
        {
            "model": stream_model,
            "version": stream_model.version,
            "features": list(FEATURES),
        },
        path,
    )

    return path


def load_stream_model(path=MODEL_PATH, expected_version=MODEL_VERSION):

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Train it first: python -m src.train_stream_model"
        )

    bundle = joblib.load(path)

    if not isinstance(bundle, dict) or "model" not in bundle:
        raise ValueError(f"{path} is an old-format model file. Retrain it.")

    if bundle.get("features") != list(FEATURES):
        raise ValueError(
            f"Model features {bundle.get('features')} != {FEATURES}. Retrain it."
        )

    if bundle.get("version") != expected_version:
        raise ValueError(
            f"Model version {bundle.get('version')} != "
            f"{expected_version}. Retrain it."
        )

    return bundle["model"]