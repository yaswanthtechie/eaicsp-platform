import numpy as np
import pytest

from src.temporal_detector import TemporalDetector


# ============================================================
# Integration configuration
# ============================================================

WINDOW_SIZE = 24

MIN_SLOPE = 0.03
MIN_TOTAL_CHANGE = 0.75
MIN_R_SQUARED = 0.15

REQUIRED_CONSECUTIVE_WINDOWS = 3

MAX_DRIFT_CONFIRMATION_LATENCY = 72

# Real-world data is noisy. The integration test should not
# require zero false confirmations. It should enforce a
# bounded false-confirmation rate.
MAX_NORMAL_DRIFT_RATE = 0.01


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def integration_detector():
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

def run_stream(
    detector,
    dataframe,
):
    temperatures = (
        dataframe["temperature"]
        .to_numpy(dtype=float)
    )

    results = []

    for temperature in temperatures:
        results.append(
            detector.update(
                float(temperature)
            )
        )

    return results


def confirmed_indices(results):
    return [
        index
        for index, result in enumerate(results)
        if result.get(
            "is_drift",
            False,
        )
    ]


def anomaly_range(dataframe):
    labels = (
        dataframe["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    indices = np.where(
        labels == 1
    )[0]

    assert len(indices) > 0

    return (
        int(indices[0]),
        int(indices[-1]),
    )


def drift_confirmation_rate(results):
    confirmations = confirmed_indices(
        results
    )

    if not results:
        return 0.0

    return (
        len(confirmations)
        / len(results)
    )


# ============================================================
# Dataset availability
# ============================================================

def test_real_calibration_dataset_is_available(
    calibration_df,
):
    assert not calibration_df.empty

    assert "temperature" in (
        calibration_df.columns
    )

    assert len(
        calibration_df
    ) > WINDOW_SIZE


def test_real_seasonal_dataset_is_available(
    seasonal_df,
):
    assert not seasonal_df.empty

    assert "temperature" in (
        seasonal_df.columns
    )

    assert len(
        seasonal_df
    ) > WINDOW_SIZE


def test_real_spike_dataset_is_available(
    spikes_df,
):
    assert not spikes_df.empty

    assert "temperature" in (
        spikes_df.columns
    )

    assert len(
        spikes_df
    ) > WINDOW_SIZE


def test_real_drift_dataset_is_available(
    drift_df,
):
    assert not drift_df.empty

    assert "temperature" in (
        drift_df.columns
    )

    assert "is_anomaly" in (
        drift_df.columns
    )

    assert len(
        drift_df
    ) > WINDOW_SIZE


# ============================================================
# Normal calibration integration
# ============================================================

def test_real_calibration_stream_has_bounded_drift_rate(
    integration_detector,
    calibration_df,
):
    results = run_stream(
        integration_detector,
        calibration_df,
    )

    rate = drift_confirmation_rate(
        results
    )

    assert rate <= MAX_NORMAL_DRIFT_RATE, (
        "Real calibration data produced "
        f"an excessive temporal-drift "
        f"confirmation rate: {rate:.4%}"
    )


# ============================================================
# Seasonal integration
# ============================================================

def test_real_seasonal_stream_has_bounded_drift_rate(
    integration_detector,
    seasonal_df,
):
    results = run_stream(
        integration_detector,
        seasonal_df,
    )

    rate = drift_confirmation_rate(
        results
    )

    assert rate <= MAX_NORMAL_DRIFT_RATE, (
        "Real seasonal data produced "
        f"an excessive temporal-drift "
        f"confirmation rate: {rate:.4%}"
    )


# ============================================================
# Temperature spike integration
# ============================================================

def test_real_spike_stream_has_no_sustained_temporal_drift(
    integration_detector,
    spikes_df,
):
    results = run_stream(
        integration_detector,
        spikes_df,
    )

    rate = drift_confirmation_rate(
        results
    )

    assert rate <= MAX_NORMAL_DRIFT_RATE, (
        "Temperature spikes produced "
        f"an excessive temporal-drift "
        f"confirmation rate: {rate:.4%}"
    )


# ============================================================
# Real temperature drift
# ============================================================

def test_real_temperature_drift_is_detected(
    integration_detector,
    drift_df,
):
    results = run_stream(
        integration_detector,
        drift_df,
    )

    drift_start, drift_end = (
        anomaly_range(
            drift_df
        )
    )

    confirmations = confirmed_indices(
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
        "The real temperature-drift "
        "dataset did not produce a "
        "temporal-drift confirmation."
    )


def test_real_temperature_drift_is_not_detected_before_injection(
    integration_detector,
    drift_df,
):
    results = run_stream(
        integration_detector,
        drift_df,
    )

    drift_start, _ = anomaly_range(
        drift_df
    )

    confirmations = confirmed_indices(
        results
    )

    before_drift = [
        index
        for index in confirmations
        if index < drift_start
    ]

    assert before_drift == []


# ============================================================
# Real drift confirmation latency
# ============================================================

def test_real_temperature_drift_confirmation_latency_is_bounded(
    integration_detector,
    drift_df,
):
    results = run_stream(
        integration_detector,
        drift_df,
    )

    drift_start, drift_end = (
        anomaly_range(
            drift_df
        )
    )

    confirmations = [
        index
        for index in confirmed_indices(
            results
        )
        if (
            drift_start
            <= index
            <= drift_end
        )
    ]

    assert confirmations

    first_confirmation = (
        confirmations[0]
    )

    latency = (
        first_confirmation
        - drift_start
    )

    assert latency <= (
        MAX_DRIFT_CONFIRMATION_LATENCY
    )


# ============================================================
# Real drift diagnostics
# ============================================================

def test_real_drift_confirmation_contains_valid_diagnostics(
    integration_detector,
    drift_df,
):
    results = run_stream(
        integration_detector,
        drift_df,
    )

    drift_start, drift_end = (
        anomaly_range(
            drift_df
        )
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
            and result.get(
                "is_drift",
                False,
            )
        )
    ]

    assert confirmed_results

    for result in confirmed_results:

        assert np.isfinite(
            result["slope"]
        )

        assert np.isfinite(
            result["total_change"]
        )

        assert np.isfinite(
            result["r_squared"]
        )

        assert 0.0 <= result[
            "r_squared"
        ] <= 1.0


# ============================================================
# Stream processing integrity
# ============================================================

def test_real_calibration_stream_processes_every_sample(
    integration_detector,
    calibration_df,
):
    results = run_stream(
        integration_detector,
        calibration_df,
    )

    assert len(results) == len(
        calibration_df
    )

    assert results[-1][
        "sample_count"
    ] == len(calibration_df)


def test_real_seasonal_stream_processes_every_sample(
    integration_detector,
    seasonal_df,
):
    results = run_stream(
        integration_detector,
        seasonal_df,
    )

    assert len(results) == len(
        seasonal_df
    )

    assert results[-1][
        "sample_count"
    ] == len(seasonal_df)


def test_real_drift_stream_processes_every_sample(
    integration_detector,
    drift_df,
):
    results = run_stream(
        integration_detector,
        drift_df,
    )

    assert len(results) == len(
        drift_df
    )

    assert results[-1][
        "sample_count"
    ] == len(drift_df)


# ============================================================
# Detector remains usable after normal streams
# ============================================================

def test_detector_remains_usable_after_normal_stream(
    integration_detector,
    calibration_df,
):
    run_stream(
        integration_detector,
        calibration_df,
    )

    result = integration_detector.update(
        float(
            calibration_df[
                "temperature"
            ].iloc[-1]
        )
    )

    assert isinstance(
        result,
        dict,
    )

    assert result[
        "sample_count"
    ] == len(calibration_df) + 1


def test_detector_remains_usable_after_seasonal_stream(
    integration_detector,
    seasonal_df,
):
    run_stream(
        integration_detector,
        seasonal_df,
    )

    result = integration_detector.update(
        float(
            seasonal_df[
                "temperature"
            ].iloc[-1]
        )
    )

    assert isinstance(
        result,
        dict,
    )

    assert result[
        "sample_count"
    ] == len(seasonal_df) + 1


# ============================================================
# Dataset behavior
# ============================================================

def test_normal_and_drift_streams_have_different_temporal_behavior(
    calibration_df,
    drift_df,
):
    normal_temperature = (
        calibration_df["temperature"]
        .to_numpy(dtype=float)
    )

    drift_temperature = (
        drift_df["temperature"]
        .to_numpy(dtype=float)
    )

    assert len(
        normal_temperature
    ) > 0

    assert len(
        drift_temperature
    ) > 0

    assert not np.isclose(
        np.mean(normal_temperature),
        np.mean(drift_temperature),
    )


# ============================================================
# Drift labels
# ============================================================

def test_real_drift_labels_define_a_non_empty_interval(
    drift_df,
):
    start, end = anomaly_range(
        drift_df
    )

    assert start >= 0

    assert end >= start

    assert end < len(
        drift_df
    )


def test_real_drift_labels_do_not_cover_entire_dataset(
    drift_df,
):
    labels = (
        drift_df["is_anomaly"]
        .astype(int)
        .to_numpy()
    )

    anomaly_count = int(
        np.sum(labels == 1)
    )

    assert anomaly_count > 0

    assert anomaly_count < len(
        drift_df
    )