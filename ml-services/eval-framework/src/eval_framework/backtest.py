import pandas as pd

from .guardrails import check_no_train_test_overlap, check_chronological_order, LeakageError


def _backtest_single_series(df_sorted, date_col, target_col, forecast_fn,
                               horizon, min_train_size, step, run_guardrails):
    """Backtests a single series (one forecaster's worth of data, already
    date-parsed and sorted). Internal helper -- see backtest() for the
    public, multi-series-aware entry point.
    """
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

        if len(actual) != horizon:
            raise ValueError(
                f"backtest: test window has {len(actual)} actual value(s) for "
                f"horizon={horizon}. This usually means multiple rows share the "
                f"same date within a single series (e.g. duplicate rows) -- "
                f"for multiple SKUs/series, pass series_col instead of mixing "
                f"them into one series."
            )

        results.append({
            "pretend_date": train_cutoff_dates[-1],
            "actual": actual,
            "predicted": predicted,
        })

    if not results:
        raise ValueError("backtest: no valid windows were produced -- check min_train_size, horizon, and step.")

    return results


def backtest(df: pd.DataFrame, date_col: str, target_col: str, forecast_fn,
              horizon: int = 1, min_train_size: int = 10, step: int = 1,
              run_guardrails: bool = True, series_col: str = None,
              dayfirst: bool = False, date_format: str = None) -> list:
    """
    Reusable backtesting harness: repeatedly "pretends" it's a certain
    historical date, asks forecast_fn to predict `horizon` steps forward
    using only data up to that date, then compares against what actually
    happened.

    Dates are explicitly parsed with pd.to_datetime before any sorting or
    comparison -- sorting a raw string column (e.g. "10/1/2024" vs
    "4/1/2024") sorts alphabetically, not chronologically, which both
    false-alarms the leakage guardrail on genuinely clean data and can
    silently run windows out of order when guardrails are off.

    dayfirst / date_format: passed through to pd.to_datetime, since date
    strings are genuinely ambiguous (e.g. "10/01/2024" could be Jan 10 or
    Oct 1 depending on convention) -- pass whichever matches your data.

    series_col: optional column identifying separate series (e.g. SKU ID).
    If given, the dataset is split by series and each series is backtested
    independently, then results are tagged with their series id. This is
    required for multi-series data -- without it, multiple rows sharing a
    date (one per series) would make a single window's "actual"/"predicted"
    lengths disagree with `horizon`, which now raises a clear error instead
    of silently returning mismatched lists.

    df: full dataset (any date format, will be parsed)
    date_col, target_col: column names
    forecast_fn: a function with signature (train_df, horizon) -> list of
        `horizon` predicted values, called once per series if series_col
        is given. This is what makes the harness reusable by ANY
        forecaster -- callers plug in their own model here.
    horizon: how many steps ahead to forecast at each simulated point
    min_train_size: minimum number of unique dates before backtesting starts
    step: how many unique dates to advance between each simulated "pretend date"
    run_guardrails: if True (default), each window is checked with
        check_no_train_test_overlap and check_chronological_order.

    Returns a list of dicts: {"pretend_date": ..., "actual": [...],
    "predicted": [...]} -- with a "series" key added to each dict if
    series_col was given.

    Raises ValueError if forecast_fn returns the wrong number of
    predictions for the requested horizon, or if a single-series window
    ends up with more actual values than the horizon expects (a sign
    multiple series were mixed together without series_col).
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=dayfirst, format=date_format)

    if series_col is None:
        df_sorted = df.sort_values(date_col).reset_index(drop=True)
        return _backtest_single_series(
            df_sorted, date_col, target_col, forecast_fn,
            horizon, min_train_size, step, run_guardrails
        )

    all_results = []
    for series_value, series_df in df.groupby(series_col):
        series_sorted = series_df.sort_values(date_col).reset_index(drop=True)
        try:
            series_results = _backtest_single_series(
                series_sorted, date_col, target_col, forecast_fn,
                horizon, min_train_size, step, run_guardrails
            )
        except ValueError as e:
            raise ValueError(f"backtest: series '{series_value}' failed: {e}")

        for r in series_results:
            r["series"] = series_value
        all_results.extend(series_results)

    if not all_results:
        raise ValueError("backtest: no valid windows were produced across any series.")

    return all_results