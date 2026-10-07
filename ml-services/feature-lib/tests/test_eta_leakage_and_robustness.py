import pandas as pd
import pytest

from feature_lib import add_eta_features, add_sensor_features


def _shipments(**overrides):
    data = {
        "scheduled_pickup_date": [
            "2026-01-01",
            "2026-01-05",
            "2026-01-10",
        ],
        "actual_delivery_date": [
            "2026-01-03",
            "2026-01-08",
            "2026-01-12",
        ],
        "expected_delivery_date": [
            "2026-01-03",
            "2026-01-07",
            "2026-01-12",
        ],
        "carrier_name": ["A", "A", "A"],
        "route_id": ["R1", "R1", "R1"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_output_contains_no_label_or_internal_columns():
    result = add_eta_features(_shipments())

    assert "transit_days" not in result.columns
    assert "is_on_time" not in result.columns
    assert not [c for c in result.columns if c.startswith("__")]


def test_outcome_at_exact_departure_time_is_excluded():
    # Shipment 0 is delivered exactly when shipment 1 departs.
    shipments = _shipments(
        scheduled_pickup_date=[
            "2026-01-01",
            "2026-01-03",
            "2026-01-10",
        ],
        actual_delivery_date=[
            "2026-01-03",
            "2026-01-05",
            "2026-01-12",
        ],
        expected_delivery_date=[
            "2026-01-04",
            "2026-01-06",
            "2026-01-12",
        ],
    )

    result = add_eta_features(shipments)

    assert pd.isna(
        result.loc[1, "historical_on_time_rate_carrier"]
    )


def test_weekday_and_season_rates_ignore_future_deliveries():
    # Shipment 0 departs first but is delivered (late) AFTER shipment 1
    # departs. Shipment 1 must not see that outcome.
    shipments = _shipments(
        scheduled_pickup_date=[
            "2026-01-05",
            "2026-01-12",
            "2026-02-20",
        ],
        actual_delivery_date=[
            "2026-01-20",
            "2026-01-14",
            "2026-02-22",
        ],
        expected_delivery_date=[
            "2026-01-07",
            "2026-01-14",
            "2026-02-22",
        ],
    )

    result = add_eta_features(shipments)

    # 2026-01-05 and 2026-01-12 are both Mondays, both winter.
    assert pd.isna(
        result.loc[
            1,
            "historical_on_time_rate_departure_day_of_week",
        ]
    )
    assert pd.isna(
        result.loc[
            1,
            "historical_on_time_rate_departure_season",
        ]
    )

    # By 2026-02-20 both earlier outcomes are known:
    # one late, one on time.
    assert result.loc[
        2,
        "historical_on_time_rate_departure_season",
    ] == pytest.approx(0.5)


def test_duplicate_index_labels_are_supported():
    shipments = _shipments()
    shipments.index = [0, 0, 1]

    result = add_eta_features(shipments)

    assert list(result.index) == [0, 0, 1]
    assert result[
        "historical_on_time_rate_carrier"
    ].iloc[2] == pytest.approx(0.5)


def test_transit_history_does_not_require_expected_delivery_date():
    shipments = _shipments(
        expected_delivery_date=[
            None,
            None,
            "2026-01-12",
        ],
    )

    result = add_eta_features(shipments)

    # Transit of the two earlier shipments: 2 days and 3 days.
    assert result.loc[
        2,
        "historical_avg_transit_days_carrier",
    ] == pytest.approx(2.5)

    # No known on-time outcome yet, so the rate stays unknown.
    assert pd.isna(
        result.loc[
            2,
            "historical_on_time_rate_carrier",
        ]
    )


def test_mixed_datetime_precision_is_accepted():
    shipments = _shipments()

    for column in (
        "scheduled_pickup_date",
        "actual_delivery_date",
        "expected_delivery_date",
    ):
        shipments[column] = pd.to_datetime(shipments[column])

    shipments["scheduled_pickup_date"] = (
        shipments["scheduled_pickup_date"]
        .astype("datetime64[s]")
    )

    result = add_eta_features(shipments)

    assert result.loc[
        2,
        "historical_on_time_rate_carrier",
    ] == pytest.approx(0.5)


def test_empty_sensor_batch_returns_expected_columns():
    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-01-01"]),
            "a": [1.0],
            "b": [2.0],
        }
    ).iloc[:0]

    result = add_sensor_features(
        df,
        ["a", "b"],
        "ts",
        window=3,
    )

    assert result.empty

    for column in (
        "a_rolling_zscore_3",
        "a_rate_of_change",
        "a_rolling_min_3",
        "a_rolling_max_3",
        "a_to_b_ratio",
    ):
        assert column in result.columns