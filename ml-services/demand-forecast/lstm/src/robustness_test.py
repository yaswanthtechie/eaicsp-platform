import os
import numpy as np
import torch
from config import HIDDEN_SIZE, HORIZON, LOOKBACK, MODEL_PATH, NUM_LAYERS, SCALER_PATH
from data import load_scaler, validate_sequence
from model import MultiStepLSTM


def run_robustness_tests():
    print("=" * 65)
    print("DEMAND FORECAST SERVICE - ROBUSTNESS & GUARD VALIDATION")
    print("=" * 65)

    scaler = load_scaler(SCALER_PATH)
    data_min = float(scaler.data_min_[0])
    data_max = float(scaler.data_max_[0])
    data_range = data_max - data_min

    # Tech Lead fix: tightened OOD multiplier from 6.0 down to 1.0
    oor_range_multiplier = 1.0
    valid_min = data_min - (oor_range_multiplier * data_range)
    valid_max = data_max + (oor_range_multiplier * data_range)

    print(f"Training Range: [{data_min:.2f}, {data_max:.2f}]")
    print(f"Valid Input Range (multiplier={oor_range_multiplier}): [{valid_min:.2f}, {valid_max:.2f}]\n")

    # Load raw PyTorch model for unguarded comparison
    raw_model = MultiStepLSTM(1, HIDDEN_SIZE, NUM_LAYERS, HORIZON)
    if os.path.exists(MODEL_PATH):
        raw_model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
    raw_model.eval()

    test_cases = [
        ("case1_nan", np.array([np.nan] * LOOKBACK)),
        ("case2_inf", np.array([np.inf] * LOOKBACK)),
        ("case3_oor", np.array([5000.0] * LOOKBACK)),  # Raw extreme outlier (32x max)
        ("case4_zero", np.zeros(LOOKBACK)),
        ("case5_wrong_length", np.array([100.0] * 10)),  # 10 timesteps instead of LOOKBACK
    ]

    for name, raw_seq in test_cases:
        print(f"[{name}]")

        # 1. Guard check evaluation
        guard_verdict = None
        if not np.all(np.isfinite(raw_seq)):
            guard_verdict = "contains NaN" if np.isnan(raw_seq).any() else "contains Inf"
        elif len(raw_seq) != LOOKBACK:
            guard_verdict = f"wrong length: expected {LOOKBACK}, got {len(raw_seq)}"
        else:
            is_valid, err_msg = validate_sequence(raw_seq, scaler, oor_multiplier=oor_range_multiplier)
            if not is_valid:
                guard_verdict = "contains out-of-range values (far outside training distribution)"

        print(f"  Guard verdict: {guard_verdict}")

        # 2. Raw model behavior without guard
        try:
            if not np.all(np.isfinite(raw_seq)):
                # Normalization attempt via scaler raises ValueError on Inf/NaN
                _ = scaler.transform(raw_seq.reshape(-1, 1))

            x_in = raw_seq.reshape(1, -1, 1)
            t_in = torch.tensor(x_in, dtype=torch.float32)
            with torch.no_grad():
                out = raw_model(t_in).numpy().flatten()
                tag="finite output" if np.all(np.isfinite(out)) else "contains N0N/FINITE output (Nan/Inf)"
            print(f"  Raw model output (no guard): {out[:3]}... -> {tag}")
        except Exception as e:
            print(f"  Raw model (no guard) raised: {type(e).__name__}: {e}")
        print()

    print("=" * 65)
    print("FINDING: validate_sequence() now checks RAW (pre-scale) values against")
    print("scaler.data_min_ / data_max_ with oor_range_multiplier=1.0. This guard is executed in")
    print("service.py BEFORE scaling any incoming request -- scale only after validation passes.")
    print("=" * 65)


if __name__ == "__main__":
    run_robustness_tests()