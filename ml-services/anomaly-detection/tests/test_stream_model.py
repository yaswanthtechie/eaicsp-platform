import numpy as np
import pytest

from src.stream_model import (
    load_stream_model,
    save_stream_model,
    train_stream_model,
)
from src.stream_simulator import FEATURES


@pytest.fixture(scope="module")
def model():
    return train_stream_model()


NORMAL = {
    "temperature": 22.0,
    "humidity": 45.0,
    "door_open": 0,
    "power": 300.0,
}


def test_calibration_scores(model):

    assert model.calibration_scores.shape == (2000,)
    assert np.all(np.isfinite(model.calibration_scores))


def test_anomaly_scores_higher_than_normal(model):

    extreme = dict(NORMAL, temperature=40.0, power=600.0)

    assert model.score_one(extreme) > np.percentile(model.calibration_scores, 99)
    assert model.score_one(extreme) > model.score_one(NORMAL)


def test_explain_format_and_top_feature(model):

    result = model.explain(dict(NORMAL, temperature=40.0))

    assert 1 <= len(result) <= 3
    assert result[0]["feature"] == "temperature"
    assert result[0]["direction"] == "high"

    contributions = [item["contribution"] for item in result]

    assert contributions == sorted(contributions, reverse=True)
    assert sum(contributions) <= 1.0001
    assert all(item["feature"] in FEATURES for item in result)


def test_explain_low_direction(model):

    result = model.explain(dict(NORMAL, temperature=5.0))

    top = next(i for i in result if i["feature"] == "temperature")

    assert top["direction"] == "low"


def test_save_and_load_roundtrip(model, tmp_path):

    path = save_stream_model(model, tmp_path / "m.joblib")
    loaded = load_stream_model(path)

    assert loaded.score_one(NORMAL) == pytest.approx(model.score_one(NORMAL))
    assert loaded.explain(NORMAL)