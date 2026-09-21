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

@pytest.fixture
def manager():
    return IncidentManager()


# ============================================================
# Basic creation
# ============================================================

def test_first_anomaly_creates_new_incident(manager):
    status, incident = manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
        reasons=["high_score"],
    )

    assert status == "new"
    assert incident is not None

    assert incident["start"] == 100
    assert incident["end"] == 100
    assert incident["count"] == 1
    assert incident["max_score"] == 0.80
    assert incident["reasons"] == ["high_score"]


def test_new_incident_is_open_after_first_anomaly(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    assert (
        manager.open_incidents["iforest"]
        is not None
    )

    assert (
        manager.open_incidents["iforest"]["start"]
        == 100
    )


# ============================================================
# Incident extension
# ============================================================

def test_consecutive_anomalies_extend_same_incident(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    status, incident = manager.register_anomaly(
        "iforest",
        101,
        score=0.90,
    )

    assert status == "extended"

    assert incident["start"] == 100
    assert incident["end"] == 101
    assert incident["count"] == 2


def test_gap_within_tolerance_keeps_same_incident(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    status, incident = manager.register_anomaly(
        "iforest",
        103,
        score=0.90,
    )

    assert status == "extended"

    assert incident["start"] == 100
    assert incident["end"] == 103
    assert incident["count"] == 2


def test_gap_beyond_tolerance_creates_new_incident(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    status, incident = manager.register_anomaly(
        "iforest",
        104,
        score=0.90,
    )

    assert status == "new"

    assert incident["start"] == 104
    assert incident["end"] == 104
    assert incident["count"] == 1


def test_previous_incident_is_closed_when_new_incident_starts(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    manager.register_anomaly(
        "iforest",
        101,
        score=0.90,
    )

    manager.register_anomaly(
        "iforest",
        105,
        score=0.95,
    )

    assert len(
        manager.closed_incidents["iforest"]
    ) == 1

    closed = (
        manager.closed_incidents["iforest"][0]
    )

    assert closed["start"] == 100
    assert closed["end"] == 101
    assert closed["count"] == 2


# ============================================================
# Duplicate protection
# ============================================================

def test_same_reading_is_marked_duplicate(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    status, incident = manager.register_anomaly(
        "iforest",
        100,
        score=0.95,
    )

    assert status == "duplicate"
    assert incident is None


def test_duplicate_does_not_increase_incident_count(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    manager.register_anomaly(
        "iforest",
        101,
        score=0.90,
    )

    status, incident = manager.register_anomaly(
        "iforest",
        101,
        score=0.99,
    )

    assert status == "duplicate"
    assert incident is None

    open_incident = (
        manager.open_incidents["iforest"]
    )

    assert open_incident["count"] == 2
    assert open_incident["end"] == 101


def test_duplicate_reading_is_excluded(manager):
    manager.register_anomaly(
        "iforest",
        100,
    )

    assert manager.is_excluded(
        "iforest",
        100,
    )

    status, _ = manager.register_anomaly(
        "iforest",
        100,
    )

    assert status == "duplicate"


# ============================================================
# Score and reason tracking
# ============================================================

def test_higher_score_updates_max_score(manager):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.50,
        reasons=["initial"],
    )

    status, incident = manager.register_anomaly(
        "iforest",
        101,
        score=0.90,
        reasons=["higher_score"],
    )

    assert status == "extended"
    assert incident["max_score"] == 0.90
    assert incident["reasons"] == [
        "higher_score"
    ]


def test_lower_score_does_not_replace_max_score(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.90,
        reasons=["peak"],
    )

    status, incident = manager.register_anomaly(
        "iforest",
        101,
        score=0.50,
        reasons=["lower"],
    )

    assert status == "extended"
    assert incident["max_score"] == 0.90
    assert incident["reasons"] == ["peak"]


# ============================================================
# Stale incident closing
# ============================================================

def test_stale_incident_is_closed_after_gap_exceeds_tolerance(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    closed = manager.close_stale_incidents(
        "iforest",
        104,
    )

    assert closed is not None

    assert closed["start"] == 100
    assert closed["end"] == 100
    assert closed["count"] == 1

    assert (
        manager.open_incidents["iforest"]
        is None
    )


def test_stale_close_does_not_happen_within_tolerance(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    closed = manager.close_stale_incidents(
        "iforest",
        103,
    )

    assert closed is None

    assert (
        manager.open_incidents["iforest"]
        is not None
    )


def test_closing_stale_incident_does_not_duplicate_it(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    first_close = (
        manager.close_stale_incidents(
            "iforest",
            104,
        )
    )

    second_close = (
        manager.close_stale_incidents(
            "iforest",
            105,
        )
    )

    assert first_close is not None
    assert second_close is None

    assert len(
        manager.closed_incidents["iforest"]
    ) == 1


# ============================================================
# Model independence
# ============================================================

def test_incidents_are_independent_per_model(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
        score=0.80,
    )

    manager.register_anomaly(
        "lof",
        100,
        score=0.70,
    )

    manager.register_anomaly(
        "ocsvm",
        100,
        score=0.60,
    )

    assert (
        manager.open_incidents["iforest"]["max_score"]
        == 0.80
    )

    assert (
        manager.open_incidents["lof"]["max_score"]
        == 0.70
    )

    assert (
        manager.open_incidents["ocsvm"]["max_score"]
        == 0.60
    )


def test_excluded_readings_are_independent_per_model(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    assert manager.is_excluded(
        "iforest",
        100,
    )

    assert not manager.is_excluded(
        "lof",
        100,
    )

    assert not manager.is_excluded(
        "ocsvm",
        100,
    )


# ============================================================
# Incident retrieval
# ============================================================

def test_get_all_incidents_includes_open_incident(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    manager.register_anomaly(
        "iforest",
        101,
    )

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 1

    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 101
    assert incidents[0]["count"] == 2


def test_get_all_incidents_contains_closed_and_open_incidents(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    manager.register_anomaly(
        "iforest",
        101,
    )

    manager.register_anomaly(
        "iforest",
        105,
    )

    incidents = (
        manager.get_all_incidents(
            "iforest"
        )
    )

    assert len(incidents) == 2

    assert incidents[0]["start"] == 100
    assert incidents[0]["end"] == 101

    assert incidents[1]["start"] == 105
    assert incidents[1]["end"] == 105


# ============================================================
# Exclusion management
# ============================================================

def test_get_excluded_readings_returns_copy(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    excluded = (
        manager.get_excluded_readings(
            "iforest"
        )
    )

    assert excluded == {100}

    excluded.add(999)

    assert (
        manager.get_excluded_readings(
            "iforest"
        )
        == {100}
    )


def test_remove_excluded_reading_allows_reprocessing(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    assert manager.is_excluded(
        "iforest",
        100,
    )

    manager.remove_excluded_reading(
        "iforest",
        100,
    )

    assert not manager.is_excluded(
        "iforest",
        100,
    )


def test_exclusion_count_matches_processed_readings(
    manager,
):
    manager.register_anomaly(
        "iforest",
        100,
    )

    manager.register_anomaly(
        "iforest",
        101,
    )

    # Repeated reading does not increase count.
    manager.register_anomaly(
        "iforest",
        101,
    )

    assert (
        manager.get_exclusion_count(
            "iforest"
        )
        == 2
    )


# ============================================================
# Reset
# ============================================================

def test_reset_clears_all_incident_state(
    manager,
):
    for model in MODELS:

        manager.register_anomaly(
            model,
            100,
            score=0.80,
        )

        manager.register_anomaly(
            model,
            101,
            score=0.90,
        )

    manager.reset()

    for model in MODELS:

        assert (
            manager.get_exclusion_count(
                model
            )
            == 0
        )

        assert (
            manager.get_excluded_readings(
                model
            )
            == set()
        )

        assert (
            manager.open_incidents[model]
            is None
        )

        assert (
            manager.closed_incidents[model]
            == []
        )


# ============================================================
# Validation
# ============================================================

def test_invalid_model_is_rejected(
    manager,
):
    with pytest.raises(ValueError):
        manager.register_anomaly(
            "invalid_model",
            100,
        )


@pytest.mark.parametrize(
    "method,args",
    [
        (
            "is_excluded",
            ("invalid_model", 100),
        ),
        (
            "close_stale_incidents",
            ("invalid_model", 100),
        ),
        (
            "get_excluded_readings",
            ("invalid_model",),
        ),
        (
            "get_exclusion_count",
            ("invalid_model",),
        ),
        (
            "get_all_incidents",
            ("invalid_model",),
        ),
        (
            "remove_excluded_reading",
            ("invalid_model", 100),
        ),
    ],
)
def test_invalid_model_is_rejected_by_all_model_operations(
    manager,
    method,
    args,
):
    with pytest.raises(ValueError):
        getattr(manager, method)(*args)