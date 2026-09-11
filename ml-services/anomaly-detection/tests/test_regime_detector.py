import numpy as np
import pytest

from src.regime_detector import RegimeDetector


# ============================================================
# Helpers
# ============================================================

DEFAULT_CANDIDATE_SIZES = [
    10,
    25,
    50,
    100,
    200,
]


def create_detector(
    candidate_sizes=None,
    baseline_size=100,
    shift_sigma=1.5,
    stability_tolerance=0.20,
    min_stable_blocks=2,
):
    """
    Create a fresh RegimeDetector with deterministic settings.
    """

    if candidate_sizes is None:
        candidate_sizes = DEFAULT_CANDIDATE_SIZES

    return RegimeDetector(
        candidate_sizes=candidate_sizes,
        baseline_size=baseline_size,
        shift_sigma=shift_sigma,
        stability_tolerance=stability_tolerance,
        min_stable_blocks=min_stable_blocks,
    )


def feed(detector, scores):
    """
    Feed scores sequentially and return all results.
    """

    results = []

    for score in scores:
        results.append(
            detector.observe(
                float(score)
            )
        )

    return results


def constant_scores(value, count):
    """
    Deterministic constant score sequence.
    """

    return np.full(
        count,
        float(value),
        dtype=float,
    )


def normal_baseline(count=100):
    """
    Deterministic trusted baseline.

    The values have enough spread to provide a meaningful
    baseline standard deviation.
    """

    return np.linspace(
        -1.0,
        1.0,
        count,
    )


def stable_shift(
    value=5.0,
    count=100,
):
    """
    Deterministic sustained shifted regime.
    """

    return constant_scores(
        value,
        count,
    )


def confirm_stable_shift(
    detector,
    value=5.0,
    max_observations=500,
):
    """
    Drive a detector through its actual candidate lifecycle
    until a stable regime becomes confirmed.

    The test deliberately does not assume that 100 observations
    are sufficient for confirmation.

    With the default configuration the detector reaches the
    largest candidate stage at 200 observations and performs
    subsequent validation according to its configured lifecycle.
    """

    results = []

    for _ in range(
        max_observations
    ):

        result = detector.observe(
            float(value)
        )

        results.append(
            result
        )

        if result["regime_confirmed"]:
            return results

    raise AssertionError(
        "Stable shifted regime was not confirmed "
        "within the configured detector lifecycle."
    )


# ============================================================
# Construction
# ============================================================

def test_default_detector_can_be_created():

    detector = RegimeDetector()

    state = detector.get_state()

    assert state["candidate_sizes"] == [
        10,
        25,
        50,
        100,
        200,
    ]

    assert state["baseline_size"] == 100

    assert state["candidate_sample_count"] == 0

    assert state["baseline_sample_count"] == 0

    assert state["candidate_observations"] == 0

    assert state["regime_confirmed"] is False


def test_candidate_sizes_are_sorted_and_deduplicated():

    detector = RegimeDetector(
        candidate_sizes=[
            50,
            10,
            50,
            25,
            10,
        ]
    )

    state = detector.get_state()

    assert state["candidate_sizes"] == [
        10,
        25,
        50,
    ]


# ============================================================
# Validation
# ============================================================

def test_invalid_candidate_sizes_are_rejected():

    with pytest.raises(
        ValueError,
        match="candidate_sizes",
    ):
        RegimeDetector(
            candidate_sizes=[
                0,
                -1,
            ]
        )


def test_invalid_baseline_size_is_rejected():

    with pytest.raises(
        ValueError,
        match="baseline_size",
    ):
        RegimeDetector(
            baseline_size=1
        )


def test_invalid_shift_sigma_is_rejected():

    with pytest.raises(
        ValueError,
        match="shift_sigma",
    ):
        RegimeDetector(
            shift_sigma=0
        )


def test_invalid_stability_tolerance_is_rejected():

    with pytest.raises(
        ValueError,
        match="stability_tolerance",
    ):
        RegimeDetector(
            stability_tolerance=-0.1
        )


def test_invalid_min_stable_blocks_is_rejected():

    with pytest.raises(
        ValueError,
        match="min_stable_blocks",
    ):
        RegimeDetector(
            min_stable_blocks=0
        )


# ============================================================
# Initialization
# ============================================================

def test_initialize_creates_trusted_baseline():

    scores = normal_baseline(
        150
    )

    detector = create_detector()

    detector.initialize(
        scores
    )

    state = detector.get_state()

    assert state["baseline_sample_count"] == 100

    assert state["candidate_sample_count"] == 0

    assert state["candidate_observations"] == 0

    assert state["candidate_started"] is False

    assert state["regime_confirmed"] is False


def test_initialize_keeps_only_recent_baseline_scores():

    scores = np.arange(
        1.0,
        151.0,
    )

    detector = create_detector(
        baseline_size=50
    )

    detector.initialize(
        scores
    )

    state = detector.get_state()

    assert (
        state["baseline_sample_count"]
        == 50
    )

    statistics = state[
        "baseline_statistics"
    ]

    assert statistics is not None

    assert statistics[
        "mean"
    ] == pytest.approx(
        np.mean(
            scores[-50:]
        )
    )


def test_empty_initialization_leaves_detector_empty():

    detector = create_detector()

    detector.initialize(
        []
    )

    state = detector.get_state()

    assert (
        state["baseline_sample_count"]
        == 0
    )

    assert (
        state["candidate_sample_count"]
        == 0
    )

    assert (
        state["candidate_observations"]
        == 0
    )

    assert (
        state["regime_confirmed"]
        is False
    )


def test_initialize_replaces_previous_state():

    detector = create_detector()

    first = normal_baseline()

    second = constant_scores(
        20.0,
        100,
    )

    detector.initialize(
        first
    )

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=25,
        ),
    )

    detector.initialize(
        second
    )

    state = detector.get_state()

    assert (
        state["baseline_sample_count"]
        == 100
    )

    assert (
        state["candidate_sample_count"]
        == 0
    )

    assert (
        state["candidate_observations"]
        == 0
    )

    assert (
        state["candidate_started"]
        is False
    )

    assert (
        state["regime_confirmed"]
        is False
    )

    assert (
        state["baseline_statistics"]
        ["mean"]
        == pytest.approx(
            20.0
        )
    )


# ============================================================
# Normal operation
# ============================================================

def test_original_baseline_does_not_confirm_regime():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    results = feed(
        detector,
        baseline,
    )

    assert (
        detector.is_confirmed()
        is False
    )

    assert not any(
        result["regime_confirmed"]
        for result in results
    )


def test_normal_scores_do_not_report_shift():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    results = feed(
        detector,
        baseline,
    )

    assert not any(
        result["shift_detected"]
        for result in results
    )


# ============================================================
# Candidate lifecycle
# ============================================================

def test_first_observation_starts_candidate():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    result = detector.observe(
        5.0
    )

    state = detector.get_state()

    assert (
        state["candidate_started"]
        is True
    )

    assert (
        state["candidate_sample_count"]
        == 1
    )

    assert (
        state["candidate_observations"]
        == 1
    )

    assert (
        result["candidate_started"]
        is True
    )


def test_candidate_observations_do_not_modify_trusted_baseline():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    before = detector.get_state()

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=25,
        ),
    )

    after = detector.get_state()

    assert (
        after["baseline_sample_count"]
        == before["baseline_sample_count"]
    )

    assert (
        after["baseline_statistics"]["mean"]
        == pytest.approx(
            before[
                "baseline_statistics"
            ]["mean"]
        )
    )


def test_candidate_storage_is_bounded():

    detector = create_detector(
        candidate_sizes=[
            10,
            25,
            50,
        ]
    )

    detector.initialize(
        normal_baseline()
    )

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=100,
        ),
    )

    state = detector.get_state()

    assert (
        state["candidate_sample_count"]
        <= 50
    )

    assert (
        state["candidate_observations"]
        <= 51
    )

    assert (
        state["candidate_observations"]
        >= state["candidate_sample_count"]
    )


# ============================================================
# Shift detection
# ============================================================

def test_sustained_shift_is_detected():

    detector = create_detector(
        shift_sigma=1.5
    )

    detector.initialize(
        normal_baseline()
    )

    results = feed(
        detector,
        stable_shift(
            value=5.0,
            count=50,
        ),
    )

    assert any(
        result["shift_detected"]
        for result in results
    )


def test_short_shift_does_not_confirm_regime():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=25,
        ),
    )

    assert (
        detector.is_confirmed()
        is False
    )

    state = detector.get_state()

    assert (
        state["regime_confirmed"]
        is False
    )


def test_shift_strength_is_positive_for_large_shift():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    results = feed(
        detector,
        stable_shift(
            value=5.0,
            count=50,
        ),
    )

    strengths = [
        result["shift_strength"]
        for result in results
    ]

    assert max(
        strengths
    ) > 0


# ============================================================
# Stability
# ============================================================

def test_stable_constant_shift_has_stable_diagnostics():

    detector = create_detector(
        candidate_sizes=[
            10,
            25,
            50,
            100,
        ]
    )

    detector.initialize(
        normal_baseline()
    )

    results = feed(
        detector,
        stable_shift(
            value=5.0,
            count=100,
        ),
    )

    stable_results = [
        result
        for result in results
        if result[
            "stability_reason"
        ] == "stable"
    ]

    assert stable_results

    diagnostics = stable_results[-1][
        "stability_diagnostics"
    ]

    assert diagnostics[
        "stable"
    ] is True

    assert len(
        diagnostics[
            "block_medians"
        ]
    ) == 3


def test_unstable_shift_does_not_confirm_regime():

    detector = create_detector(
        candidate_sizes=[
            10,
            25,
            50,
            100,
        ],
        shift_sigma=1.5,
        stability_tolerance=0.20,
        min_stable_blocks=2,
    )

    detector.initialize(
        normal_baseline()
    )

    unstable_shift = np.concatenate(
        [
            constant_scores(
                5.0,
                34,
            ),
            constant_scores(
                20.0,
                33,
            ),
            constant_scores(
                5.0,
                33,
            ),
        ]
    )

    results = feed(
        detector,
        unstable_shift,
    )

    assert any(
        result["shift_detected"]
        for result in results
    )

    assert (
        detector.is_confirmed()
        is False
    )

    state = detector.get_state()

    assert (
        state["regime_confirmed"]
        is False
    )


# ============================================================
# Candidate stages
# ============================================================

def test_candidate_stage_reaches_largest_configured_stage():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    results = feed(
        detector,
        stable_shift(
            value=5.0,
            count=200,
        ),
    )

    final_result = results[-1]

    # stage is the CURRENT selected stage.
    # It is not a history of every stage crossed.
    assert (
        final_result["stage"]
        == 4
    )

    state = detector.get_state()

    assert (
        state["candidate_observations"]
        >= 200
    )


def test_stage_is_unreported_before_a_valid_stage_evaluation():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    for count in [
        10,
        25,
        50,
        100,
    ]:

        detector.reset()

        detector.initialize(
            normal_baseline()
        )

        results = feed(
            detector,
            stable_shift(
                value=5.0,
                count=count,
            ),
        )

        # The detector may report -1 when there is no valid
        # stage evaluation at the current observation.
        assert results[-1]["stage"] == -1


def test_reaching_two_hundred_observations_does_not_fake_confirmation():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    results = feed(
        detector,
        stable_shift(
            value=5.0,
            count=200,
        ),
    )

    assert (
        results[-1][
            "candidate_observations"
        ]
        >= 200
    )

    assert (
        detector.is_confirmed()
        is False
    )


# ============================================================
# Confirmation lifecycle
# ============================================================

def test_confirmation_requires_repeated_validation():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    results = confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    confirmation_results = [
        result
        for result in results
        if result[
            "regime_confirmed"
        ]
    ]

    assert confirmation_results

    confirmation = (
        confirmation_results[0]
    )

    assert (
        confirmation[
            "candidate_observations"
        ]
        >= 200
    )

    assert (
        confirmation[
            "stable_blocks"
        ]
        >= 2
    )

    assert (
        confirmation[
            "validation_checks"
        ]
        >= 1
    )


def test_stable_shift_is_confirmed_after_required_validation():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    results = confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    confirmations = [
        result
        for result in results
        if result[
            "regime_confirmed"
        ]
    ]

    assert confirmations

    confirmation = confirmations[0]

    assert (
        confirmation[
            "regime_confirmed"
        ]
        is True
    )

    assert (
        confirmation[
            "stable_blocks"
        ]
        >= 2
    )


# ============================================================
# Confirmation data
# ============================================================

def test_confirmation_contains_candidate_scores():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    assert (
        detector.is_confirmed()
        is True
    )

    confirmed = np.asarray(
        detector.get_confirmed_scores(),
        dtype=float,
    )

    assert confirmed.size > 0

    assert np.all(
        np.isfinite(
            confirmed
        )
    )

    assert np.median(
        confirmed
    ) == pytest.approx(
        5.0
    )


def test_confirmed_scores_are_bounded_by_candidate_window():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    confirmed = (
        detector.get_confirmed_scores()
    )

    assert len(
        confirmed
    ) <= 200


# ============================================================
# Acceptance
# ============================================================

def test_accept_regime_replaces_trusted_baseline():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    assert (
        detector.is_confirmed()
        is True
    )

    confirmed = (
        detector.get_confirmed_scores()
    )

    detector.accept_regime()

    state = detector.get_state()

    assert (
        state["baseline_sample_count"]
        == 100
    )

    assert (
        state["candidate_sample_count"]
        == 0
    )

    assert (
        state["candidate_observations"]
        == 0
    )

    assert (
        state["regime_confirmed"]
        is False
    )

    assert (
        state[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            np.mean(
                confirmed
            )
        )
    )


def test_accept_regime_can_use_explicit_scores():

    detector = create_detector(
        baseline_size=5
    )

    detector.initialize(
        normal_baseline()
    )

    new_baseline = np.array(
        [
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
        ]
    )

    detector.accept_regime(
        new_baseline
    )

    state = detector.get_state()

    assert (
        state["baseline_sample_count"]
        == 5
    )

    expected = new_baseline[
        -5:
    ]

    assert (
        state[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            np.mean(
                expected
            )
        )
    )

    assert (
        state[
            "candidate_sample_count"
        ]
        == 0
    )


def test_accept_candidate_is_compatibility_alias():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    assert (
        detector.is_confirmed()
        is True
    )

    detector.accept_candidate()

    state = detector.get_state()

    assert (
        state["regime_confirmed"]
        is False
    )

    assert (
        state["candidate_sample_count"]
        == 0
    )

    assert (
        state["candidate_observations"]
        == 0
    )


# ============================================================
# Rejection
# ============================================================

def test_reject_candidate_preserves_trusted_baseline():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    before = detector.get_state()

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=25,
        ),
    )

    detector.reject_candidate()

    after = detector.get_state()

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
            "candidate_started"
        ]
        is False
    )

    assert (
        after[
            "regime_confirmed"
        ]
        is False
    )


def test_rejecting_confirmed_candidate_preserves_baseline():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    original_mean = (
        detector.get_state()
        [
            "baseline_statistics"
        ]
        [
            "mean"
        ]
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    assert (
        detector.is_confirmed()
        is True
    )

    detector.reject_candidate()

    state = detector.get_state()

    assert (
        state[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            original_mean
        )
    )

    assert (
        state["regime_confirmed"]
        is False
    )

    assert (
        state[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        state[
            "candidate_observations"
        ]
        == 0
    )


# ============================================================
# Confirmed-state behavior
# ============================================================

def test_confirmed_state_is_held_until_accept_or_reject():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    assert (
        detector.is_confirmed()
        is True
    )

    state_before = (
        detector.get_state()
    )

    result = detector.observe(
        5.0
    )

    state_after = (
        detector.get_state()
    )

    assert (
        result[
            "regime_confirmed"
        ]
        is True
    )

    assert (
        state_after[
            "candidate_observations"
        ]
        == state_before[
            "candidate_observations"
        ]
    )

    assert (
        state_after[
            "candidate_sample_count"
        ]
        == state_before[
            "candidate_sample_count"
        ]
    )


# ============================================================
# Diagnostics / state
# ============================================================

def test_state_reports_shift_diagnostics():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=50,
        ),
    )

    state = detector.get_state()

    assert (
        "last_shift_strength"
        in state
    )

    assert (
        "last_stability_reason"
        in state
    )

    assert (
        "last_stability_diagnostics"
        in state
    )

    assert (
        state[
            "last_shift_strength"
        ]
        > 0
    )


def test_state_reports_validation_configuration():

    detector = create_detector()

    state = detector.get_state()

    assert (
        state[
            "validation_interval"
        ]
        == 100
    )

    assert (
        state[
            "validation_checks"
        ]
        == 0
    )

    assert (
        state[
            "validation_observations"
        ]
        == 0
    )


# ============================================================
# Reset
# ============================================================

def test_reset_clears_candidate_and_baseline():

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    feed(
        detector,
        stable_shift(
            value=5.0,
            count=25,
        ),
    )

    detector.reset()

    state = detector.get_state()

    assert (
        state[
            "baseline_sample_count"
        ]
        == 0
    )

    assert (
        state[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        state[
            "candidate_observations"
        ]
        == 0
    )

    assert (
        state[
            "candidate_started"
        ]
        is False
    )

    assert (
        state[
            "regime_confirmed"
        ]
        is False
    )

    assert (
        state[
            "stable_blocks"
        ]
        == 0
    )

    assert (
        state[
            "validation_checks"
        ]
        == 0
    )


def test_detector_can_be_reinitialized_after_reset():

    detector = create_detector()

    first_baseline = (
        normal_baseline()
    )

    second_baseline = (
        constant_scores(
            20.0,
            100,
        )
    )

    detector.initialize(
        first_baseline
    )

    detector.reset()

    detector.initialize(
        second_baseline
    )

    state = detector.get_state()

    assert (
        state[
            "baseline_sample_count"
        ]
        == 100
    )

    assert (
        state[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            20.0
        )
    )

    assert (
        state[
            "candidate_sample_count"
        ]
        == 0
    )

    assert (
        state[
            "candidate_observations"
        ]
        == 0
    )

    assert (
        state[
            "regime_confirmed"
        ]
        is False
    )


# ============================================================
# Input validation
# ============================================================

@pytest.mark.parametrize(
    "bad_score",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_non_finite_score_is_rejected(
    bad_score,
):

    detector = create_detector()

    detector.initialize(
        normal_baseline()
    )

    with pytest.raises(
        ValueError,
        match="finite",
    ):
        detector.observe(
            bad_score
        )


# ============================================================
# Baseline protection
# ============================================================

def test_confirmation_alone_does_not_change_baseline():

    baseline = normal_baseline()

    detector = create_detector()

    detector.initialize(
        baseline
    )

    original = (
        detector.get_state()
    )

    confirm_stable_shift(
        detector,
        value=5.0,
        max_observations=500,
    )

    state = (
        detector.get_state()
    )

    assert (
        state[
            "baseline_statistics"
        ]["mean"]
        == pytest.approx(
            original[
                "baseline_statistics"
            ]["mean"]
        )
    )

    assert (
        state[
            "baseline_sample_count"
        ]
        == original[
            "baseline_sample_count"
        ]
    )

    assert (
        detector.is_confirmed()
        is True
    )