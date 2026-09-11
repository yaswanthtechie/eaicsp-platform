import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

import pytest

from src.ensemble import (
    validate_weights,
    weighted_ensemble,
    ensemble_interval,
)


def test_valid_weights():

    assert validate_weights(
        0.3,
        0.7
    ) is True


def test_prophet_weight_zero():

    assert validate_weights(
        0.0,
        1.0
    ) is True


def test_xgb_weight_zero():

    assert validate_weights(
        1.0,
        0.0
    ) is True


def test_both_weights_valid():

    assert validate_weights(
        0.5,
        0.5
    ) is True


def test_invalid_weights_not_sum_to_one():

    with pytest.raises(
        ValueError,
        match="sum to 1"
    ):

        validate_weights(
            0.5,
            0.8
        )


def test_negative_prophet_weight():

    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):

        validate_weights(
            -0.1,
            1.1
        )


def test_negative_xgb_weight():

    with pytest.raises(
        ValueError,
        match="cannot be negative"
    ):

        validate_weights(
            1.1,
            -0.1
        )


def test_weighted_ensemble():

    result = weighted_ensemble(
        prophet_prediction=100,
        xgb_prediction=200,
        prophet_weight=0.3,
        xgb_weight=0.7
    )

    assert result == 170


def test_ensemble_interval():

    lower, upper = ensemble_interval(
        prophet_lower=80,
        prophet_upper=120,
        xgb_lower=160,
        xgb_upper=240,
        prophet_weight=0.3,
        xgb_weight=0.7
    )

    predicted = weighted_ensemble(
        prophet_prediction=100,
        xgb_prediction=200,
        prophet_weight=0.3,
        xgb_weight=0.7
    )

    assert lower <= predicted <= upper