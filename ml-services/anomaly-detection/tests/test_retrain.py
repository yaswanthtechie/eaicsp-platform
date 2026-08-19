import pandas as pd

from src.retrain import (
    WINDOW_SIZE,
    compare_models,
    generate_rolling_windows,
    increment_version,
)


# Version Incrementing

def test_increment_version():
    assert increment_version("1.0.0") == "1.0.1"
    assert increment_version("2.5.9") == "2.5.10"
    assert increment_version("10.0.99") == "10.0.100"


# Rolling Window Generation


def test_generate_rolling_windows_count():
    windows = generate_rolling_windows()

    # 35 days -> 6 rolling windows of 30 days
    assert len(windows) == 6


def test_generate_rolling_window_size():
    windows = generate_rolling_windows()

    for (
        window_number,
        start_day,
        end_day,
        window_df,
    ) in windows:

        assert len(window_df) == WINDOW_SIZE


def test_generate_rolling_window_days():
    windows = generate_rolling_windows()

    first = windows[0]
    last = windows[-1]

    assert first[1] == 1
    assert first[2] == 30

    assert last[1] == 6
    assert last[2] == 35


# Model Comparison

def test_compare_models_deploy():

    deployed = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
            ],
            "Precision": [
                0.80,
                0.85,
            ],
        }
    )

    candidate = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
            ],
            "Precision": [
                0.90,
                0.90,
            ],
        }
    )

    comparison = compare_models(
        deployed,
        candidate,
    )

    assert comparison["Isolation Forest"]
    assert comparison["LOF"]


def test_compare_models_reject():

    deployed = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
            ],
            "Precision": [
                0.95,
                0.92,
            ],
        }
    )

    candidate = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
            ],
            "Precision": [
                0.82,
                0.90,
            ],
        }
    )

    comparison = compare_models(
        deployed,
        candidate,
    )

    assert not comparison["Isolation Forest"]
    assert not comparison["LOF"]


def test_compare_models_mixed():

    deployed = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
                "One-Class SVM",
            ],
            "Precision": [
                0.80,
                0.90,
                0.75,
            ],
        }
    )

    candidate = pd.DataFrame(
        {
            "Model": [
                "Isolation Forest",
                "LOF",
                "One-Class SVM",
            ],
            "Precision": [
                0.83,
                0.88,
                0.78,
            ],
        }
    )

    comparison = compare_models(
        deployed,
        candidate,
    )

    assert comparison["Isolation Forest"]
    assert not comparison["LOF"]
    assert comparison["One-Class SVM"]