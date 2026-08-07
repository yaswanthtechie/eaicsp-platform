def time_based_split(df, date_col, test_size=0.2) -> tuple:
    """Splits chronologically: train on the past, test on the future.
    NEVER randomly shuffle time-series data -- that leaks the future into training.
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    split_idx = int(len(df_sorted) * (1 - test_size))
    train = df_sorted.iloc[:split_idx]
    test = df_sorted.iloc[split_idx:]
    return train, test