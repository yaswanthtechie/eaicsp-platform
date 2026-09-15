import pandas as pd

from .guardrails import check_no_train_test_overlap, check_chronological_order, LeakageError


def backtest(df: pd.DataFrame, date_col: str, target_col: str, forecast_fn,
              horizon: int = 1, min_train_size: int = 10, step: int = 1,
              run_guardrails: bool = True) -> list:
    """
    Reusable backtesting harness: repeatedly "pretends" it's a certain
    historical date, asks forecast_fn to predict `horizon` steps forward
    using only data up to that date, then compares against what actually
    happened.

    Splits on UNIQUE DATES, not row position -- this matters for datasets
    where multiple rows share the same date (e.g. multiple SKUs). Splitting
    by row index (iloc) would let same-date rows from other SKUs leak
    across the pretend train/test boundary. Splitting by unique date value
    guarantees every row for a given date lands entirely on one side.

    df: full chronologically-sortable dataset
    date_col, target_col: column names
    forecast_fn: a function with signature (train_df, horizon) -> list of
        `horizon` predicted values. This is what makes the harness reusable
        by ANY forecaster -- callers plug in their own model here, this
        harness never needs to know how the model works internally.
    horizon: how many steps ahead to forecast at each simulated point
    min_train_size: minimum number of unique dates before backtesting starts
    step: how many unique dates to advance between each simulated
        "pretend date"
    run_guardrails: if True (default), each window is checked with
        check_no_train_test_overlap and check_chronological_order before
        being used -- connects this harness to Milestone 5's safety checks
        instead of them living independently.

    Returns a list of dicts, one per simulated window:
    {"pretend_date": ..., "actual": [...], "predicted": [...]}

    Raises ValueError if forecast_fn returns the wrong number of predictions
    for the requested horizon -- caught here with a clear message, rather
    than surfacing later as a confusing IndexError inside a metric function.
    """
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    unique_dates = sorted(df_sorted[date_col].unique())
    n_dates = len(unique_dates)

    if n_dates < min_train_size + horizon:
        raise ValueError(
            f"backtest: not enough unique dates ({n_dates}) for min_train_size="
            f"{min_train_size} plus horizon={horizon}."
        )

    results = []
    start = min_train_size
    end = n_dates - horizon

    for i in range(start, end + 1, step):
        train_cutoff_dates = unique_dates[:i]
        test_dates = unique_dates[i:i + horizon]

        if len(test_dates) < horizon:
            break

        train_window = df_sorted[df_sorted[date_col].isin(train_cutoff_dates)]
        test_window = df_sorted[df_sorted[date_col].isin(test_dates)]

        if run_guardrails:
            check_no_train_test_overlap(train_window, test_window)
            check_chronological_order(train_window, test_window, date_col)

        predicted = forecast_fn(train_window, horizon)

        if len(predicted) != horizon:
            raise ValueError(
                f"backtest: forecast_fn returned {len(predicted)} prediction(s), "
                f"expected exactly {horizon} (the requested horizon)."
            )

        actual = test_window[target_col].tolist()

        results.append({
            "pretend_date": train_cutoff_dates[-1],
            "actual": actual,
            "predicted": predicted,
        })

    if not results:
        raise ValueError("backtest: no valid windows were produced -- check min_train_size, horizon, and step.")

    return results