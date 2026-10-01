
import pandas as pd
import pytest

from feature_lib.eta_features import add_eta_features


@pytest.fixture
def shipments():
    return pd.DataFrame({
        "scheduled_pickup_date": [
            "2026-01-01",
            "2026-01-05",
            "2026-01-10",
            "2026-01-15",
        ],
        "actual_pickup_date": [
            "2026-01-01",
            "2026-01-05",
            "2026-01-10",
            "2026-01-15",
        ],
        "expected_delivery_date": [
            "2026-01-03",
            "2026-01-07",
            "2026-01-12",
            "2026-01-17",
        ],
        "actual_delivery_date": [
            "2026-01-03",  # On time
            "2026-01-08",  # Late
            "2026-01-11",  # On time
            "2026-01-18",  # Late
        ],
        "carrier_name": ["A", "A", "A", "A"],
        "route_id": ["R1", "R1", "R1", "R1"],
    })


def test_departure_calendar_features(shipments):
    result = add_eta_features(shipments)

    assert result["departure_day_of_week"].tolist() == [
        3,  # Thursday
        0,  # Monday
        5,  # Saturday
        3,  # Thursday
    ]
    assert result["departure_month"].tolist() == [1, 1, 1, 1]
    assert result["departure_season"].tolist() == [
        "winter", "winter", "winter", "winter"
    ]


def test_historical_on_time_rates(shipments):
    result = add_eta_features(shipments)

    # First shipment has no prior completed deliveries.
    assert pd.isna(
        result.loc[0, "historical_on_time_rate_carrier"]
    )

    # Second shipment can use the first shipment's on-time result.
    assert result.loc[
        1, "historical_on_time_rate_carrier"
    ] == pytest.approx(1.0)

    assert result.loc[
        1, "historical_on_time_rate_route"
    ] == pytest.approx(1.0)

    # Third shipment's eligible history: one on time, one late.
    assert result.loc[
        2, "historical_on_time_rate_carrier"
    ] == pytest.approx(0.5)


def test_historical_transit_days(shipments):
    result = add_eta_features(shipments)

    # First shipment has no history.
    assert pd.isna(
        result.loc[0, "historical_avg_transit_days_carrier_route"]
    )

    # Before Jan 5, only the Jan 1 shipment is completed:
    # its transit duration is 2 days.
    assert result.loc[
        1, "historical_avg_transit_days_carrier_route"
    ] == pytest.approx(2.0)


def test_future_delivery_does_not_leak(shipments):
    result = add_eta_features(shipments)

    # The Jan 15 shipment must not use the Jan 18 outcome
    # because that delivery occurs after its departure.
    # Eligible completed outcomes before Jan 15:
    # Jan 3 on time, Jan 8 late, Jan 11 on time.
    assert result.loc[
        3, "historical_on_time_rate_carrier"
    ] == pytest.approx(2 / 3)


def test_same_day_delivery_is_not_prior_history():
    data = pd.DataFrame({
        "scheduled_pickup_date": ["2026-02-01", "2026-02-02"],
        "actual_pickup_date": ["2026-02-01", "2026-02-02"],
        "expected_delivery_date": ["2026-02-02", "2026-02-04"],
        "actual_delivery_date": ["2026-02-02", "2026-02-04"],
        "carrier_name": ["A", "A"],
        "route_id": ["R1", "R1"],
    })

    result = add_eta_features(data)

    # The first shipment's delivery date equals the second's
    # departure date, so it is not strictly earlier.
    assert pd.isna(
        result.loc[1, "historical_on_time_rate_carrier"]
    )


def test_missing_required_column_raises_error(shipments):
    data = shipments.drop(columns=["route_id"])

    with pytest.raises(ValueError, match="route_id"):
        add_eta_features(data)


def test_original_input_is_not_modified(shipments):
    original = shipments.copy(deep=True)

    add_eta_features(shipments)

    pd.testing.assert_frame_equal(shipments, original)