import numpy as np
import pytest

from src.regime_detector import RegimeDetector


# ============================================================
# Purpose
# ============================================================
#
# These are REAL-DATA integration tests.
#
# They verify that:
#
#     real ML model
#          ↓
#     real anomaly scores
#          ↓
#     RegimeDetector
#
# behaves correctly.
#
# Unit-level detector behavior belongs in:
#
#     tests/test_regime_detector.py
#
# This file should NOT duplicate those tests.
#
# The tests here deliberately avoid requiring every model
# to produce identical confirmation timing because IF, LOF,
# and OCSVM naturally produce different score distributions.
# ============================================================


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


# ============================================================
# Detector configuration
# ============================================================

CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]

BASELINE_SIZE = 100

SHIFT_SIGMA = 1.5

STABILITY_TOLERANCE = 0.20

MIN_STABLE_BLOCKS = 2


# ============================================================
# Helpers
# ============================================================

def create_detector():
    """
    Create a detector using the production-style
    regime configuration used by the integration tests.
    """

    return RegimeDetector(
        candidate_sizes=CANDIDATE_SIZES,
        baseline_size=BASELINE_SIZE,
        shift_sigma=SHIFT_SIGMA,
        stability_tolerance=STABILITY_TOLERANCE,
        min_stable_blocks=MIN_STABLE_BLOCKS,
    )


def finite(scores):
    """
    Keep only finite real model scores.
    """

    scores = np.asarray(
        scores,
        dtype=float,
    )

    return scores[
        np.isfinite(scores)
    ]


def initialize(
    detector,
    scores,
):
    """
    Initialize from a trusted portion of the
    real calibration scores.
    """

    scores = finite(scores)

    assert len(scores) >= BASELINE_SIZE

    detector.initialize(
        scores[
            :BASELINE_SIZE
        ]
    )


def observe_stream(
    detector,
    scores,
):
    """
    Feed a real score stream into the detector.
    """

    results = []

    for score in finite(scores):

        results.append(
            detector.observe(
                float(score)
            )
        )

    return results


def state(detector):
    return detector.get_state()


# ============================================================
# 1. Real model-score sanity
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_calibration_scores_are_available(
    model_name,
    model_calibration_scores,
):
    """
    Every supported model must produce a usable
    real calibration score stream.
    """

    scores = finite(
        model_calibration_scores
    )

    assert len(scores) >= BASELINE_SIZE

    assert np.all(
        np.isfinite(scores)
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_seasonal_scores_are_available(
    model_name,
    seasonal_scores,
):
    """
    Every model must be able to score the real
    seasonal dataset.
    """

    scores = finite(
        seasonal_scores
    )

    assert len(scores) > 0

    assert np.all(
        np.isfinite(scores)
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_drift_scores_are_available(
    model_name,
    drift_scores,
):
    """
    Every model must be able to score the real
    temperature-drift dataset.
    """

    scores = finite(
        drift_scores
    )

    assert len(scores) > 0

    assert np.all(
        np.isfinite(scores)
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_spike_scores_are_available(
    model_name,
    spike_scores,
):
    """
    Every model must be able to score the real
    temperature-spike dataset.
    """

    scores = finite(
        spike_scores
    )

    assert len(scores) > 0

    assert np.all(
        np.isfinite(scores)
    )


# ============================================================
# 2. Real calibration → regime detector
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_model_calibration_initializes_detector(
    model_name,
    model_calibration_scores,
):
    """
    Real calibration scores must create a trusted
    baseline inside the regime detector.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    current = state(
        detector
    )

    assert (
        current[
            "baseline_sample_count"
        ]
        == BASELINE_SIZE
    )

    assert (
        current[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        current[
            "candidate_observations"
        ]
        == 0
    )

    assert (
        current[
            "regime_confirmed"
        ]
        is False
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_calibration_baseline_statistics_are_valid(
    model_name,
    model_calibration_scores,
):
    """
    The baseline calculated from real model scores
    must have valid statistics.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    statistics = state(
        detector
    )[
        "baseline_statistics"
    ]

    assert statistics is not None

    assert np.isfinite(
        statistics["mean"]
    )

    assert np.isfinite(
        statistics["std"]
    )

    assert (
        statistics["std"] >= 0
    )


# ============================================================
# 3. Real seasonal data
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_seasonal_stream_does_not_immediately_confirm(
    model_name,
    model_calibration_scores,
    seasonal_scores,
):
    """
    Seasonal normal data should not cause an immediate
    regime confirmation simply because the distribution
    differs somewhat from calibration.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    results = observe_stream(
        detector,
        seasonal_scores[
            :200
        ],
    )

    assert len(
        results
    ) > 0

    assert not any(
        result[
            "regime_confirmed"
        ]
        for result in results
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_seasonal_stream_preserves_trusted_baseline(
    model_name,
    model_calibration_scores,
    seasonal_scores,
):
    """
    Merely observing seasonal data must not silently
    overwrite the trusted baseline.

    Acceptance is a separate explicit lifecycle action.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    before = state(
        detector
    )

    observe_stream(
        detector,
        seasonal_scores[
            :200
        ],
    )

    after = state(
        detector
    )

    assert (
        after[
            "baseline_sample_count"
        ]
        == before[
            "baseline_sample_count"
        ]
    )

    assert (
        after[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            before[
                "baseline_statistics"
            ]["mean"]
        )
    )


# ============================================================
# 4. Real temperature drift
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_temperature_drift_produces_shift_evidence(
    model_name,
    model_calibration_scores,
    drift_scores,
):
    """
    The real temperature-drift dataset should provide
    evidence that the score distribution has moved.

    We do NOT require every model to confirm a regime.
    The purpose here is to verify that the detector sees
    the sustained change rather than silently treating all
    drift observations as ordinary baseline observations.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    results = observe_stream(
        detector,
        drift_scores,
    )

    assert len(
        results
    ) > 0

    assert any(
        result[
            "shift_detected"
        ]
        for result in results
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_temperature_drift_can_build_candidate(
    model_name,
    model_calibration_scores,
    drift_scores,
):
    """
    A sustained real drift should be capable of building
    a candidate regime.

    We intentionally do not require confirmation here.
    Confirmation is a stronger condition than candidate
    formation.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    results = observe_stream(
        detector,
        drift_scores,
    )

    assert any(
        result[
            "candidate_started"
        ]
        for result in results
    )


# ============================================================
# 5. Real spike data
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_temperature_spikes_do_not_modify_baseline(
    model_name,
    model_calibration_scores,
    spike_scores,
):
    """
    Short-lived anomaly spikes must not automatically
    become the trusted baseline.
    """

    detector = create_detector()

    initialize(
        detector,
        model_calibration_scores,
    )

    before = state(
        detector
    )

    observe_stream(
        detector,
        spike_scores,
    )

    after = state(
        detector
    )

    assert (
        after[
            "baseline_sample_count"
        ]
        == before[
            "baseline_sample_count"
        ]
    )

    assert (
        after[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            before[
                "baseline_statistics"
            ]["mean"]
        )
    )


# ============================================================
# 6. Real calibration and seasonal score scales
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_each_model_uses_its_own_real_score_distribution(
    model_name,
    all_calibration_scores,
):
    """
    IF, LOF and OCSVM scores have different numerical scales.

    The detector therefore has to operate on each model's
    own score distribution rather than assuming a universal
    anomaly-score range.
    """

    scores = finite(
        all_calibration_scores[
            model_name
        ]
    )

    assert len(scores) >= BASELINE_SIZE

    detector = create_detector()

    initialize(
        detector,
        scores,
    )

    statistics = state(
        detector
    )[
        "baseline_statistics"
    ]

    expected_mean = float(
        np.mean(
            scores[
                :BASELINE_SIZE
            ]
        )
    )

    expected_std = float(
        np.std(
            scores[
                :BASELINE_SIZE
            ]
        )
    )

    assert (
        statistics["mean"]
        == pytest.approx(
            expected_mean
        )
    )

    assert (
        statistics["std"]
        == pytest.approx(
            expected_std
        )
    )


# ============================================================
# 7. Real-score sustained shift
#
# This is a controlled integration scenario:
#
# - baseline comes from REAL model scores
# - shift magnitude is derived from the REAL baseline
# - shifted observations are controlled
#
# This avoids hard-coding +5, +10, etc. across models
# with completely different score scales.
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_model_scale_supports_sustained_regime_detection(
    model_name,
    model_calibration_scores,
):
    """
    Verify the detector can detect a sustained shift on the
    numerical scale actually produced by the selected model.
    """

    detector = create_detector()

    calibration = finite(
        model_calibration_scores
    )

    initialize(
        detector,
        calibration,
    )

    baseline = state(
        detector
    )[
        "baseline_statistics"
    ]

    mean = float(
        baseline["mean"]
    )

    std = max(
        float(
            baseline["std"]
        ),
        1e-6,
    )

    shifted_value = (
        mean
        + 4.0 * std
    )

    results = observe_stream(
        detector,
        np.full(
            200,
            shifted_value,
            dtype=float,
        ),
    )

    assert any(
        result[
            "shift_detected"
        ]
        for result in results
    )


@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_model_scale_can_reach_candidate_stage(
    model_name,
    model_calibration_scores,
):
    """
    A sustained controlled shift, expressed using the
    real model's score scale, should be able to progress
    through the configured candidate stages.
    """

    detector = create_detector()

    calibration = finite(
        model_calibration_scores
    )

    initialize(
        detector,
        calibration,
    )

    baseline = state(
        detector
    )[
        "baseline_statistics"
    ]

    shifted_value = (
        float(
            baseline["mean"]
        )
        + 4.0
        * max(
            float(
                baseline["std"]
            ),
            1e-6,
        )
    )

    results = observe_stream(
        detector,
        np.full(
            200,
            shifted_value,
            dtype=float,
        ),
    )

    assert (
        results[-1][
            "candidate_observations"
        ]
        >= 200
    )

    assert (
        results[-1][
            "stage"
        ]
        == 4
    )


# ============================================================
# 8. Explicit acceptance lifecycle
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_score_regime_can_be_confirmed_and_accepted(
    model_name,
    model_calibration_scores,
):
    """
    Full controlled lifecycle:

        real calibration
            ↓
        real score scale
            ↓
        sustained shift
            ↓
        confirmation
            ↓
        explicit acceptance
            ↓
        baseline replacement
    """

    detector = create_detector()

    calibration = finite(
        model_calibration_scores
    )

    initialize(
        detector,
        calibration,
    )

    before = state(
        detector
    )

    original_mean = float(
        before[
            "baseline_statistics"
        ]["mean"]
    )

    baseline = before[
        "baseline_statistics"
    ]

    shifted_value = (
        float(
            baseline["mean"]
        )
        + 4.0
        * max(
            float(
                baseline["std"]
            ),
            1e-6,
        )
    )

    confirmed = False

    for _ in range(500):

        result = detector.observe(
            shifted_value
        )

        if result[
            "regime_confirmed"
        ]:

            confirmed = True

            break

    assert confirmed is True

    confirmed_scores = np.asarray(
        detector.get_confirmed_scores(),
        dtype=float,
    )

    assert len(
        confirmed_scores
    ) > 0

    assert np.all(
        np.isfinite(
            confirmed_scores
        )
    )

    detector.accept_regime()

    after = state(
        detector
    )

    new_mean = float(
        after[
            "baseline_statistics"
        ]["mean"]
    )

    assert (
        new_mean
        != pytest.approx(
            original_mean
        )
    )

    assert (
        new_mean
        == pytest.approx(
            float(
                np.mean(
                    confirmed_scores
                )
            )
        )
    )

    assert (
        after[
            "regime_confirmed"
        ]
        is False
    )

    assert (
        after[
            "candidate_sample_count"
        ]
        == 0
    )


# ============================================================
# 9. Explicit rejection lifecycle
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_score_candidate_rejection_preserves_baseline(
    model_name,
    model_calibration_scores,
):
    """
    Candidate formation must never itself replace the
    trusted baseline.

    Explicit rejection must restore the detector to its
    original trusted-baseline state.
    """

    detector = create_detector()

    calibration = finite(
        model_calibration_scores
    )

    initialize(
        detector,
        calibration,
    )

    before = state(
        detector
    )

    original_mean = float(
        before[
            "baseline_statistics"
        ]["mean"]
    )

    baseline = before[
        "baseline_statistics"
    ]

    shifted_value = (
        float(
            baseline["mean"]
        )
        + 4.0
        * max(
            float(
                baseline["std"]
            ),
            1e-6,
        )
    )

    observe_stream(
        detector,
        np.full(
            100,
            shifted_value,
            dtype=float,
        ),
    )

    detector.reject_candidate()

    after = state(
        detector
    )

    assert (
        after[
            "baseline_sample_count"
        ]
        == before[
            "baseline_sample_count"
        ]
    )

    assert (
        after[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            original_mean
        )
    )

    assert (
        after[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        after[
            "candidate_observations"
        ]
        == 0
    )

    assert (
        after[
            "regime_confirmed"
        ]
        is False
    )


# ============================================================
# 10. All-model score independence
# ============================================================

def test_all_models_produce_independent_real_calibration_scores(
    all_calibration_scores,
):
    """
    Verify that all three model score streams exist
    independently.

    This is intentionally a structural check, not a
    requirement that their numerical values match.
    """

    for model_name in MODELS:

        assert (
            model_name
            in all_calibration_scores
        )

        scores = finite(
            all_calibration_scores[
                model_name
            ]
        )

        assert len(
            scores
        ) >= BASELINE_SIZE

    score_arrays = [
        all_calibration_scores[
            model_name
        ][
            :BASELINE_SIZE
        ]
        for model_name in MODELS
    ]

    # At least the model score streams should not all
    # collapse to exactly the same numerical sequence.
    assert not (
        np.array_equal(
            score_arrays[0],
            score_arrays[1],
        )
        and np.array_equal(
            score_arrays[1],
            score_arrays[2],
        )
    )