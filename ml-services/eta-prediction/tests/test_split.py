import pandas as pd
import pytest

from src.split import chronological_split


def make_features(count=10):
    """Create a minimal preprocessed feature dataset."""

    return pd.DataFrame(
        {
            "order_id": [
                f"order_{i}"
                for i in range(count)
            ],
            "delivery_days": [
                float(i + 1)
                for i in range(count)
            ],
        }
    )


def make_orders(count=10):
    """
    Create matching orders with chronological purchase
    timestamps and estimated delivery dates.
    """

    purchase_dates = pd.date_range(
        "2018-01-01",
        periods=count,
        freq="D",
    )

    return pd.DataFrame(
        {
            "order_id": [
                f"order_{i}"
                for i in range(count)
            ],
            "order_purchase_timestamp": purchase_dates,
            "order_estimated_delivery_date": (
                purchase_dates
                + pd.Timedelta(days=10)
            ),
        }
    )


def test_chronological_split_is_80_20():
    """Verify the default split produces an 80/20 partition."""

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert len(split.train) == 8
    assert len(split.test) == 2


def test_all_rows_are_assigned_exactly_once():
    """
    Verify chronological splitting does not lose or duplicate
    feature rows.
    """

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    combined_ids = (
        split.train["order_id"].tolist()
        + split.test["order_id"].tolist()
    )

    assert len(combined_ids) == len(features)

    assert len(
        set(combined_ids)
    ) == len(features)

    assert set(combined_ids) == set(
        features["order_id"]
    )


def test_training_data_is_earlier_than_test_data():
    """Training observations must precede test observations."""

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    train_end = split.train[
        "order_purchase_timestamp"
    ].max()

    test_start = split.test[
        "order_purchase_timestamp"
    ].min()

    assert train_end < test_start


def test_split_timestamp_is_first_test_timestamp():
    """The split timestamp must equal the first test timestamp."""

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert (
        split.split_timestamp
        == split.test[
            "order_purchase_timestamp"
        ].iloc[0]
    )


def test_earliest_orders_are_training_data():
    """The earliest chronological orders must be in training."""

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert split.train[
        "order_id"
    ].tolist() == [
        "order_0",
        "order_1",
        "order_2",
        "order_3",
        "order_4",
        "order_5",
        "order_6",
        "order_7",
    ]


def test_latest_orders_are_test_data():
    """The latest chronological orders must be in testing."""

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert split.test[
        "order_id"
    ].tolist() == [
        "order_8",
        "order_9",
    ]


def test_timestamp_is_available_only_for_split():
    """
    Purchase timestamp must be used for chronological splitting
    but must not be part of the original model feature dataset.
    """

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert (
        "order_purchase_timestamp"
        not in features.columns
    )

    assert (
        "order_purchase_timestamp"
        in split.train.columns
    )

    assert (
        "order_purchase_timestamp"
        in split.test.columns
    )


def test_estimated_delivery_date_is_available_for_baseline():
    """
    The Olist estimated delivery date must be carried into the
    train/test split for baseline evaluation, but must not be
    present in the original model feature dataset.
    """

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    assert (
        "order_estimated_delivery_date"
        not in features.columns
    )

    assert (
        "order_estimated_delivery_date"
        in split.train.columns
    )

    assert (
        "order_estimated_delivery_date"
        in split.test.columns
    )


def test_estimated_delivery_date_is_preserved():
    """
    Verify the estimated delivery dates remain correctly matched
    to their order IDs after the chronological split.
    """

    features = make_features()
    orders = make_orders()

    split = chronological_split(
        features,
        orders,
    )

    expected = orders.set_index(
        "order_id"
    )[
        "order_estimated_delivery_date"
    ]

    for dataframe in (
        split.train,
        split.test,
    ):
        for _, row in dataframe.iterrows():
            assert (
                row[
                    "order_estimated_delivery_date"
                ]
                == expected.loc[
                    row["order_id"]
                ]
            )


def test_missing_feature_column_raises_error():
    """Missing order_id in preprocessed features must be rejected."""

    features = make_features().drop(
        columns=[
            "order_id"
        ]
    )

    orders = make_orders()

    with pytest.raises(
        ValueError,
        match="Preprocessed features are missing",
    ):
        chronological_split(
            features,
            orders,
        )


def test_missing_order_column_raises_error():
    """
    Missing purchase timestamp in the orders dataset
    must be rejected.
    """

    features = make_features()

    orders = make_orders().drop(
        columns=[
            "order_purchase_timestamp"
        ]
    )

    with pytest.raises(
        ValueError,
        match="Orders are missing",
    ):
        chronological_split(
            features,
            orders,
        )


def test_missing_estimated_delivery_column_raises_error():
    """
    Missing estimated delivery date must be rejected because
    it is required for the Olist baseline evaluation.
    """

    features = make_features()

    orders = make_orders().drop(
        columns=[
            "order_estimated_delivery_date"
        ]
    )

    with pytest.raises(
        ValueError,
        match="Orders are missing",
    ):
        chronological_split(
            features,
            orders,
        )


def test_invalid_test_size_raises_error():
    """test_size must be strictly between zero and one."""

    features = make_features()
    orders = make_orders()

    with pytest.raises(
        ValueError,
        match="test_size must be between 0 and 1",
    ):
        chronological_split(
            features,
            orders,
            test_size=0,
        )


def test_duplicate_order_ids_in_orders_raise_error():
    """Duplicate order IDs in the orders table must be rejected."""

    features = make_features()
    orders = make_orders()

    orders.loc[
        1,
        "order_id",
    ] = "order_0"

    with pytest.raises(
        ValueError,
        match="Duplicate order_id values found in orders",
    ):
        chronological_split(
            features,
            orders,
        )


def test_invalid_timestamp_raises_error():
    """Invalid purchase timestamps must be rejected."""

    features = make_features()
    orders = make_orders()

    # Convert to object so pandas accepts the invalid string.
    orders[
        "order_purchase_timestamp"
    ] = (
        orders[
            "order_purchase_timestamp"
        ].astype(object)
    )

    orders.loc[
        0,
        "order_purchase_timestamp",
    ] = "invalid-date"

    with pytest.raises(
        ValueError,
        match="Missing or invalid",
    ):
        chronological_split(
            features,
            orders,
        )


def test_invalid_estimated_delivery_date_raises_error():
    """Invalid estimated delivery dates must be rejected."""

    features = make_features()
    orders = make_orders()

    orders[
        "order_estimated_delivery_date"
    ] = (
        orders[
            "order_estimated_delivery_date"
        ].astype(object)
    )

    orders.loc[
        0,
        "order_estimated_delivery_date",
    ] = "invalid-date"

    with pytest.raises(
        ValueError,
        match="Missing or invalid",
    ):
        chronological_split(
            features,
            orders,
        )


def test_unmatched_feature_order_raises_error():
    """
    Every feature order must have a corresponding order
    timestamp.
    """

    features = make_features()

    features.loc[
        0,
        "order_id",
    ] = "unknown_order"

    orders = make_orders()

    with pytest.raises(
        ValueError,
        match="could not be matched",
    ):
        chronological_split(
            features,
            orders,
        )