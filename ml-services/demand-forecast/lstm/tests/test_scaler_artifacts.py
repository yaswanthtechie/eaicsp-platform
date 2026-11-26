"""Scaler JSON format and the committed output/ artifacts."""

from pathlib import Path

import numpy as np
import pytest
from sklearn.preprocessing import MinMaxScaler

from src.config import LOOKBACK, SCALER_PATH
from src.data import load_scaler, save_scaler
from src.predict import forecast_demand

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def test_scaler_json_round_trip(tmp_path):
    original = MinMaxScaler().fit(np.array([[3.0], [10.0], [250.0]]))
    path = tmp_path / "scaler.json"

    save_scaler(original, path)
    loaded = load_scaler(path)

    values = np.array([[0.0], [50.0], [123.4], [1000.0]])
    assert np.allclose(loaded.transform(values), original.transform(values))
    assert np.allclose(
        loaded.inverse_transform(values), original.inverse_transform(values)
    )


def test_scaler_json_with_missing_key_fails_clearly(tmp_path):
    path = tmp_path / "scaler.json"
    path.write_text('{"feature_range": [0, 1]}', encoding="utf-8")

    with pytest.raises(ValueError, match="missing keys"):
        load_scaler(path)


def test_committed_scaler_is_json_and_loads():
    assert Path(SCALER_PATH) == OUTPUT_DIR / "scaler.json"
    scaler = load_scaler(SCALER_PATH)
    assert scaler.n_features_in_ == 1
    assert not (OUTPUT_DIR / "scaler.pkl").exists()


def test_forecast_runs_on_committed_artifacts():
    result = forecast_demand([100.0] * LOOKBACK)

    assert len(result["mean_forecast"]) > 0
    assert all(value >= 0 for value in result["mean_forecast"])
