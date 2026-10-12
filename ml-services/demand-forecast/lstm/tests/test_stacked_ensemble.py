import numpy as np
import pandas as pd
import pytest

import stacked_ensemble as stacked


def sample_data(rows=120):
    return pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=rows, freq="D"),
        "Demand": 100 + np.arange(rows, dtype=float),
    })


def test_oof_blocks_use_only_prior_history(monkeypatch):
    df = sample_data()
    calls = []

    def fake_predict(history, forecast):
        assert history["Date"].max() < forecast["Date"].min()
        assert history["Date"].max() + pd.Timedelta(days=1) == (
            forecast["Date"].min()
        )
        calls.append((history["Date"].max(), forecast["Date"].min()))
        values = np.full(len(forecast), float(history["Demand"].iloc[-1]))
        return {
            "Prophet": values,
            "XGBoost": values + 1,
            "LSTM": values + 2,
        }

    monkeypatch.setattr(stacked, "_predict_base_models", fake_predict)

    result = stacked.generate_oof_predictions(
        df, start_idx=70, end_idx=100, block_size=10
    )

    assert len(result) == 30
    assert len(calls) == 3
    assert not result["Date"].duplicated().any()
    assert result["Date"].min() == df.iloc[70]["Date"]
    assert result["Date"].max() == df.iloc[99]["Date"]


def test_oof_rejects_invalid_ranges():
    df = sample_data()

    with pytest.raises(ValueError):
        stacked.generate_oof_predictions(df, 0, 20)

    with pytest.raises(ValueError):
        stacked.generate_oof_predictions(df, 20, 121)

    with pytest.raises(ValueError):
        stacked.generate_oof_predictions(df, 20, 40, block_size=0)


def test_meta_learner_uses_oof_prediction_columns():
    actual = np.arange(20, dtype=float) + 100
    oof = pd.DataFrame({
        "Actual": actual,
        "Prophet": actual + 1,
        "XGBoost": actual - 2,
        "LSTM": actual + 3,
    })

    model = stacked.fit_meta_learner(oof)

    assert len(model.coef_) == 3
    assert np.isfinite(model.coef_).all()


def test_meta_learner_rejects_missing_oof_columns():
    oof = pd.DataFrame({
        "Actual": [10.0, 11.0],
        "Prophet": [10.5, 10.5],
    })

    with pytest.raises(ValueError, match="Missing OOF columns"):
        stacked.fit_meta_learner(oof)


def test_all_methods_use_the_same_test_rows():
    actual = np.arange(20, dtype=float) + 100
    test = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=20, freq="D"),
        "Actual": actual,
        "Prophet": actual + 1,
        "XGBoost": actual - 2,
        "LSTM": actual + 3,
    })

    model = stacked.fit_meta_learner(test[[
        "Actual", "Prophet", "XGBoost", "LSTM"
    ]])
    result, metrics = stacked.evaluate_test_predictions(test, model)

    assert len(result) == len(test)
    assert set(metrics) == {
        "Prophet",
        "XGBoost",
        "LSTM",
        "EqualWeightAverage",
        "StackedRidge",
    }
    assert all(set(values) == {"MAE", "RMSE", "MAPE"}
               for values in metrics.values())


def test_equal_weight_average_is_exact_mean():
    actual = np.array([10.0, 20.0, 30.0])
    test = pd.DataFrame({
        "Actual": actual,
        "Prophet": actual + 3,
        "XGBoost": actual + 6,
        "LSTM": actual + 9,
    })

    model = stacked.fit_meta_learner(test)
    result, _ = stacked.evaluate_test_predictions(test, model)

    np.testing.assert_allclose(
        result["EqualWeightAverage"].to_numpy(),
        np.mean(
            test[["Prophet", "XGBoost", "LSTM"]].to_numpy(),
            axis=1,
        ),
    )
