from collections import deque
import threading

import numpy as np


class RegimeDetector:
    """
    Detect sustained and stable changes in anomaly-score
    distributions.

    Responsibilities
    ----------------
    This detector ONLY identifies a possible new operating
    regime.

    It does NOT:

        - classify individual observations
        - calculate anomaly thresholds
        - update AdaptiveThreshold
        - use temperature
        - automatically replace the trusted baseline

    Lifecycle
    ---------
        ESTABLISHED
             |
             v
        CANDIDATE
             |
             v
        SHIFT CANDIDATE
             |
             v
        STABILITY VALIDATION
             |
             +---- unstable ------> continue validation
             |
             +---- stable --------> stable checkpoint
                                          |
                                          v
                                  repeated checkpoints
                                          |
                                          v
                                      CONFIRMED
                                       /      \
                                      /        \
                                  ACCEPT       REJECT
                                    |             |
                                    v             v
                              new baseline    discard candidate
    """

    def __init__(
        self,
        candidate_sizes=None,
        baseline_size=100,
        shift_sigma=1.5,
        stability_tolerance=0.20,
        min_stable_blocks=2,
    ):
        if candidate_sizes is None:
            candidate_sizes = [10, 25, 50, 100, 200]

        candidate_sizes = sorted(
            set(
                int(size)
                for size in candidate_sizes
                if int(size) > 0
            )
        )

        if not candidate_sizes:
            raise ValueError(
                "candidate_sizes must contain at least one "
                "positive value."
            )

        if baseline_size <= 1:
            raise ValueError(
                "baseline_size must be greater than 1."
            )

        if shift_sigma <= 0:
            raise ValueError(
                "shift_sigma must be greater than 0."
            )

        if stability_tolerance < 0:
            raise ValueError(
                "stability_tolerance cannot be negative."
            )

        if min_stable_blocks < 1:
            raise ValueError(
                "min_stable_blocks must be at least 1."
            )

        self.candidate_sizes = candidate_sizes
        self.baseline_size = int(baseline_size)
        self.shift_sigma = float(shift_sigma)
        self.stability_tolerance = float(
            stability_tolerance
        )
        self.min_stable_blocks = int(
            min_stable_blocks
        )

        # ----------------------------------------------------
        # TRUSTED BASELINE
        # ----------------------------------------------------

        self.baseline_scores = deque(
            maxlen=self.baseline_size
        )

        # ----------------------------------------------------
        # CANDIDATE WINDOW
        # ----------------------------------------------------

        self.max_candidate_size = (
            self.candidate_sizes[-1]
        )

        self.candidate_scores = deque(
            maxlen=self.max_candidate_size
        )

        self.confirmed_regime_scores = []

        # Total observations entering candidate lifecycle.
        # This is separate from len(candidate_scores), because
        # the candidate deque is only a rolling window.
        self.candidate_observations = 0

        self.candidate_started = False
        self.regime_confirmed = False

        # ----------------------------------------------------
        # STAGE
        # ----------------------------------------------------

        self.current_stage = -1
        self.last_stage_evaluated = None
        self.stable_blocks = 0

        # ----------------------------------------------------
        # LAST SHIFT
        # ----------------------------------------------------

        self.last_shift_detected = False
        self.last_shift_strength = 0.0

        # ----------------------------------------------------
        # ROLLING VALIDATION
        # ----------------------------------------------------

        self.validation_interval = max(
            25,
            self.max_candidate_size
            // self.min_stable_blocks,
        )

        self.validation_observations = 0
        self.validation_checks = 0

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        self.last_stability_reason = "not_evaluated"
        self.last_stability_diagnostics = {}

        self.lock = threading.RLock()

    # ========================================================
    # NUMERIC HELPERS
    # ========================================================

    @staticmethod
    def _clean(scores):
        values = np.asarray(
            scores,
            dtype=float,
        )

        return values[
            np.isfinite(values)
        ]

    @staticmethod
    def _mad(scores):
        values = RegimeDetector._clean(scores)

        if values.size == 0:
            return None

        median = np.median(values)

        return float(
            np.median(
                np.abs(values - median)
            )
        )

    @staticmethod
    def _iqr(scores):
        values = RegimeDetector._clean(scores)

        if values.size == 0:
            return None

        q25, q75 = np.percentile(
            values,
            [25, 75],
        )

        return float(q75 - q25)

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def initialize(self, scores):
        """
        Initialize trusted baseline from calibration scores.
        """

        values = self._clean(scores)

        with self.lock:
            self.reset()

            if values.size == 0:
                return

            for score in values[
                -self.baseline_size:
            ]:
                self.baseline_scores.append(
                    float(score)
                )

    # ========================================================
    # STATISTICS
    # ========================================================

    def _baseline_statistics(self):
        if not self.baseline_scores:
            return None

        values = np.asarray(
            self.baseline_scores,
            dtype=float,
        )

        return {
            "median": float(np.median(values)),
            "mad": float(self._mad(values)),
            "iqr": float(self._iqr(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
        }

    def _candidate_statistics(self):
        if not self.candidate_scores:
            return None

        values = np.asarray(
            self.candidate_scores,
            dtype=float,
        )

        return {
            "median": float(np.median(values)),
            "mad": float(self._mad(values)),
            "iqr": float(self._iqr(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
        }

    @staticmethod
    def _scale_from_statistics(statistics):
        if statistics is None:
            return None

        mad = statistics.get("mad")

        if mad is not None and mad > 1e-12:
            return float(1.4826 * mad)

        iqr = statistics.get("iqr")

        if iqr is not None and iqr > 1e-12:
            return float(iqr / 1.349)

        std = statistics.get("std")

        if std is not None and std > 1e-12:
            return float(std)

        return 1e-12

    def _baseline_scale(self):
        return self._scale_from_statistics(
            self._baseline_statistics()
        )

    def _candidate_scale(self):
        return self._scale_from_statistics(
            self._candidate_statistics()
        )

    # ========================================================
    # SHIFT
    # ========================================================

    def _shift_strength(self, values):
        baseline = self._baseline_statistics()

        candidate_values = self._clean(values)

        if (
            baseline is None
            or candidate_values.size == 0
        ):
            return 0.0

        baseline_scale = self._baseline_scale()

        if baseline_scale is None:
            return 0.0

        candidate_median = float(
            np.median(candidate_values)
        )

        return float(
            abs(
                candidate_median
                - baseline["median"]
            )
            / max(
                baseline_scale,
                1e-12,
            )
        )

    def _is_shifted(self):
        if not self.candidate_scores:
            self.last_shift_strength = 0.0
            return False

        strength = self._shift_strength(
            self.candidate_scores
        )

        self.last_shift_strength = strength

        return strength >= self.shift_sigma

    # ========================================================
    # BLOCK ANALYSIS
    # ========================================================

    def _get_blocks(self, values):
        values = self._clean(values)

        if values.size < 30:
            return []

        block_count = 3

        block_size = (
            values.size // block_count
        )

        if block_size < 5:
            return []

        blocks = []

        for index in range(block_count):
            start = index * block_size

            if index == block_count - 1:
                end = values.size
            else:
                end = start + block_size

            block = values[start:end]

            if block.size >= 5:
                blocks.append(block)

        return blocks

    def _block_medians(self, values):
        blocks = self._get_blocks(values)

        return [
            float(np.median(block))
            for block in blocks
        ]

    # ========================================================
    # STABILITY
    # ========================================================

    def _stability_diagnostics(self):
        values = self._clean(
            self.candidate_scores
        )

        diagnostics = {
            "sample_count": int(values.size),
            "shift_strength": 0.0,
            "baseline_scale": None,
            "candidate_scale": None,
            "movement_limit": None,
            "block_medians": [],
            "block_changes": [],
            "directional": False,
            "stable": False,
            "reason": "insufficient_samples",
        }

        if values.size < 30:
            return diagnostics

        baseline_scale = self._baseline_scale()
        candidate_scale = self._candidate_scale()

        diagnostics["baseline_scale"] = (
            baseline_scale
        )

        diagnostics["candidate_scale"] = (
            candidate_scale
        )

        shift_strength = self._shift_strength(
            values
        )

        diagnostics["shift_strength"] = (
            shift_strength
        )

        if shift_strength < self.shift_sigma:
            diagnostics["reason"] = (
                "shift_below_gate"
            )
            return diagnostics

        medians = self._block_medians(values)

        diagnostics["block_medians"] = medians

        if len(medians) < 3:
            diagnostics["reason"] = (
                "insufficient_blocks"
            )
            return diagnostics

        changes = [
            current - previous
            for previous, current in zip(
                medians[:-1],
                medians[1:],
            )
        ]

        diagnostics["block_changes"] = changes

        if candidate_scale is None:
            diagnostics["reason"] = (
                "candidate_scale_unavailable"
            )
            return diagnostics

        movement_limit = (
            self.stability_tolerance
            * max(
                candidate_scale,
                1e-12,
            )
        )

        diagnostics["movement_limit"] = (
            movement_limit
        )

        if any(
            abs(change) > movement_limit
            for change in changes
        ):
            diagnostics["reason"] = (
                "block_movement_too_large"
            )
            return diagnostics

        meaningful = [
            change
            for change in changes
            if abs(change) > 1e-12
        ]

        directional = False

        if len(meaningful) >= 2:
            positive = all(
                change > 0
                for change in meaningful
            )

            negative = all(
                change < 0
                for change in meaningful
            )

            directional = positive or negative

        diagnostics["directional"] = directional

        if directional:
            diagnostics["reason"] = (
                "persistent_directional_movement"
            )
            return diagnostics

        diagnostics["stable"] = True
        diagnostics["reason"] = "stable"

        return diagnostics

    def _is_candidate_stable(self):
        diagnostics = (
            self._stability_diagnostics()
        )

        self.last_stability_reason = (
            diagnostics["reason"]
        )

        self.last_stability_diagnostics = (
            diagnostics
        )

        return bool(
            diagnostics["stable"]
        )

    # ========================================================
    # STAGES
    # ========================================================

    def _next_stage(self):
        for index, size in enumerate(
            self.candidate_sizes
        ):
            if self.candidate_observations < size:
                return index

        return (
            len(self.candidate_sizes) - 1
        )

    def _stage_ready(self):
        next_stage = self._next_stage()

        if next_stage <= self.current_stage:
            return None

        if (
            self.candidate_observations
            >= self.candidate_sizes[next_stage]
        ):
            return next_stage

        return None

    def _validation_ready(self):
        if (
            self.current_stage
            != len(self.candidate_sizes) - 1
        ):
            return False

        if (
            self.candidate_observations
            < self.max_candidate_size
        ):
            return False

        if self.validation_checks == 0:
            return True

        elapsed = (
            self.candidate_observations
            - self.max_candidate_size
        )

        return (
            elapsed > 0
            and elapsed % self.validation_interval == 0
        )

    # ========================================================
    # RESULT
    # ========================================================

    def _build_result(self, shift_detected):
        return {
            "regime_confirmed": bool(
                self.regime_confirmed
            ),
            "candidate_started": bool(
                self.candidate_started
            ),
            "candidate_size": int(
                len(self.candidate_scores)
            ),
            "candidate_observations": int(
                self.candidate_observations
            ),
            "stage": int(self.current_stage),
            "stable_blocks": int(
                self.stable_blocks
            ),
            "validation_checks": int(
                self.validation_checks
            ),
            "validation_interval": int(
                self.validation_interval
            ),
            "shift_detected": bool(
                shift_detected
            ),
            "shift_strength": float(
                self.last_shift_strength
            ),
            "stability_reason": (
                self.last_stability_reason
            ),
            "stability_diagnostics": dict(
                self.last_stability_diagnostics
            ),
        }

    # ========================================================
    # OBSERVE
    # ========================================================

    def observe(self, score):
        """
        Process one incoming score.

        Candidate observations NEVER modify the trusted
        baseline.

        Only accept_regime() changes the baseline.
        """

        score = float(score)

        if not np.isfinite(score):
            raise ValueError(
                "score must be a finite number."
            )

        with self.lock:

            # Once confirmed, hold state until caller accepts
            # or rejects the candidate.
            if self.regime_confirmed:
                return self._build_result(
                    shift_detected=True
                )

            if not self.candidate_started:

                self.candidate_started = True
                self.current_stage = -1
                self.last_stage_evaluated = None
                self.stable_blocks = 0
                self.last_shift_detected = False
                self.last_shift_strength = 0.0

                self.validation_checks = 0
                self.validation_observations = 0
                self.candidate_observations = 0

                self.last_stability_reason = (
                    "not_evaluated"
                )

                self.last_stability_diagnostics = {}

            self.candidate_scores.append(score)
            self.candidate_observations += 1

            # ------------------------------------------------
            # Configured stage evaluation
            # ------------------------------------------------

            stage = self._stage_ready()

            if stage is not None:

                self.current_stage = stage
                self.last_stage_evaluated = stage

                shifted = self._is_shifted()

                self.last_shift_detected = shifted

                if not shifted:

                    self.stable_blocks = 0
                    self.last_stability_reason = (
                        "shift_below_gate"
                    )

                    return self._build_result(
                        shift_detected=False
                    )

                stable = (
                    self._is_candidate_stable()
                )

                if stable:
                    self.stable_blocks += 1
                else:
                    self.stable_blocks = 0

                if (
                    stable
                    and self.stable_blocks
                    >= self.min_stable_blocks
                ):
                    self.regime_confirmed = True

                    self.confirmed_regime_scores = list(
                        self.candidate_scores
                    )

                return self._build_result(
                    shift_detected=True
                )

            # ------------------------------------------------
            # Rolling validation
            # ------------------------------------------------

            if self._validation_ready():

                self.validation_checks += 1

                self.validation_observations = (
                    self.candidate_observations
                    - self.max_candidate_size
                )

                shifted = self._is_shifted()

                self.last_shift_detected = shifted

                if not shifted:

                    self.stable_blocks = 0
                    self.last_stability_reason = (
                        "shift_lost_during_validation"
                    )

                    return self._build_result(
                        shift_detected=False
                    )

                stable = (
                    self._is_candidate_stable()
                )

                if stable:
                    self.stable_blocks += 1
                else:
                    self.stable_blocks = 0

                if (
                    stable
                    and self.stable_blocks
                    >= self.min_stable_blocks
                ):
                    self.regime_confirmed = True

                    self.confirmed_regime_scores = list(
                        self.candidate_scores
                    )

                return self._build_result(
                    shift_detected=True
                )

            # ------------------------------------------------
            # Candidate continuation
            # ------------------------------------------------

            shifted = self._is_shifted()

            self.last_shift_detected = shifted

            if not shifted:
                self.last_stability_reason = (
                    "shift_below_gate"
                )

            return self._build_result(
                shift_detected=shifted
            )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def is_confirmed(self):
        """
        State query.

        Returns True for as long as a regime remains confirmed
        and has not been accepted/rejected.
        """
        with self.lock:
            return bool(
                self.regime_confirmed
            )

    def get_confirmed_scores(self):
        with self.lock:
            return list(
                self.confirmed_regime_scores
            )

    # ========================================================
    # ACCEPT
    # ========================================================

    def accept_regime(self, scores=None):
        """
        Explicitly promote confirmed regime into trusted
        baseline.

        This is the ONLY operation that changes the baseline
        after initialization.
        """

        with self.lock:

            if scores is None:
                scores = (
                    self.confirmed_regime_scores
                )

            values = self._clean(scores)

            if values.size == 0:
                raise ValueError(
                    "Cannot accept a regime without "
                    "valid scores."
                )

            self.baseline_scores.clear()

            for score in values[
                -self.baseline_size:
            ]:
                self.baseline_scores.append(
                    float(score)
                )

            self._clear_candidate_state()

    def accept_candidate(self, scores=None):
        """
        Compatibility alias.
        """
        self.accept_regime(scores=scores)

    # ========================================================
    # REJECT
    # ========================================================

    def reject_candidate(self):
        with self.lock:
            self._clear_candidate_state()

    # ========================================================
    # INTERNAL CLEAR
    # ========================================================

    def _clear_candidate_state(self):
        self.candidate_scores.clear()
        self.confirmed_regime_scores = []

        self.candidate_started = False
        self.regime_confirmed = False

        self.current_stage = -1
        self.last_stage_evaluated = None

        self.stable_blocks = 0

        self.last_shift_detected = False
        self.last_shift_strength = 0.0

        self.validation_observations = 0
        self.validation_checks = 0

        self.candidate_observations = 0

        self.last_stability_reason = (
            "not_evaluated"
        )

        self.last_stability_diagnostics = {}

    # ========================================================
    # STATE
    # ========================================================

    def get_state(self):
        with self.lock:

            return {
                "baseline_size": (
                    self.baseline_size
                ),
                "baseline_sample_count": (
                    len(self.baseline_scores)
                ),
                "candidate_sample_count": (
                    len(self.candidate_scores)
                ),
                "candidate_observations": (
                    self.candidate_observations
                ),
                "candidate_sizes": list(
                    self.candidate_sizes
                ),
                "current_stage": (
                    self.current_stage
                ),
                "last_stage_evaluated": (
                    self.last_stage_evaluated
                ),
                "shift_sigma": (
                    self.shift_sigma
                ),
                "stability_tolerance": (
                    self.stability_tolerance
                ),
                "min_stable_blocks": (
                    self.min_stable_blocks
                ),
                "candidate_started": (
                    self.candidate_started
                ),
                "regime_confirmed": (
                    self.regime_confirmed
                ),
                "stable_blocks": (
                    self.stable_blocks
                ),
                "last_shift_detected": (
                    self.last_shift_detected
                ),
                "last_shift_strength": (
                    self.last_shift_strength
                ),
                "validation_interval": (
                    self.validation_interval
                ),
                "validation_observations": (
                    self.validation_observations
                ),
                "validation_checks": (
                    self.validation_checks
                ),
                "last_stability_reason": (
                    self.last_stability_reason
                ),
                "last_stability_diagnostics": dict(
                    self.last_stability_diagnostics
                ),
                "baseline_statistics": (
                    self._baseline_statistics()
                ),
                "candidate_statistics": (
                    self._candidate_statistics()
                ),
            }

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):
        """
        Completely reset detector.

        initialize() calls reset() and then restores the
        trusted calibration baseline.
        """

        with self.lock:

            self.baseline_scores.clear()
            self.candidate_scores.clear()

            self.confirmed_regime_scores = []

            self.candidate_started = False
            self.regime_confirmed = False

            self.current_stage = -1
            self.last_stage_evaluated = None

            self.stable_blocks = 0

            self.last_shift_detected = False
            self.last_shift_strength = 0.0

            self.validation_observations = 0
            self.validation_checks = 0

            self.candidate_observations = 0

            self.last_stability_reason = (
                "not_evaluated"
            )

            self.last_stability_diagnostics = {}