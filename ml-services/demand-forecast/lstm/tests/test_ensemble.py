import numpy as np
import pandas as pd
import pytest

import ensemble
from data import generate_data
from ensemble import (
    MODEL_NAMES,
    check_contiguous,
    combine,
    create_time_split,
    explain_predictions,
    find_best_ensemble_weights,
    fit_lstm_and_predict,
    fit_xgboost_and_predict,
)


@pytest.fixture(scope="module")
def splits():
    return create_time_split(generate_data(days=300))


def test_time_split_is_chronological_and_non_overlapping(splits):
    train_df, validation_df, test_df = splits

    assert train_df["Date"].max() < validation_df["Date"].min()
    assert validation_df["Date"].max() < test_df["Date"].min()
    assert len(train_df) + len(validation_df) + len(test_df) == 300


def test_forecast_with_gap_is_rejected(splits):
    train_df, _, test_df = splits

    with pytest.raises(ValueError, match="history ends"):
        check_contiguous(train_df, test_df)


def test_xgboost_never_reads_future_demand(splits):
    train_df, validation_df, _ = splits
    scrambled = validation_df.copy()
    scrambled["Demand"] = 1e6

    original = fit_xgboost_and_predict(train_df, validation_df)
    after = fit_xgboost_and_predict(train_df, scrambled)

    np.testing.assert_allclose(original, after)


def test_lstm_never_reads_future_demand(splits, monkeypatch):
    monkeypatch.setattr(ensemble, "EPOCHS", 1)
    train_df, validation_df, _ = splits
    scrambled = validation_df.copy()
    scrambled["Demand"] = 1e6

    original = fit_lstm_and_predict(train_df, validation_df)
    after = fit_lstm_and_predict(train_df, scrambled)

    assert len(original) == len(validation_df)
    np.testing.assert_allclose(original, after)


def test_weights_sum_to_one_and_respect_min_weight():
    rng = np.random.default_rng(0)
    y_true = rng.normal(100, 5, 50)
    predictions = {name: y_true + rng.normal(0, i + 1, 50) for i, name in enumerate(MODEL_NAMES)}

    weights, _ = find_best_ensemble_weights(y_true, predictions, min_weight=0.05)

    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(w >= 0.05 - 1e-9 for w in weights.values())


def test_weight_grid_does_not_skip_edge_splits():
    # Prophet is perfect, the other two are both +50 too high, so the unique
    # best split is Prophet 0.90 / XGBoost 0.05 / LSTM 0.05 (MAE 5.0).
    # The old float grid computed LSTM as 0.0499999... and skipped it.
    y_true = np.full(10, 100.0)
    predictions = {
        "Prophet": np.full(10, 100.0),
        "XGBoost": np.full(10, 150.0),
        "LSTM": np.full(10, 150.0),
    }

    weights, mae = find_best_ensemble_weights(y_true, predictions, min_weight=0.05)

    assert mae == pytest.approx(5.0)
    assert weights == pytest.approx({"Prophet": 0.90, "XGBoost": 0.05, "LSTM": 0.05})


def test_explanation_contributions_sum_to_ensemble():
    dates = pd.Series(pd.date_range("2024-01-01", periods=5))
    predictions = {name: np.arange(5, dtype=float) + i for i, name in enumerate(MODEL_NAMES)}
    weights = {"Prophet": 0.6, "XGBoost": 0.1, "LSTM": 0.3}

    table = explain_predictions(dates, predictions, weights)
    contribution_sum = table[[f"{n}_contribution" for n in MODEL_NAMES]].sum(axis=1)

    np.testing.assert_allclose(contribution_sum, table["Ensemble"])
    np.testing.assert_allclose(table["Ensemble"], combine(predictions, weights))
    assert set(table["top_contributor"]) <= set(MODEL_NAMES)