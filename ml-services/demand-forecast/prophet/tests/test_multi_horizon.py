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