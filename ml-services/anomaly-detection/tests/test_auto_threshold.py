"""
Milestone 2 - significance-gated auto-tuning thresholds.

Pure synthetic scores: fast, deterministic, no models required.
"""

import numpy as np
import pytest

from src.auto_threshold import SignificanceThresholdTuner, robust_scale


def _scores(n, loc=0.0, scale=1.0, seed=0):
    return np.random.default_rng(seed).normal(loc, scale, n)


@pytest.fixture
def tuner():
    return SignificanceThresholdTuner(_scores(2000, seed=1), percentile=97.0)


def test_starts_at_reference_percentile(tuner):
    expected = np.percentile(_scores(2000, seed=1), 97.0)

    assert tuner.threshold == pytest.approx(expected)
    assert tuner.initial_threshold == tuner.threshold


def test_same_distribution_never_moves_the_threshold(tuner):
    start = tuner.threshold

    for seed in range(10, 30):
        result = tuner.evaluate_window(_scores(200, seed=seed))

        assert result["action"] == "hold"

    assert tuner.threshold == start
    assert tuner.adaptations == 0


def test_one_shifted_window_is_only_a_candidate(tuner):
    start = tuner.threshold

    result = tuner.evaluate_window(_scores(200, loc=3.0, seed=2))

    assert result["action"] == "candidate"
    assert tuner.threshold == start


def test_confirmed_stable_shift_adapts_upward_with_capped_step(tuner):
    start = tuner.threshold
    scale = tuner.reference_scale

    tuner.evaluate_window(_scores(200, loc=3.0, seed=3))
    result = tuner.evaluate_window(_scores(200, loc=3.0, seed=4))

    assert result["action"] == "adapt"
    assert tuner.threshold > start
    assert tuner.threshold - start <= tuner.max_raise_sigma * scale + 1e-9
    assert tuner.adaptations == 1


def test_downward_shift_may_move_further_than_upward():
    tuner = SignificanceThresholdTuner(_scores(2000, seed=1))
    start = tuner.threshold
    scale = tuner.reference_scale

    tuner.evaluate_window(_scores(200, loc=-4.0, seed=5))
    tuner.evaluate_window(_scores(200, loc=-4.0, seed=6))

    moved = start - tuner.threshold

    assert moved > tuner.max_raise_sigma * scale
    assert moved <= tuner.max_lower_sigma * scale + 1e-9


def test_trending_window_is_frozen_as_drift(tuner):
    start = tuner.threshold

    drifting = _scores(200, seed=7) + np.linspace(0.0, 6.0, 200)

    result = tuner.evaluate_window(drifting)

    assert result["action"] == "freeze"
    assert tuner.threshold == start
    assert tuner.freezes == 1


def test_cooldown_holds_after_drift(tuner):
    tuner.evaluate_window(_scores(200, seed=8) + np.linspace(0, 6, 200))

    result = tuner.evaluate_window(_scores(200, loc=3.0, seed=9))

    assert result["reason"] == "drift_cooldown"


def test_spikes_do_not_contaminate_the_baseline(tuner):
    window = _scores(200, seed=11)
    window[:5] = 500.0

    result = tuner.evaluate_window(window)

    assert result["n_trimmed"] >= 5
    assert result["action"] == "hold"


def test_step_cap_means_threshold_never_jumps_to_the_candidate(tuner):
    start = tuner.threshold
    cap = tuner.max_raise_sigma * tuner.reference_scale

    tuner.evaluate_window(_scores(200, loc=20.0, seed=12))
    tuner.evaluate_window(_scores(200, loc=20.0, seed=13))

    assert 0 < tuner.threshold - start <= cap + 1e-9


def test_capped_move_converges_to_the_new_regime_percentile(tuner):
    target = np.percentile(_scores(200000, loc=3.0, seed=99), 97.0)

    for seed in range(100, 112):
        tuner.evaluate_window(_scores(200, loc=3.0, seed=seed))

    # Not stuck after the first capped step.
    assert tuner.refinements >= 1
    assert abs(tuner.threshold - target) < 0.5


def test_convergence_never_exceeds_the_step_cap_per_window(tuner):
    previous = tuner.threshold

    for seed in range(120, 132):
        cap = tuner.max_raise_sigma * tuner.reference_scale

        tuner.evaluate_window(_scores(200, loc=3.0, seed=seed))

        assert tuner.threshold - previous <= cap + 1e-9

        previous = tuner.threshold


def test_drift_after_adaptation_stops_convergence(tuner):
    tuner.evaluate_window(_scores(200, loc=3.0, seed=140))
    tuner.evaluate_window(_scores(200, loc=3.0, seed=141))

    frozen_at = tuner.threshold

    tuner.evaluate_window(
        _scores(200, loc=3.0, seed=142) + np.linspace(0.0, 6.0, 200)
    )

    for seed in range(143, 145):
        tuner.evaluate_window(_scores(200, loc=3.0, seed=seed))

    assert tuner.freezes >= 1
    assert tuner.threshold == frozen_at

def test_observe_buffers_until_a_window_is_full():
    tuner = SignificanceThresholdTuner(
        _scores(1000, seed=1), window_size=50
    )

    outputs = [tuner.observe(s) for s in _scores(50, seed=14)]

    assert all(o is None for o in outputs[:-1])
    assert outputs[-1]["action"] == "hold"


def test_is_anomaly_uses_greater_or_equal(tuner):
    assert tuner.is_anomaly(tuner.threshold) is True
    assert tuner.is_anomaly(tuner.threshold - 1e-6) is False


def test_validation():
    ref = _scores(100)

    with pytest.raises(ValueError):
        SignificanceThresholdTuner(_scores(5))

    with pytest.raises(ValueError):
        SignificanceThresholdTuner(ref, percentile=100)

    with pytest.raises(ValueError):
        SignificanceThresholdTuner(ref, alpha=0)

    with pytest.raises(ValueError):
        SignificanceThresholdTuner(ref).evaluate_window(_scores(5))

    with pytest.raises(ValueError):
        SignificanceThresholdTuner(ref).evaluate_window(
            np.array([np.nan] * 50)
        )


def test_robust_scale_is_never_zero():
    assert robust_scale(np.ones(20)) > 0