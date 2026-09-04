from dataclasses import dataclass

import pandas as pd


TARGET_COLUMN = "delivery_days"
TIME_COLUMN = "order_purchase_timestamp"
ESTIMATED_DELIVERY_COLUMN = (
    "order_estimated_delivery_date"
)


@dataclass
class TimeSplit:
    train: pd.DataFrame
    test: pd.DataFrame
    split_timestamp: pd.Timestamp


def chronological_split(
    features: pd.DataFrame,
    orders: pd.DataFrame,
    test_size: float = 0.20,
) -> TimeSplit:
    """
    Split preprocessed ETA features chronologically.

    The original order_purchase_timestamp from the Olist orders
    dataset is used to establish temporal ordering.

    order_estimated_delivery_date is also carried into the
    resulting train/test data for evaluation of Olist's existing
    delivery-date estimate as a baseline.

    Neither timestamp is a model feature.

    With test_size=0.20:
        - earliest 80% -> training
        - latest 20%   -> testing
    """

    if not 0 < test_size < 1:
        raise ValueError(
            "test_size must be between 0 and 1."
        )

    # ---------------------------------------------------------
    # 1. Validate preprocessed feature data
    # ---------------------------------------------------------
    required_features = {
        "order_id",
        TARGET_COLUMN,
    }

    missing_features = (
        required_features
        - set(features.columns)
    )

    if missing_features:
        raise ValueError(
            "Preprocessed features are missing required "
            f"columns: {sorted(missing_features)}"
        )

    # ---------------------------------------------------------
    # 2. Validate original order data
    # ---------------------------------------------------------
    required_orders = {
        "order_id",
        TIME_COLUMN,
        ESTIMATED_DELIVERY_COLUMN,
    }

    missing_orders = (
        required_orders
        - set(orders.columns)
    )

    if missing_orders:
        raise ValueError(
            "Orders are missing required "
            f"columns: {sorted(missing_orders)}"
        )

    # ---------------------------------------------------------
    # 3. Extract original order timestamps
    #
    # These values are evaluation/split metadata only.
    # They are never passed to the model.
    # ---------------------------------------------------------
    order_times = orders[
        [
            "order_id",
            TIME_COLUMN,
            ESTIMATED_DELIVERY_COLUMN,
        ]
    ].copy()

    order_times[TIME_COLUMN] = pd.to_datetime(
        order_times[TIME_COLUMN],
        errors="coerce",
    )

    order_times[
        ESTIMATED_DELIVERY_COLUMN
    ] = pd.to_datetime(
        order_times[
            ESTIMATED_DELIVERY_COLUMN
        ],
        errors="coerce",
    )

    # Purchase timestamp is required because it determines
    # the chronological split.
    if order_times[
        TIME_COLUMN
    ].isna().any():
        raise ValueError(
            "Missing or invalid "
            "order_purchase_timestamp values."
        )

    # Estimated delivery date is required for the Olist
    # baseline. An invalid value means that the baseline
    # cannot be calculated honestly for that order.
    if order_times[
        ESTIMATED_DELIVERY_COLUMN
    ].isna().any():
        raise ValueError(
            "Missing or invalid "
            "order_estimated_delivery_date values."
        )

    # Exactly one order record per order_id.
    if order_times[
        "order_id"
    ].duplicated().any():
        raise ValueError(
            "Duplicate order_id values found in orders."
        )

    # ---------------------------------------------------------
    # 4. Temporarily attach timestamps
    # ---------------------------------------------------------
    data = features.merge(
        order_times,
        on="order_id",
        how="inner",
        validate="one_to_one",
    )

    if len(data) != len(features):
        raise ValueError(
            "Some preprocessed feature rows could not be "
            "matched to order_purchase_timestamp."
        )

    # ---------------------------------------------------------
    # 5. Sort chronologically
    # ---------------------------------------------------------
    data = data.sort_values(
        TIME_COLUMN
    ).reset_index(drop=True)

    # ---------------------------------------------------------
    # 6. Calculate chronological split
    # ---------------------------------------------------------
    split_index = int(
        len(data) * (1.0 - test_size)
    )

    if split_index <= 0 or split_index >= len(data):
        raise ValueError(
            "Invalid split: train or test set would be empty."
        )

    # Earliest 80% → training.
    # Latest 20%   → testing.
    train = data.iloc[
        :split_index
    ].copy()

    test = data.iloc[
        split_index:
    ].copy()

    split_timestamp = test[
        TIME_COLUMN
    ].iloc[0]

    # ---------------------------------------------------------
    # 7. Chronological safety check
    # ---------------------------------------------------------
    train_end = train[
        TIME_COLUMN
    ].max()

    test_start = test[
        TIME_COLUMN
    ].min()

    if train_end > test_start:
        raise ValueError(
            "Chronological split violated: training data "
            "contains timestamps later than the test data."
        )

    # ---------------------------------------------------------
    # 8. Return split
    # ---------------------------------------------------------
    return TimeSplit(
        train=train,
        test=test,
        split_timestamp=split_timestamp,
    )