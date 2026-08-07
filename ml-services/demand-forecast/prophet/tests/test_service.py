import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from src.predict import predict



def test_prediction():

    result = predict(30)

    assert isinstance(
        result,
        dict
    )

    assert "forecast" in result

    assert len(
        result["forecast"]
    ) == 30




def test_output():

    result = predict(5)

    forecast = result["forecast"]

    assert len(
        forecast
    ) == 5


    assert "date" in forecast[0]

    assert "predicted" in forecast[0]

    assert "lower" in forecast[0]

    assert "upper" in forecast[0]