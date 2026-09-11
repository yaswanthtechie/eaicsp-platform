import pandas as pd


def backtest(df: pd.DataFrame, date_col: str, target_col: str, forecast_fn,
              horizon: int = 1, min_train_size: int = 10, step: int = 1) -> list:
    """
    Reusable backtesting harness: repeatedly "pretends" it's a certain
    historical date, asks forecast_fn to predict `horizon` steps forward
    using only data up to that date, then compares against what actually
    happened.

    df: full chronologically-sortable dataset
    date_col, target_col: column names
    forecast_fn: a function with signature (train_df, horizon) -> list of
        `horizon` predicted values. This is what makes the harness reusable
        by ANY forecaster -- callers plug in their own model here, this
        harness never needs to know how the model works internally.
    horizon: how many steps ahead to forecast at each simulated point
    min_train_size: don't start backtesting until at least this many rows
        of history exist (avoids testing on absurdly small training windows)
    step: how many rows to advance between each simulated "pretend date"
        (step=1 tests every possible point; larger step tests less densely,
        faster to run)

    Returns a list of dicts, one per simulated window:
    {"pretend_date": ..., "actual": [...], "predicted": [...]}
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    n_rows = len(df_sorted)

    if n_rows < min_train_size + horizon:
        raise ValueError(
            f"backtest: not enough data ({n_rows} rows) for min_train_size="
            f"{min_train_size} plus horizon={horizon}."
        )

    results = []
    start = min_train_size
    end = n_rows - horizon

    for i in range(start, end + 1, step):
        train_window = df_sorted.iloc[:i]
        test_window = df_sorted.iloc[i:i + horizon]

        if len(test_window) < horizon:
            break  # not enough remaining rows for a full horizon

        predicted = forecast_fn(train_window, horizon)
        actual = test_window[target_col].tolist()

        results.append({
            "pretend_date": train_window[date_col].iloc[-1],
            "actual": actual,
            "predicted": predicted,
        })

    if not results:
        raise ValueError("backtest: no valid windows were produced -- check min_train_size, horizon, and step.")

    return results