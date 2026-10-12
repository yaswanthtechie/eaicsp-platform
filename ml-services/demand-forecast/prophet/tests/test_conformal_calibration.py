import pandas as pd
import pytest

from src.train_multi_horizon import (
    
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
import contextlib

import pandas as pd

import src.train_multi_horizon as tmh


def test_train_all_runs_calibration_and_logs_to_mlflow(monkeypatch):
    calls = []

    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=3),
            "quantity_sold": [1.0, 2.0, 3.0],
        }
    )

    def fake_calibrate(data):
        calls.append("calibrate")
        return {"ratio_quantiles": {}}

    def fake_log(calibration, weights, n_rows):
        calls.append("log")

    monkeypatch.setattr(tmh, "load_daily_data", lambda: df)
    monkeypatch.setattr(tmh, "evaluate_xgboost_daily", lambda *a, **k: None)
    monkeypatch.setattr(tmh, "train_prophet_daily", lambda data: "prophet")
    monkeypatch.setattr(tmh, "train_xgboost_daily", lambda data: "xgb")
    monkeypatch.setattr(tmh, "calibrate_horizon_intervals", fake_calibrate)
    monkeypatch.setattr(
        tmh,
        "load_ensemble_weights",
        lambda: {"prophet": 0.5, "xgb": 0.5},
    )
    monkeypatch.setattr(tmh, "log_training_run", fake_log)
    monkeypatch.setattr(
        tmh.mlflow,
        "set_experiment",
        lambda name: None,
    )
    monkeypatch.setattr(
        tmh.mlflow,
        "start_run",
        lambda **k: contextlib.nullcontext(),
    )

    tmh.train_all()

    assert calls == ["calibrate", "log"]
                    