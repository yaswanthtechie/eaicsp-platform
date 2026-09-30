# test_regressor_ablation.py

import numpy as np
import pandas as pd
import pytest

import src.regressor_ablation as ra
from src.regressor_ablation import (
    build_ablation_experiments,
    calculate_delta,
    interpret_result,
    noise_band,
    score,
    split_at_cutoff,
    with_weather_seed,
)
from src.train_prophet import (
    EXTERNAL_REGRESSORS,
    predict_prophet,
    resolve_regressors,
    train_prophet,
)


def _monthly(n=48):
    """Small monthly series with all three regressors."""
    dates = pd.date_range("2010-01-01", periods=n, freq="MS")
    y = 1000 + 50 * np.sin(np.arange(n) * 2 * np.pi / 12) + np.arange(n)
    df = pd.DataFrame({"ds": dates, "y": y})
    df["is_holiday"] = df["ds"].dt.month.isin([11, 12]).astype(int)
    df["promotion"] = df["ds"].dt.month.isin([3, 6, 9, 12]).astype(int)
    df["weather_index"] = np.random.default_rng(0).uniform(0, 1, n)
    return df


# ------------------------------------------------------------------
# Experiment design
# ------------------------------------------------------------------

def test_experiments_are_baseline_three_removals_and_no_regressors():
    names = [e["experiment"] for e in build_ablation_experiments()]

    assert names == [
        "baseline",
        "remove_is_holiday",
        "remove_promotion",
        "remove_weather_index",
        "no_regressors",
    ]


def test_each_removal_drops_exactly_one_regressor():
    for e in build_ablation_experiments()[1:4]:
        assert e["removed_regressor"] not in e["regressors"]
        assert len(e["regressors"]) == len(EXTERNAL_REGRESSORS) - 1


def test_no_regressors_experiment_uses_none():
    assert build_ablation_experiments()[-1]["regressors"] == []


def test_split_at_cutoff_is_time_based():
    train, test = split_at_cutoff(_monthly(), "2012-01-01", horizon_months=12)

    assert train["ds"].max() < pd.Timestamp("2012-01-01")
    assert test["ds"].min() == pd.Timestamp("2012-01-01")
    assert len(test) == 12


def test_with_weather_seed_changes_only_weather():
    df = _monthly()
    redrawn = with_weather_seed(df, seed=7)

    assert not np.allclose(df["weather_index"], redrawn["weather_index"])
    pd.testing.assert_frame_equal(
        df.drop(columns="weather_index"), redrawn.drop(columns="weather_index")
    )


# ------------------------------------------------------------------
# Metrics and honest interpretation
# ------------------------------------------------------------------

def test_score_is_unrounded():
    metrics = score([100.0, 200.0, 300.0], [101.0, 199.0, 302.0])
    assert metrics["MAPE"] == pytest.approx((1 / 100 + 1 / 200 + 2 / 300) / 3 * 100)


def test_calculate_delta():
    assert calculate_delta(3.42, 3.46) == pytest.approx(0.04)
    assert calculate_delta(3.42, 3.40) == pytest.approx(-0.02)


def test_noise_band_is_the_full_spread():
    assert noise_band([4.50, 4.53, 4.49, 4.54]) == pytest.approx(0.05)


@pytest.mark.parametrize("delta, expected", [
    (0.04, "no measurable effect"),   # inside a 0.05 band
    (-0.04, "no measurable effect"),
    (0.20, "it helps"),               # removing it made MAPE worse
    (-0.20, "it hurts"),              # removing it made MAPE better
])
def test_interpretation_respects_the_noise_band(delta, expected):
    row = {"experiment": "remove_promotion", "removed_regressor": "promotion", "delta_MAPE": delta}
    assert expected in interpret_result(row, band=0.05)


def test_baseline_interpretation():
    assert interpret_result({"experiment": "baseline"}, band=0.05) == "Baseline with all regressors."


# ------------------------------------------------------------------
# New train_prophet behaviour: subsets of regressors
# ------------------------------------------------------------------

def test_resolve_regressors_rejects_unknown_and_duplicates():
    with pytest.raises(ValueError, match="Unknown"):
        resolve_regressors(["not_a_regressor"])
    with pytest.raises(ValueError, match="Duplicate"):
        resolve_regressors(["promotion", "promotion"])


@pytest.mark.parametrize("regressors", [["promotion"], []])
def test_train_and_predict_with_subset_of_regressors(regressors, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # save_model=False must not write output/
    train, test = split_at_cutoff(_monthly(), "2013-01-01", horizon_months=6)

    model = train_prophet(train, regressors=regressors, save_model=False)
    forecast = predict_prophet(model, test, regressors=regressors)

    assert len(forecast) == len(test)
    assert set(model.extra_regressors) == set(regressors)
    assert not (tmp_path / "output").exists()


# ------------------------------------------------------------------
# MLflow: every experiment is logged
# ------------------------------------------------------------------

def test_study_logs_every_experiment_to_mlflow(tmp_path, monkeypatch):
    import mlflow

    # Fast fake backtest: the study's bookkeeping is what is under test.
    fake_mape = {3: 4.50, 2: 4.51, 0: 4.52}
    monkeypatch.setattr(
        ra, "backtest", lambda df, regressors: {"MAPE": fake_mape[len(regressors)], "RMSE": 100.0}
    )
    monkeypatch.setattr(ra, "prepare_dataset", _monthly)
    monkeypatch.setattr(ra, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(ra, "RESULTS_PATH", tmp_path / "ablation_results.csv")
    monkeypatch.setattr(ra, "NOISE_PATH", tmp_path / "noise_band.csv")

    # Keep the tracking DB and artifacts inside tmp_path, never in the repo.
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    mlflow.create_experiment(ra.MLFLOW_EXPERIMENT, artifact_location=(tmp_path / "artifacts").as_uri())

    results, noise = ra.run_ablation_study()

    runs = mlflow.search_runs(experiment_names=[ra.MLFLOW_EXPERIMENT])
    child_runs = runs[runs["tags.mlflow.parentRunId"].notna()]
    assert set(child_runs["tags.mlflow.runName"]) == {e["experiment"] for e in build_ablation_experiments()}
    assert child_runs["metrics.mape"].notna().all()
    assert (tmp_path / "ablation_results.csv").exists()
    assert len(noise) == len(ra.NOISE_SEEDS)