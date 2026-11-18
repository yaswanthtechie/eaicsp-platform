import numpy as np


def test_unk_prediction_is_clipped_before_embedding_effect():
    forecast = np.array([0.0, 5.0, 10.0])
    unk_prediction = np.array([-3.0, 2.0, 12.0])

    unk_prediction = np.maximum(unk_prediction, 0)
    embedding_effect = forecast - unk_prediction

    np.testing.assert_array_equal(
        unk_prediction,
        np.array([0.0, 2.0, 12.0]),
    )
    np.testing.assert_array_equal(
        embedding_effect,
        np.array([0.0, 3.0, -2.0]),
    )
