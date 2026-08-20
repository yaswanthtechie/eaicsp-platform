from pathlib import Path

import numpy as np
import pandas as pd

from src.adaptive_engine import (
    AdaptiveEngine,
    EngineState,
)


# ================================================================
# PROJECT PATHS
# ================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = PROJECT_ROOT / "output"

CALIBRATION = OUTPUT_DIR / "calibration_normal.csv"
SEASONAL = OUTPUT_DIR / "test_seasonal_normal.csv"
DRIFT = OUTPUT_DIR / "test_temperature_drift.csv"
SPIKES = OUTPUT_DIR / "test_temperature_spike.csv"

MODEL_NAMES = (
    "iforest",
    "lof",
    "ocsvm",
)


# ================================================================
# CONSTANTS
# ================================================================

RTOL = 1e-10
ATOL = 1e-12


# ================================================================
# DATA HELPERS
# ================================================================

def load_dataset(path):
    """Load and validate a test dataset."""

    df = pd.read_csv(path)

    required_columns = {
        "temperature",
        "humidity",
        "stock_count",
        "is_anomaly",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"{path} is missing columns: {sorted(missing)}"
        )

    if df.empty:
        raise ValueError(
            f"{path} contains no observations."
        )

    return df


def get_scores(df, model_name):
    """
    Generate project-convention anomaly scores.

    Project convention:

        raw model score -> negative score

    Higher score means more anomalous.
    """

    from src.model_loader import (
        feature_names,
        get_models,
    )

    models = get_models()

    if model_name not in models:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    features = (
        df[feature_names]
        .to_numpy(dtype=float)
    )

    raw_scores = models[model_name].score(
        features
    )

    scores = -np.asarray(
        raw_scores,
        dtype=float,
    ).reshape(-1)

    if len(scores) != len(df):
        raise ValueError(
            f"Model '{model_name}' produced "
            f"{len(scores)} scores for "
            f"{len(df)} rows."
        )

    if not np.all(np.isfinite(scores)):
        raise ValueError(
            f"Model '{model_name}' produced "
            "non-finite anomaly scores."
        )

    return scores


# ================================================================
# ENGINE HELPERS
# ================================================================

def create_engine(
    calibration_scores,
    model_name,
):
    """Create and initialize an AdaptiveEngine."""

    engine = AdaptiveEngine()

    engine.initialize(
        calibration_scores,
        model_name=model_name,
    )

    return engine


def get_threshold(engine):
    """Return the active adaptive threshold."""

    threshold = (
        engine.adaptive_threshold.get_threshold()
    )

    if threshold is None:
        raise AssertionError(
            "Adaptive threshold unexpectedly became None."
        )

    threshold = float(threshold)

    assert np.isfinite(threshold), (
        "Adaptive threshold is not finite."
    )

    return threshold


def process_stream(
    engine,
    df,
    scores,
):
    """
    Process a dataframe and matching score array.

    Each result is copied so later engine mutations cannot
    change the historical test record.
    """

    if len(df) != len(scores):
        raise ValueError(
            "Dataframe and score arrays must have "
            "the same length."
        )

    results = []

    for position, (_, row) in enumerate(
        df.iterrows()
    ):
        result = engine.process(
            score=float(scores[position]),
            temperature=float(row["temperature"]),
        )

        results.append(dict(result))

    return results


def result_state(result):
    """Normalize a result state to a string."""

    state = result.get("state")

    if isinstance(state, EngineState):
        return state.value

    if hasattr(state, "value"):
        return str(state.value).lower()

    return str(state).lower()


def engine_state(engine):
    """Normalize the current engine state to a string."""

    state = engine.state

    if isinstance(state, EngineState):
        return state.value

    if hasattr(state, "value"):
        return str(state.value).lower()

    return str(state).lower()


# ================================================================
# RESULT HELPERS
# ================================================================

def count_results(results, key):
    """Count truthy result fields."""

    return sum(
        bool(result.get(key, False))
        for result in results
    )


def first_index(results, key):
    """Return the first index where key is truthy."""

    for index, result in enumerate(results):
        if bool(result.get(key, False)):
            return index

    return None


def first_result(results, key):
    """Return (index, result) for the first truthy event."""

    index = first_index(results, key)

    if index is None:
        return None, None

    return index, results[index]


def threshold_changes(results):
    """
    Return active threshold changes.

    Each entry:

        (index, previous, current)
    """

    previous = None
    changes = []

    for index, result in enumerate(results):

        current = result.get("threshold")

        if current is None:
            continue

        current = float(current)

        if previous is not None:
            if not np.isclose(
                previous,
                current,
                rtol=RTOL,
                atol=ATOL,
            ):
                changes.append(
                    (
                        index,
                        previous,
                        current,
                    )
                )

        previous = current

    return changes


def print_separator():
    print("-" * 80)


def print_result_counts(results):
    """Print common engine diagnostics."""

    print(
        f"Regime changes          : "
        f"{count_results(results, 'regime_changed')}"
    )

    print(
        f"Temporal checks         : "
        f"{count_results(results, 'temporal_checked')}"
    )

    print(
        f"Temporal drift signals  : "
        f"{count_results(results, 'temporal_drift')}"
    )

    print(
        f"Alerts                  : "
        f"{count_results(results, 'alert')}"
    )

    print(
        f"Regime confirmations    : "
        f"{count_results(results, 'regime_confirmed')}"
    )

    print(
        f"Adaptation events       : "
        f"{count_results(results, 'adapted')}"
    )


# ================================================================
# CONTROLLED SCORE REGIME
# ================================================================

def inject_score_regime(
    calibration_scores,
    scores,
    start=0,
):
    """
    Create a sustained model-score regime change.

    Temperature is intentionally untouched.
    """

    calibration_scores = np.asarray(
        calibration_scores,
        dtype=float,
    )

    modified_scores = np.asarray(
        scores,
        dtype=float,
    ).copy()

    baseline_std = float(
        np.std(calibration_scores)
    )

    if baseline_std <= 0.0:
        baseline_std = 1.0

    shift = max(
        3.0 * baseline_std,
        0.25,
    )

    start = max(0, int(start))

    if start >= len(modified_scores):
        raise ValueError(
            "Score-regime start is outside "
            "the supplied score array."
        )

    modified_scores[start:] += shift

    return (
        modified_scores,
        baseline_std,
        shift,
    )


# ================================================================
# CONTROLLED TEMPORAL DRIFT
# ================================================================

def create_controlled_drift(
    source_df,
    calibration_df,
):
    """
    Create a deterministic sustained temperature trend.

    The trend is intentionally strong enough to satisfy
    the TemporalDetector configuration.
    """

    df = source_df.copy()

    calibration_temperature = (
        calibration_df["temperature"]
        .to_numpy(dtype=float)
    )

    if len(calibration_temperature) == 0:
        raise ValueError(
            "Calibration dataset has no "
            "temperature observations."
        )

    baseline_mean = float(
        np.mean(calibration_temperature)
    )

    baseline_std = float(
        np.std(calibration_temperature)
    )

    if baseline_std <= 0.0:
        baseline_std = 1.0

    count = len(df)

    if count < 80:
        raise ValueError(
            "Controlled drift test requires "
            "at least 80 observations."
        )

    slope = 0.04

    noise = np.random.default_rng(
        12345
    ).normal(
        0.0,
        0.01,
        count,
    )

    trend = (
        baseline_mean
        + slope * np.arange(count)
        + noise
    )

    df["temperature"] = trend

    return (
        df,
        {
            "baseline_mean": baseline_mean,
            "baseline_std": baseline_std,
            "slope": slope,
        },
    )


# ================================================================
# PHASE 1
# STABLE BASELINE
# ================================================================

def test_normal_operation(
    calibration_df,
    calibration_scores,
    model_name,
):
    print()
    print("PHASE 1 — STABLE BASELINE")
    print_separator()

    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(engine)

    sample_count = min(
        100,
        len(calibration_df),
        len(calibration_scores),
    )

    results = process_stream(
        engine,
        calibration_df.iloc[:sample_count],
        calibration_scores[:sample_count],
    )

    final_threshold = get_threshold(engine)

    adaptations = count_results(
        results,
        "adapted",
    )

    transitions = count_results(
        results,
        "regime_changed",
    )

    temporal_drift = count_results(
        results,
        "temporal_drift",
    )

    alerts = count_results(
        results,
        "alert",
    )

    print(
        f"Initial threshold       : "
        f"{initial_threshold:.9f}"
    )

    print(
        f"Final threshold         : "
        f"{final_threshold:.9f}"
    )

    print(
        f"Adaptation updates      : "
        f"{adaptations}"
    )

    print(
        f"Regime changes          : "
        f"{transitions}"
    )

    print(
        f"Temporal drift signals  : "
        f"{temporal_drift}"
    )

    print(
        f"Alerts                  : "
        f"{alerts}"
    )

    assert temporal_drift == 0, (
        "Stable calibration data unexpectedly "
        "generated temporal drift."
    )

    assert alerts == 0, (
        "Stable calibration data unexpectedly "
        "generated alerts."
    )

    assert np.isfinite(final_threshold), (
        "Adaptive threshold became invalid."
    )

    if transitions > 0:
        print()
        print(
            "[INFO] Regime detector entered a "
            "candidate transition during the "
            "stable sample."
        )

        print(
            "[INFO] Candidate transition is not "
            "treated as a successful regime change."
        )

    print()
    print(
        "[PASS] Stable operation produced "
        "no temporal drift or alerts."
    )

    print(
        "[PASS] Active threshold remained valid."
    )

    return engine, results


# ================================================================
# PHASE 2
# SUCCESSFUL SEASONAL REGIME
# ================================================================

def test_successful_seasonal_acceptance(
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    model_name,
):
    print()
    print(
        "PHASE 2 — SUCCESSFUL SEASONAL "
        "REGIME ACCEPTANCE"
    )
    print_separator()

    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(engine)

    results = process_stream(
        engine,
        seasonal_df,
        seasonal_scores,
    )

    final_threshold = get_threshold(engine)

    confirmations = count_results(
        results,
        "regime_confirmed",
    )

    temporal_drift = count_results(
        results,
        "temporal_drift",
    )

    alerts = count_results(
        results,
        "alert",
    )

    transition_observations = sum(
        bool(
            result.get(
                "transition_active",
                False,
            )
        )
        for result in results
    )

    changes = threshold_changes(results)

    # ------------------------------------------------------------
    # Locate actual accepted-regime events.
    #
    # A valid acceptance must:
    #
    #   adapted == True
    #   state == STABLE
    #   transition_active == False
    #
    # and must replace the previous threshold.
    # ------------------------------------------------------------

    acceptance_candidates = []

    previous_threshold = initial_threshold

    for index, result in enumerate(results):

        threshold = result.get("threshold")

        if threshold is None:
            continue

        threshold = float(threshold)

        adapted = bool(
            result.get(
                "adapted",
                False,
            )
        )

        stable = (
            result_state(result)
            == EngineState.STABLE.value
        )

        transition_active = bool(
            result.get(
                "transition_active",
                False,
            )
        )

        threshold_changed = not np.isclose(
            previous_threshold,
            threshold,
            rtol=RTOL,
            atol=ATOL,
        )

        if (
            adapted
            and stable
            and not transition_active
            and threshold_changed
        ):
            acceptance_candidates.append(
                (
                    index,
                    result,
                )
            )

        previous_threshold = threshold

    print(
        f"Initial threshold       : "
        f"{initial_threshold:.9f}"
    )

    print(
        f"Final threshold         : "
        f"{final_threshold:.9f}"
    )

    print(
        f"Regime confirmations    : "
        f"{confirmations}"
    )

    print(
        f"Transition observations : "
        f"{transition_observations}"
    )

    print(
        f"Acceptance candidates   : "
        f"{len(acceptance_candidates)}"
    )

    print(
        f"Threshold changes       : "
        f"{len(changes)}"
    )

    print(
        f"Temporal drift signals  : "
        f"{temporal_drift}"
    )

    print(
        f"Alerts                  : "
        f"{alerts}"
    )

    assert confirmations > 0, (
        "Seasonal data never produced "
        "a regime confirmation."
    )

    assert temporal_drift == 0, (
        "Seasonal regime incorrectly "
        "produced temporal drift."
    )

    assert alerts == 0, (
        "Seasonal regime generated an alert."
    )

    assert acceptance_candidates, (
        "Seasonal regime was confirmed but "
        "was never successfully accepted."
    )

    assert not np.isclose(
        initial_threshold,
        final_threshold,
        rtol=RTOL,
        atol=ATOL,
    ), (
        "Accepted seasonal regime did not "
        "replace the active threshold."
    )

    acceptance_index, acceptance = (
        acceptance_candidates[0]
    )

    print()
    print(
        f"Acceptance index        : "
        f"{acceptance_index}"
    )

    print(
        f"Acceptance state        : "
        f"{result_state(acceptance)}"
    )

    print(
        f"Acceptance adapted      : "
        f"{acceptance.get('adapted')}"
    )

    print(
        f"Acceptance threshold    : "
        f"{float(acceptance['threshold']):.9f}"
    )

    print(
        f"Transition active       : "
        f"{acceptance.get('transition_active')}"
    )

    assert (
        result_state(acceptance)
        == EngineState.STABLE.value
    ), (
        "Successful seasonal acceptance "
        "did not return the engine to STABLE."
    )

    assert bool(
        acceptance.get(
            "adapted",
            False,
        )
    ), (
        "Successful regime acceptance did "
        "not report adaptation."
    )

    assert not bool(
        acceptance.get(
            "transition_active",
            False,
        )
    ), (
        "Accepted regime left the transition active."
    )

    print()
    print(
        "[PASS] Seasonal regime was confirmed."
    )

    print(
        "[PASS] Temporal validation remained clean."
    )

    print(
        "[PASS] Pending regime was accepted."
    )

    print(
        "[PASS] Active threshold was replaced."
    )

    print(
        "[PASS] Acceptance returned the "
        "engine to STABLE."
    )

    return (
        engine,
        results,
        acceptance_index,
    )


# ================================================================
# PHASE 3
# DRIFT REJECTION
# ================================================================

def test_regime_drift_rejection(
    calibration_df,
    calibration_scores,
    drift_df,
    drift_scores,
    model_name,
):
    print()
    print(
        "PHASE 3 — REGIME CHANGE + "
        "TEMPERATURE DRIFT"
    )
    print_separator()

    controlled_df, drift_info = (
        create_controlled_drift(
            drift_df,
            calibration_df,
        )
    )

    controlled_scores, baseline_std, shift = (
        inject_score_regime(
            calibration_scores,
            drift_scores,
            start=0,
        )
    )

    print(
        f"Controlled drift slope  : "
        f"{drift_info['slope']:.6f}"
    )

    print(
        f"Calibration score std   : "
        f"{baseline_std:.9f}"
    )

    print(
        f"Injected score shift    : "
        f"{shift:.9f}"
    )

    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(engine)

    results = process_stream(
        engine,
        controlled_df,
        controlled_scores,
    )

    final_threshold = get_threshold(engine)

    print()
    print_result_counts(results)

    first_regime_index, first_regime = (
        first_result(
            results,
            "regime_changed",
        )
    )

    first_drift_index, first_drift = (
        first_result(
            results,
            "temporal_drift",
        )
    )

    print(
        f"Initial threshold       : "
        f"{initial_threshold:.9f}"
    )

    print(
        f"Final threshold         : "
        f"{final_threshold:.9f}"
    )

    print(
        f"First regime change     : "
        f"{first_regime_index}"
    )

    print(
        f"First temporal drift    : "
        f"{first_drift_index}"
    )

    # ------------------------------------------------------------
    # 3A — REAL REGIME CHANGE
    # ------------------------------------------------------------

    assert first_regime_index is not None, (
        "Controlled score regime change "
        "was not detected."
    )

    # ------------------------------------------------------------
    # 3B — TEMPORAL VALIDATION STARTED
    # ------------------------------------------------------------

    assert count_results(
        results,
        "temporal_checked",
    ) > 0, (
        "Regime change did not trigger "
        "temporal validation."
    )

    # ------------------------------------------------------------
    # 3C — TEMPORAL DRIFT
    # ------------------------------------------------------------

    assert first_drift_index is not None, (
        "Controlled sustained temperature "
        "drift was not detected."
    )

    assert first_drift_index >= first_regime_index, (
        "Temporal drift occurred before "
        "the regime transition."
    )

    # ------------------------------------------------------------
    # 3D — FIRST DRIFT MUST ENTER DRIFT_LOCKED
    # ------------------------------------------------------------

    first_drift_state = result_state(
        first_drift
    )

    print(
        f"First drift state       : "
        f"{first_drift_state}"
    )

    assert (
        first_drift_state
        == EngineState.DRIFT_LOCKED.value
    ), (
        "First temporal drift event did "
        "not enter DRIFT_LOCKED."
    )

    assert bool(
        first_drift.get(
            "alert",
            False,
        )
    ), (
        "First temporal drift event did "
        "not generate an alert."
    )

    # ------------------------------------------------------------
    # 3E — CAPTURE THRESHOLD AT THE FIRST
    #      REAL REGIME TRANSITION
    #
    # IMPORTANT:
    #
    # Normal adaptation is allowed BEFORE the real regime
    # transition.
    #
    # Therefore comparing everything against the original
    # calibration threshold is incorrect.
    # ------------------------------------------------------------

    transition_reference_threshold = (
        initial_threshold
    )

    if first_regime_index > 0:

        previous_result = results[
            first_regime_index - 1
        ]

        previous_threshold = (
            previous_result.get(
                "threshold"
            )
        )

        if previous_threshold is not None:
            transition_reference_threshold = float(
                previous_threshold
            )

    transition_threshold = (
        first_regime.get(
            "threshold"
        )
    )

    assert transition_threshold is not None, (
        "First regime-transition result did "
        "not expose an active threshold."
    )

    transition_threshold = float(
        transition_threshold
    )

    assert np.isclose(
        transition_threshold,
        transition_reference_threshold,
        rtol=RTOL,
        atol=ATOL,
    ), (
        "Active threshold changed at the first "
        "regime-transition observation."
    )

    # ------------------------------------------------------------
    # 3F — PER-OBSERVATION FREEZE
    #
    # From the first real regime transition through the first
    # temporal drift event:
    #
    #   adapted == False
    #   threshold == frozen transition threshold
    #
    # This is the core orchestration invariant.
    # ------------------------------------------------------------

    transition_window = results[
        first_regime_index:
        first_drift_index + 1
    ]

    adaptation_during_transition = []
    threshold_violations = []

    expected_threshold = transition_threshold

    for offset, result in enumerate(
        transition_window
    ):

        absolute_index = (
            first_regime_index + offset
        )

        if bool(
            result.get(
                "adapted",
                False,
            )
        ):
            adaptation_during_transition.append(
                absolute_index
            )

        current_threshold = result.get(
            "threshold"
        )

        if current_threshold is None:
            threshold_violations.append(
                absolute_index
            )
            continue

        if not np.isclose(
            float(current_threshold),
            expected_threshold,
            rtol=RTOL,
            atol=ATOL,
        ):
            threshold_violations.append(
                absolute_index
            )

    print(
        f"Transition observations : "
        f"{len(transition_window)}"
    )

    print(
        f"Adaptations in transition: "
        f"{len(adaptation_during_transition)}"
    )

    print(
        f"Threshold violations    : "
        f"{len(threshold_violations)}"
    )

    assert not adaptation_during_transition, (
        "Normal adaptive threshold updates "
        "occurred after the regime detector "
        "entered the transition path."
    )

    assert not threshold_violations, (
        "Active threshold changed during the "
        "regime-transition / temporal-validation "
        "lifecycle."
    )

    # ------------------------------------------------------------
    # 3G — FIRST DRIFT MUST ALSO BE FROZEN
    # ------------------------------------------------------------

    first_drift_threshold = (
        first_drift.get(
            "threshold"
        )
    )

    assert first_drift_threshold is not None, (
        "First drift result did not expose "
        "an active threshold."
    )

    assert np.isclose(
        float(first_drift_threshold),
        expected_threshold,
        rtol=RTOL,
        atol=ATOL,
    ), (
        "Adaptive threshold changed at the "
        "first temporal drift event."
    )

    assert not bool(
        first_drift.get(
            "adapted",
            False,
        )
    ), (
        "Engine adapted on the same observation "
        "that produced temporal drift."
    )

    # ------------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT assert:
    #
    #     final_threshold == initial_threshold
    #
    # here.
    #
    # After the first drift event, quarantine/recovery may occur.
    # Any later adaptation belongs to Phase 4.
    # ------------------------------------------------------------

    print()
    print(
        "[PASS] Score regime change triggered "
        "temporal validation."
    )

    print(
        "[PASS] First temporal drift entered "
        "DRIFT_LOCKED."
    )

    print(
        "[PASS] Temporal drift generated an alert."
    )

    print(
        "[PASS] No adaptive updates occurred "
        "during the transition lifecycle."
    )

    print(
        "[PASS] Active threshold remained frozen "
        "through the first drift event."
    )

    return (
        engine,
        results,
        first_drift_index,
        expected_threshold,
    )


# ================================================================
# PHASE 4
# QUARANTINE / RECOVERY
# ================================================================
def test_quarantine_recovery(
    calibration_df,
    calibration_scores,
    model_name,
):
    print()
    print(
        "PHASE 4 — QUARANTINE / RECOVERY"
    )
    print_separator()

    # ------------------------------------------------------------
    # Fresh engine.
    #
    # Phase 4 is intentionally isolated from Phase 3.
    # ------------------------------------------------------------

    engine = create_engine(
        calibration_scores,
        model_name,
    )

    initial_threshold = get_threshold(engine)

    # ------------------------------------------------------------
    # Create controlled temperature drift.
    # ------------------------------------------------------------

    drift_df, drift_info = (
        create_controlled_drift(
            calibration_df,
            calibration_df,
        )
    )

    drift_scores, baseline_std, shift = (
        inject_score_regime(
            calibration_scores,
            calibration_scores,
            start=0,
        )
    )

    print(
        f"Controlled drift slope  : "
        f"{drift_info['slope']:.6f}"
    )

    # ------------------------------------------------------------
    # Drive the engine only until the FIRST temporal drift.
    #
    # IMPORTANT:
    #
    # We track the threshold on every observation.
    #
    # This lets us distinguish:
    #
    #   normal adaptation before drift
    #
    # from:
    #
    #   illegal threshold mutation when DRIFT_LOCKED begins.
    # ------------------------------------------------------------

    results_before_drift = []

    first_drift_index = None
    first_drift = None

    threshold_before_drift = None

    for position, (_, row) in enumerate(
        drift_df.iterrows()
    ):

        result = engine.process(
            score=float(
                drift_scores[position]
            ),
            temperature=float(
                row["temperature"]
            ),
        )

        result = dict(result)

        results_before_drift.append(
            result
        )

        # --------------------------------------------------------
        # First temporal drift event.
        # --------------------------------------------------------

        if bool(
            result.get(
                "temporal_drift",
                False,
            )
        ):

            first_drift_index = position
            first_drift = result

            # The previous observation is the threshold that
            # existed immediately before DRIFT_LOCKED was entered.
            #
            # If drift occurs at observation 0, use the engine's
            # initial threshold.
            if position == 0:

                threshold_before_drift = (
                    initial_threshold
                )

            else:

                previous_result = (
                    results_before_drift[
                        position - 1
                    ]
                )

                previous_threshold = (
                    previous_result.get(
                        "threshold"
                    )
                )

                if previous_threshold is None:
                    raise AssertionError(
                        "Previous result before temporal "
                        "drift did not expose a threshold."
                    )

                threshold_before_drift = float(
                    previous_threshold
                )

            break

    assert first_drift_index is not None, (
        "Controlled temperature drift was "
        "not detected."
    )

    assert first_drift is not None

    assert threshold_before_drift is not None

    first_drift_state = result_state(
        first_drift
    )

    print(
        f"First drift index        : "
        f"{first_drift_index}"
    )

    print(
        f"State at drift           : "
        f"{first_drift_state}"
    )

    print(
        f"Threshold before drift   : "
        f"{threshold_before_drift:.9f}"
    )

    # ------------------------------------------------------------
    # 4A — FIRST DRIFT MUST ENTER DRIFT_LOCKED
    # ------------------------------------------------------------

    assert (
        first_drift_state
        == EngineState.DRIFT_LOCKED.value
    ), (
        "First temporal drift did not "
        "enter DRIFT_LOCKED."
    )

    assert bool(
        first_drift.get(
            "alert",
            False,
        )
    ), (
        "First temporal drift did not "
        "generate an alert."
    )

    # ------------------------------------------------------------
    # 4B — THRESHOLD MUST NOT CHANGE AT DRIFT ENTRY
    #
    # This is the important correction.
    #
    # We compare against the threshold from the immediately
    # preceding observation, NOT the threshold from engine
    # initialization.
    # ------------------------------------------------------------

    drift_threshold = (
        first_drift.get(
            "threshold"
        )
    )

    assert drift_threshold is not None, (
        "DRIFT_LOCKED result has no threshold."
    )

    drift_threshold = float(
        drift_threshold
    )

    assert np.isclose(
        drift_threshold,
        threshold_before_drift,
        rtol=RTOL,
        atol=ATOL,
    ), (
        "Entering DRIFT_LOCKED changed the "
        "active threshold."
    )

    # ------------------------------------------------------------
    # The observation that detects temporal drift must never
    # perform normal adaptive threshold updating.
    # ------------------------------------------------------------

    assert not bool(
        first_drift.get(
            "adapted",
            False,
        )
    ), (
        "Engine adapted on the same observation "
        "that produced temporal drift."
    )

    # ------------------------------------------------------------
    # 4C — READ QUARANTINE CONFIGURATION
    # ------------------------------------------------------------

    state_at_drift = engine.get_state()

    required_recovery = int(
        state_at_drift[
            "quarantine_recovery_required"
        ]
    )

    assert required_recovery >= 1, (
        "Invalid quarantine recovery requirement."
    )

    # ------------------------------------------------------------
    # Verify the engine is actually locked after the event.
    # ------------------------------------------------------------

    assert (
        engine_state(engine)
        == EngineState.DRIFT_LOCKED.value
    ), (
        "Engine was not actually DRIFT_LOCKED "
        "after the first temporal drift event."
    )

    # ------------------------------------------------------------
    # 4D — CLEAN RECOVERY DATA
    # ------------------------------------------------------------

    recovery_results = process_stream(
        engine,
        calibration_df,
        calibration_scores,
    )

    print(
        f"Recovery observations    : "
        f"{len(recovery_results)}"
    )

    print(
        f"Recovery requirement     : "
        f"{required_recovery}"
    )

    # ------------------------------------------------------------
    # 4E — FIND THE ACTUAL DRIFT_LOCKED -> STABLE EVENT
    # ------------------------------------------------------------

    recovery_index = None
    recovery_result = None

    previous_state = (
        EngineState.DRIFT_LOCKED.value
    )

    for index, result in enumerate(
        recovery_results
    ):

        current_state = result_state(
            result
        )

        if (
            previous_state
            == EngineState.DRIFT_LOCKED.value
            and
            current_state
            == EngineState.STABLE.value
        ):

            recovery_index = index
            recovery_result = result

            break

        previous_state = current_state

    assert recovery_index is not None, (
        "Engine never recovered from "
        "DRIFT_LOCKED."
    )

    assert recovery_result is not None

    print(
        f"Recovery index            : "
        f"{recovery_index}"
    )

    print(
        f"Recovery state            : "
        f"{result_state(recovery_result)}"
    )

    # ------------------------------------------------------------
    # 4F — RECOVERY PERIOD MUST BE RESPECTED
    #
    # With a recovery requirement of 25:
    #
    #   index 0  -> first clean observation
    #   ...
    #   index 24 -> 25th clean observation
    #
    # Therefore STABLE must not occur before index 24.
    # ------------------------------------------------------------

    assert recovery_index >= (
        required_recovery - 1
    ), (
        "Engine returned to STABLE before "
        "the configured quarantine recovery "
        "period was completed."
    )

    # ------------------------------------------------------------
    # 4G — EVERY OBSERVATION BEFORE RECOVERY MUST REMAIN
    #      DRIFT_LOCKED
    # ------------------------------------------------------------

    quarantine_results = (
        recovery_results[
            :recovery_index
        ]
    )

    for index, result in enumerate(
        quarantine_results
    ):

        state = result_state(
            result
        )

        assert (
            state
            == EngineState.DRIFT_LOCKED.value
        ), (
            "Engine left DRIFT_LOCKED before "
            "quarantine recovery completed. "
            f"Observation={index}"
        )

    # ------------------------------------------------------------
    # 4H — VERIFY ACTUAL RECOVERY TRANSITION
    # ------------------------------------------------------------

    assert (
        result_state(recovery_result)
        == EngineState.STABLE.value
    ), (
        "Recovery event did not return "
        "the engine to STABLE."
    )

    assert not bool(
        recovery_result.get(
            "transition_active",
            False,
        )
    ), (
        "Engine returned to STABLE while "
        "transition_active was still True."
    )

    assert not bool(
        recovery_result.get(
            "post_drift_quarantine",
            False,
        )
    ), (
        "Engine returned to STABLE while "
        "post_drift_quarantine was still active."
    )

    # ------------------------------------------------------------
    # 4I — CHECK FINAL ENGINE STATE SEPARATELY
    # ------------------------------------------------------------

    final_state = engine_state(
        engine
    )

    print(
        f"Final engine state        : "
        f"{final_state}"
    )

    assert (
        final_state
        == EngineState.STABLE.value
    ), (
        "Engine did not remain STABLE "
        "after quarantine recovery."
    )

    # ------------------------------------------------------------
    # 4J — RECOVERED THRESHOLD MUST BE VALID
    #
    # We intentionally do NOT require the recovered threshold
    # to equal the threshold before drift.
    #
    # After recovery, normal adaptation is allowed again.
    # ------------------------------------------------------------

    recovery_threshold = (
        recovery_result.get(
            "threshold"
        )
    )

    assert recovery_threshold is not None, (
        "Recovery result has no threshold."
    )

    recovery_threshold = float(
        recovery_threshold
    )

    assert np.isfinite(
        recovery_threshold
    ), (
        "Recovery produced an invalid threshold."
    )

    print(
        f"Recovery threshold       : "
        f"{recovery_threshold:.9f}"
    )

    print(
        f"Threshold before drift   : "
        f"{threshold_before_drift:.9f}"
    )

    # ------------------------------------------------------------
    # PASS
    # ------------------------------------------------------------

    print()
    print(
        "[PASS] Engine entered quarantine "
        "when temporal drift was detected."
    )

    print(
        "[PASS] Threshold remained unchanged "
        "when DRIFT_LOCKED was entered."
    )

    print(
        "[PASS] Engine remained DRIFT_LOCKED "
        "during quarantine recovery."
    )

    print(
        "[PASS] Engine transitioned from "
        "DRIFT_LOCKED to STABLE."
    )

    print(
        "[PASS] Final engine state is STABLE."
    )

    print(
        "[PASS] Recovered threshold remained valid."
    )

    return (
        engine,
        recovery_results,
        recovery_index,
    )


# ================================================================
# PHASE 5
# TEMPERATURE SPIKES
# ================================================================

def test_temperature_spikes(
    calibration_scores,
    spikes_df,
    spike_scores,
    model_name,
):
    print()
    print(
        "PHASE 5 — TEMPERATURE SPIKES"
    )
    print_separator()

    engine = create_engine(
        calibration_scores,
        model_name,
    )

    results = process_stream(
        engine,
        spikes_df,
        spike_scores,
    )

    temporal_checks = count_results(
        results,
        "temporal_checked",
    )

    temporal_drift = count_results(
        results,
        "temporal_drift",
    )

    alerts = count_results(
        results,
        "alert",
    )

    drift_rate = (
        temporal_drift / len(results)
        if results
        else 0.0
    )

    print(
        f"Temporal checks          : "
        f"{temporal_checks}"
    )

    print(
        f"Temporal drift detections: "
        f"{temporal_drift}"
    )

    print(
        f"Alerts                   : "
        f"{alerts}"
    )

    print(
        f"Temporal drift rate      : "
        f"{drift_rate:.4f}"
    )

    assert drift_rate < 0.05, (
        "Temperature spikes are being "
        "classified as sustained temporal "
        "drift too frequently."
    )

    print()
    print(
        "[PASS] Temperature spikes do not "
        "produce excessive temporal drift."
    )

    return engine, results


# ================================================================
# MODEL RUNNER
# ================================================================

def run_model(
    model_name,
    calibration_df,
    calibration_scores,
    seasonal_df,
    seasonal_scores,
    drift_df,
    drift_scores,
    spikes_df,
    spike_scores,
):
    print()
    print("#" * 80)
    print(
        f"MODEL: {model_name.upper()}"
    )
    print("#" * 80)

    print()
    print("Generating model scores...")
    print("Scores generated.")

    # ------------------------------------------------------------
    # PHASE 1
    # ------------------------------------------------------------

    test_normal_operation(
        calibration_df,
        calibration_scores,
        model_name,
    )

    # ------------------------------------------------------------
    # PHASE 2
    # ------------------------------------------------------------

    test_successful_seasonal_acceptance(
        calibration_scores,
        seasonal_df,
        seasonal_scores,
        model_name,
    )

    # ------------------------------------------------------------
    # PHASE 3
    # ------------------------------------------------------------

    test_regime_drift_rejection(
        calibration_df,
        calibration_scores,
        drift_df,
        drift_scores,
        model_name,
    )

    # ------------------------------------------------------------
    # PHASE 4
    # ------------------------------------------------------------

    test_quarantine_recovery(
        calibration_df,
        calibration_scores,
        model_name,
    )

    # ------------------------------------------------------------
    # PHASE 5
    # ------------------------------------------------------------

    test_temperature_spikes(
        calibration_scores,
        spikes_df,
        spike_scores,
        model_name,
    )

    print()
    print(
        f"[COMPLETED] {model_name.upper()}"
    )


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 80)
    print("ADAPTIVE ENGINE ARCHITECTURE TEST")
    print("=" * 80)

    print()
    print("Architecture being tested:")

    print("STABLE → NORMAL ADAPTATION")
    print("REGIME CHANGE → FREEZE")
    print("REGIME CONFIRMATION → PENDING REGIME")
    print("PENDING REGIME → TEMPORAL VALIDATION")
    print(
        "CLEAN VALIDATION → ACCEPT REGIME → NEW BASELINE"
    )
    print(
        "TEMPORAL DRIFT → REJECT REGIME → DRIFT_LOCKED"
    )
    print(
        "DRIFT_LOCKED → CLEAN DATA → RECOVERY → STABLE"
    )
    print(
        "TEMPERATURE SPIKES → NO FALSE DRIFT"
    )

    calibration_df = load_dataset(
        CALIBRATION
    )

    seasonal_df = load_dataset(
        SEASONAL
    )

    drift_df = load_dataset(
        DRIFT
    )

    spikes_df = load_dataset(
        SPIKES
    )

    for model_name in MODEL_NAMES:

        calibration_scores = get_scores(
            calibration_df,
            model_name,
        )

        seasonal_scores = get_scores(
            seasonal_df,
            model_name,
        )

        drift_scores = get_scores(
            drift_df,
            model_name,
        )

        spike_scores = get_scores(
            spikes_df,
            model_name,
        )

        run_model(
            model_name,
            calibration_df,
            calibration_scores,
            seasonal_df,
            seasonal_scores,
            drift_df,
            drift_scores,
            spikes_df,
            spike_scores,
        )

    print()
    print("=" * 80)
    print(
        "ADAPTIVE ENGINE ARCHITECTURE TEST COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()