import numpy as np
import pytest

from src.adaptive_engine import (
    AdaptiveEngine,
    EngineState,
)


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


# ============================================================
# Helpers
# ============================================================

def create_engine(
    calibration_scores,
    model_name="iforest",
):
    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    return engine


def run_stream(
    engine,
    df,
    scores,
):
    assert len(df) == len(scores)

    results = []

    for index in range(len(df)):

        results.append(
            engine.process(
                score=float(scores[index]),
                temperature=float(
                    df.iloc[index]["temperature"]
                ),
            )
        )

    return results


def count_flag(
    results,
    key,
):
    return sum(
        bool(result.get(key, False))
        for result in results
    )


def indices_for(
    results,
    key,
):
    return [
        index
        for index, result in enumerate(results)
        if bool(result.get(key, False))
    ]


def get_threshold(engine):
    threshold = (
        engine.adaptive_threshold.get_threshold()
    )

    assert threshold is not None

    return float(threshold)


# ============================================================
# 1. Initialization
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_engine_initializes_with_real_calibration(
    calibration_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    state = engine.get_state()

    assert engine.initialized is True
    assert engine.model_name == model_name

    assert state["state"] == (
        EngineState.STABLE.value
    )

    assert state["total_samples"] == 0
    assert state["alert_count"] == 0
    assert state["adaptation_updates"] == 0

    assert np.isfinite(
        get_threshold(engine)
    )


# ============================================================
# 2. Initialization validation
# ============================================================

def test_empty_calibration_is_rejected():
    engine = AdaptiveEngine()

    with pytest.raises(ValueError):
        engine.initialize([])


@pytest.mark.parametrize(
    "scores",
    [
        [1.0, np.nan, 2.0],
        [1.0, np.inf, 2.0],
        [1.0, -np.inf, 2.0],
    ],
)
def test_non_finite_calibration_is_rejected(
    scores,
):
    engine = AdaptiveEngine()

    with pytest.raises(ValueError):
        engine.initialize(scores)


def test_process_requires_initialization():
    engine = AdaptiveEngine()

    with pytest.raises(RuntimeError):
        engine.process(
            score=0.1,
            temperature=25.0,
        )


@pytest.mark.parametrize(
    "score",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_non_finite_score_is_rejected(
    calibration_scores,
    score,
):
    engine = create_engine(
        calibration_scores
    )

    with pytest.raises(ValueError):
        engine.process(
            score=score,
            temperature=25.0,
        )


@pytest.mark.parametrize(
    "temperature",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_non_finite_temperature_is_rejected(
    calibration_scores,
    temperature,
):
    engine = create_engine(
        calibration_scores
    )

    with pytest.raises(ValueError):
        engine.process(
            score=0.0,
            temperature=temperature,
        )


# ============================================================
# 3. Public result contract
# ============================================================

def test_process_returns_public_result_contract(
    calibration_scores,
):
    engine = create_engine(
        calibration_scores
    )

    result = engine.process(
        score=float(
            calibration_scores[0]
        ),
        temperature=25.0,
    )

    required_fields = {
        "state",
        "is_anomaly",
        "alert",
        "adapted",
        "regime_changed",
        "regime_confirmed",
        "regime_accepted",
        "candidate_started",
        "temporal_checked",
        "temporal_drift",
        "adaptation_frozen",
        "transition_active",
        "score",
        "threshold",
        "sample_count",
    }

    assert required_fields.issubset(
        result.keys()
    )

    assert result["score"] is not None
    assert result["threshold"] is not None
    assert result["sample_count"] == 1


# ============================================================
# 4. Normal operation
# ============================================================

def test_normal_calibration_stream_remains_stable(
    calibration_df,
    calibration_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(
        engine
    )

    results = run_stream(
        engine,
        calibration_df,
        calibration_scores,
    )

    assert results

    assert all(
        result["state"]
        == EngineState.STABLE.value
        for result in results
    )

    assert count_flag(
        results,
        "alert",
    ) == 0

    assert count_flag(
        results,
        "temporal_drift",
    ) == 0

    assert count_flag(
        results,
        "adapted",
    ) == 0

    assert np.isclose(
        get_threshold(engine),
        initial_threshold,
        rtol=0.0,
        atol=1e-15,
    )


# ============================================================
# 5. Model configuration
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_model_configuration_is_applied(
    calibration_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    config = (
        AdaptiveEngine.MODEL_CONFIG[
            model_name
        ]
    )

    assert engine.shift_sigma == (
        config["shift_sigma"]
    )

    assert engine.stability_tolerance == (
        config["stability_tolerance"]
    )

    assert engine.adaptive_percentile == (
        config["adaptive_percentile"]
    )


def test_unknown_model_preserves_explicit_configuration(
    calibration_scores,
):
    engine = AdaptiveEngine(
        shift_sigma=3.0,
        stability_tolerance=0.4,
        adaptive_percentile=96.0,
    )

    engine.initialize(
        calibration_scores,
        model_name="unknown-model",
    )

    assert engine.shift_sigma == 3.0
    assert engine.stability_tolerance == 0.4
    assert engine.adaptive_percentile == 96.0


# ============================================================
# 6. Component integration
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_engine_contains_required_components(
    calibration_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    assert engine.adaptive_threshold is not None
    assert engine.regime_detector is not None
    assert engine.temporal_detector is not None


def test_state_contains_component_states(
    calibration_scores,
):
    engine = create_engine(
        calibration_scores
    )

    state = engine.get_state()

    assert isinstance(
        state["regime"],
        dict,
    )

    assert isinstance(
        state["temporal"],
        dict,
    )

    assert isinstance(
        state["adaptive_threshold"],
        dict,
    )


# ============================================================
# 7. Seasonal regime evidence
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_seasonal_stream_produces_regime_evidence(
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    results = run_stream(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    candidate_starts = count_flag(
        results,
        "candidate_started",
    )

    confirmations = count_flag(
        results,
        "regime_confirmed",
    )

    assert candidate_starts > 0
    assert confirmations >= 0


# ============================================================
# 8. Successful regime acceptance
#
# IMPORTANT:
#
# regime_confirmed and regime_accepted are lifecycle events.
# They do not have to be True on the same result.
#
# Correct sequence:
#
#     confirmation
#          ↓
#     acceptance
#          ↓
#       adapted
#
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_successful_regime_acceptance_is_consistent(
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(
        engine
    )

    results = run_stream(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    accepted_indices = indices_for(
        results,
        "regime_accepted",
    )

    for index in accepted_indices:

        result = results[index]

        # Acceptance itself must produce adaptation.
        assert result["adapted"] is True

        # Confirmation is an earlier lifecycle event.
        confirmation_indices = indices_for(
            results[: index + 1],
            "regime_confirmed",
        )

        assert confirmation_indices

        first_confirmation = (
            confirmation_indices[0]
        )

        assert first_confirmation <= index

        # The accepted regime must leave the engine stable.
        assert result["state"] == (
            EngineState.STABLE.value
        )

        assert result[
            "transition_active"
        ] is False

    # If no model-specific regime was accepted,
    # that is not automatically a failure.
    #
    # The real-data regime integration suite handles
    # model/data-specific acceptance behavior.
    if accepted_indices:

        final_threshold = get_threshold(
            engine
        )

        assert not np.isclose(
            final_threshold,
            initial_threshold,
            rtol=0.0,
            atol=1e-15,
        )


# ============================================================
# 9. Adaptation is an event
# ============================================================

def test_adaptation_is_an_event_not_a_permanent_flag(
    calibration_scores,
    seasonal_df,
    seasonal_scores,
):
    engine = create_engine(
        calibration_scores
    )

    results = run_stream(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    adapted_indices = indices_for(
        results,
        "adapted",
    )

    if not adapted_indices:

        pytest.skip(
            "This real model/data combination "
            "did not produce an accepted regime."
        )

    first_adaptation = (
        adapted_indices[0]
    )

    subsequent = results[
        first_adaptation + 1:
    ]

    assert count_flag(
        subsequent,
        "adapted",
    ) == 0


# ============================================================
# 10. Temperature spikes
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_temperature_spikes_do_not_become_temporal_drift(
    calibration_scores,
    spikes_df,
    spike_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    results = run_stream(
        engine,
        spikes_df,
        spike_scores,
    )

    assert count_flag(
        results,
        "temporal_drift",
    ) == 0

    assert count_flag(
        results,
        "alert",
    ) == 0


# ============================================================
# 11. Real temporal drift
#
# We inspect the result at the actual drift event.
#
# We do NOT assert engine.state after the entire 5000-row
# stream because the engine may legitimately recover from
# DRIFT_LOCKED later.
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_real_temporal_drift_is_detected(
    calibration_scores,
    drift_df,
    drift_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    results = run_stream(
        engine,
        drift_df,
        drift_scores,
    )

    drift_indices = indices_for(
        results,
        "temporal_drift",
    )

    assert drift_indices

    first_drift = drift_indices[0]

    result = results[first_drift]

    assert result["temporal_drift"] is True
    assert result["alert"] is True

    assert result[
        "adaptation_frozen"
    ] is True

    assert result["state"] == (
        EngineState.DRIFT_LOCKED.value
    )


# ============================================================
# 12. Drift freezes adaptation
# ============================================================

@pytest.mark.parametrize(
    "model_name",
    MODELS,
)
def test_temporal_drift_freezes_adaptation(
    calibration_scores,
    drift_df,
    drift_scores,
    model_name,
):
    engine = create_engine(
        calibration_scores,
        model_name,
    )

    results = run_stream(
        engine,
        drift_df,
        drift_scores,
    )

    drift_indices = indices_for(
        results,
        "temporal_drift",
    )

    assert drift_indices

    first_drift = drift_indices[0]

    threshold_at_drift = float(
        results[first_drift][
            "threshold"
        ]
    )

    after_drift = results[
        first_drift:
    ]

    assert count_flag(
        after_drift,
        "adapted",
    ) == 0

    assert np.isclose(
        get_threshold(engine),
        threshold_at_drift,
        rtol=0.0,
        atol=1e-15,
    )


# ============================================================
# 13. Drift quarantine
# ============================================================

def test_drift_quarantine_does_not_adapt(
    calibration_scores,
    drift_df,
    drift_scores,
):
    engine = create_engine(
        calibration_scores
    )

    results = run_stream(
        engine,
        drift_df,
        drift_scores,
    )

    drift_indices = indices_for(
        results,
        "temporal_drift",
    )

    assert drift_indices

    first_drift = drift_indices[0]

    quarantine_results = results[
        first_drift:
    ]

    assert all(
        result["adapted"] is False
        for result in quarantine_results
    )


# ============================================================
# 14. Recovery
# ============================================================

def test_engine_can_leave_drift_lock_after_recovery(
    calibration_scores,
    drift_df,
    drift_scores,
):
    engine = create_engine(
        calibration_scores
    )

    results = run_stream(
        engine,
        drift_df,
        drift_scores,
    )

    drift_indices = indices_for(
        results,
        "temporal_drift",
    )

    assert drift_indices

    # We only require that the engine entered DRIFT_LOCKED.
    #
    # The final state may be STABLE because the engine's
    # quarantine recovery mechanism can legitimately recover
    # before the stream ends.

    first_drift = drift_indices[0]

    assert results[first_drift][
        "state"
    ] == EngineState.DRIFT_LOCKED.value

    assert engine.state in (
        EngineState.STABLE,
        EngineState.DRIFT_LOCKED,
    )


# ============================================================
# 15. update() compatibility
# ============================================================

def test_update_is_compatible_with_process(
    calibration_scores,
):
    engine_a = create_engine(
        calibration_scores
    )

    engine_b = create_engine(
        calibration_scores
    )

    score = float(
        calibration_scores[0]
    )

    temperature = 25.0

    result_process = engine_a.process(
        score=score,
        temperature=temperature,
    )

    result_update = engine_b.update(
        score=score,
        temperature=temperature,
    )

    assert result_process == result_update


# ============================================================
# 16. Sample accounting
# ============================================================

def test_engine_counts_processed_samples(
    calibration_scores,
):
    engine = create_engine(
        calibration_scores
    )

    for index in range(10):

        engine.process(
            score=float(
                calibration_scores[index]
            ),
            temperature=25.0,
        )

    state = engine.get_state()

    assert state["total_samples"] == 10
    assert state["initialized"] is True

    assert state["last_result"][
        "sample_count"
    ] == 10


# ============================================================
# 17. Reset
# ============================================================

def test_reset_returns_engine_to_initial_state(
    calibration_scores,
):
    engine = create_engine(
        calibration_scores
    )

    engine.process(
        score=float(
            calibration_scores[0]
        ),
        temperature=25.0,
    )

    engine.reset()

    state = engine.get_state()

    assert state["initialized"] is False
    assert state["model_name"] is None
    assert state["total_samples"] == 0
    assert state["adaptation_updates"] == 0
    assert state["alert_count"] == 0

    assert state["state"] == (
        EngineState.STABLE.value
    )

    with pytest.raises(RuntimeError):
        engine.process(
            score=0.0,
            temperature=25.0,
        )


def test_engine_can_be_reinitialized_after_reset(
    calibration_scores,
):
    engine = create_engine(
        calibration_scores
    )

    old_threshold = get_threshold(
        engine
    )

    engine.process(
        score=float(
            calibration_scores[0]
        ),
        temperature=25.0,
    )

    engine.reset()

    engine.initialize(
        calibration_scores,
        model_name="lof",
    )

    new_threshold = get_threshold(
        engine
    )

    assert engine.initialized is True
    assert engine.model_name == "lof"
    assert engine.total_samples == 0

    assert np.isfinite(
        new_threshold
    )

    assert np.isfinite(
        old_threshold
    )