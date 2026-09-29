# test_regressor_ablation.py

import pandas as pd
import pytest

from src.regressor_ablation import (
    build_ablation_experiments,
    calculate_delta,
    interpret_result,
)


def test_ablation_creates_baseline_and_three_removals():

    experiments = (
        build_ablation_experiments()
    )

    assert len(experiments) == 4

    names = [
        experiment["experiment"]
        for experiment in experiments
    ]

    assert names == [
        "baseline",
        "remove_is_holiday",
        "remove_promotion",
        "remove_weather_index",
    ]


def test_baseline_uses_all_regressors():

    experiments = (
        build_ablation_experiments()
    )

    baseline = experiments[0]

    assert baseline["removed_regressor"] is None

    assert baseline["regressors"] == [
        "is_holiday",
        "promotion",
        "weather_index",
    ]


def test_each_ablation_removes_only_one_regressor():

    experiments = (
        build_ablation_experiments()
    )

    for experiment in experiments[1:]:

        removed = (
            experiment["removed_regressor"]
        )

        regressors = (
            experiment["regressors"]
        )

        assert removed not in regressors

        assert len(regressors) == 2


def test_calculate_delta():

    assert (
        calculate_delta(
            10.0,
            12.0,
        )
        == 2.0
    )

    assert (
        calculate_delta(
            10.0,
            8.0,
        )
        == -2.0
    )


def test_baseline_interpretation():

    row = pd.Series(
        {
            "experiment": "baseline",
            "delta_MAPE": 0.0,
            "delta_RMSE": 0.0,
        }
    )

    result = interpret_result(
        row
    )

    assert (
        result
        == "Baseline with all regressors."
    )


def test_regressor_removal_worsens_metrics():

    row = pd.Series(
        {
            "experiment": "remove_promotion",
            "delta_MAPE": 1.5,
            "delta_RMSE": 500.0,
        }
    )

    result = interpret_result(
        row
    )

    assert (
        "worsened"
        in result
    )


def test_regressor_removal_improves_metrics():

    row = pd.Series(
        {
            "experiment": "remove_weather_index",
            "delta_MAPE": -1.0,
            "delta_RMSE": -250.0,
        }
    )

    result = interpret_result(
        row
    )

    assert (
        "improved"
        in result
    )