from types import SimpleNamespace

import numpy as np
import pandas as pd

import src.stacked_ensemble as stacked

def test_robustness_run_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(stacked, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(stacked, "set_seeds", lambda seed: None)

    dates = pd.date_range("2026-01-01", periods=20, freq="D")
    data = pd.DataFrame({
        "Date": dates,
        "Demand": np.arange(20, dtype=float),
    })

    monkeypatch.setattr(
        stacked,
        "generate_data",
        lambda days, seed: data.copy(),
    )

    def fake_predictions(df, start, end, block_size):
        return df.iloc[start:end].copy()

    monkeypatch.setattr(
        stacked, "generate_oof_predictions", fake_predictions
    )

    fake_meta = SimpleNamespace(
        coef_=np.zeros(len(stacked.BASE_COLUMNS)),
        intercept_=0.0,
    )
    monkeypatch.setattr(
        stacked, "fit_meta_learner", lambda predictions: fake_meta
    )

    monkeypatch.setattr(
        stacked,
        "evaluate_test_predictions",
        lambda predictions, model: (predictions.copy(), {}),
    )

    stacked.run_stacked_ensemble(
        data_seed=11,
        model_seed=11,
        write_outputs=False,
    )

    assert list(tmp_path.iterdir()) == []
