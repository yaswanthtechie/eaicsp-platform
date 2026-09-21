from collections import deque
import threading

import numpy as np


class AdaptiveThreshold:
    """
    Maintains a rolling baseline of trusted normal anomaly
    scores and calculates an adaptive threshold.

    Assumption:
        Higher score = more anomalous.
    """

    def __init__(
        self,
        window_size=50,
        percentile=99.0,
    ):
        self.window_size = window_size
        self.percentile = percentile

        self.scores = deque(
            maxlen=window_size
        )

        self.initial_threshold = None

        self.adaptive_started = False

        self.lock = threading.Lock()

    def initialize(self, scores):
        """
        Initialize the baseline with trusted normal scores.

        The initial threshold is calculated from all
        supplied calibration scores.

        Only the most recent window_size scores are
        retained for future adaptive updates.
        """

        with self.lock:

            self.scores.clear()

            self.initial_threshold = None

            self.adaptive_started = False

            scores = np.asarray(
                scores,
                dtype=float,
            )

            if scores.size == 0:

                return

            self.initial_threshold = float(
                np.percentile(
                    scores,
                    self.percentile,
                )
            )

            for score in scores[-self.window_size:]:

                self.scores.append(
                    float(score)
                )

    def update(self, score):
        """
        Add one trusted normal score to the rolling baseline.

        Only trusted normal scores should be passed
        to this method.
        """

        with self.lock:

            self.scores.append(
                float(score)
            )

            self.adaptive_started = True

    def get_threshold(self):
        """
        Calculate the current adaptive threshold.

        Before adaptive updates begin, return the
        initial calibration threshold.

        After adaptive updates begin, calculate the
        threshold from the rolling baseline.

        Returns None if there are no baseline scores.
        """

        with self.lock:

            if not self.scores:

                return None

            if not self.adaptive_started:

                return self.initial_threshold

            return float(
                np.percentile(
                    np.asarray(
                        self.scores,
                        dtype=float,
                    ),
                    self.percentile,
                )
            )

    def is_anomaly(self, score):
        """
        Compare a score against the current adaptive threshold.

        Higher score = more anomalous.

        Returns:
            (is_anomaly, threshold)
        """

        threshold = self.get_threshold()

        if threshold is None:
            return False, None

        score = float(score)

        return (
            score > threshold,
            threshold,
        )

    def get_state(self):
        """
        Return the current baseline state.
        """

        with self.lock:

            threshold = None

            if self.scores:

                if not self.adaptive_started:

                    threshold = self.initial_threshold

                else:

                    threshold = float(
                        np.percentile(
                            np.asarray(
                                self.scores,
                                dtype=float,
                            ),
                            self.percentile,
                        )
                    )

            return {
                "sample_count": len(
                    self.scores
                ),
                "window_size": self.window_size,
                "percentile": self.percentile,
                "threshold": threshold,
                "initial_threshold": self.initial_threshold,
                "adaptive_started": self.adaptive_started,
            }

    def reset(self):
        """
        Clear the rolling baseline.
        """

        with self.lock:

            self.scores.clear()

            self.initial_threshold = None

            self.adaptive_started = False


# ------------------------------------------------------------
# Model-specific threshold managers
# ------------------------------------------------------------

adaptive_thresholds = {
    "iforest": AdaptiveThreshold(
        window_size=50,
        percentile=99.0,
    ),
    "lof": AdaptiveThreshold(
        window_size=50,
        percentile=99.0,
    ),
    "ocsvm": AdaptiveThreshold(
        window_size=50,
        percentile=99.0,
    ),
}


def get_adaptive_threshold(model_name):
    """
    Return the threshold manager for a specific model.
    """

    if model_name not in adaptive_thresholds:

        raise ValueError(
            f"Unknown model: {model_name}"
        )

    return adaptive_thresholds[model_name]


def reset_adaptive_thresholds():
    """
    Reset all model-specific adaptive thresholds.
    """

    for manager in adaptive_thresholds.values():
        manager.reset()