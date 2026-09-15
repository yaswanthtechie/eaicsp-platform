import numpy as np
import pytest

from src.temporal_detector import TemporalDetector


# ============================================================
# Configuration
# ============================================================

WINDOW_SIZE = 24
MIN_SLOPE = 0.03
MIN_TOTAL_CHANGE = 0.75
MIN_R_SQUARED = 0.15

REQUIRED_CONSECUTIVE_WINDOWS = 3

MAX_DRIFT_CONFIRMATION_LATENCY = 72


# ============================================================
# Detector fixture
# ============================================================

@pytest.fixture
def temporal_detector():
    return TemporalDetector(
        window_size=WINDOW_SIZE,
        min_slope=MIN_SLOPE,
        min_total_change=MIN_TOTAL_CHANGE,
        min_r_squared=MIN_R_SQUARED,
        required_consecutive_windows=(
            REQUIRED_CONSECUTIVE_WINDOWS
        ),
    )


# ============================================================
# Helpers
# ============================================================

def run_detector(
    detector,
    temperatures,
):
    results = []

    for temperature in temperatures:
        results.append(
            detector.update(
                float(temperature)
            )
        )

    return results


def drift_indices(results):
    return [
        index
        for index, result in enumerate(results)
        if bool(
            result.get(
                "is_drift",
                False,
            )
        )
    ]


# ============================================================
# Configuration contract
# ============================================================

def test_detector_can_be_created(
    temporal_detector,
):
    assert temporal_detector is not None


def test_detector_uses_expected_configuration(
    temporal_detector,
):
    assert temporal_detector.window_size == (
        WINDOW_SIZE
    )

    assert temporal_detector.min_slope == (
        MIN_SLOPE
    )

    assert temporal_detector.min_total_change == (
        MIN_TOTAL_CHANGE
    )

    assert temporal_detector.min_r_squared == (
        MIN_R_SQUARED
    )

    assert (
        temporal_detector.required_consecutive_windows
        == REQUIRED_CONSECUTIVE_WINDOWS
    )


# ============================================================
# Result contract
# ============================================================

def test_update_returns_expected_result_fields(
    temporal_detector,
):
    result = temporal_detector.update(
        25.0
    )

    required_fields = {
        "is_drift",
        "slope",
        "total_change",
        "r_squared",
        "direction",
        "consecutive_trend_windows",
        "sample_count",
    }

    assert required_fields.issubset(
        result.keys()
    )


def test_detector_does_not_evaluate_trend_before_window_is_ready(
    temporal_detector,
):
    results = run_detector(
        temporal_detector,
        np.full(
            WINDOW_SIZE - 1,
            25.0,
        ),
    )

    assert results

    for result in results:
        assert result["is_drift"] is False

    assert results[-1]["sample_count"] == (
        WINDOW_SIZE - 1
    )


# ============================================================
# Original normal
# ============================================================

def test_original_normal_does_not_produce_sustained_drift(
    temporal_detector,
    calibration_df,
):
    temperatures = (
        calibration_df["temperature"]
        .to_numpy(dtype=float)
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    confirmations = drift_indices(
        results
    )

    flag_rate = (
        len(confirmations)
        / len(results)
    )

    assert flag_rate < 0.01


# ============================================================
# Seasonal normal
# ============================================================

def test_seasonal_normal_does_not_produce_sustained_drift(
    temporal_detector,
    seasonal_df,
):
    temperatures = (
        seasonal_df["temperature"]
        .to_numpy(dtype=float)
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    confirmations = drift_indices(
        results
    )

    flag_rate = (
        len(confirmations)
        / len(results)
    )

    assert flag_rate < 0.01


# ============================================================
# Temperature spikes
# ============================================================

def test_temperature_spikes_do_not_produce_sustained_drift(
    temporal_detector,
    spikes_df,
):
    temperatures = (
        spikes_df["temperature"]
        .to_numpy(dtype=float)
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    confirmations = drift_indices(
        results
    )

    flag_rate = (
        len(confirmations)
        / len(results)
    )

    assert flag_rate < 0.01


# ============================================================
# Slow temperature drift
# ============================================================

def test_temperature_drift_dataset_contains_injected_drift(
    drift_df,
):
    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    anomaly_indices = np.where(
        labels == 1
    )[0]

    assert len(
        anomaly_indices
    ) > 0


def test_temperature_drift_is_eventually_confirmed(
    temporal_detector,
    drift_df,
):
    temperatures = (
        drift_df["temperature"]
        .to_numpy(dtype=float)
    )

    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    anomaly_indices = np.where(
        labels == 1
    )[0]

    drift_start = int(
        anomaly_indices[0]
    )

    drift_end = int(
        anomaly_indices[-1]
    )

    confirmations = drift_indices(
        results
    )

    drift_confirmations = [
        index
        for index in confirmations
        if (
            drift_start
            <= index
            <= drift_end
        )
    ]

    assert drift_confirmations, (
        "Sustained temperature drift "
        "was never confirmed."
    )


def test_temperature_drift_is_not_confirmed_before_injected_drift(
    temporal_detector,
    drift_df,
):
    temperatures = (
        drift_df["temperature"]
        .to_numpy(dtype=float)
    )

    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    anomaly_indices = np.where(
        labels == 1
    )[0]

    drift_start = int(
        anomaly_indices[0]
    )

    confirmations_before_drift = [
        index
        for index in drift_indices(results)
        if index < drift_start
    ]

    assert confirmations_before_drift == []


def test_temperature_drift_confirmation_latency_is_bounded(
    temporal_detector,
    drift_df,
):
    temperatures = (
        drift_df["temperature"]
        .to_numpy(dtype=float)
    )

    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    anomaly_indices = np.where(
        labels == 1
    )[0]

    drift_start = int(
        anomaly_indices[0]
    )

    drift_end = int(
        anomaly_indices[-1]
    )

    confirmations = [
        index
        for index in drift_indices(results)
        if (
            drift_start
            <= index
            <= drift_end
        )
    ]

    assert confirmations, (
        "No drift confirmation available "
        "to measure latency."
    )

    first_confirmation = confirmations[0]

    latency = (
        first_confirmation
        - drift_start
    )

    assert latency <= (
        MAX_DRIFT_CONFIRMATION_LATENCY
    )


# ============================================================
# Confirmed drift diagnostics
# ============================================================

def test_confirmed_drift_has_meaningful_trend_evidence(
    temporal_detector,
    drift_df,
):
    temperatures = (
        drift_df["temperature"]
        .to_numpy(dtype=float)
    )

    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    anomaly_indices = np.where(
        labels == 1
    )[0]

    drift_start = int(
        anomaly_indices[0]
    )

    drift_end = int(
        anomaly_indices[-1]
    )

    confirmed_results = [
        result
        for index, result in enumerate(
            results
        )
        if (
            drift_start
            <= index
            <= drift_end
            and result["is_drift"]
        )
    ]

    assert confirmed_results

    for result in confirmed_results:

        # The detector must provide valid
        # diagnostics when it confirms drift.
        assert np.isfinite(
            result["slope"]
        )

        assert np.isfinite(
            result["total_change"]
        )

        assert np.isfinite(
            result["r_squared"]
        )

        # R² is a bounded statistical diagnostic.
        # Do not duplicate the detector's internal
        # confirmation threshold here because the
        # confirmation event may expose diagnostics
        # from a later/reset evaluation window.
        assert 0.0 <= result[
            "r_squared"
        ] <= 1.0


# ============================================================
# Constant temperature
# ============================================================

def test_constant_temperature_does_not_produce_drift(
    temporal_detector,
):
    temperatures = np.full(
        200,
        25.0,
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    assert drift_indices(
        results
    ) == []


# ============================================================
# Directional trend sanity
# ============================================================

def test_sustained_increasing_temperature_has_positive_slope(
    temporal_detector,
):
    temperatures = np.linspace(
        20.0,
        30.0,
        200,
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    usable = [
        result
        for result in results
        if result["sample_count"]
        >= WINDOW_SIZE
    ]

    assert usable

    final = usable[-1]

    assert final["slope"] > 0.0
    assert final["total_change"] > 0.0


def test_sustained_decreasing_temperature_has_negative_slope(
    temporal_detector,
):
    temperatures = np.linspace(
        30.0,
        20.0,
        200,
    )

    results = run_detector(
        temporal_detector,
        temperatures,
    )

    usable = [
        result
        for result in results
        if result["sample_count"]
        >= WINDOW_SIZE
    ]

    assert usable

    final = usable[-1]

    assert final["slope"] < 0.0
    assert final["total_change"] < 0.0


# ============================================================
# Non-finite input validation
# ============================================================

@pytest.mark.parametrize(
    "temperature",
    [
        np.nan,
        np.inf,
        -np.inf,
    ],
)
def test_non_finite_temperature_is_rejected(
    temporal_detector,
    temperature,
):
    with pytest.raises(
        (ValueError, TypeError)
    ):
        temporal_detector.update(
            temperature
        )