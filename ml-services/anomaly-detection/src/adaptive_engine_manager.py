from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd

from .adaptive_engine import AdaptiveEngine
from .model_loader import get_models


FEATURE_NAMES = [
    "temperature",
    "humidity",
    "stock_count",
]


# ============================================================
# MODEL-SPECIFIC PRODUCTION CONFIGURATION
# ============================================================
#
# These values were selected from the completed regime
# calibration + adaptive percentile evaluation.
#
# IFOREST:
#   P98.0
#   sigma 1.50
#   tolerance 0.20
#
# LOF:
#   P97.0
#   sigma 2.50
#   tolerance 0.30
#
# OCSVM:
#   P97.0
#   sigma 2.25
#   tolerance 0.20
#
# Do not use one global configuration for all models.
# Each model operates in its own score distribution.
# ============================================================

MODEL_CONFIG = {
    "iforest": {
        "shift_sigma": 1.50,
        "stability_tolerance": 0.20,
        "adaptive_percentile": 98.0,
    },
    "lof": {
        "shift_sigma": 2.50,
        "stability_tolerance": 0.30,
        "adaptive_percentile": 97.0,
    },
    "ocsvm": {
        "shift_sigma": 2.25,
        "stability_tolerance": 0.20,
        "adaptive_percentile": 97.0,
    },
}


BASELINE_SIZE = 100

CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

MIN_STABLE_BLOCKS = 2

ADAPTIVE_WINDOW_SIZE = 50

QUARANTINE_RECOVERY_REQUIRED = 25


class AdaptiveEngineManager:
    """
    Owns one independent AdaptiveEngine per model.

    Each model receives its own calibrated regime and
    adaptive-threshold configuration.
    """

    def __init__(
        self,
        calibration_path=None,
    ):
        self.lock = Lock()

        if calibration_path is None:
            self.calibration_path = (
                Path(__file__).resolve().parent.parent
                / "output"
                / "calibration_normal.csv"
            )
        else:
            self.calibration_path = Path(
                calibration_path
            )

        self.engines = {}

        self.initialized = False

    # ========================================================
    # MODEL CONFIGURATION
    # ========================================================

    @staticmethod
    def _get_model_config(model_name):
        """
        Return the explicitly configured parameters for one
        model.

        Keeping this lookup centralized prevents accidental
        fallback to AdaptiveEngine's generic defaults.
        """

        model_name = str(
            model_name
        )

        if model_name not in MODEL_CONFIG:
            raise ValueError(
                f"No adaptive configuration exists "
                f"for model '{model_name}'. "
                f"Configured models: "
                f"{sorted(MODEL_CONFIG)}"
            )

        return dict(
            MODEL_CONFIG[
                model_name
            ]
        )

    # ========================================================
    # CALIBRATION SCORES
    # ========================================================

    def _load_calibration_scores(self):
        """
        Calculate calibration anomaly scores for every model.

        Project convention:

            anomaly_score = -model.score(...)

        Higher score means more anomalous.
        """

        if not self.calibration_path.exists():
            raise FileNotFoundError(
                "calibration_normal.csv not found: "
                f"{self.calibration_path}"
            )

        calibration_df = pd.read_csv(
            self.calibration_path
        )

        missing_columns = [
            column
            for column in FEATURE_NAMES
            if column not in calibration_df.columns
        ]

        if missing_columns:
            raise ValueError(
                "Calibration dataset is missing "
                f"required feature columns: "
                f"{missing_columns}"
            )

        if calibration_df.empty:
            raise ValueError(
                "calibration_normal.csv contains "
                "no calibration samples."
            )

        X_calibration = calibration_df[
            FEATURE_NAMES
        ].to_numpy(
            dtype=float
        )

        models = get_models()

        calibration_scores = {}

        for model_name, model in models.items():

            raw_scores = model.score(
                X_calibration
            )

            scores = -np.asarray(
                raw_scores,
                dtype=float,
            )

            scores = scores[
                np.isfinite(scores)
            ]

            if scores.size == 0:
                raise ValueError(
                    "No valid calibration scores "
                    f"were produced for model "
                    f"'{model_name}'."
                )

            calibration_scores[
                model_name
            ] = scores

        return calibration_scores

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def initialize(self):
        """
        Initialize all model-specific AdaptiveEngines once.

        IMPORTANT:

        Each model gets its own:
            - shift sigma
            - stability tolerance
            - adaptive percentile

        The AdaptiveEngine defaults are deliberately NOT used
        for these production parameters.
        """

        with self.lock:

            if self.initialized:
                return

            calibration_scores = (
                self._load_calibration_scores()
            )

            for model_name, scores in (
                calibration_scores.items()
            ):

                config = (
                    self._get_model_config(
                        model_name
                    )
                )

                engine = AdaptiveEngine(
                    baseline_size=BASELINE_SIZE,
                    candidate_sizes=CANDIDATE_SIZES,
                    shift_sigma=config[
                        "shift_sigma"
                    ],
                    stability_tolerance=config[
                        "stability_tolerance"
                    ],
                    min_stable_blocks=MIN_STABLE_BLOCKS,
                    adaptive_window_size=(
                        ADAPTIVE_WINDOW_SIZE
                    ),
                    adaptive_percentile=config[
                        "adaptive_percentile"
                    ],
                    quarantine_recovery_required=(
                        QUARANTINE_RECOVERY_REQUIRED
                    ),
                )

                engine.initialize(
                    scores,
                    model_name=model_name,
                )

                self.engines[
                    model_name
                ] = engine

            self.initialized = True

    # ========================================================
    # GET ENGINE
    # ========================================================

    def get_engine(
        self,
        model_name,
    ):
        """
        Return the AdaptiveEngine for the requested model.
        """

        model_name = str(
            model_name
        )

        self.initialize()

        if model_name not in self.engines:
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Available models: "
                f"{sorted(self.engines)}"
            )

        return self.engines[
            model_name
        ]

    # ========================================================
    # PROCESS
    # ========================================================

    def process(
        self,
        model_name,
        score,
        temperature,
    ):
        """
        Process one reading through the model-specific
        adaptive state machine.
        """

        model_name = str(
            model_name
        )

        engine = self.get_engine(
            model_name
        )

        return engine.process(
            score=float(score),
            temperature=float(
                temperature
            ),
        )

    # ========================================================
    # STATE
    # ========================================================

    def get_state(
        self,
        model_name,
    ):
        """
        Return the state of one model engine.
        """

        engine = self.get_engine(
            model_name
        )

        return engine.get_state()

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def get_config(
        self,
        model_name,
    ):
        """
        Return the production configuration used by one model.

        Useful for tests and diagnostics.
        """

        return self._get_model_config(
            model_name
        )

    # ========================================================
    # ALL CONFIGURATIONS
    # ========================================================

    def get_all_configs(self):
        """
        Return a copy of all model-specific configurations.
        """

        return {
            model_name: dict(
                config
            )
            for model_name, config
            in MODEL_CONFIG.items()
        }

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):
        """
        Reset all engines.

        Useful for tests and controlled restarts.
        """

        with self.lock:

            for engine in self.engines.values():

                engine.reset()

            self.engines.clear()

            self.initialized = False


# ============================================================
# GLOBAL MANAGER
# ============================================================

adaptive_engine_manager = (
    AdaptiveEngineManager()
)