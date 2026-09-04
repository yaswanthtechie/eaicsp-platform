from enum import Enum

import numpy as np

from .adaptive_threshold import AdaptiveThreshold
from .regime_detector import RegimeDetector
from .temporal_detector import TemporalDetector


class EngineState(str, Enum):
    STABLE = "stable"
    REGIME_CONFIRMATION = "regime_confirmation"
    DRIFT = "drift"
    DRIFT_LOCKED = "drift_locked"


class AdaptiveEngine:
    """
    Coordinates:

        - score-regime detection
        - temporal validation
        - adaptive thresholding

    Lifecycle:

        STABLE
            |
            | score distribution changes
            v
        REGIME_CONFIRMATION
            |
            | stable + temporally normal
            v
        ACCEPT NEW REGIME
            |
            v
        STABLE

    Genuine sustained temporal drift:

        REGIME_CONFIRMATION
            |
            | TemporalDetector confirms drift
            v
        DRIFT_LOCKED
            |
            | recovery
            v
        STABLE

    TemporalDetector owns temporal persistence.
    AdaptiveEngine does not maintain another independent
    consecutive-window drift counter.
    """

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

    def __init__(
        self,
        baseline_size=100,
        candidate_sizes=None,
        shift_sigma=2.0,
        stability_tolerance=0.2,
        min_stable_blocks=2,
        temporal_detector=None,
        adaptive_threshold=None,
        adaptive_window_size=50,
        adaptive_percentile=99.0,
        quarantine_recovery_required=25,
    ):
        if baseline_size < 1:
            raise ValueError(
                "baseline_size must be positive."
            )

        if candidate_sizes is None:
            candidate_sizes = [
                10,
                25,
                50,
                100,
                200,
            ]

        candidate_sizes = sorted(
            set(
                int(value)
                for value in candidate_sizes
                if int(value) > 0
            )
        )

        if not candidate_sizes:
            raise ValueError(
                "candidate_sizes must not be empty."
            )

        if shift_sigma <= 0:
            raise ValueError(
                "shift_sigma must be positive."
            )

        if stability_tolerance < 0:
            raise ValueError(
                "stability_tolerance cannot be negative."
            )

        if min_stable_blocks < 1:
            raise ValueError(
                "min_stable_blocks must be at least 1."
            )

        if adaptive_window_size < 1:
            raise ValueError(
                "adaptive_window_size must be positive."
            )

        if not 0 < adaptive_percentile < 100:
            raise ValueError(
                "adaptive_percentile must be between 0 and 100."
            )

        if quarantine_recovery_required < 1:
            raise ValueError(
                "quarantine_recovery_required must be positive."
            )

        self.baseline_size = int(baseline_size)
        self.candidate_sizes = candidate_sizes
        self.shift_sigma = float(shift_sigma)
        self.stability_tolerance = float(
            stability_tolerance
        )
        self.min_stable_blocks = int(
            min_stable_blocks
        )

        self.adaptive_window_size = int(
            adaptive_window_size
        )
        self.adaptive_percentile = float(
            adaptive_percentile
        )

        self.regime_detector = RegimeDetector(
            baseline_size=self.baseline_size,
            candidate_sizes=self.candidate_sizes,
            shift_sigma=self.shift_sigma,
            stability_tolerance=self.stability_tolerance,
            min_stable_blocks=self.min_stable_blocks,
        )

        self.temporal_detector = (
            temporal_detector
            if temporal_detector is not None
            else TemporalDetector()
        )

        self.adaptive_threshold = (
            adaptive_threshold
            if adaptive_threshold is not None
            else AdaptiveThreshold(
                window_size=self.adaptive_window_size,
                percentile=self.adaptive_percentile,
            )
        )

        self.state = EngineState.STABLE

        self.initialized = False
        self.model_name = None

        self.total_samples = 0
        self.adaptation_updates = 0
        self.alert_count = 0

        self.regime_transition_count = 0
        self.regime_confirmation_count = 0

        self._transition_active = False

        self._pending_regime_scores = None
        self._pending_threshold = None
        self._pending_regime_confirmed = False

        self._regime_confirmation_emitted = False

        self._temporal_validation_started = False
        self._temporal_clean_checks = 0

        self._temporal_validation_required = max(
            1,
            int(
                getattr(
                    self.temporal_detector,
                    "required_consecutive_windows",
                    3,
                )
            ),
        )

        self._regime_validation_required = max(
            self.candidate_sizes
        )

        self._regime_validation_samples = 0

        self._post_drift_quarantine = False
        self._quarantine_recovery_count = 0

        self._quarantine_recovery_required = int(
            quarantine_recovery_required
        )

        self._drift_detected = False

        self.last_result = self._empty_result()

    # ============================================================
    # MODEL CONFIGURATION
    # ============================================================

    def _apply_model_configuration(
        self,
        model_name,
    ):
        if model_name is None:
            return

        model_name = str(
            model_name
        ).lower()

        config = self.MODEL_CONFIG.get(
            model_name
        )

        if config is None:
            return

        self.shift_sigma = float(
            config["shift_sigma"]
        )

        self.stability_tolerance = float(
            config["stability_tolerance"]
        )

        self.adaptive_percentile = float(
            config["adaptive_percentile"]
        )

        self.regime_detector = RegimeDetector(
            baseline_size=self.baseline_size,
            candidate_sizes=self.candidate_sizes,
            shift_sigma=self.shift_sigma,
            stability_tolerance=self.stability_tolerance,
            min_stable_blocks=self.min_stable_blocks,
        )

        self.adaptive_threshold = AdaptiveThreshold(
            window_size=self.adaptive_window_size,
            percentile=self.adaptive_percentile,
        )

    # ============================================================
    # VALIDATION
    # ============================================================

    @staticmethod
    def _validate_score(score):
        score = float(score)

        if not np.isfinite(score):
            raise ValueError(
                "score must be finite."
            )

        return score

    @staticmethod
    def _validate_temperature(temperature):
        temperature = float(temperature)

        if not np.isfinite(temperature):
            raise ValueError(
                "temperature must be finite."
            )

        return temperature

    @staticmethod
    def _validate_scores(scores):
        values = np.asarray(
            scores,
            dtype=float,
        ).reshape(-1)

        if values.size == 0:
            return values

        if not np.all(
            np.isfinite(values)
        ):
            raise ValueError(
                "scores must contain only finite values."
            )

        return values

    # ============================================================
    # EMPTY RESULT
    # ============================================================

    def _empty_result(self):
        return {
            "state": self.state.value,
            "is_anomaly": False,
            "alert": False,
            "adapted": False,
            "regime_changed": False,
            "regime_confirmed": False,
            "regime_accepted": False,
            "candidate_started": False,
            "temporal_checked": False,
            "temporal_drift": False,
            "adaptation_frozen": False,
            "transition_active": False,
            "post_drift_quarantine": False,
            "quarantine_recovery_count": 0,
            "temporal_validation_started": False,
            "temporal_clean_checks": 0,
            "temporal_validation_required": (
                self._temporal_validation_required
            ),
            "regime_validation_samples": (
                self._regime_validation_samples
            ),
            "regime_validation_required": (
                self._regime_validation_required
            ),
            "pending_regime_confirmed": False,
            "temporal_validation_complete": False,
            "score": None,
            "threshold": None,
            "pending_threshold": None,
            "direction": None,
            "slope": 0.0,
            "total_change": 0.0,
            "r_squared": 0.0,
            "sample_count": self.total_samples,
        }

    # ============================================================
    # RESULT BUILDER
    # ============================================================

    def _build_result(
        self,
        score,
        is_anomaly=False,
        alert=False,
        adapted=False,
        regime_changed=False,
        regime_confirmed=False,
        regime_accepted=False,
        candidate_started=False,
        temporal_checked=False,
        temporal_drift=False,
        temporal_result=None,
    ):
        if temporal_result is None:
            temporal_result = {}

        threshold = (
            self.adaptive_threshold.get_threshold()
        )

        frozen = (
            self._transition_active
            or self._post_drift_quarantine
            or self.state
            in (
                EngineState.REGIME_CONFIRMATION,
                EngineState.DRIFT,
                EngineState.DRIFT_LOCKED,
            )
        )

        result = {
            "state": self.state.value,
            "is_anomaly": bool(
                is_anomaly
            ),
            "alert": bool(
                alert
            ),
            "adapted": bool(
                adapted
            ),
            "regime_changed": bool(
                regime_changed
            ),
            "regime_confirmed": bool(
                regime_confirmed
            ),
            "regime_accepted": bool(
                regime_accepted
            ),
            "candidate_started": bool(
                candidate_started
            ),
            "temporal_checked": bool(
                temporal_checked
            ),
            "temporal_drift": bool(
                temporal_drift
            ),
            "adaptation_frozen": bool(
                frozen
            ),
            "transition_active": bool(
                self._transition_active
            ),
            "post_drift_quarantine": bool(
                self._post_drift_quarantine
            ),
            "quarantine_recovery_count": int(
                self._quarantine_recovery_count
            ),
            "temporal_validation_started": bool(
                self._temporal_validation_started
            ),
            "temporal_clean_checks": int(
                self._temporal_clean_checks
            ),
            "temporal_validation_required": int(
                self._temporal_validation_required
            ),
            "regime_validation_samples": int(
                self._regime_validation_samples
            ),
            "regime_validation_required": int(
                self._regime_validation_required
            ),
            "pending_regime_confirmed": bool(
                self._pending_regime_confirmed
            ),
            "temporal_validation_complete": bool(
                temporal_result.get(
                    "validation_complete",
                    False,
                )
            ),
            "score": float(
                score
            ),
            "threshold": (
                None
                if threshold is None
                else float(threshold)
            ),
            "pending_threshold": (
                None
                if self._pending_threshold is None
                else float(
                    self._pending_threshold
                )
            ),
            "direction": temporal_result.get(
                "direction"
            ),
            "slope": float(
                temporal_result.get(
                    "slope",
                    0.0,
                )
            ),
            "total_change": float(
                temporal_result.get(
                    "total_change",
                    0.0,
                )
            ),
            "r_squared": float(
                temporal_result.get(
                    "r_squared",
                    0.0,
                )
            ),
            "sample_count": self.total_samples,
        }

        self.last_result = dict(
            result
        )

        return result

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def initialize(
        self,
        calibration_scores,
        model_name=None,
    ):
        scores = self._validate_scores(
            calibration_scores
        )

        if scores.size == 0:
            raise ValueError(
                "calibration_scores must not be empty."
            )

        self._apply_model_configuration(
            model_name
        )

        self.regime_detector.initialize(
            scores
        )

        self.adaptive_threshold.initialize(
            scores
        )

        self.temporal_detector.reset()

        self.state = EngineState.STABLE

        self.initialized = True
        self.model_name = model_name

        self.total_samples = 0
        self.adaptation_updates = 0
        self.alert_count = 0

        self.regime_transition_count = 0
        self.regime_confirmation_count = 0

        self._transition_active = False

        self._pending_regime_scores = None
        self._pending_threshold = None
        self._pending_regime_confirmed = False

        self._regime_confirmation_emitted = False

        self._temporal_validation_started = False
        self._temporal_clean_checks = 0

        self._regime_validation_samples = 0

        self._post_drift_quarantine = False
        self._quarantine_recovery_count = 0

        self._drift_detected = False

        threshold = (
            self.adaptive_threshold.get_threshold()
        )

        self.last_result = {
            "state": self.state.value,
            "is_anomaly": False,
            "alert": False,
            "adapted": False,
            "regime_changed": False,
            "regime_confirmed": False,
            "regime_accepted": False,
            "candidate_started": False,
            "temporal_checked": False,
            "temporal_drift": False,
            "adaptation_frozen": False,
            "transition_active": False,
            "post_drift_quarantine": False,
            "quarantine_recovery_count": 0,
            "temporal_validation_started": False,
            "temporal_clean_checks": 0,
            "temporal_validation_required": (
                self._temporal_validation_required
            ),
            "regime_validation_samples": 0,
            "regime_validation_required": (
                self._regime_validation_required
            ),
            "pending_regime_confirmed": False,
            "temporal_validation_complete": False,
            "score": None,
            "threshold": (
                None
                if threshold is None
                else float(threshold)
            ),
            "pending_threshold": None,
            "direction": None,
            "slope": 0.0,
            "total_change": 0.0,
            "r_squared": 0.0,
            "sample_count": 0,
        }

        return self.get_state()

    # ============================================================
    # INTERNAL STATE
    # ============================================================

    def _clear_transition(self):
        self._transition_active = False

        self._pending_regime_scores = None
        self._pending_threshold = None
        self._pending_regime_confirmed = False

        self._temporal_validation_started = False
        self._temporal_clean_checks = 0

        self._regime_validation_samples = 0

    def _clear_quarantine(self):
        self._post_drift_quarantine = False
        self._quarantine_recovery_count = 0

    # ============================================================
    # REGIME STABILITY
    # ============================================================

    def _has_regime_stability(
        self,
        regime_result=None,
    ):
        if regime_result is None:
            regime_result = {}

        try:
            state = (
                self.regime_detector.get_state()
            )
        except Exception:
            state = {}

        if not isinstance(
            state,
            dict,
        ):
            state = {}

        if not isinstance(
            regime_result,
            dict,
        ):
            regime_result = {}

        explicit_keys = (
            "stable",
            "is_stable",
            "regime_stable",
            "candidate_stable",
            "stable_regime",
        )

        for key in explicit_keys:

            value = regime_result.get(
                key
            )

            if isinstance(
                value,
                (bool, np.bool_),
            ) and bool(value):
                return True

            value = state.get(
                key
            )

            if isinstance(
                value,
                (bool, np.bool_),
            ) and bool(value):
                return True

        for source in (
            regime_result,
            state,
        ):

            for key in (
                "stable_blocks",
                "consecutive_stable_blocks",
                "regime_stable_blocks",
            ):

                if key not in source:
                    continue

                try:
                    blocks = int(
                        source[key]
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if (
                    blocks
                    >= self.min_stable_blocks
                ):
                    return True

        if self.regime_detector.is_confirmed():
            return True

        minimum_candidate = min(
            self.candidate_sizes
        )

        required = max(
            minimum_candidate,
            self.min_stable_blocks
            * minimum_candidate,
        )

        return (
            self._regime_validation_samples
            >= required
        )

    # ============================================================
    # TEMPORAL
    # ============================================================

    def _check_temporal(
        self,
        temperature,
    ):
        return self.temporal_detector.update(
            temperature
        )

    # ============================================================
    # STAGE CONFIRMED REGIME
    # ============================================================

    def _stage_confirmed_regime(self):
        if self._pending_regime_confirmed:
            return False

        scores = self._validate_scores(
            self.regime_detector.get_confirmed_scores()
        )

        if scores.size == 0:
            return False

        self._pending_regime_scores = (
            scores.copy()
        )

        candidate_threshold = AdaptiveThreshold(
            window_size=(
                self.adaptive_threshold.window_size
            ),
            percentile=(
                self.adaptive_threshold.percentile
            ),
        )

        candidate_threshold.initialize(
            scores
        )

        self._pending_threshold = (
            candidate_threshold.get_threshold()
        )

        self._pending_regime_confirmed = True

        return True

    # ============================================================
    # CONFIRMATION EVENT
    # ============================================================

    def _emit_confirmation_event(self):
        if self._regime_confirmation_emitted:
            return False

        self._regime_confirmation_emitted = True

        self.regime_confirmation_count += 1

        return True

    # ============================================================
    # COMMIT REGIME
    # ============================================================

    def _commit_pending_regime(self):
        if not self._pending_regime_confirmed:
            return False

        if self._pending_regime_scores is None:
            return False

        scores = self._validate_scores(
            self._pending_regime_scores
        )

        if scores.size == 0:
            return False

        self.regime_detector.accept_regime(
            scores
        )

        self.adaptive_threshold.initialize(
            scores
        )

        self.adaptation_updates += 1

        self._clear_transition()

        self._regime_confirmation_emitted = False

        self.temporal_detector.reset()

        self._drift_detected = False

        self.state = EngineState.STABLE

        return True

    # ============================================================
    # DRIFT LOCK
    # ============================================================

    def _enter_drift_locked(self):
        self.regime_detector.reject_candidate()

        self.temporal_detector.reset()

        self._clear_transition()

        self._regime_confirmation_emitted = False

        self._post_drift_quarantine = True
        self._quarantine_recovery_count = 0

        self._drift_detected = True

        self.state = EngineState.DRIFT_LOCKED

    # ============================================================
    # QUARANTINE
    # ============================================================

    def _process_quarantine(
        self,
        score,
        temperature,
    ):
        self.state = EngineState.DRIFT_LOCKED

        temporal_result = (
            self._check_temporal(
                temperature
            )
        )

        temporal_drift = bool(
            temporal_result.get(
                "is_drift",
                False,
            )
        )

        if temporal_drift:

            self._quarantine_recovery_count = 0

        else:

            self._quarantine_recovery_count += 1

            if (
                self._quarantine_recovery_count
                >= self._quarantine_recovery_required
            ):
                self._finish_quarantine_recovery()

        threshold = (
            self.adaptive_threshold.get_threshold()
        )

        is_anomaly = (
            False
            if threshold is None
            else bool(
                score > threshold
            )
        )

        return self._build_result(
            score=score,
            is_anomaly=is_anomaly,
            alert=temporal_drift,
            adapted=False,
            regime_confirmed=False,
            regime_accepted=False,
            temporal_checked=True,
            temporal_drift=temporal_drift,
            temporal_result=temporal_result,
        )

    def _finish_quarantine_recovery(self):
        self._clear_quarantine()

        self.temporal_detector.reset()

        self.regime_detector.reset()

        self._clear_transition()

        self._regime_confirmation_emitted = False

        self._drift_detected = False

        self.state = EngineState.STABLE

    # ============================================================
    # START TRANSITION
    # ============================================================

    def _start_transition(
        self,
        score,
        temperature,
        regime_result,
    ):
        self._transition_active = True

        self.regime_transition_count += 1

        self.state = (
            EngineState.REGIME_CONFIRMATION
        )

        self._temporal_validation_started = True
        self._temporal_clean_checks = 0
        self._regime_validation_samples = 1

        temporal_result = (
            self._check_temporal(
                temperature
            )
        )

        detector_confirmed = bool(
            regime_result.get(
                "regime_confirmed",
                False,
            )
            or self.regime_detector.is_confirmed()
        )

        # A single observation is never sufficient to call
        # temporal drift. TemporalDetector itself owns persistence.

        if detector_confirmed:

            staged = (
                self._stage_confirmed_regime()
            )

            confirmation_event = False

            if staged:
                confirmation_event = (
                    self._emit_confirmation_event()
                )

            if temporal_result.get(
                "is_trend",
                False,
            ):
                self._temporal_clean_checks = 0
            else:
                self._temporal_clean_checks = 1

            return (
                temporal_result,
                True,
                False,
                False,
                confirmation_event,
            )

        if temporal_result.get(
            "is_trend",
            False,
        ):
            self._temporal_clean_checks = 0
        else:
            self._temporal_clean_checks = 1

        return (
            temporal_result,
            True,
            False,
            False,
            False,
        )

    # ============================================================
    # CONTINUE TRANSITION
    # ============================================================

    def _continue_transition(
        self,
        score,
        temperature,
    ):
        self.state = (
            EngineState.REGIME_CONFIRMATION
        )

        self._regime_validation_samples += 1

        regime_result = (
            self.regime_detector.observe(
                score
            )
        )

        regime_confirmed = bool(
            regime_result.get(
                "regime_confirmed",
                False,
            )
            or self.regime_detector.is_confirmed()
        )

        temporal_result = (
            self._check_temporal(
                temperature
            )
        )

        temporal_drift = bool(
            temporal_result.get(
                "is_drift",
                False,
            )
        )

        confirmation_event = False

        # --------------------------------------------------------
        # IMPORTANT:
        #
        # TemporalDetector has already performed its persistence
        # check. If it confirms temporal drift, DRIFT_LOCKED must
        # win over regime stability.
        # --------------------------------------------------------

        if temporal_drift:

            self.alert_count += 1

            self._enter_drift_locked()

            return (
                temporal_result,
                True,
                False,
                True,
                False,
            )

        # --------------------------------------------------------
        # Score regime confirmation
        # --------------------------------------------------------

        if (
            regime_confirmed
            and not self._pending_regime_confirmed
        ):

            staged = (
                self._stage_confirmed_regime()
            )

            if staged:
                confirmation_event = (
                    self._emit_confirmation_event()
                )

        # --------------------------------------------------------
        # Pending confirmed regime
        # --------------------------------------------------------

        if self._pending_regime_confirmed:

            self._temporal_validation_started = True

            if temporal_result.get(
                "is_trend",
                False,
            ):

                self._temporal_clean_checks = 0

            else:

                self._temporal_clean_checks += 1

            committed = False

            if self._can_accept_pending_regime():

                committed = (
                    self._commit_pending_regime()
                )

            return (
                temporal_result,
                True,
                committed,
                False,
                confirmation_event,
            )

        # --------------------------------------------------------
        # Stable candidate without explicit confirmation
        # --------------------------------------------------------

        if self._has_regime_stability(
            regime_result
        ):

            self._temporal_validation_started = True

            if temporal_result.get(
                "is_trend",
                False,
            ):

                self._temporal_clean_checks = 0

            else:

                self._temporal_clean_checks += 1

            return (
                temporal_result,
                True,
                False,
                False,
                confirmation_event,
            )

        # --------------------------------------------------------
        # Continue candidate validation
        # --------------------------------------------------------

        self._temporal_validation_started = True

        if temporal_result.get(
            "is_trend",
            False,
        ):

            self._temporal_clean_checks = 0

        else:

            self._temporal_clean_checks += 1

        return (
            temporal_result,
            True,
            False,
            False,
            confirmation_event,
        )

    # ============================================================
    # ACCEPTANCE GATE
    # ============================================================

    def _can_accept_pending_regime(self):
        if not self._pending_regime_confirmed:
            return False

        if not self._transition_active:
            return False

        if self._post_drift_quarantine:
            return False

        if self._drift_detected:
            return False

        if (
            self._regime_validation_samples
            < self._regime_validation_required
        ):
            return False

        return True

    # ============================================================
    # STABLE PROCESSING
    # ============================================================

    def _process_stable(
        self,
        score,
        temperature,
    ):
        confirmed_before = (
            self.regime_detector.is_confirmed()
        )

        regime_result = (
            self.regime_detector.observe(
                score
            )
        )

        detector_state = (
            self.regime_detector.get_state()
        )

        candidate_started = bool(
            detector_state.get(
                "candidate_started",
                False,
            )
        )

        confirmed_after = (
            self.regime_detector.is_confirmed()
        )

        shift_detected = bool(
            regime_result.get(
                "shift_detected",
                False,
            )
        )

        new_detector_confirmation = bool(
            confirmed_after
            and not confirmed_before
        )

        threshold = (
            self.adaptive_threshold.get_threshold()
        )

        is_anomaly = (
            False
            if threshold is None
            else bool(
                score > threshold
            )
        )

        if not shift_detected:

            self.state = EngineState.STABLE

            return {
                "adapted": False,
                "is_anomaly": is_anomaly,
                "alert": False,
                "regime_changed": False,
                "regime_confirmed": False,
                "regime_accepted": False,
                "candidate_started": (
                    candidate_started
                ),
                "temporal_checked": False,
                "temporal_drift": False,
                "temporal_result": {},
            }

        (
            temporal_result,
            checked,
            drift,
            accepted,
            confirmation_event,
        ) = self._start_transition(
            score,
            temperature,
            regime_result,
        )

        if new_detector_confirmation:

            confirmation_event = (
                self._emit_confirmation_event()
                or confirmation_event
            )

        return {
            "adapted": False,

            "is_anomaly": (
                True
                if drift
                else is_anomaly
            ),

            "alert": bool(
                drift
            ),

            "regime_changed": True,

            "regime_confirmed": bool(
                confirmation_event
            ),

            "regime_accepted": bool(
                accepted
            ),

            "candidate_started": (
                candidate_started
            ),

            "temporal_checked": bool(
                checked
            ),

            "temporal_drift": bool(
                drift
            ),

            "temporal_result": (
                temporal_result
            ),
        }

    # ============================================================
    # MAIN PROCESS
    # ============================================================

    def process(
        self,
        score,
        temperature,
    ):
        if not self.initialized:
            raise RuntimeError(
                "AdaptiveEngine must be initialized "
                "before processing observations."
            )

        score = self._validate_score(
            score
        )

        temperature = (
            self._validate_temperature(
                temperature
            )
        )

        self.total_samples += 1

        # --------------------------------------------------------
        # DRIFT QUARANTINE
        # --------------------------------------------------------

        if self._post_drift_quarantine:

            return self._process_quarantine(
                score,
                temperature,
            )

        # --------------------------------------------------------
        # ACTIVE REGIME TRANSITION
        # --------------------------------------------------------

        if self._transition_active:

            (
                temporal_result,
                temporal_checked,
                committed,
                drift,
                confirmation_event,
            ) = self._continue_transition(
                score,
                temperature,
            )

            threshold = (
                self.adaptive_threshold.get_threshold()
            )

            is_anomaly = (
                True
                if drift
                else (
                    False
                    if threshold is None
                    else bool(
                        score > threshold
                    )
                )
            )

            return self._build_result(
                score=score,
                is_anomaly=is_anomaly,
                alert=bool(
                    drift
                ),
                adapted=committed,
                regime_changed=False,
                regime_confirmed=(
                    confirmation_event
                ),
                regime_accepted=committed,
                candidate_started=bool(
                    self.regime_detector
                    .get_state()
                    .get(
                        "candidate_started",
                        False,
                    )
                ),
                temporal_checked=(
                    temporal_checked
                ),
                temporal_drift=bool(
                    drift
                ),
                temporal_result=(
                    temporal_result
                ),
            )

        # --------------------------------------------------------
        # STABLE
        # --------------------------------------------------------

        outcome = self._process_stable(
            score,
            temperature,
        )

        return self._build_result(
            score=score,
            is_anomaly=(
                outcome["is_anomaly"]
            ),
            alert=(
                outcome["alert"]
            ),
            adapted=(
                outcome["adapted"]
            ),
            regime_changed=(
                outcome["regime_changed"]
            ),
            regime_confirmed=(
                outcome["regime_confirmed"]
            ),
            regime_accepted=(
                outcome["regime_accepted"]
            ),
            candidate_started=(
                outcome["candidate_started"]
            ),
            temporal_checked=(
                outcome["temporal_checked"]
            ),
            temporal_drift=(
                outcome["temporal_drift"]
            ),
            temporal_result=(
                outcome["temporal_result"]
            ),
        )

    # ============================================================
    # UPDATE ALIAS
    # ============================================================

    def update(
        self,
        score,
        temperature,
    ):
        return self.process(
            score=score,
            temperature=temperature,
        )

    # ============================================================
    # STATE
    # ============================================================

    def get_state(self):
        return {
            "state": self.state.value,
            "initialized": self.initialized,
            "model_name": self.model_name,
            "shift_sigma": self.shift_sigma,
            "stability_tolerance": (
                self.stability_tolerance
            ),
            "adaptive_percentile": (
                self.adaptive_threshold.percentile
            ),
            "total_samples": self.total_samples,
            "adaptation_updates": (
                self.adaptation_updates
            ),
            "alert_count": self.alert_count,
            "regime_transition_count": (
                self.regime_transition_count
            ),
            "regime_confirmation_count": (
                self.regime_confirmation_count
            ),
            "regime_confirmation_emitted": (
                self._regime_confirmation_emitted
            ),
            "transition_active": (
                self._transition_active
            ),
            "post_drift_quarantine": (
                self._post_drift_quarantine
            ),
            "quarantine_recovery_count": (
                self._quarantine_recovery_count
            ),
            "quarantine_recovery_required": (
                self._quarantine_recovery_required
            ),
            "drift_detected": (
                self._drift_detected
            ),
            "temporal_validation_started": (
                self._temporal_validation_started
            ),
            "temporal_clean_checks": (
                self._temporal_clean_checks
            ),
            "temporal_validation_required": (
                self._temporal_validation_required
            ),
            "regime_validation_samples": (
                self._regime_validation_samples
            ),
            "regime_validation_required": (
                self._regime_validation_required
            ),
            "pending_regime_confirmed": (
                self._pending_regime_confirmed
            ),
            "pending_threshold": (
                self._pending_threshold
            ),
            "regime": (
                self.regime_detector.get_state()
            ),
            "temporal": (
                self.temporal_detector.get_state()
            ),
            "adaptive_threshold": (
                self.adaptive_threshold.get_state()
            ),
            "last_result": dict(
                self.last_result
            ),
        }

    # ============================================================
    # RESET
    # ============================================================

    def reset(self):
        self.regime_detector.reset()
        self.temporal_detector.reset()
        self.adaptive_threshold.reset()

        self.state = EngineState.STABLE

        self.initialized = False
        self.model_name = None

        self.total_samples = 0
        self.adaptation_updates = 0
        self.alert_count = 0

        self.regime_transition_count = 0
        self.regime_confirmation_count = 0

        self._clear_transition()
        self._clear_quarantine()

        self._regime_confirmation_emitted = False
        self._drift_detected = False

        self.last_result = self._empty_result()