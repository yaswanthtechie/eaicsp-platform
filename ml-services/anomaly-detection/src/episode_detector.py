"""
Episode detector: turns per-reading anomaly flags into episodes.

Pure logic. No Kafka, no InfluxDB, no model. Time is the simulated
(or sensor) timestamp passed in with each reading.

Score convention (same as the project): higher = more anomalous,
score >= threshold -> flagged.

Rules:
  - Flags from one sensor are grouped while each new flag arrives
    within `gap` of the previous flag (exactly `gap` still joins).
  - An episode is CONFIRMED when it has min_flagged_readings flags,
    or when any reading is severe:
        score >= threshold + severe_margin * scale
  - An episode closes when a later reading arrives more than `gap`
    after its last flag (closed_by="quiet"), or at flush()
    (closed_by="shutdown").
  - Only confirmed episodes are returned. Unconfirmed candidates are
    dropped and counted in `dropped_candidates`.
"""

from datetime import timedelta
import math


class EpisodeDetector:

    def __init__(
        self,
        gap,
        scale,
        min_flagged_readings=2,
        severe_margin=3.0,
    ):
        if not isinstance(gap, timedelta) or gap <= timedelta(0):
            raise ValueError("gap must be a positive timedelta.")

        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("scale must be a positive finite number.")

        if (
            isinstance(min_flagged_readings, bool)
            or not isinstance(min_flagged_readings, int)
            or min_flagged_readings < 1
        ):
            raise ValueError("min_flagged_readings must be an integer >= 1.")

        if not math.isfinite(severe_margin) or severe_margin < 0:
            raise ValueError("severe_margin must be a finite number >= 0.")

        self.gap = gap
        self.scale = float(scale)
        self.min_flagged_readings = min_flagged_readings
        self.severe_margin = float(severe_margin)

        self._state = {}
        self._last_seen = {}

        self.dropped_candidates = 0
        self.episodes_emitted = 0

    # ------------------------------------------------------------

    def is_active(self, sensor_id):
        """True while the sensor has a candidate or open episode."""

        return sensor_id in self._state

    def accepts(self, sensor_id, timestamp):
        """False for a duplicate or late reading (same or earlier timestamp)."""

        last = self._last_seen.get(sensor_id)

        return last is None or timestamp > last

    def has_open_state(self):
        """True while any sensor has a candidate or open episode."""

        return bool(self._state)

    def _is_severe(self, score, threshold):
        return score >= threshold + self.severe_margin * self.scale

    def _close(self, sensor_id, closed_by):
        """Remove the sensor's state. Return the episode or None."""

        state = self._state.pop(sensor_id)

        if state["confirmed_time"] is None:
            self.dropped_candidates += 1
            return None

        self.episodes_emitted += 1

        return {
            "sensor_id": sensor_id,
            "window_start": state["first_flag_time"],
            "window_end": state["last_flag_time"],
            "first_flag_time": state["first_flag_time"],
            "confirmed_time": state["confirmed_time"],
            "peak_time": state["peak_time"],
            "peak_score": state["peak_score"],
            "threshold": state["peak_threshold"],
            "n_flagged": state["n_flagged"],
            "severe": state["severe"],
            "closed_by": closed_by,
            "peak_reading": state["peak_reading"],
        }

    # ------------------------------------------------------------

    def process(
        self,
        sensor_id,
        timestamp,
        score,
        threshold,
        reading=None,
    ):
        """
        Process one reading. Return a closed episode dict, or None.

        Call this for EVERY reading (flagged or not), in time order
        per sensor, so quiet periods can close episodes.
        """

        score = float(score)
        threshold = float(threshold)

        if not math.isfinite(score) or not math.isfinite(threshold):
            raise ValueError("score and threshold must be finite.")

        last = self._last_seen.get(sensor_id)

        if last is not None and timestamp <= last:
            raise ValueError(
                f"Duplicate or out-of-order reading for {sensor_id}: "
                f"{timestamp} is not after {last}."
            )

        self._last_seen[sensor_id] = timestamp

        closed = None
        state = self._state.get(sensor_id)

        if (
            state is not None
            and timestamp - state["last_flag_time"] > self.gap
        ):
            closed = self._close(sensor_id, "quiet")
            state = None

        if score < threshold:
            return closed

        severe = self._is_severe(score, threshold)

        if state is None:
            state = {
                "first_flag_time": timestamp,
                "last_flag_time": timestamp,
                "confirmed_time": None,
                "n_flagged": 0,
                "severe": False,
                "peak_score": score,
                "peak_time": timestamp,
                "peak_threshold": threshold,
                "peak_reading": reading,
            }

            self._state[sensor_id] = state

        state["last_flag_time"] = timestamp
        state["n_flagged"] += 1
        state["severe"] = state["severe"] or severe

        if score > state["peak_score"]:
            state["peak_score"] = score
            state["peak_time"] = timestamp
            state["peak_threshold"] = threshold
            state["peak_reading"] = reading

        if state["confirmed_time"] is None and (
            state["n_flagged"] >= self.min_flagged_readings or severe
        ):
            state["confirmed_time"] = timestamp

        return closed

    def flush(self):
        """
        Close everything at shutdown. Confirmed episodes are returned
        with closed_by="shutdown". Unconfirmed candidates are dropped.
        """

        episodes = []

        for sensor_id in sorted(self._state):
            episode = self._close(sensor_id, "shutdown")

            if episode is not None:
                episodes.append(episode)

        return episodes