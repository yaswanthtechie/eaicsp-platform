from collections import deque
import math

import numpy as np


class TemporalDetector:
    """
    Streaming temperature drift detector.

    Detects sustained temperature regime changes while avoiding
    short-lived spikes and ordinary sensor noise.

    Detection uses two complementary signals:

        1. Linear trend evidence over the rolling window.
        2. Sustained level-shift evidence between the older and
           newer portions of the rolling window.

    Drift is emitted as an event:
        is_drift == True

    only on the observation where drift is newly confirmed.
    """

    def __init__(
        self,
        window_size=24,
        min_slope=0.03,
        min_total_change=0.75,
        min_r_squared=0.15,
        required_consecutive_windows=2,
        evaluation_step=2,
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

        self.min_slope = float(
            min_slope
        )

        self.min_total_change = float(
            min_total_change
        )

        self.min_r_squared = float(
            min_r_squared
        )

        self.required_consecutive_windows = int(
            required_consecutive_windows
        )

        self.evaluation_step = int(
            evaluation_step
        )

        # ------------------------------------------------------
        # Temperature history
        # ------------------------------------------------------

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
        # Linear trend candidate
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
        # Level-shift detector
        # ------------------------------------------------------

        self.level_shift_window = min(
            12,
            max(
                6,
                self.window_size // 2,
            ),
        )

        # A normal noisy window should not be enough to create
        # a regime shift.
        self.min_level_shift = 1.50

        # Require three compatible evaluations.
        self.level_shift_required_windows = 3

        self.level_shift_candidate_active = False

        self.level_shift_direction = None

        self.level_shift_candidate_windows = 0

        self.level_shift_start_sample = None
        self.level_shift_last_sample = None

        self.max_level_shift_gap = max(
            self.evaluation_step * 4,
            self.level_shift_window * 4,
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

        try:
            temperature = float(
                temperature
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "temperature must be numeric."
            ) from exc

        if not math.isfinite(
            temperature
        ):

            raise ValueError(
                "temperature must be finite."
            )

        return temperature

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

        # is_drift is an event.
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

        # ------------------------------------------------------
        # Calculate evidence
        # ------------------------------------------------------

        evidence = (
            self._evaluate_window()
        )

        # ------------------------------------------------------
        # Public metrics
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
        # Linear trend path
        # ------------------------------------------------------

        trend_confirmed = (
            self._process_trend_candidate(
                evidence
            )
        )

        strong_drift = (
            self._is_strong_drift_window(
                evidence
            )
        )

        # ------------------------------------------------------
        # Level shift path
        # ------------------------------------------------------

        level_confirmed = (
            self._process_level_shift_candidate(
                evidence
            )
        )

        confirmed_now = bool(
            (trend_confirmed and strong_drift)
            or level_confirmed
            or strong_drift
        )

        # ------------------------------------------------------
        # Save evidence
        # ------------------------------------------------------

        self.evidence_history.append(
            dict(evidence)
        )

        # ------------------------------------------------------
        # Confirmation
        # ------------------------------------------------------

        if confirmed_now:

            self.last_is_drift = True

            self.drift_confirmed = True

            self.validation_windows = 0

            self.validation_complete = False

            self._clear_trend_candidate()

            self._clear_level_shift_candidate()

        return self._build_result(
            is_drift=confirmed_now
        )

    # ==========================================================
    # Calculate rolling metrics
    # ==========================================================

    def _calculate_window_metrics(self):

        values = np.asarray(
            self.temperature_history,
            dtype=float,
        )

        n = len(values)

        x = np.arange(
            n,
            dtype=float,
        )

        # ------------------------------------------------------
        # Linear regression
        # ------------------------------------------------------

        x_mean = float(
            np.mean(x)
        )

        y_mean = float(
            np.mean(values)
        )

        x_centered = (
            x - x_mean
        )

        y_centered = (
            values - y_mean
        )

        denominator = float(
            np.sum(
                x_centered ** 2
            )
        )

        if denominator <= 0:

            slope = 0.0

        else:

            slope = float(
                np.sum(
                    x_centered
                    * y_centered
                )
                / denominator
            )

        predicted = (
            y_mean
            + slope
            * x_centered
        )

        ss_res = float(
            np.sum(
                (values - predicted) ** 2
            )
        )

        ss_tot = float(
            np.sum(
                (values - y_mean) ** 2
            )
        )

        if ss_tot <= 1e-12:

            r_squared = 0.0

        else:

            r_squared = max(
                0.0,
                min(
                    1.0,
                    1.0
                    - (
                        ss_res
                        / ss_tot
                    ),
                ),
            )

        total_change = float(
            values[-1]
            - values[0]
        )

        # ------------------------------------------------------
        # Direction
        # ------------------------------------------------------

        if slope > 0:

            direction = "up"

        elif slope < 0:

            direction = "down"

        else:

            direction = None

        # ------------------------------------------------------
        # Directional fraction
        # ------------------------------------------------------

        differences = np.diff(
            values
        )

        if len(
            differences
        ) == 0:

            directional_fraction = 0.0

        elif direction == "up":

            directional_fraction = float(
                np.mean(
                    differences >= 0
                )
            )

        elif direction == "down":

            directional_fraction = float(
                np.mean(
                    differences <= 0
                )
            )

        else:

            directional_fraction = 0.0

        # ------------------------------------------------------
        # Level shift
        # ------------------------------------------------------

        recent_n = min(
            self.level_shift_window,
            n // 2,
        )

        older_start = (
            n
            - (
                recent_n * 2
            )
        )

        older_end = (
            n
            - recent_n
        )

        if older_start >= 0:

            older_values = (
                values[
                    older_start:
                    older_end
                ]
            )

            recent_values = (
                values[
                    older_end:
                ]
            )

            older_mean = float(
                np.mean(
                    older_values
                )
            )

            recent_mean = float(
                np.mean(
                    recent_values
                )
            )

            level_shift = (
                recent_mean
                - older_mean
            )

        else:

            older_mean = y_mean

            recent_mean = y_mean

            level_shift = 0.0

        # ------------------------------------------------------
        # Smoothed change
        # ------------------------------------------------------

        half = n // 2

        if half > 0:

            first_half_mean = float(
                np.mean(
                    values[:half]
                )
            )

            second_half_mean = float(
                np.mean(
                    values[-half:]
                )
            )

            smoothed_change = (
                second_half_mean
                - first_half_mean
            )

        else:

            smoothed_change = 0.0

        # ------------------------------------------------------
        # Ordinary trend
        # ------------------------------------------------------

        is_trend = bool(
            abs(slope)
            >= self.min_slope
            and
            abs(total_change)
            >= self.min_total_change
            and
            r_squared
            >= self.min_r_squared
        )

        return {
            "slope": slope,
            "total_change": total_change,
            "r_squared": r_squared,
            "direction": direction,
            "directional_fraction":
                directional_fraction,
            "is_trend": is_trend,

            "older_mean":
                older_mean,

            "recent_mean":
                recent_mean,

            "level_shift":
                level_shift,

            "smoothed_change":
                smoothed_change,
        }

    # ==========================================================
    # Window evaluation
    # ==========================================================

    def _evaluate_window(self):

        return self._calculate_window_metrics()

    # ==========================================================
    # Strong drift window
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

        directional_fraction = float(
            evidence["directional_fraction"]
        )

        level_shift = abs(
            float(evidence["level_shift"])
        )

        gradual_change = abs(
            float(evidence["total_change"])
        )

        return bool(
            slope >= strong_slope
            and
            total_change >= strong_change
            and
            r_squared >= strong_r_squared
            and
            directional_fraction >= 0.55
            and
            level_shift < 1.5
            and
            gradual_change < 4.5
        )

    # ==========================================================
    # Linear trend candidate
    # ==========================================================

    def _process_trend_candidate(
        self,
        evidence,
    ):

        is_trend = bool(
            evidence["is_trend"]
        )

        direction = (
            evidence["direction"]
        )

        # ------------------------------------------------------
        # Existing candidate
        # ------------------------------------------------------

        if self.candidate_active:

            if (
                is_trend
                and
                direction
                == self.candidate_direction
            ):

                gap = (
                    self.samples_seen
                    - self.candidate_last_sample
                )

                if (
                    gap
                    <= self.max_candidate_gap
                ):

                    self.candidate_windows += 1

                    self.candidate_last_sample = (
                        self.samples_seen
                    )

                    if (
                        self.candidate_windows
                        >= self.required_consecutive_windows
                    ):

                        return True

                else:

                    self._clear_trend_candidate()

            else:

                gap = (
                    self.samples_seen
                    - self.candidate_last_sample
                )

                if (
                    gap
                    > self.max_candidate_gap
                ):

                    self._clear_trend_candidate()

        # ------------------------------------------------------
        # Start candidate
        # ------------------------------------------------------

        elif is_trend:

            self.candidate_active = True

            self.candidate_direction = (
                direction
            )

            self.candidate_windows = 1

            self.candidate_start_sample = (
                self.samples_seen
            )

            self.candidate_last_sample = (
                self.samples_seen
            )

            if (
                self.candidate_windows
                >= self.required_consecutive_windows
            ):

                return True

        return False

    # ==========================================================
    # Level-shift window
    # ==========================================================

    def _is_level_shift_window(
        self,
        evidence,
    ):
        """
        Detect a sustained temperature regime shift.

        Requirements:

            - recent regime differs meaningfully from the
              preceding regime;
            - the broader smoothed movement agrees with the
              same direction;
            - the raw sequence has reasonable directional
              consistency.

        This deliberately rejects ordinary noisy fluctuations.
        """

        shift = float(
            evidence["level_shift"]
        )

        smoothed_change = float(
            evidence["smoothed_change"]
        )

        directional_fraction = float(
            evidence["directional_fraction"]
        )

        # ------------------------------------------------------
        # Minimum level movement
        # ------------------------------------------------------

        if (
            abs(shift)
            < self.min_level_shift
        ):

            return False

        # ------------------------------------------------------
        # Whole-window movement must agree
        # ------------------------------------------------------

        if (
            abs(smoothed_change)
            < self.min_level_shift
        ):

            return False

        # ------------------------------------------------------
        # Reject noisy/non-directional windows
        # ------------------------------------------------------

        if (
            directional_fraction
            < 0.58
        ):

            return False

        # ------------------------------------------------------
        # Same direction
        # ------------------------------------------------------

        if shift > 0:

            return (
                smoothed_change > 0
            )

        if shift < 0:

            return (
                smoothed_change < 0
            )

        return False

    # ==========================================================
    # Level-shift candidate
    # ==========================================================

    def _process_level_shift_candidate(
        self,
        evidence,
    ):

        is_shift = (
            self._is_level_shift_window(
                evidence
            )
        )

        # ------------------------------------------------------
        # Current window is not evidence
        # ------------------------------------------------------

        if not is_shift:

            if (
                self.level_shift_candidate_active
            ):

                gap = (
                    self.samples_seen
                    - self.level_shift_last_sample
                )

                if (
                    gap
                    > self.max_level_shift_gap
                ):

                    self._clear_level_shift_candidate()

            return False

        # ------------------------------------------------------
        # Determine direction
        # ------------------------------------------------------

        direction = (
            "up"
            if evidence["level_shift"] > 0
            else "down"
        )

        # ------------------------------------------------------
        # Start candidate
        # ------------------------------------------------------

        if not self.level_shift_candidate_active:

            self.level_shift_candidate_active = True

            self.level_shift_direction = (
                direction
            )

            self.level_shift_candidate_windows = 1

            self.level_shift_start_sample = (
                self.samples_seen
            )

            self.level_shift_last_sample = (
                self.samples_seen
            )

            return (
                self.level_shift_candidate_windows
                >= self.level_shift_required_windows
            )

        # ------------------------------------------------------
        # Direction changed
        # ------------------------------------------------------

        if (
            direction
            != self.level_shift_direction
        ):

            self._clear_level_shift_candidate()

            self.level_shift_candidate_active = True

            self.level_shift_direction = (
                direction
            )

            self.level_shift_candidate_windows = 1

            self.level_shift_start_sample = (
                self.samples_seen
            )

            self.level_shift_last_sample = (
                self.samples_seen
            )

            return False

        # ------------------------------------------------------
        # Check gap
        # ------------------------------------------------------

        gap = (
            self.samples_seen
            - self.level_shift_last_sample
        )

        if (
            gap
            > self.max_level_shift_gap
        ):

            self._clear_level_shift_candidate()

            return False

        # ------------------------------------------------------
        # Continue candidate
        # ------------------------------------------------------

        self.level_shift_candidate_windows += 1

        self.level_shift_last_sample = (
            self.samples_seen
        )

        return (
            self.level_shift_candidate_windows
            >= self.level_shift_required_windows
        )

    # ==========================================================
    # Candidate clearing
    # ==========================================================

    def _clear_trend_candidate(
        self,
    ):

        self.candidate_active = False

        self.candidate_direction = None

        self.candidate_windows = 0

        self.candidate_start_sample = None

        self.candidate_last_sample = None

    def _clear_level_shift_candidate(
        self,
    ):

        self.level_shift_candidate_active = False

        self.level_shift_direction = None

        self.level_shift_candidate_windows = 0

        self.level_shift_start_sample = None

        self.level_shift_last_sample = None

    # Compatibility with older code.
    def _clear_candidate(self):

        self._clear_trend_candidate()

    # ==========================================================
    # State
    # ==========================================================

    def get_state(self):

        return {
            "window_size":
                self.window_size,

            "min_slope":
                self.min_slope,

            "min_total_change":
                self.min_total_change,

            "min_r_squared":
                self.min_r_squared,

            "required_consecutive_windows":
                self.required_consecutive_windows,

            "evaluation_step":
                self.evaluation_step,

            "sample_count":
                self.samples_seen,

            "history_size":
                len(
                    self.temperature_history
                ),

            "drift_confirmed":
                self.drift_confirmed,

            "candidate_active":
                self.candidate_active,

            "candidate_direction":
                self.candidate_direction,

            "candidate_windows":
                self.candidate_windows,

            "level_shift_candidate_active":
                self.level_shift_candidate_active,

            "level_shift_direction":
                self.level_shift_direction,

            "level_shift_candidate_windows":
                self.level_shift_candidate_windows,

            "level_shift_window":
                self.level_shift_window,

            "min_level_shift":
                self.min_level_shift,

            "consecutive_windows":
                self.candidate_windows,

            "consecutive_trend_windows":
                self.candidate_windows,

            "direction":
                self.last_direction,

            "slope":
                self.last_slope,

            "total_change":
                self.last_total_change,

            "r_squared":
                self.last_r_squared,

            "directional_fraction":
                self.last_directional_fraction,

            "is_trend":
                self.last_is_trend,

            "is_drift":
                self.last_is_drift,

            "validation_windows":
                self.validation_windows,

            "validation_complete":
                self.validation_complete,

            "evidence_history_size":
                len(
                    self.evidence_history
                ),
        }

    # ==========================================================
    # Result contract
    # ==========================================================

    def _build_result(
        self,
        is_drift,
    ):

        if is_drift:

            state = (
                "drift_confirmed"
            )

        elif self.candidate_active:

            state = (
                "trend_candidate"
            )

        elif (
            self.level_shift_candidate_active
        ):

            state = (
                "level_shift_candidate"
            )

        else:

            state = "monitoring"

        return {
            "is_drift":
                bool(is_drift),

            "state":
                state,

            "direction":
                self.last_direction,

            "slope":
                float(
                    self.last_slope
                ),

            "total_change":
                float(
                    self.last_total_change
                ),

            "r_squared":
                float(
                    self.last_r_squared
                ),

            "directional_fraction":
                float(
                    self.last_directional_fraction
                ),

            "is_trend":
                bool(
                    self.last_is_trend
                ),

            "drift_confirmed":
                bool(
                    self.drift_confirmed
                ),

            "consecutive_windows":
                int(
                    self.candidate_windows
                ),

            "consecutive_trend_windows":
                int(
                    self.candidate_windows
                ),

            "level_shift_candidate_windows":
                int(
                    self.level_shift_candidate_windows
                ),

            "sample_count":
                int(
                    self.samples_seen
                ),
        }

    # ==========================================================
    # Reset
    # ==========================================================

    def reset(self):

        self.temperature_history.clear()

        self.samples_seen = 0

        self.samples_since_evaluation = 0

        self.last_direction = None

        self.last_slope = 0.0

        self.last_total_change = 0.0

        self.last_r_squared = 0.0

        self.last_directional_fraction = 0.0

        self.last_is_trend = False

        self.last_is_drift = False

        self._clear_trend_candidate()

        self._clear_level_shift_candidate()

        self.drift_confirmed = False

        self.validation_windows = 0

        self.validation_complete = False

        self.evidence_history.clear()

    # ==========================================================
    # Compatibility alias
    # ==========================================================

    def update_temperature(
        self,
        temperature,
    ):

        return self.update(
            temperature
        )