import pandas as pd
import pytest

from src.train_multi_horizon import (
    _split_calibration_test,
    _split_backtest_calibration_evaluation,
)


def _make_history(rows=200):
    return pd.DataFrame(
        {
            "date": pd.date_range(
                "2020-01-01",
                periods=rows,
                freq="D",
            ),
            "quantity_sold": range(rows),
        }
    )


def test_split_calibration_and_test_chronologically():
    df = _make_history(200)

    calibration, test = (
        _split_calibration_test(
            df,
            calibration_days=30,
            test_days=20,
        )
    )

    assert len(calibration) == 30
    assert len(test) == 20

    assert (
        calibration["date"].max()
        < test["date"].min()
    )


def test_split_uses_latest_test_window():
    df = _make_history(200)

    calibration, test = (
        _split_calibration_test(
            df,
            calibration_days=30,
            test_days=20,
        )
    )

    assert test["date"].min() == pd.Timestamp(
        "2020-06-29"
    )

    assert test["date"].max() == pd.Timestamp(
        "2020-07-18"
    )


def test_split_rejects_invalid_window():
    df = _make_history(100)

    with pytest.raises(ValueError):
        _split_calibration_test(
            df,
            calibration_days=0,
            test_days=20,
        )

    with pytest.raises(ValueError):
        _split_calibration_test(
            df,
            calibration_days=20,
            test_days=0,
        )


def test_split_rejects_insufficient_history():
    df = _make_history(50)

    with pytest.raises(ValueError):
        _split_calibration_test(
            df,
            calibration_days=30,
            test_days=20,
        )
def _make_backtest():
    rows = []

    for cutoff in pd.date_range(
        "2024-01-01",
        periods=6,
        freq="30D",
    ):
        for horizon in [
            "1_day",
            "7_day",
        ]:
            rows.append(
                {
                    "cutoff": cutoff,
                    "horizon": horizon,
                    "actual": 100.0,
                    "predicted": 95.0,
                }
            )

    return pd.DataFrame(rows)


def test_backtest_split_is_chronological():
    backtest = _make_backtest()

    calibration, evaluation = (
        _split_backtest_calibration_evaluation(
            backtest,
            calibration_cutoffs=4,
        )
    )

    assert calibration["cutoff"].nunique() == 4
    assert evaluation["cutoff"].nunique() == 2

    assert (
        calibration["cutoff"].max()
        < evaluation["cutoff"].min()
    )


def test_backtest_split_preserves_all_rows():
    backtest = _make_backtest()

    calibration, evaluation = (
        _split_backtest_calibration_evaluation(
            backtest,
            calibration_cutoffs=4,
        )
    )

    assert (
        len(calibration) + len(evaluation)
        == len(backtest)
    )


def test_backtest_split_rejects_too_many_calibration_cutoffs():
    backtest = _make_backtest()

    with pytest.raises(ValueError):
        _split_backtest_calibration_evaluation(
            backtest,
            calibration_cutoffs=6,
        )        