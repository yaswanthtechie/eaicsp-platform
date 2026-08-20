import pytest
import pandas as pd

from src.adaptive_threshold import (
    get_adaptive_threshold,
    reset_adaptive_thresholds,
)

from src.model_loader import (
    feature_names,
    get_model_version,
    get_models,
)

from src.predict import (
    predict,
    adaptive_predict,
)


READING = {
    "temperature": 22.0,
    "humidity": 45.0,
    "stock_count": 100,
}


CALIBRATION_DATASET = (
    "output/calibration_normal.csv"
)


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_predict_returns_expected_schema(model):

    result = predict(READING, model)

    assert result["model"] == model
    assert "model_label" in result

    assert isinstance(result["is_anomaly"], bool)
    assert isinstance(result["score"], (int, float))

    assert "reasons" in result
    assert isinstance(result["reasons"], list)

    assert result["model_version"] == get_model_version()


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_predict_returns_three_feature_contributions(model):

    result = predict(READING, model)

    reasons = result["reasons"]

    assert len(reasons) == 3

    expected = {
        "temperature",
        "humidity",
        "stock_count",
    }

    returned = {r["feature"] for r in reasons}

    assert returned == expected


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_feature_contributions_are_valid(model):

    result = predict(READING, model)

    total = 0

    for reason in result["reasons"]:

        assert isinstance(
            reason["contribution"],
            (int, float),
        )

        assert reason["contribution"] >= 0

        total += reason["contribution"]

    # SHAP contributions are normalized
    assert abs(total - 1.0) < 1e-3


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_score_is_numeric(model):

    result = predict(READING, model)

    assert isinstance(
        result["score"],
        (int, float),
    )


def test_invalid_model_name():

    with pytest.raises(
        ValueError,
        match="Unknown model",
    ):

        predict(
            READING,
            "invalid_model",
        )


# Adaptive Prediction

@pytest.fixture(
    scope="module",
    autouse=True,
)
def initialize_adaptive_thresholds():

    df = pd.read_csv(
        CALIBRATION_DATASET
    )

    X = df[
        feature_names
    ].to_numpy()

    models = get_models()

    reset_adaptive_thresholds()

    for model_name, model in models.items():

        scores = -model.score(X)

        manager = get_adaptive_threshold(
            model_name
        )

        manager.initialize(
            scores
        )

    yield

    reset_adaptive_thresholds()


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_adaptive_predict_returns_expected_schema(
    model,
):

    result = adaptive_predict(
        READING,
        model,
    )

    assert result["model"] == model
    assert "model_label" in result
    assert "model_version" in result

    assert isinstance(
        result["is_anomaly"],
        bool,
    )

    assert isinstance(
        result["score"],
        (int, float),
    )

    assert isinstance(
        result["adaptive_threshold"],
        (int, float),
    )

    assert isinstance(
        result["model_prediction"],
        int,
    )

    assert isinstance(
        result["model_is_anomaly"],
        bool,
    )

    assert "reasons" in result
    assert isinstance(
        result["reasons"],
        list,
    )

    assert (
        result["model_version"]
        == get_model_version()
    )


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_adaptive_predict_uses_calibration_threshold(
    model,
):

    manager = get_adaptive_threshold(
        model
    )

    threshold_before = (
        manager.get_threshold()
    )

    result = adaptive_predict(
        READING,
        model,
    )

    assert (
        result["adaptive_threshold"]
        == threshold_before
    )


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_adaptive_predict_does_not_update_baseline(
    model,
):

    manager = get_adaptive_threshold(
        model
    )

    threshold_before = (
        manager.get_threshold()
    )

    state_before = (
        manager.get_state()
    )

    adaptive_predict(
        READING,
        model,
    )

    threshold_after = (
        manager.get_threshold()
    )

    state_after = (
        manager.get_state()
    )

    assert (
        threshold_after
        == threshold_before
    )

    assert (
        state_after["sample_count"]
        == state_before["sample_count"]
    )

    assert (
        state_after["adaptive_started"]
        == state_before["adaptive_started"]
    )


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_adaptive_predict_returns_three_feature_contributions(
    model,
):

    result = adaptive_predict(
        READING,
        model,
    )

    reasons = result["reasons"]

    assert len(reasons) == 3

    expected = {
        "temperature",
        "humidity",
        "stock_count",
    }

    returned = {
        r["feature"]
        for r in reasons
    }

    assert returned == expected


@pytest.mark.parametrize(
    "model",
    [
        "iforest",
        "lof",
        "ocsvm",
    ],
)
def test_adaptive_feature_contributions_are_valid(
    model,
):

    result = adaptive_predict(
        READING,
        model,
    )

    total = 0

    for reason in result["reasons"]:

        assert isinstance(
            reason["contribution"],
            (int, float),
        )

        assert reason["contribution"] >= 0

        total += reason["contribution"]

    # SHAP contributions are normalized
    assert abs(total - 1.0) < 1e-3