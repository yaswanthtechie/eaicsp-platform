from collections import deque

import numpy as np


class TemporalDetector:
    """
    Detect sustained temperature drift.

    Detection has two levels of evidence:

    1. Normal/strong trend detection
       Uses the configured slope, total-change and R² thresholds.

    2. Sustained early-drift detection
       Allows a slow drift to be detected before the regression
       R² reaches the normal trend threshold.

    A single regression window is never sufficient for drift
    confirmation.

    `is_drift` is an event and is therefore True only on the
    observation where drift is newly confirmed.
    """

    def __init__(
        self,
        window_size=24,
        min_slope=0.03,
        min_total_change=0.75,
        min_r_squared=0.15,
        required_consecutive_windows=2,
        evaluation_step=6,
    ):
        if window_size < 5:
            raise ValueError(
                "window_size must be at least 5."
            )

        if min_slope <= 0:
            raise ValueError(
                "min_slope must be positive."
            )

        if min_total_change <= 0:
            raise ValueError(
                "min_total_change must be positive."
            )

        if not 0.0 <= min_r_squared <= 1.0:
            raise ValueError(
                "min_r_squared must be between 0 and 1."
            )

        if required_consecutive_windows < 1:
            raise ValueError(
                "required_consecutive_windows must be at least 1."
            )

        if evaluation_step < 1:
            raise ValueError(
                "evaluation_step must be positive."
            )

        self.window_size = int(window_size)
        self.min_slope = float(min_slope)
        self.min_total_change = float(min_total_change)
        self.min_r_squared = float(min_r_squared)

        self.required_consecutive_windows = int(
            required_consecutive_windows
        )

        self.evaluation_step = int(
            evaluation_step
        )

        self.temperature_history = deque(
            maxlen=self.window_size
        )

        self.samples_seen = 0
        self.samples_since_evaluation = 0

        # ------------------------------------------------------
        # Latest metrics
        # ------------------------------------------------------

        self.last_direction = None
        self.last_slope = 0.0
        self.last_total_change = 0.0
        self.last_r_squared = 0.0
        self.last_directional_fraction = 0.0

        self.last_is_trend = False
        self.last_is_drift = False

        # ------------------------------------------------------
        # Strong candidate
        # ------------------------------------------------------

        self.candidate_active = False
        self.candidate_direction = None
        self.candidate_windows = 0

        self.candidate_start_sample = None
        self.candidate_last_sample = None

        self.max_candidate_gap = max(
            self.window_size * 3,
            self.evaluation_step * 8,
        )

        # ------------------------------------------------------
        # Early sustained-drift candidate
        #
        # IMPORTANT:
        #
        # This does NOT require every evaluation to be a trend.
        #
        # Instead, several sufficiently strong moderate windows
        # must occur inside a bounded evidence horizon.
        # ------------------------------------------------------

        self.early_candidate_active = False
        self.early_candidate_direction = None

        self.early_candidate_windows = 0
        self.early_candidate_start_sample = None
        self.early_candidate_last_sample = None

        self.early_evidence_samples = deque(
            maxlen=20
        )

        self.early_required_windows = 3

        self.early_evidence_horizon = max(
            72,
            self.window_size * 3,
        )

        # ------------------------------------------------------
        # Confirmation
        # ------------------------------------------------------

        self.drift_confirmed = False

        self.validation_windows = 0
        self.validation_complete = False

        # ------------------------------------------------------
        # Historical evidence
        # ------------------------------------------------------

        self.evidence_history = deque(
            maxlen=100
        )

    # ==========================================================
    # Validation
    # ==========================================================

    @staticmethod
    def _validate_temperature(
        temperature,
    ):
        temperature = float(
            temperature
        )

        if not np.isfinite(
            temperature
        ):
            raise ValueError(
                "temperature must be finite."
            )

        return temperature

    # ==========================================================
    # Regression
    # ==========================================================

    def _calculate_window_metrics(self):
        values = np.asarray(
            self.temperature_history,
            dtype=float,
        )

        if values.size < self.window_size:
            return {
                "slope": 0.0,
                "total_change": 0.0,
                "r_squared": 0.0,
                "direction": None,
                "directional_fraction": 0.0,
            }

        x = np.arange(
            values.size,
            dtype=float,
        )

        x_mean = np.mean(x)
        y_mean = np.mean(values)

        x_centered = x - x_mean
        y_centered = values - y_mean

        denominator = np.sum(
            x_centered ** 2
        )

        if denominator <= 0.0:
            slope = 0.0
        else:
            slope = (
                np.sum(
                    x_centered * y_centered
                )
                / denominator
            )

        intercept = (
            y_mean
            - slope * x_mean
        )

        predicted = (
            intercept
            + slope * x
        )

        residual_sum = np.sum(
            (
                values - predicted
            ) ** 2
        )

        total_sum = np.sum(
            (
                values - y_mean
            ) ** 2
        )

        if total_sum <= 1e-12:
            r_squared = 0.0
        else:
            r_squared = (
                1.0
                - residual_sum / total_sum
            )

            r_squared = float(
                np.clip(
                    r_squared,
                    0.0,
                    1.0,
                )
            )

        total_change = float(
            predicted[-1] - predicted[0]
        )

        differences = np.diff(
            values
        )

        if slope > 0.0:
            direction = "up"

            directional_fraction = float(
                np.mean(
                    differences > 0.0
                )
            )

        elif slope < 0.0:
            direction = "down"

            directional_fraction = float(
                np.mean(
                    differences < 0.0
                )
            )

        else:
            direction = None
            directional_fraction = 0.0

        return {
            "slope": float(slope),
            "total_change": float(
                total_change
            ),
            "r_squared": float(
                r_squared
            ),
            "direction": direction,
            "directional_fraction": float(
                directional_fraction
            ),
        }

    # ==========================================================
    # Normal trend
    # ==========================================================

    def _evaluate_window(self):
        metrics = (
            self._calculate_window_metrics()
        )

        is_trend = bool(
            abs(metrics["slope"])
            >= self.min_slope
            and
            abs(metrics["total_change"])
            >= self.min_total_change
            and
            metrics["r_squared"]
            >= self.min_r_squared
        )

        return {
            **metrics,
            "is_trend": is_trend,
        }

    # ==========================================================
    # Strong evidence
    # ==========================================================

    def _is_strong_drift_window(
        self,
        evidence,
    ):
        slope = abs(
            evidence["slope"]
        )

        total_change = abs(
            evidence["total_change"]
        )

        r_squared = (
            evidence["r_squared"]
        )

        strong_slope = max(
            self.min_slope * 3.0,
            0.10,
        )

        strong_change = max(
            self.min_total_change * 2.0,
            1.50,
        )

        strong_r_squared = max(
            self.min_r_squared,
            0.24,
        )

        return bool(
            slope >= strong_slope
            and
            total_change >= strong_change
            and
            r_squared >= strong_r_squared
        )

    # ==========================================================
    # Early sustained evidence
    # ==========================================================

    def _is_early_drift_window(
        self,
        evidence,
    ):
        """
        Moderate evidence for a slowly developing drift.

        These thresholds are intentionally much stricter than
        the previous early-drift implementation.

        For the current 24-sample test window, useful early
        evidence looks approximately like:

            slope       >= 0.04
            total change >= 0.90
            R²           >= 0.04
            directional fraction >= 0.55

        Crucially, this still cannot confirm drift alone.
        Three compatible windows must accumulate.
        """

        slope = abs(
            evidence["slope"]
        )

        total_change = abs(
            evidence["total_change"]
        )

        r_squared = (
            evidence["r_squared"]
        )

        directional_fraction = (
            evidence["directional_fraction"]
        )

        early_min_slope = max(
            self.min_slope * 1.25,
            0.04,
        )

        early_min_change = max(
            self.min_total_change * 1.20,
            0.90,
        )

        early_min_r_squared = max(
            self.min_r_squared * 0.30,
            0.04,
        )

        early_min_directional_fraction = 0.55

        return bool(
            evidence["direction"] is not None
            and
            slope >= early_min_slope
            and
            total_change >= early_min_change
            and
            r_squared >= early_min_r_squared
            and
            directional_fraction
            >= early_min_directional_fraction
        )

    # ==========================================================
    # Strong candidate
    # ==========================================================

    def _start_candidate(
        self,
        evidence,
    ):
        self.candidate_active = True

        self.candidate_direction = (
            evidence["direction"]
        )

        self.candidate_windows = 1

        self.candidate_start_sample = (
            self.samples_seen
        )

        self.candidate_last_sample = (
            self.samples_seen
        )

    def _continue_candidate(
        self,
        evidence,
    ):
        if not self.candidate_active:
            return False

        if (
            evidence["direction"]
            != self.candidate_direction
        ):
            self._clear_candidate()
            return False

        gap = (
            self.samples_seen
            - self.candidate_last_sample
        )

        if gap > self.max_candidate_gap:
            self._clear_candidate()
            return False

        self.candidate_windows += 1

        self.candidate_last_sample = (
            self.samples_seen
        )

        return True

    def _clear_candidate(self):
        self.candidate_active = False
        self.candidate_direction = None
        self.candidate_windows = 0
        self.candidate_start_sample = None
        self.candidate_last_sample = None

    # ==========================================================
    # Early candidate
    # ==========================================================

    def _start_early_candidate(
        self,
        evidence,
    ):
        self.early_candidate_active = True

        self.early_candidate_direction = (
            evidence["direction"]
        )

        self.early_candidate_windows = 1

        self.early_candidate_start_sample = (
            self.samples_seen
        )

        self.early_candidate_last_sample = (
            self.samples_seen
        )

        self.early_evidence_samples.clear()

        self.early_evidence_samples.append(
            self.samples_seen
        )

    def _continue_early_candidate(
        self,
        evidence,
    ):
        if not self.early_candidate_active:
            return False

        if (
            evidence["direction"]
            != self.early_candidate_direction
        ):
            self._clear_early_candidate()
            return False

        gap = (
            self.samples_seen
            - self.early_candidate_last_sample
        )

        if gap > self.early_evidence_horizon:
            self._clear_early_candidate()
            return False

        self.early_candidate_windows += 1

        self.early_candidate_last_sample = (
            self.samples_seen
        )

        self.early_evidence_samples.append(
            self.samples_seen
        )

        return True

    def _clear_early_candidate(self):
        self.early_candidate_active = False

        self.early_candidate_direction = None

        self.early_candidate_windows = 0

        self.early_candidate_start_sample = None

        self.early_candidate_last_sample = None

        self.early_evidence_samples.clear()

    # ==========================================================
    # Confirmation
    # ==========================================================

    def _confirm_drift(self):
        self.drift_confirmed = True

        self._clear_candidate()
        self._clear_early_candidate()

        self.validation_windows = 0
        self.validation_complete = False

        return True

    # ==========================================================
    # Candidate processing
    # ==========================================================

    def _process_drift_candidates(
        self,
        evidence,
    ):
        is_trend = bool(
            evidence["is_trend"]
        )

        is_strong = bool(
            evidence["strong_drift"]
        )

        is_early = bool(
            evidence["early_drift"]
        )

        # ------------------------------------------------------
        # Strong path
        # ------------------------------------------------------

        if self.candidate_active:

            if is_trend:

                if self._continue_candidate(
                    evidence
                ):

                    if (
                        self.candidate_windows
                        >= self.required_consecutive_windows
                    ):
                        return self._confirm_drift()

            else:

                gap = (
                    self.samples_seen
                    - self.candidate_last_sample
                )

                if gap > self.max_candidate_gap:
                    self._clear_candidate()

        elif is_strong:

            self._start_candidate(
                evidence
            )

            if (
                self.candidate_windows
                >= self.required_consecutive_windows
            ):
                return self._confirm_drift()

        # ------------------------------------------------------
        # Early sustained path
        # ------------------------------------------------------

        if self.early_candidate_active:

            if is_early or is_trend:

                if self._continue_early_candidate(
                    evidence
                ):

                    # Ensure all early evidence is recent.
                    first_sample = (
                        self.early_evidence_samples[0]
                    )

                    evidence_span = (
                        self.samples_seen
                        - first_sample
                    )

                    if (
                        evidence_span
                        <= self.early_evidence_horizon
                        and
                        self.early_candidate_windows
                        >= self.early_required_windows
                    ):
                        return self._confirm_drift()

            else:

                gap = (
                    self.samples_seen
                    - self.early_candidate_last_sample
                )

                if gap > self.early_evidence_horizon:
                    self._clear_early_candidate()

        elif is_early:

            self._start_early_candidate(
                evidence
            )

        return False

    # ==========================================================
    # Validation
    # ==========================================================

    def _update_validation(
        self,
        evidence,
    ):
        if evidence["is_trend"]:

            self.validation_windows = 0
            self.validation_complete = False

            return

        self.validation_windows += 1

        if (
            self.validation_windows
            >= self.required_consecutive_windows
        ):
            self.validation_complete = True

    # ==========================================================
    # Main update
    # ==========================================================

    def update(
        self,
        temperature,
    ):
        temperature = (
            self._validate_temperature(
                temperature
            )
        )

        self.samples_seen += 1

        self.samples_since_evaluation += 1

        self.temperature_history.append(
            temperature
        )

        # Event semantics.
        self.last_is_drift = False

        # ------------------------------------------------------
        # Warm-up
        # ------------------------------------------------------

        if len(
            self.temperature_history
        ) < self.window_size:

            return self._build_result(
                is_drift=False
            )

        # ------------------------------------------------------
        # Evaluation cadence
        # ------------------------------------------------------

        if (
            self.samples_since_evaluation
            < self.evaluation_step
        ):

            return self._build_result(
                is_drift=False
            )

        self.samples_since_evaluation = 0

        evidence = (
            self._evaluate_window()
        )

        evidence[
            "strong_drift"
        ] = self._is_strong_drift_window(
            evidence
        )

        evidence[
            "early_drift"
        ] = self._is_early_drift_window(
            evidence
        )

        # ------------------------------------------------------
        # Metrics
        # ------------------------------------------------------

        self.last_slope = float(
            evidence["slope"]
        )

        self.last_total_change = float(
            evidence["total_change"]
        )

        self.last_r_squared = float(
            evidence["r_squared"]
        )

        self.last_direction = (
            evidence["direction"]
        )

        self.last_directional_fraction = float(
            evidence["directional_fraction"]
        )

        self.last_is_trend = bool(
            evidence["is_trend"]
        )

        # ------------------------------------------------------
        # Candidate processing
        # ------------------------------------------------------

        confirmed_now = (
            self._process_drift_candidates(
                evidence
            )
        )

        # ------------------------------------------------------
        # History
        # ------------------------------------------------------

        self.evidence_history.append(
            dict(evidence)
        )

        # ------------------------------------------------------
        # Validation
        # ------------------------------------------------------

        if confirmed_now:

            self.last_is_drift = True

            self.validation_windows = 0
            self.validation_complete = False

        else:

            self._update_validation(
                evidence
            )

        return self._build_result(
            is_drift=confirmed_now
        )

    # ==========================================================
    # Result
    # ==========================================================

    def _build_result(
        self,
        is_drift,
    ):
        return {
            "is_drift": bool(
                is_drift
            ),

            "slope": float(
                self.last_slope
            ),

            "total_change": float(
                self.last_total_change
            ),

            "r_squared": float(
                self.last_r_squared
            ),

            "direction": (
                self.last_direction
            ),

            "directional_fraction": float(
                self.last_directional_fraction
            ),

            "is_trend": bool(
                self.last_is_trend
            ),

            "consecutive_windows": int(
                self.candidate_windows
            ),

            "consecutive_trend_windows": int(
                self.candidate_windows
            ),

            "validation_windows": int(
                self.validation_windows
            ),

            "validation_complete": bool(
                self.validation_complete
            ),

            "sample_count": int(
                self.samples_seen
            ),
        }

    # ==========================================================
    # State
    # ==========================================================

    def get_state(self):
        return {
            "window_size": int(
                self.window_size
            ),

            "min_slope": float(
                self.min_slope
            ),

            "min_total_change": float(
                self.min_total_change
            ),

            "min_r_squared": float(
                self.min_r_squared
            ),

            "required_consecutive_windows": int(
                self.required_consecutive_windows
            ),

            "evaluation_step": int(
                self.evaluation_step
            ),

            "sample_count": int(
                self.samples_seen
            ),

            "history_size": int(
                len(
                    self.temperature_history
                )
            ),

            "drift_confirmed": bool(
                self.drift_confirmed
            ),

            # Strong candidate
            "candidate_active": bool(
                self.candidate_active
            ),

            "candidate_direction": (
                self.candidate_direction
            ),

            "candidate_windows": int(
                self.candidate_windows
            ),

            # Early candidate
            "early_candidate_active": bool(
                self.early_candidate_active
            ),

            "early_candidate_direction": (
                self.early_candidate_direction
            ),

            "early_candidate_windows": int(
                self.early_candidate_windows
            ),

            "early_required_windows": int(
                self.early_required_windows
            ),

            "early_evidence_horizon": int(
                self.early_evidence_horizon
            ),

            # Backwards-compatible fields
            "consecutive_windows": int(
                self.candidate_windows
            ),

            "consecutive_trend_windows": int(
                self.candidate_windows
            ),

            "direction": (
                self.last_direction
            ),

            "slope": float(
                self.last_slope
            ),

            "total_change": float(
                self.last_total_change
            ),

            "r_squared": float(
                self.last_r_squared
            ),

            "directional_fraction": float(
                self.last_directional_fraction
            ),

            "is_trend": bool(
                self.last_is_trend
            ),

            "is_drift": bool(
                self.last_is_drift
            ),

            "validation_windows": int(
                self.validation_windows
            ),

            "validation_complete": bool(
                self.validation_complete
            ),

            "evidence_history_size": int(
                len(
                    self.evidence_history
                )
            ),
        }

    # ==========================================================
    # Convenience
    # ==========================================================

    def is_confirmed(self):
        return bool(
            self.drift_confirmed
        )

    def is_validation_complete(self):
        return bool(
            self.validation_complete
            and not self.drift_confirmed
        )

    # ==========================================================
    # Reset
    # ==========================================================

    def reset(self):
        self.temperature_history.clear()

        self.evidence_history.clear()

        self.samples_seen = 0
        self.samples_since_evaluation = 0

        self.last_direction = None
        self.last_slope = 0.0
        self.last_total_change = 0.0
        self.last_r_squared = 0.0
        self.last_directional_fraction = 0.0

        self.last_is_trend = False
        self.last_is_drift = False

        # Strong candidate
        self.candidate_active = False
        self.candidate_direction = None
        self.candidate_windows = 0
        self.candidate_start_sample = None
        self.candidate_last_sample = None

        # Early candidate
        self.early_candidate_active = False
        self.early_candidate_direction = None
        self.early_candidate_windows = 0
        self.early_candidate_start_sample = None
        self.early_candidate_last_sample = None
        self.early_evidence_samples.clear()

        # Confirmation
        self.drift_confirmed = False

        self.validation_windows = 0
        self.validation_complete = False