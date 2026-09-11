def time_based_split(df, date_col, test_size=0.2) -> tuple:
    """Splits chronologically: train on the past, test on the future.
    NEVER randomly shuffle time-series data -- that leaks the future into training.
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    split_idx = int(len(df_sorted) * (1 - test_size))
    train = df_sorted.iloc[:split_idx]
    test = df_sorted.iloc[split_idx:]
    return train, test


def walk_forward_split(df, date_col, n_splits=5, min_train_size=1) -> list:
    """General-purpose k-fold walk-forward splitter, reusable for any dataset shape.

    Splits the sorted dataframe into n_splits sequential (train, test) pairs.
    Each fold's train set only contains rows strictly before its test set
    (chronological order preserved -- never shuffled), and each fold's train
    set grows as folds progress, mimicking real retraining over time.

    Returns a list of (train_df, test_df) tuples.
    Raises ValueError if there isn't enough data to produce n_splits folds
    of at least min_train_size rows each.
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    n_rows = len(df_sorted)

    if n_rows < 2:
        raise ValueError("walk_forward_split: need at least 2 rows to split")

    fold_size = n_rows // (n_splits + 1)
    if fold_size < 1:
        raise ValueError(
            f"walk_forward_split: not enough rows ({n_rows}) for {n_splits} splits"
        )

    folds = []
    for i in range(1, n_splits + 1):
        train_end = fold_size * i
        test_end = min(fold_size * (i + 1), n_rows)
        if train_end < min_train_size or train_end >= n_rows:
            break
        train = df_sorted.iloc[:train_end]
        test = df_sorted.iloc[train_end:test_end]
        if len(test) == 0:
            break
        folds.append((train, test))

    if not folds:
        raise ValueError("walk_forward_split: no valid folds could be created")

    return folds