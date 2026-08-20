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
import os
import numpy as np
import torch
import mlflow

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
    why it was rejected.
    """
    x = np.asarray(x, dtype=np.float64)

    if x.shape[0] != lookback:
        return f"wrong length: expected {lookback}, got {x.shape[0]}"
    if np.isnan(x).any():
        return "contains NaN"
    if np.isinf(x).any():
        return "contains Inf"
    if scaler is not None:
        data_min = scaler.data_min_[0]
        data_max = scaler.data_max_[0]
        data_range = max(data_max - data_min, 1e-8)
        if np.any(x < data_min - oor_std_threshold * data_range) or \
           np.any(x > data_max + oor_std_threshold * data_range):
            return "contains out-of-range values (far outside training distribution)"
    return None


def run_robustness_tests():
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("Demand-Forecast-LSTM-Robustness")

    df = generate_data(days=1000)
    folds = get_walk_forward_folds(df, n_folds=5, lookback=LOOKBACK, horizon=HORIZON,
                                    save_scaler_path=None)
    X_tr, y_tr, X_te, y_te, scaler = folds[-1]

    model = build_model(MultiStepLSTM, hidden_size=64, num_layers=2, horizon=HORIZON)
    model = train_model(model, X_tr, y_tr, epochs=25)
    model.eval()

    base_scaled = X_te[0].copy()
    base_raw = scaler.inverse_transform(base_scaled.reshape(-1, 1)).flatten()

    print("=" * 78)
    print("ROBUSTNESS TEST -- LSTM path (model.py + data.py)")
    print("=" * 78)

    results = {}

    with mlflow.start_run(run_name="Input_Guard_Robustness_Validation"):
        # Log test parameters & scaler reference bounds
        mlflow.log_params({
            "lookback": LOOKBACK,
            "horizon": HORIZON,
            "oor_std_threshold": 6.0,
            "data_min_raw": float(scaler.data_min_[0]),
            "data_max_raw": float(scaler.data_max_[0]),
        })

        def run_case(name, raw_seq, expect_reject=True):
            verdict = validate_sequence(raw_seq, LOOKBACK, scaler)
            print(f"\n{name}")
            print(f"    Guard verdict: {verdict}")
            raw_out = None
            try:
                scaled_seq = scaler.transform(raw_seq.reshape(-1, 1)).flatten()
                with torch.no_grad():
                    raw_out = model(torch.tensor(scaled_seq, dtype=torch.float32).view(1, -1, 1)).numpy()
                finite = np.isfinite(raw_out).all()
                print(f"    Raw model (no guard) output: {raw_out.flatten()[:3]}... -> {'finite output' if finite else 'NaN/Inf propagated through output'}")
            except Exception as e:
                print(f"    Raw model (no guard) raised: {type(e).__name__}: {e}")
            
            # Guard passes if expected outcome matches verdict existence
            guard_correct = (verdict is not None) if expect_reject else (verdict is None)
            results[name] = guard_correct
            return raw_out

        # 1. NaN in lookback window
        nan_seq = base_raw.copy()
        nan_seq[5] = np.nan
        run_case("case1_nan", nan_seq, expect_reject=True)

        # 2. Inf in lookback window
        inf_seq = base_raw.copy()
        inf_seq[10] = np.inf
        run_case("case2_inf", inf_seq, expect_reject=True)

        # 3. Out-of-range values in raw units
        oor_seq = base_raw.copy()
        oor_seq[:] = base_raw.mean() + 50 * (base_raw.max() - base_raw.min())
        print(f"\n[3] Out-of-range raw values (value~{oor_seq[0]:.0f}, training range ~[{scaler.data_min_[0]:.0f}, {scaler.data_max_[0]:.0f}])")
        run_case("case3_oor", oor_seq, expect_reject=True)

        # 4. Degenerate all-zero window
        zero_seq = np.zeros(LOOKBACK)
        run_case("case4_zero", zero_seq, expect_reject=False)

        # 5. Wrong-length input
        short_seq = base_raw[:10]
        verdict = validate_sequence(short_seq, LOOKBACK, scaler)
        print(f"\n[5] Wrong-length input (10 values, expected {LOOKBACK})")
        print(f"    Guard verdict: {verdict}")
        try:
            scaled_short = scaler.transform(short_seq.reshape(-1, 1)).flatten()
            with torch.no_grad():
                model(torch.tensor(scaled_short, dtype=torch.float32).view(1, -1, 1))
            print("    Raw model (no guard): accepted short input silently (shape mismatch not caught)")
        except Exception as e:
            print(f"    Raw model (no guard) raised: {type(e).__name__}: {e}")
        
        results["case5_short"] = (verdict is not None)

        print("\n" + "=" * 78)
        print("FINDING: validate_sequence() now checks RAW (pre-scale) values against")
        print("scaler.data_min_/data_max_, matching units. This is the guard to call in")
        print("predict.py/service.py BEFORE scaling any incoming request -- scale only")
        print("after validation passes.")
        print("=" * 78)

        # Log individual guard validation metrics to MLflow
        mlflow.log_metrics({
            "case1_nan_guard_passed": float(results.get("case1_nan", False)),
            "case2_inf_guard_passed": float(results.get("case2_inf", False)),
            "case3_oor_guard_passed": float(results.get("case3_oor", False)),
            "case4_zero_guard_passed": float(results.get("case4_zero", False)),
            "case5_short_guard_passed": float(results.get("case5_short", False)),
            "all_guards_passed": float(all(results.values())),
        })


if __name__ == "__main__":
    run_robustness_tests()