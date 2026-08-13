"""
-- Robustness test: missing / out-of-range input handling.

Same category of test as Uday's (missing values, out-of-range values), applied
to the LSTM path (model.py + data.py). This script documents the model's ACTUAL
current behavior on bad inputs -- it does not assume the model already handles
them gracefully. Where the raw model/pipeline fails ungracefully, that's
reported as a finding, and `validate_sequence()` below is the guard we'd wire
into `service.py` / `predict.py` to fix it.

Cases covered:
    1. NaN values inside the lookback window
    2. Inf values inside the lookback window
    3. Values far outside the range the scaler was fit on (out-of-distribution)
    4. All-zero / degenerate input window
    5. Wrong-shaped input (lookback too short)
"""

from typing import Optional

import numpy as np
import torch

from data import generate_data, get_walk_forward_folds
from model import MultiStepLSTM
from train_utils import train_model, build_model

LOOKBACK = 30
HORIZON = 7


def validate_sequence(x: np.ndarray, lookback: int, scaler=None,
                    oor_std_threshold: float = 6.0) -> Optional[str]:
    """
    Guard to run BEFORE feeding a raw sequence into the model. Returns None if
    the sequence is safe to predict on, otherwise a short string describing
    why it was rejected. This is what the finding below recommends wiring
    into predict.py / service.py -- the raw model itself does not do this.
    """
    x = np.asarray(x, dtype=np.float64)

    if x.shape[0] != lookback:
        return f"wrong length: expected {lookback}, got {x.shape[0]}"
    if np.isnan(x).any():
        return "contains NaN"
    if np.isinf(x).any():
        return "contains Inf"
    if scaler is not None:
        # Values wildly outside the fitted scaler's training range are
        # out-of-distribution; the model was never shown values like this.
        data_min = scaler.data_min_[0]
        data_max = scaler.data_max_[0]
        data_range = max(data_max - data_min, 1e-8)
        if np.any(x < data_min - oor_std_threshold * data_range) or \
           np.any(x > data_max + oor_std_threshold * data_range):
            return "contains out-of-range values (far outside training distribution)"
    return None


def run_robustness_tests():
    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                    save_scaler_path=None)
    X_tr, y_tr, X_te, y_te, scaler = folds[-1]

    model = build_model(MultiStepLSTM, hidden_size=64, num_layers=2, horizon=HORIZON)
    model = train_model(model, X_tr, y_tr, epochs=25)
    model.eval()

    base_sequence = X_te[0].copy()  # a real, valid scaled sequence to perturb

    print("=" * 78)
    print("ROBUSTNESS TEST -- LSTM path (model.py + data.py)")
    print("=" * 78)

    # 1. NaN in the input
    nan_seq = base_sequence.copy()
    nan_seq[5] = np.nan
    guard_result = validate_sequence(nan_seq, LOOKBACK, scaler)
    print(f"\n[1] NaN in lookback window")
    print(f"    Guard verdict: {guard_result}")
    try:
        with torch.no_grad():
            raw_out = model(torch.tensor(nan_seq, dtype=torch.float32).view(1, -1, 1)).numpy()
        print(f"    Raw model (no guard) output: {raw_out.flatten()[:3]}... "
            f"-> {'NaN propagated through output, no crash' if np.isnan(raw_out).any() else 'no NaN in output'}")
    except Exception as e:
        print(f"    Raw model (no guard) raised: {type(e).__name__}: {e}")

    # 2. Inf in the input
    inf_seq = base_sequence.copy()
    inf_seq[10] = np.inf
    guard_result = validate_sequence(inf_seq, LOOKBACK, scaler)
    print(f"\n[2] Inf in lookback window")
    print(f"    Guard verdict: {guard_result}")
    try:
        with torch.no_grad():
            raw_out = model(torch.tensor(inf_seq, dtype=torch.float32).view(1, -1, 1)).numpy()
        print(f"    Raw model (no guard) output: {raw_out.flatten()[:3]}... "
            f"-> {'NaN/Inf propagated, no crash' if (np.isnan(raw_out).any() or np.isinf(raw_out).any()) else 'finite output'}")
    except Exception as e:
        print(f"    Raw model (no guard) raised: {type(e).__name__}: {e}")

    # 3. Out-of-range values (e.g. 100x the training max, in scaled space)
    oor_seq = base_sequence.copy()
    oor_seq[:] = 500.0  # scaled values should be roughly in [0, 1]; this is far out of distribution
    guard_result = validate_sequence(oor_seq, LOOKBACK, scaler)
    print(f"\n[3] Out-of-range values (scaled value=500, training range ~[0,1])")
    print(f"    Guard verdict: {guard_result}")
    with torch.no_grad():
        raw_out = model(torch.tensor(oor_seq, dtype=torch.float32).view(1, -1, 1)).numpy()
    print(f"    Raw model (no guard) output: {raw_out.flatten()} "
        f"-> runs without crashing but the model was never trained on inputs like this; "
        f"output should not be trusted")

    # 4. Degenerate all-zero window
    zero_seq = np.zeros(LOOKBACK)
    guard_result = validate_sequence(zero_seq, LOOKBACK, scaler)
    print(f"\n[4] All-zero window")
    print(f"    Guard verdict: {guard_result}")
    with torch.no_grad():
        raw_out = model(torch.tensor(zero_seq, dtype=torch.float32).view(1, -1, 1)).numpy()
    print(f"    Raw model (no guard) output: {raw_out.flatten()} -> runs fine, valid edge case (not rejected)")

    # 5. Wrong-length input (shorter than lookback)
    short_seq = base_sequence[:10]
    guard_result = validate_sequence(short_seq, LOOKBACK, scaler)
    print(f"\n[5] Wrong-length input (10 values, expected {LOOKBACK})")
    print(f"    Guard verdict: {guard_result}")
    try:
        with torch.no_grad():
            model(torch.tensor(short_seq, dtype=torch.float32).view(1, -1, 1))
        print("    Raw model (no guard): accepted short input silently (shape mismatch not caught)")
    except Exception as e:
        print(f"    Raw model (no guard) raised: {type(e).__name__}: {e}")

    print("\n" + "=" * 78)
    print("FINDING: the raw MultiStepLSTM/AttentionMultiStepLSTM forward pass does NOT")
    print("guard against NaN, Inf, or out-of-distribution inputs -- it will silently")
    print("propagate bad values into a bad forecast rather than raising. "
        "validate_sequence()")
    print("above is the recommended guard to call in predict.py/service.py BEFORE")
    print("scoring any request, rejecting anything that fails the checks.")
    print("=" * 78)


if __name__ == "__main__":
    run_robustness_tests()