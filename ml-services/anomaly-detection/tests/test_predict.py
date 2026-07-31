import pytest

from src.predict import predict

READING = {
    "temperature": 22.0,
    "humidity": 45.0,
    "stock_count": 100,
}


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

    assert result["model_version"] == "1.0.0"


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

        assert isinstance(reason["contribution"], (int, float))
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

    assert isinstance(result["score"], (int, float))


def test_invalid_model_name():

    with pytest.raises(ValueError, match="Unknown model"):
        predict(READING, "invalid_model")