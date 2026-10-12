import ast
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.multi_horizon import (
    add_intervals,
    check_history_matches_model,
    prepare_history,
    reconcile_horizons,
    validate_history,
    validate_reconciliation,
)
from src.multi_horizon_config import HORIZONS, INTERVALS_PATH
from src.multi_horizon_inference import predict_future_xgboost
from src.train_multi_horizon import fit_xgboost


def _series(days=120):
    dates = pd.date_range("2020-01-01", periods=days, freq="D")
    y = 100 + 10 * np.sin(np.arange(days) * 2 * np.pi / 7)
    return pd.DataFrame({"ds": dates, "y": y})


def _path(values):
    dates = pd.date_range("2021-01-01", periods=len(values), freq="D")
    return [{"date": d.strftime("%Y-%m-%d"), "prediction": float(v)} for d, v in zip(dates, values)]


def _calibration(low=0.9, high=1.1):
    return {
        "interval_label": "test",
        "ratio_quantiles": {name: {"low": low, "high": high} for name in HORIZONS},
    }


def test_prediction_module_does_not_import_training_code():
    source = Path(__file__).resolve().parents[1] / "src" / "multi_horizon.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not any("train" in m for m in modules)


def test_horizons_are_sums_of_one_daily_path():
    path = _path(range(1, 91))
    horizons = reconcile_horizons(path)
    assert horizons["1_day"]["predicted"] == 1
    assert horizons["7_day"]["predicted"] == sum(range(1, 8))
    assert horizons["90_day"]["predicted"] == sum(range(1, 91))
    assert horizons["90_day"]["end_date"] == path[89]["date"]


def test_reconciliation_check_catches_tampered_total():
    path = _path([100] * 90)
    horizons = add_intervals(reconcile_horizons(path), _calibration())
    horizons["30_day"]["predicted"] += 50
    with pytest.raises(ValueError, match="30_day"):
        validate_reconciliation(horizons, path)


def test_intervals_widen_with_horizon_and_pass_validation():
    path = _path([100] * 90)
    horizons = add_intervals(reconcile_horizons(path), _calibration())
    widths = [horizons[n]["upper"] - horizons[n]["lower"] for n in HORIZONS]
    assert widths == sorted(widths)
    validate_reconciliation(horizons, path)


def test_shrinking_interval_is_rejected():
    path = _path([100] * 90)
    horizons = add_intervals(reconcile_horizons(path), _calibration())
    horizons["90_day"]["lower"] = horizons["90_day"]["upper"] - 1
    with pytest.raises(ValueError, match="shrinks"):
        validate_reconciliation(horizons, path)


def test_history_with_gap_is_rejected():
    history = prepare_history(_series().drop(index=50))
    with pytest.raises(ValueError, match="continuous"):
        validate_history(history)


def test_history_must_match_training_end():
    history = prepare_history(_series())
    model = SimpleNamespace(history=history.iloc[:-10])
    with pytest.raises(ValueError, match="Retrain"):
        check_history_matches_model(model, history)


def test_recursive_xgboost_forecast_with_explanations():
    history = _series()
    package = fit_xgboost(history)

    forecast = predict_future_xgboost(package, history, horizon_days=10)

    assert len(forecast) == 10
    dates = pd.to_datetime([r["date"] for r in forecast])
    assert (dates.to_series().diff().dropna() == pd.Timedelta(days=1)).all()
    assert dates[0] == history["ds"].max() + pd.Timedelta(days=1)
    for row in forecast:
        assert np.isclose(sum(row["contributions"].values()), row["prediction"], atol=0.05)


@pytest.mark.skipif(not INTERVALS_PATH.exists(), reason="run python -m src.train_multi_horizon first")
def test_end_to_end_predict_on_committed_models():
    from src.multi_horizon import predict

    result = predict()
    assert len(result["forecast"]) == 90
    for name in HORIZONS:
        horizon = result["horizons"][name]
        assert horizon["lower"] <= horizon["upper"]
        assert horizon["explanation"]["top_drivers"]


# ---------------------------------------------------------------------------
# Calibration: real MAPE, real 80% interval, per-horizon (not copied)
# ---------------------------------------------------------------------------

from src.multi_horizon import parse_ensemble_weights
from src.train_multi_horizon import summarise_backtest


def _backtest(errors_by_horizon, predicted=1000.0):
    """One row per (cutoff, horizon) with actual = predicted * (1 + error)."""
    rows = []
    for horizon, errors in errors_by_horizon.items():
        for e in errors:
            rows.append({"horizon": horizon, "predicted": predicted, "actual": predicted * (1 + e)})
    return pd.DataFrame(rows)


def test_summarise_backtest_reports_real_mape_and_80_percent_label():
    errors = np.linspace(-0.2, 0.2, 21)  # symmetric errors from -20% to +20%
    result = summarise_backtest(_backtest({name: errors for name in HORIZONS}))

    assert result["interval_label"] == "80% empirical interval"
    for name in HORIZONS:
        q = result["ratio_quantiles"][name]
        assert q["low"] == pytest.approx(1 + np.quantile(errors, 0.10))
        assert q["high"] == pytest.approx(1 + np.quantile(errors, 0.90))
        expected_mape = np.mean(np.abs(errors) / (1 + errors)) * 100  # |a - p| / a
        assert result["backtest_metrics"][name]["mape"] == pytest.approx(expected_mape, abs=0.01)


def test_each_horizon_is_calibrated_on_its_own_errors():
    result = summarise_backtest(_backtest({
        "1_day": np.linspace(-0.20, 0.20, 21),
        "7_day": np.linspace(-0.10, 0.10, 21),
        "30_day": np.linspace(-0.05, 0.05, 21),
        "90_day": np.linspace(-0.03, 0.03, 21),
    }))

    highs = [result["ratio_quantiles"][name]["high"] for name in HORIZONS]
    assert len(set(highs)) == 4  # not copied from the 1-day horizon


def test_interval_always_contains_the_prediction():
    # The model always under-forecasts, so every error is positive.
    result = summarise_backtest(_backtest({name: np.linspace(0.05, 0.15, 11) for name in HORIZONS}))

    for name in HORIZONS:
        assert result["ratio_quantiles"][name]["low"] == 1.0
        assert result["ratio_quantiles"][name]["high"] > 1.0
        assert result["backtest_metrics"][name]["bias_pct"] > 0


def test_summarise_backtest_needs_enough_observations():
    with pytest.raises(ValueError, match="Not enough calibration observations"):
        summarise_backtest(_backtest({name: [0.1, -0.1] for name in HORIZONS}))


# ---------------------------------------------------------------------------
# Weights: both formats that exist in the repo are accepted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("weights", [
    {"prophet": 0.7, "xgb": 0.3},                 # this PR
    {"prophet_weight": 0.7, "xgb_weight": 0.3},   # automated_retraining.py
])
def test_parse_ensemble_weights_accepts_both_formats(weights):
    assert parse_ensemble_weights(weights) == {"prophet": 0.7, "xgb": 0.3}


@pytest.mark.parametrize("weights, message", [
    ({"a": 1}, "must contain"),
    ({"prophet": 0.8, "xgb": 0.3}, "sum to 1.0"),
    ({"prophet": 1.2, "xgb": -0.2}, "negative"),
])
def test_parse_ensemble_weights_rejects_bad_input(weights, message):
    with pytest.raises(ValueError, match=message):
        parse_ensemble_weights(weights)


# ---------------------------------------------------------------------------
# MLflow: the training run is actually logged
# ---------------------------------------------------------------------------

def test_log_training_run_logs_params_metrics_and_artifacts(tmp_path, monkeypatch):
    import mlflow
    import src.train_multi_horizon as tmh

    artifacts = {}
    for attr in ("PROPHET_MODEL_PATH", "XGB_MODEL_PATH", "INTERVALS_PATH", "BACKTEST_RESULTS_PATH"):
        path = tmp_path / f"{attr.lower()}.txt"
        path.write_text("x", encoding="utf-8")
        monkeypatch.setattr(tmh, attr, path)
        artifacts[attr] = path.name

    calibration = summarise_backtest(_backtest({name: np.linspace(-0.1, 0.1, 11) for name in HORIZONS}))
    calibration["backtest_cutoffs"] = 11

    # Keep the tracking DB and artifacts inside tmp_path, never in the repo.
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    experiment_id = mlflow.create_experiment(
        "test_multi_horizon",
        artifact_location=(tmp_path / "artifacts").as_uri(),
    )
    with mlflow.start_run(experiment_id=experiment_id) as run:
        tmh.log_training_run(calibration, {"prophet": 0.7, "xgb": 0.3}, n_rows=1913)

    logged = mlflow.get_run(run.info.run_id).data
    assert logged.params["weight_prophet"] == "0.7"
    for name in HORIZONS:
        assert f"{name}_mape" in logged.metrics
        assert f"{name}_interval_coverage" in logged.metrics

    listed = {a.path for a in mlflow.MlflowClient().list_artifacts(run.info.run_id, "multi_horizon")}
    assert {f"multi_horizon/{n}" for n in artifacts.values()} <= listed