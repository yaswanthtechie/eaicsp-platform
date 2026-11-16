
import pandas as pd
import pytest

from src.client_split import chronological_client_split


def sample_data():
    X = pd.DataFrame({"distance_km": [100, 200, 300, 400, 500]})
    y = pd.Series([2, 3, 4, 5, 6], name="delivery_days")

    dispatch_dates = pd.to_datetime(
        [
            "2026-01-05",
            "2026-01-01",
            "2026-01-04",
            "2026-01-02",
            "2026-01-03",
        ]
    )

    metadata = pd.DataFrame(
        {
            "shipment_id": ["S1", "S2", "S3", "S4", "S5"],
            "dispatch_date": dispatch_dates,
            "actual_delivery_date": (
                dispatch_dates + pd.Timedelta(hours=12)
            ),
        }
    )

    return X, y, metadata


def test_splits_shipments_chronologically():
    X, y, metadata = sample_data()

    X_train, X_test, y_train, y_test, meta_train, meta_test = (
        chronological_client_split(X, y, metadata, test_size=0.4)
    )

    assert meta_train["dispatch_date"].max() < meta_test["dispatch_date"].min()
    assert len(X_train) == 3
    assert len(X_test) == 2


def test_keeps_features_targets_and_metadata_aligned():
    X, y, metadata = sample_data()

    X_train, X_test, y_train, y_test, meta_train, meta_test = (
        chronological_client_split(X, y, metadata, test_size=0.4)
    )

    assert X_train["distance_km"].tolist() == [200, 400, 500]
    assert y_train.tolist() == [3, 5, 6]
    assert meta_train["shipment_id"].tolist() == ["S2", "S4", "S5"]

    assert X_test["distance_km"].tolist() == [300, 100]
    assert y_test.tolist() == [4, 2]
    assert meta_test["shipment_id"].tolist() == ["S3", "S1"]


def test_rejects_missing_dispatch_dates():
    X, y, metadata = sample_data()
    metadata.loc[0, "dispatch_date"] = pd.NaT

    with pytest.raises(ValueError, match="dispatch_date"):
        chronological_client_split(X, y, metadata)


def test_rejects_mismatched_lengths():
    X, y, metadata = sample_data()

    with pytest.raises(ValueError, match="equal lengths"):
        chronological_client_split(X.iloc[:-1], y, metadata)


def test_rejects_invalid_test_size():
    X, y, metadata = sample_data()

    with pytest.raises(ValueError, match="test_size"):
        chronological_client_split(X, y, metadata, test_size=1)


def test_mismatched_indexes_are_rejected():
    X = pd.DataFrame(
        {"distance_km": [100, 200, 300]},
        index=[0, 1, 2],
    )

    y = pd.Series(
        [2, 3, 4],
        index=[10, 11, 12],
    )

    dispatch_dates = pd.date_range("2026-01-01", periods=3)

    metadata = pd.DataFrame(
        {
            "dispatch_date": dispatch_dates,
            "actual_delivery_date": (
                dispatch_dates + pd.Timedelta(hours=12)
            ),
        },
        index=[0, 1, 2],
    )

    with pytest.raises(
        ValueError,
        match="X, y, and metadata must have matching indexes",
    ):
        chronological_client_split(X, y, metadata)


def test_training_labels_after_cutoff_are_purged():
    dates = pd.date_range("2025-01-01", periods=10, freq="D")

    X = pd.DataFrame({"f": range(10)})
    y = pd.Series(range(10), dtype=float)

    metadata = pd.DataFrame(
        {
            "dispatch_date": dates,
            "actual_delivery_date": dates + pd.Timedelta(days=2),
        }
    )

    X_train, X_test, y_train, y_test, m_train, m_test = (
        chronological_client_split(X, y, metadata, test_size=0.2)
    )

    cutoff = m_test["dispatch_date"].min()

    assert len(m_test) == 2
    assert len(m_train) == 6
    assert (m_train["actual_delivery_date"] < cutoff).all()


def test_same_dispatch_day_stays_on_one_side():
    days = pd.to_datetime(
        ["2025-01-01"] * 2
        + ["2025-01-02"] * 2
        + ["2025-01-03"] * 2
        + ["2025-01-04"] * 2
        + ["2025-01-05"] * 2
    )

    X = pd.DataFrame({"f": range(10)})
    y = pd.Series(range(10), dtype=float)

    metadata = pd.DataFrame(
        {
            "dispatch_date": days,
            "actual_delivery_date": (
                days + pd.Timedelta(hours=12)
            ),
        }
    )

    _, _, _, _, m_train, m_test = chronological_client_split(
        X, y, metadata, test_size=0.25
    )

    assert len(m_test) == 4
    assert m_train["dispatch_date"].max() < m_test["dispatch_date"].min()
