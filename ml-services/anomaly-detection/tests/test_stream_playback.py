import numpy as np
import pytest

from src.incident_manager import IncidentManager


MODELS = [
    "iforest",
    "lof",
    "ocsvm",
]


# ============================================================
# Helpers
# ============================================================

def simulate_anomaly_stream(
    manager,
    model,
    reading_ids,
    score=0.90,
):
    """
    Simulate the part of stream_playback that receives
    anomalous readings and registers them with the
    IncidentManager.

    Returns:
        list of (reading_id, status, incident)
    """

    results = []

    for reading_id in reading_ids:

        status, incident = (
            manager.register_anomaly(
                model=model,
                reading_id=reading_id,
                score=score,
                reasons=["anomaly_detected"],
            )
        )

        results.append(
            (
                reading_id,
                status,
                incident,
            )
        )

    return results


# ============================================================
# Basic playback behavior
# ============================================================

def test_single_anomaly_creates_one_alert():
    manager = IncidentManager()

    results = simulate_anomaly_stream(
        manager,
        "iforest",
        [100],
    )

    assert len(results) == 1

    assert results[0][1] == "new"

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1
    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 100
    assert incidents[0]["count"] == 1


def test_consecutive_anomalies_are_grouped_into_one_alert():
    manager = IncidentManager()

    reading_ids = list(
        range(100, 150)
    )

    results = simulate_anomaly_stream(
        manager,
        "iforest",
        reading_ids,
    )

    statuses = [
        status
        for _, status, _ in results
    ]

    assert statuses[0] == "new"

    assert all(
        status == "extended"
        for status in statuses[1:]
    )

    new_alerts = statuses.count(
        "new"
    )

    assert new_alerts == 1

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1

    incident = incidents[0]

    assert incident["start"] == 100
    assert incident["end"] == 149
    assert incident["count"] == 50


def test_burst_produces_one_alert_not_one_per_reading():
    manager = IncidentManager()

    burst = list(
        range(500, 550)
    )

    results = simulate_anomaly_stream(
        manager,
        "lof",
        burst,
    )

    alert_count = sum(
        status == "new"
        for _, status, _ in results
    )

    assert alert_count == 1

    incident = (
        manager.get_all_incidents(
            "lof"
        )[0]
    )

    assert incident["count"] == 50


# ============================================================
# Duplicate playback windows
# ============================================================

def test_overlapping_playback_windows_do_not_create_duplicate_alerts():
    manager = IncidentManager()

    first_window = list(
        range(100, 125)
    )

    second_window = list(
        range(120, 145)
    )

    first_results = simulate_anomaly_stream(
        manager,
        "iforest",
        first_window,
    )

    second_results = simulate_anomaly_stream(
        manager,
        "iforest",
        second_window,
    )

    first_new = sum(
        status == "new"
        for _, status, _ in first_results
    )

    second_new = sum(
        status == "new"
        for _, status, _ in second_results
    )

    assert first_new == 1

    assert second_new == 0

    duplicates = sum(
        status == "duplicate"
        for _, status, _ in second_results
    )

    assert duplicates == 5

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1

    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 144
    assert incidents[0]["count"] == 45


# ============================================================
# Separate anomaly bursts
# ============================================================

def test_separated_anomaly_bursts_create_separate_incidents():
    manager = IncidentManager()

    first_burst = list(
        range(100, 120)
    )

    second_burst = list(
        range(130, 150)
    )

    simulate_anomaly_stream(
        manager,
        "iforest",
        first_burst,
    )

    simulate_anomaly_stream(
        manager,
        "iforest",
        second_burst,
    )

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 2

    first = incidents[0]
    second = incidents[1]

    assert first["start"] == 100
    assert first["end"] == 119
    assert first["count"] == 20

    assert second["start"] == 130
    assert second["end"] == 149
    assert second["count"] == 20


def test_gap_at_tolerance_keeps_same_incident():
    manager = IncidentManager()

    simulate_anomaly_stream(
        manager,
        "iforest",
        [100, 103],
    )

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1

    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 103
    assert incidents[0]["count"] == 2


def test_gap_beyond_tolerance_starts_new_incident():
    manager = IncidentManager()

    simulate_anomaly_stream(
        manager,
        "iforest",
        [100, 104],
    )

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 2

    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 100

    assert incidents[1]["start"] == 104
    assert incidents[1]["end"] == 104


# ============================================================
# Normal readings / stale closure
# ============================================================

def test_normal_readings_close_a_previous_anomaly_incident():
    manager = IncidentManager()

    simulate_anomaly_stream(
        manager,
        "iforest",
        [100, 101, 102],
    )

    closed = (
        manager.close_stale_incidents(
            "iforest",
            106,
        )
    )

    assert closed is not None

    assert closed["start"] == 100
    assert closed["end"] == 102
    assert closed["count"] == 3

    assert (
        manager.open_incidents["iforest"]
        is None
    )


def test_stale_closure_does_not_create_another_alert():
    manager = IncidentManager()

    simulate_anomaly_stream(
        manager,
        "iforest",
        [100, 101],
    )

    manager.close_stale_incidents(
        "iforest",
        105,
    )

    incidents_before = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    manager.close_stale_incidents(
        "iforest",
        106,
    )

    incidents_after = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(
        incidents_before
    ) == len(
        incidents_after
    )


# ============================================================
# All three models
# ============================================================

@pytest.mark.parametrize(
    "model",
    MODELS,
)
def test_each_model_deduplicates_anomaly_burst(
    model,
):
    manager = IncidentManager()

    burst = list(
        range(1000, 1050)
    )

    results = simulate_anomaly_stream(
        manager,
        model,
        burst,
    )

    new_alerts = sum(
        status == "new"
        for _, status, _ in results
    )

    assert new_alerts == 1

    incidents = (
        manager.get_all_incidents(
            model
        )
    )

    assert len(incidents) == 1

    assert incidents[0]["count"] == 50


# ============================================================
# Score/reason preservation during playback
# ============================================================

def test_playback_incident_preserves_peak_score():
    manager = IncidentManager()

    scores = [
        0.60,
        0.70,
        0.95,
        0.80,
        0.75,
    ]

    for index, score in enumerate(
        scores,
        start=200,
    ):

        manager.register_anomaly(
            "iforest",
            index,
            score=score,
            reasons=[
                "anomaly_detected"
            ],
        )

    incident = (
        manager.get_all_incidents(
            "iforest"
        )[0]
    )

    assert incident[
        "max_score"
    ] == pytest.approx(
        0.95
    )


def test_playback_incident_retains_peak_reason():
    manager = IncidentManager()

    manager.register_anomaly(
        "iforest",
        300,
        score=0.60,
        reasons=["initial"],
    )

    manager.register_anomaly(
        "iforest",
        301,
        score=0.95,
        reasons=["severe_anomaly"],
    )

    incident = (
        manager.get_all_incidents(
            "iforest"
        )[0]
    )

    assert incident[
        "max_score"
    ] == pytest.approx(
        0.95
    )

    assert incident[
        "reasons"
    ] == [
        "severe_anomaly"
    ]


# ============================================================
# End-to-end burst acceptance criteria
# ============================================================

def test_r4_deduplication_acceptance_criteria():
    """
    R4 acceptance criterion:

        A burst of anomalous readings representing
        one underlying issue must result in exactly
        one alert/incident.
    """

    manager = IncidentManager()

    burst = list(
        range(900, 950)
    )

    results = simulate_anomaly_stream(
        manager,
        "iforest",
        burst,
    )

    alert_events = [
        result
        for result in results
        if result[1] == "new"
    ]

    assert len(alert_events) == 1

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1

    incident = incidents[0]

    assert incident["start"] == 900
    assert incident["end"] == 949
    assert incident["count"] == 50


def test_r4_two_bursts_produce_two_alerts():
    """
    Two genuinely separated anomaly bursts must
    remain separate incidents.
    """

    manager = IncidentManager()

    first_burst = list(
        range(900, 925)
    )

    second_burst = list(
        range(940, 965)
    )

    first_results = simulate_anomaly_stream(
        manager,
        "iforest",
        first_burst,
    )

    second_results = simulate_anomaly_stream(
        manager,
        "iforest",
        second_burst,
    )

    alert_events = [
        result
        for result in (
            first_results
            + second_results
        )
        if result[1] == "new"
    ]

    assert len(alert_events) == 2

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 2