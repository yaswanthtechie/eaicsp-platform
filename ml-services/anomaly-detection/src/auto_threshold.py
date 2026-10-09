"""
Milestone 2 - self-adjusting anomaly thresholds, gated by significance tests.

STANDALONE. Depends only on numpy and scipy (scipy is already installed
as a scikit-learn dependency). It does not import or modify
AdaptiveEngine, AdaptiveThreshold or any other framework.

Score convention (same as the whole project):

    score = -model.score(features)      higher = more anomalous
    score >= threshold                  -> anomaly

Problem with a plain rolling percentile: it moves on every noisy
window. With large windows, a significance test alone also fires on
trivial shifts. This tuner only moves the threshold when ALL of these
hold for a window of (assumed mostly normal) scores:

    1. SHIFT      two-sample KS test vs the trusted reference is
                  significant (p < alpha) AND the median moved at least
                  `min_effect` robust sigmas (statistical AND practical
                  significance).
    2. STABLE     the window is internally stable: first half vs second
                  half KS is not significant and there is no monotonic
                  trend (Spearman). A trending window is DRIFT: freeze.
    3. CONFIRMED  `confirm_windows` consecutive windows pass 1 and 2
                  (false-adaptation rate is about alpha ** confirm).
    4. MATERIAL   the current threshold lies OUTSIDE the bootstrap
                  confidence interval of the new percentile estimate.

Safety, in line with the recall-first / cost-based project policy
(a missed anomaly costs 500, a false alarm costs 2):

    - Extreme points are trimmed from a window before it is trusted, so
      spikes cannot contaminate the baseline.
    - Raising the threshold (loses recall) is capped tighter than
      lowering it (gains recall).
    - A capped move keeps converging toward the new regime's percentile
      over later stable windows (each step still capped).
    - After a drift window the tuner holds for `drift_cooldown_windows`
      and abandons any outstanding target.
"""

import numpy as np
from scipy import stats


# Same per-model percentiles the project already validated for the
# adaptive layer. Duplicated on purpose to keep this module standalone.
DEFAULT_PERCENTILES = {
    "iforest": 98.0,
    "lof": 97.0,
    "ocsvm": 97.0,
}


def robust_scale(values):
    """MAD-based sigma, falling back to IQR then std."""

    values = np.asarray(values, dtype=float)

    mad = np.median(np.abs(values - np.median(values)))

    if mad > 1e-12:
        return float(1.4826 * mad)

    q25, q75 = np.percentile(values, [25, 75])

    if (q75 - q25) > 1e-12:
        return float((q75 - q25) / 1.349)

    std = float(np.std(values))

    return std if std > 1e-12 else 1e-12


class SignificanceThresholdTuner:
    """
    Auto-tuning threshold with statistical gating.

    Typical use:

        tuner = SignificanceThresholdTuner(calibration_scores,
                                           percentile=97.0)

        result = tuner.evaluate_window(window_scores)
        tuner.threshold           # current threshold
        result["action"]          # hold | candidate | adapt | freeze
    """

    def __init__(
        self,
        reference_scores,
        percentile=97.0,
        alpha=0.01,
        window_size=200,
        min_window=30,
        min_effect=0.5,
        confirm_windows=2,
        trim_sigma=6.0,
        min_trend_rho=0.30,
        max_raise_sigma=1.0,
        max_lower_sigma=2.0,
        drift_cooldown_windows=2,
        n_bootstrap=500,
        confidence=0.95,
        max_reference=1000,
        seed=42,
    ):
        reference = np.asarray(reference_scores, dtype=float).reshape(-1)
        reference = reference[np.isfinite(reference)]

        if reference.size < min_window:
            raise ValueError(
                f"reference_scores needs at least {min_window} finite values."
            )

        if not 0 < percentile < 100:
            raise ValueError("percentile must be between 0 and 100.")

        if not 0 < alpha < 1:
            raise ValueError("alpha must be between 0 and 1.")

        if min_window < 10 or window_size < min_window:
            raise ValueError("window_size must be >= min_window >= 10.")

        if confirm_windows < 1:
            raise ValueError("confirm_windows must be at least 1.")

        if min_effect < 0 or max_raise_sigma <= 0 or max_lower_sigma <= 0:
            raise ValueError("effect and step limits must be positive.")

        self.percentile = float(percentile)
        self.alpha = float(alpha)
        self.window_size = int(window_size)
        self.min_window = int(min_window)
        self.min_effect = float(min_effect)
        self.confirm_windows = int(confirm_windows)
        self.trim_sigma = float(trim_sigma)
        self.min_trend_rho = float(min_trend_rho)
        self.max_raise_sigma = float(max_raise_sigma)
        self.max_lower_sigma = float(max_lower_sigma)
        self.drift_cooldown_windows = int(drift_cooldown_windows)
        self.n_bootstrap = int(n_bootstrap)
        self.confidence = float(confidence)
        self.max_reference = int(max_reference)

        self._rng = np.random.default_rng(seed)

        # Initial threshold uses the FULL calibration set; only the
        # rolling reference used for later tests is truncated.
        self.initial_threshold = float(
            np.percentile(reference, self.percentile)
        )

        self.reference = reference[-self.max_reference:]
        self.reference_scale = robust_scale(self.reference)
        self.threshold = self.initial_threshold

        self._pending = []
        self._cooldown = 0
        self._buffer = []
        self._target = None

        self.windows_seen = 0
        self.adaptations = 0
        self.freezes = 0
        self.refinements = 0
        self.history = []

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _trim(self, window):
        """Drop extreme points relative to the window's own spread."""

        centre = np.median(window)
        limit = self.trim_sigma * robust_scale(window)

        kept = window[np.abs(window - centre) <= limit]

        return kept, int(window.size - kept.size)

    def _bootstrap_ci(self, values):
        """Bootstrap CI of the configured percentile."""

        idx = self._rng.integers(
            0, values.size, size=(self.n_bootstrap, values.size)
        )

        estimates = np.percentile(values[idx], self.percentile, axis=1)

        tail = (1.0 - self.confidence) / 2.0 * 100.0

        low, high = np.percentile(estimates, [tail, 100.0 - tail])

        return float(low), float(high)

    def _stability(self, values):
        """Return (unstable, diagnostics) for an ordered window."""

        half = values.size // 2

        halves_p = float(stats.ks_2samp(values[:half], values[half:]).pvalue)

        rho, trend_p = stats.spearmanr(np.arange(values.size), values)

        rho = float(rho)
        trend_p = float(trend_p)

        unstable = halves_p < self.alpha or (
            trend_p < self.alpha and abs(rho) >= self.min_trend_rho
        )

        return unstable, {
            "halves_p": halves_p,
            "trend_rho": rho,
            "trend_p": trend_p,
        }

    def _converge(self, trimmed, diagnostics):
        """
        Finish a capped move. After an adaptation the reference already
        matches the new regime, so windows no longer test as 'shifted'.
        While a target is outstanding and the window is stable, keep
        stepping (still capped) toward the percentile of the new regime.
        """

        unstable, stability = self._stability(trimmed)

        if unstable:
            return None

        candidate = float(np.percentile(trimmed, self.percentile))

        new_threshold = float(self._limit_step(candidate))

        if abs(new_threshold - self.threshold) < 1e-12:
            self._target = None
            return None

        previous = self.threshold
        self.threshold = new_threshold

        self._target = (
            None if abs(new_threshold - candidate) < 1e-12 else candidate
        )

        self.refinements += 1

        return self._result(
            "adapt",
            "converging_to_target",
            previous_threshold=previous,
            candidate_threshold=candidate,
            **diagnostics,
            **stability,
        )

    def _limit_step(self, candidate):
        """Cap the move; raising is capped tighter than lowering."""

        delta = candidate - self.threshold

        if delta > 0:
            delta = min(delta, self.max_raise_sigma * self.reference_scale)
        else:
            delta = max(delta, -self.max_lower_sigma * self.reference_scale)

        return self.threshold + delta

    def _result(self, action, reason, **extra):
        result = {
            "window": self.windows_seen,
            "action": action,
            "reason": reason,
            "threshold": self.threshold,
            "pending_windows": len(self._pending),
        }

        result.update(extra)

        self.history.append(result)

        return result

    # ------------------------------------------------------------
    # Core
    # ------------------------------------------------------------

    def evaluate_window(self, scores):
        """Evaluate one window of scores and (maybe) move the threshold."""

        window = np.asarray(scores, dtype=float).reshape(-1)

        if not np.all(np.isfinite(window)):
            raise ValueError("scores must be finite.")

        if window.size < self.min_window:
            raise ValueError(
                f"window needs at least {self.min_window} scores."
            )

        self.windows_seen += 1

        trimmed, n_trimmed = self._trim(window)

        if self._cooldown > 0:
            self._cooldown -= 1
            self._pending = []

            return self._result(
                "hold", "drift_cooldown", n_trimmed=n_trimmed
            )

        # 1. SHIFT: statistical AND practical significance.

        ks_p = float(stats.ks_2samp(self.reference, trimmed).pvalue)

        effect = float(
            abs(np.median(trimmed) - np.median(self.reference))
            / self.reference_scale
        )

        diagnostics = {
            "ks_p": ks_p,
            "effect_sigma": effect,
            "n_trimmed": n_trimmed,
        }

        if ks_p >= self.alpha or effect < self.min_effect:
            self._pending = []

            if self._target is not None:
                converged = self._converge(trimmed, diagnostics)

                if converged is not None:
                    return converged

            return self._result("hold", "no_significant_shift", **diagnostics)

        # 2. STABLE vs DRIFT.

        unstable, stability = self._stability(trimmed)

        diagnostics.update(stability)

        if unstable:
            self._pending = []
            self._cooldown = self.drift_cooldown_windows
            self._target = None
            self.freezes += 1

            return self._result("freeze", "unstable_or_trending", **diagnostics)

        # 3. CONFIRMED over consecutive windows.

        self._pending.append(trimmed)

        if len(self._pending) < self.confirm_windows:
            return self._result("candidate", "awaiting_confirmation", **diagnostics)

        pooled = np.concatenate(self._pending)

        # 4. MATERIAL: current threshold outside the CI of the new estimate.

        ci_low, ci_high = self._bootstrap_ci(pooled)

        candidate = float(np.percentile(pooled, self.percentile))

        diagnostics.update(
            candidate_threshold=candidate, ci_low=ci_low, ci_high=ci_high
        )

        if ci_low <= self.threshold <= ci_high:
            self._pending = []

            return self._result("hold", "threshold_within_ci", **diagnostics)

        previous = self.threshold

        self.threshold = float(self._limit_step(candidate))

        self.reference = pooled[-self.max_reference:]
        self.reference_scale = robust_scale(self.reference)

        self._pending = []
        self._target = (
            None if abs(self.threshold - candidate) < 1e-12 else candidate
        )
        self.adaptations += 1

        return self._result(
            "adapt",
            "confirmed_stable_shift",
            previous_threshold=previous,
            **diagnostics,
        )

    def observe(self, score):
        """Streaming helper: buffer scores, evaluate when a window fills."""

        score = float(score)

        if not np.isfinite(score):
            raise ValueError("score must be finite.")

        self._buffer.append(score)

        if len(self._buffer) < self.window_size:
            return None

        window, self._buffer = self._buffer, []

        return self.evaluate_window(window)

    def is_anomaly(self, score):
        """Project rule: score >= threshold."""

        return bool(float(score) >= self.threshold)

    def get_state(self):
        return {
            "threshold": self.threshold,
            "initial_threshold": self.initial_threshold,
            "percentile": self.percentile,
            "windows_seen": self.windows_seen,
            "adaptations": self.adaptations,
            "freezes": self.freezes,
            "refinements": self.refinements,
            "pending_windows": len(self._pending),
            "cooldown": self._cooldown,
            "reference_size": int(self.reference.size),
            "reference_scale": self.reference_scale,
        }