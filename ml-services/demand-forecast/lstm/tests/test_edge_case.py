"""
R4 item 5 -- Real test coverage for sequence-windowing and scaler edge cases.

Run with: python -m pytest tests/test_edge_cases.py -v
(from the lstm/ root, same as your existing tests/test_pipeline.py)
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data import create_sequences, get_walk_forward_folds  # noqa: E402


# ---------------------------------------------------------------------------
# Sequence-windowing edge cases
# ---------------------------------------------------------------------------

class TestSequenceWindowingEdgeCases:

    def test_lookback_longer_than_available_data_returns_empty(self):
        """If lookback + horizon exceeds the available series length, there are
        zero valid windows -- create_sequences must return empty arrays, not
        raise or silently produce garbage/negative-length arrays."""
        data = np.arange(20, dtype=float)  # only 20 points
        X, y = create_sequences(data, lookback=30, horizon=7)  # needs 37
        assert X.shape[0] == 0
        assert y.shape[0] == 0

    def test_lookback_plus_horizon_exactly_equal_to_data_length_gives_one_window(self):
        data = np.arange(37, dtype=float)  # exactly lookback + horizon
        X, y = create_sequences(data, lookback=30, horizon=7)
        assert X.shape == (1, 30)
        assert y.shape == (1, 7)
        np.testing.assert_array_equal(X[0], data[:30])
        np.testing.assert_array_equal(y[0], data[30:37])

    def test_horizon_of_1_produces_single_step_targets(self):
        data = np.arange(50, dtype=float)
        X, y = create_sequences(data, lookback=30, horizon=1)
        assert X.shape[1] == 30
        assert y.shape[1] == 1
        # number of windows should be len(data) - lookback - horizon + 1
        assert X.shape[0] == 50 - 30 - 1 + 1

    def test_horizon_of_7_produces_seven_step_targets(self):
        data = np.arange(50, dtype=float)
        X, y = create_sequences(data, lookback=30, horizon=7)
        assert X.shape[1] == 30
        assert y.shape[1] == 7
        assert X.shape[0] == 50 - 30 - 7 + 1

    def test_horizon_1_has_more_windows_than_horizon_7_on_same_data(self):
        """Smaller horizon should never produce fewer usable windows than a
        larger horizon on the same underlying series."""
        data = np.arange(100, dtype=float)
        X1, _ = create_sequences(data, lookback=30, horizon=1)
        X7, _ = create_sequences(data, lookback=30, horizon=7)
        assert X1.shape[0] >= X7.shape[0]

    def test_zero_length_data_returns_empty(self):
        data = np.array([], dtype=float)
        X, y = create_sequences(data, lookback=30, horizon=7)
        assert X.shape[0] == 0
        assert y.shape[0] == 0

    def test_walk_forward_folds_lookback_larger_than_first_fold_train_slice(self, tmp_path):
        """
        DISCOVERED BUG (reported honestly, not hidden): when `lookback` exceeds
        how much history has accumulated by an early fold (train_end < lookback),
        `train_end - lookback` goes negative. Python/numpy silently treats a
        negative slice start as counting from the end of the array instead of
        raising, so `raw_test = values[train_end - lookback : test_end]`
        produces an EMPTY slice (or a wrong-region slice) instead of a
        clipped-but-valid one. MinMaxScaler.transform() then raises ValueError
        on the 0-sample input, and the exception propagates out of
        get_walk_forward_folds -- it doesn't fail gracefully, it crashes the
        whole fold-generation call on fold 1, before folds 2-5 even run.

        Verified directly: for days=60, n_folds=5 (fold_size=10), lookback=50,
        folds k=1..4 all compute a raw_test slice of length 0 and raise;
        only k=5 (where train_end==lookback) succeeds.

        This test pins down that CURRENT behavior so a future fix is a
        deliberate, visible change instead of a silent one. See README
        "Known limitation" for the recommended fix (validate
        `lookback <= fold_size * 1` before generating folds, or clip the
        negative start to 0 instead of letting it wrap).
        """
        days = 60  # small series relative to a large lookback
        t = np.arange(days)
        dates = pd.date_range(start="2024-01-01", periods=days, freq="D")
        df = pd.DataFrame({"Day": t, "date": dates, "Demand": 100 + t * 0.1})

        scaler_path = str(tmp_path / "scaler.pkl")
        with pytest.raises(ValueError):
            get_walk_forward_folds(df, n_folds=5, lookback=50, horizon=7,
                                    save_scaler_path=scaler_path)

    def test_walk_forward_folds_lookback_equal_to_first_fold_size_succeeds(self, tmp_path):
        """Sanity check on the boundary: once lookback no longer exceeds the
        first fold's accumulated training history, fold generation succeeds
        normally end to end."""
        days = 60
        t = np.arange(days)
        dates = pd.date_range(start="2024-01-01", periods=days, freq="D")
        df = pd.DataFrame({"Day": t, "date": dates, "Demand": 100 + t * 0.1})

        fold_size = days // 6  # matches get_walk_forward_folds internal math (n_folds=5 -> //6)
        scaler_path = str(tmp_path / "scaler.pkl")
        folds = get_walk_forward_folds(df, n_folds=5, lookback=fold_size, horizon=3,
                                        save_scaler_path=scaler_path)
        assert len(folds) == 5
        for X_tr, y_tr, X_te, y_te, scaler in folds:
            assert isinstance(scaler, MinMaxScaler)
            assert X_tr.shape[0] == y_tr.shape[0]
            assert X_te.shape[0] == y_te.shape[0]


# ---------------------------------------------------------------------------
# Model-level horizon shape checks (torch-optional: skipped if torch isn't
# installed in the environment running this test file, so this file stays
# runnable standalone even without torch).
# ---------------------------------------------------------------------------

class TestModelHorizonShapes:

    def test_horizon_1_output_shape(self):
        torch = pytest.importorskip("torch")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from model import MultiStepLSTM

        model = MultiStepLSTM(input_size=1, hidden_size=16, num_layers=1, horizon=1)
        x = torch.randn(2, 10, 1)
        out = model(x)
        assert out.shape == (2, 1)

    def test_horizon_7_output_shape(self):
        torch = pytest.importorskip("torch")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from model import MultiStepLSTM

        model = MultiStepLSTM(input_size=1, hidden_size=16, num_layers=1, horizon=7)
        x = torch.randn(2, 10, 1)
        out = model(x)
        assert out.shape == (2, 7)

    def test_attention_variant_matches_plain_output_shape(self):
        """AttentionMultiStepLSTM must produce the same output shape contract
        as MultiStepLSTM for the same horizon -- attention_compare.py relies
        on this to swap models transparently."""
        torch = pytest.importorskip("torch")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from model import MultiStepLSTM, AttentionMultiStepLSTM

        x = torch.randn(3, 30, 1)
        plain = MultiStepLSTM(input_size=1, hidden_size=16, num_layers=1, horizon=7)
        attn = AttentionMultiStepLSTM(input_size=1, hidden_size=16, num_layers=1, horizon=7)
        assert plain(x).shape == attn(x).shape == (3, 7)


# ---------------------------------------------------------------------------
# Scaler edge cases
# ---------------------------------------------------------------------------

class TestScalerEdgeCases:

    def test_constant_series_scaler_does_not_crash(self):
        """A constant series has zero variance; MinMaxScaler's (x - min)/(max - min)
        divides by zero. sklearn handles this internally (treats the range as 1),
        but we assert the output is finite (no NaN/Inf) rather than assuming it."""
        constant_values = np.full(100, 42.0).reshape(-1, 1)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(constant_values)

        assert not np.isnan(scaled).any(), "constant series produced NaN after scaling"
        assert not np.isinf(scaled).any(), "constant series produced Inf after scaling"

    def test_constant_series_inverse_transform_round_trips(self):
        constant_values = np.full(50, 7.5).reshape(-1, 1)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(constant_values)
        restored = scaler.inverse_transform(scaled)
        np.testing.assert_allclose(restored, constant_values, rtol=1e-5)

    def test_single_unique_value_in_larger_array(self):
        """Same as constant series, but phrased as 'single unique value' per spec:
        every element of the array is identical."""
        values = np.array([[3.14]] * 1000)
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(values)
        assert len(np.unique(scaled)) == 1
        assert not np.isnan(scaled).any()

    def test_single_data_point_series(self):
        """Degenerate case: only one sample to fit on at all."""
        values = np.array([[10.0]])
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(values)
        assert not np.isnan(scaled).any()
        assert not np.isinf(scaled).any()

    def test_constant_series_end_to_end_through_walk_forward_folds(self):
        """A fully constant demand series run through the real pipeline
        (get_walk_forward_folds) end-to-end must not raise or produce NaNs
        in the resulting sequences."""
        days = 200
        t = np.arange(days)
        dates = pd.date_range(start="2024-01-01", periods=days, freq="D")
        df = pd.DataFrame({"Day": t, "date": dates, "Demand": np.full(days, 55.0)})

        folds = get_walk_forward_folds(df, n_folds=5, lookback=30, horizon=7,
                                        save_scaler_path=None)
        for X_tr, y_tr, X_te, y_te, scaler in folds:
            if X_tr.shape[0] > 0:
                assert not np.isnan(X_tr).any()
                assert not np.isnan(y_tr).any()
            if X_te.shape[0] > 0:
                assert not np.isnan(X_te).any()
                assert not np.isnan(y_te).any()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))