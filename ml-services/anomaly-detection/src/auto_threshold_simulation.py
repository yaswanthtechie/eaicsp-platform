"""
Reproducible synthetic checks for the auto-tuning threshold.

Every simulation figure quoted in the README comes from this script.
Pure numpy: no models or data files needed.

Run from ml-services/anomaly-detection:

    python -m src.auto_threshold_simulation
"""

import numpy as np

from src.auto_threshold import SignificanceThresholdTuner

TRIALS = 40
WINDOW = 200


def _normal(rng, loc=0.0, n=WINDOW):
    return rng.normal(loc, 1.0, n)


def _tuner(trial):
    ref = np.random.default_rng(1000 + trial).normal(0.0, 1.0, 2000)

    return SignificanceThresholdTuner(ref, percentile=97.0)


def stable_no_change():
    """No change in the data: the threshold must not move."""

    moves = freezes = windows = 0

    for t in range(TRIALS):
        tuner, rng = _tuner(t), np.random.default_rng(5000 + t)

        for _ in range(25):
            tuner.evaluate_window(_normal(rng))
            windows += 1

        moves += tuner.adaptations + tuner.refinements
        freezes += tuner.freezes

    return {"windows": windows, "threshold_moves": moves, "freezes": freezes}


def real_regime_shift():
    """Stable +2 sigma shift: should adapt."""

    adapted = 0

    for t in range(TRIALS):
        tuner, rng = _tuner(t), np.random.default_rng(9000 + t)

        for _ in range(6):
            tuner.evaluate_window(_normal(rng, loc=2.0))

        adapted += tuner.adaptations > 0

    return {"trials": TRIALS, "adapted": int(adapted)}


def in_window_drift():
    """Trend inside one window: should freeze."""

    frozen = 0

    for t in range(TRIALS):
        tuner, rng = _tuner(t), np.random.default_rng(7000 + t)

        result = tuner.evaluate_window(
            _normal(rng) + np.linspace(0.0, 5.0, WINDOW)
        )

        frozen += result["action"] == "freeze"

    return {"trials": TRIALS, "frozen": int(frozen)}


def slow_cross_window_drift(warmup_windows):
    """
    Each window flat, medians climb 0.4 sigma per window: not learned.

    warmup_windows = normal windows seen before the drift starts. The
    cross-window guard needs 3 windows of history, so 0 is the cold-start
    case (drift begins in the tuner's first windows).
    """

    learned = 0

    for t in range(TRIALS):
        tuner, rng = _tuner(t), np.random.default_rng(3000 + t)

        for _ in range(warmup_windows):
            tuner.evaluate_window(_normal(rng))

        for k in range(12):
            tuner.evaluate_window(_normal(rng, loc=0.4 * (k + 1)))

        learned += tuner.adaptations > 0

    return {"trials": TRIALS, "learned_as_normal": int(learned)}
def contaminated_windows(fraction):
    """Normal readings mixed with a cluster of anomalies: not learned."""

    learned = 0

    for t in range(TRIALS):
        tuner, rng = _tuner(t), np.random.default_rng(1500 + t)

        for _ in range(10):
            n_bad = int(WINDOW * fraction)

            window = np.concatenate(
                [_normal(rng, n=WINDOW - n_bad), rng.normal(6.0, 0.5, n_bad)]
            )
            rng.shuffle(window)

            tuner.evaluate_window(window)

        learned += tuner.adaptations > 0

    return {"trials": TRIALS, "learned_as_normal": int(learned)}


def main():
    print("Auto-threshold synthetic simulation (reproducible)")
    print("==================================================")

    checks = [
        ("no change (should not move)", stable_no_change()),
        ("stable +2 sigma shift (should adapt)", real_regime_shift()),
        ("drift inside a window (should freeze)", in_window_drift()),
        ("slow drift, cold start, 0 warm-up windows (weak spot)", slow_cross_window_drift(0)),
        ("slow drift, running tuner, 3 warm-up windows (should not learn)", slow_cross_window_drift(3)),
        ("20% anomalous windows (should not learn)", contaminated_windows(0.2)),
        ("50% anomalous windows (should not learn)", contaminated_windows(0.5)),
    ]

    for name, result in checks:
        print(f"\n{name}\n  {result}")


if __name__ == "__main__":
    main()