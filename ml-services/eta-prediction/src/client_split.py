
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

    if metadata["dispatch_date"].isna().any():
        raise ValueError("dispatch_date contains missing values.")

    ordered_indices = (
        metadata["dispatch_date"]
        .sort_values(kind="stable")
        .index
        .to_list()
    )

    split_index = int(len(ordered_indices) * (1 - test_size))

    if split_index == 0 or split_index == len(ordered_indices):
        raise ValueError("Not enough shipments for the requested split.")

    train_indices = ordered_indices[:split_index]
    test_indices = ordered_indices[split_index:]

    return (
        X.loc[train_indices].reset_index(drop=True),
        X.loc[test_indices].reset_index(drop=True),
        y.loc[train_indices].reset_index(drop=True),
        y.loc[test_indices].reset_index(drop=True),
        metadata.loc[train_indices].reset_index(drop=True),
        metadata.loc[test_indices].reset_index(drop=True),
    )
