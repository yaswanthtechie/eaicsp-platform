
"""Chronological train/test split for R15 client shipments."""

import pandas as pd


def chronological_client_split(
    X: pd.DataFrame,
    y: pd.Series,
    metadata: pd.DataFrame,
    test_size: float = 0.2,
):
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    if not (len(X) == len(y) == len(metadata)):
        raise ValueError("X, y, and metadata must have equal lengths.")

    if not X.index.equals(y.index) or not X.index.equals(metadata.index):
        raise ValueError("X, y, and metadata must have matching indexes")

    if "dispatch_date" not in metadata.columns:
        raise ValueError("metadata must contain dispatch_date.")

    if "actual_delivery_date" not in metadata.columns:
        raise ValueError("metadata must contain actual_delivery_date.")

    if metadata["dispatch_date"].isna().any():
        raise ValueError("dispatch_date contains missing values.")

    ordered_index = (
        metadata["dispatch_date"]
        .sort_values(kind="stable")
        .index
    )

    split_position = int(len(ordered_index) * (1 - test_size))

    if split_position == 0 or split_position == len(ordered_index):
        raise ValueError("Not enough shipments for the requested split.")

    cutoff = metadata["dispatch_date"].loc[
        ordered_index[split_position]
    ]

    # Whole dispatch days stay on one side of the split.
    is_test = (
        metadata["dispatch_date"]
        .loc[ordered_index]
        .ge(cutoff)
        .to_numpy()
    )

    # A training label must already be known at the cutoff.
    label_known = (
        metadata["actual_delivery_date"]
        .loc[ordered_index]
        .lt(cutoff)
        .to_numpy()
    )

    train_indices = ordered_index[
        ~is_test & label_known
    ].to_list()

    test_indices = ordered_index[
        is_test
    ].to_list()

    if not train_indices or not test_indices:
        raise ValueError("Not enough shipments for the requested split.")

    return (
        X.loc[train_indices].reset_index(drop=True),
        X.loc[test_indices].reset_index(drop=True),
        y.loc[train_indices].reset_index(drop=True),
        y.loc[test_indices].reset_index(drop=True),
        metadata.loc[train_indices].reset_index(drop=True),
        metadata.loc[test_indices].reset_index(drop=True),
    )
