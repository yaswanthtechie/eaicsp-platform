"""
Adversarial & Corrupted Input Robustness Test Suite
"""

import os
import sys
import numpy as np
import torch

from config import LOOKBACK, MODEL_PATH, SCALER_PATH
from predict import forecast_demand


def run_robustness_battery():
    # Pre-flight check: ensure required pipeline artifacts exist
    missing_artifacts = [
        path for path in [SCALER_PATH, MODEL_PATH] if not os.path.exists(path)
    ]
    if missing_artifacts:
        print("[ERROR]: Missing required artifacts:")
        for path in missing_artifacts:
            print(f"  - {path}")
        print("Please run `python src/train.py` to generate model and scaler artifacts first.")
        sys.exit(1)

    print("=" * 70)
    print("RUNNING ADVERSARIAL & CORRUPTED DATA ROBUSTNESS BATTERY")
    print("=" * 70)

    # Base valid sequence
    valid_base = [100.0 + i * 0.5 for i in range(LOOKBACK)]

    test_cases = [
        ("Extreme Demand Spike (+100x outlier)", valid_base[:-1] + [10000.0]),
        ("Negative Demand Figure (-50.0 demand)", [-50.0] + valid_base[1:]),
        ("All Zero Demand (Complete outage)", [0.0] * LOOKBACK),
        ("Huge Baseline Demand Level (10,000 baseline)", [10000.0 + i for i in range(LOOKBACK)]),
        ("Contains NaN values", valid_base[:-5] + [float("nan")] * 5),
        ("Contains Negative Infinite values", valid_base[:-2] + [float("-inf"), 100.0]),
    ]

    for name, input_seq in test_cases:
        print(f"\nEvaluating: [{name}]")
        try:
            result = forecast_demand(input_seq)
            forecast = result["mean_forecast"]

            forecast_arr = np.array(forecast, dtype=np.float32)
            has_nan = np.isnan(forecast_arr).any()
            has_inf = np.isinf(forecast_arr).any()
            has_negative = (forecast_arr < 0.0).any()

            if has_nan or has_inf:
                print(f"  [FAILED]: Returned NaN/Inf predictions -> {forecast}")
            elif has_negative:
                print(f"  [FAILED]: Returned negative demand predictions -> {forecast}")
            else:
                tag = "finite non-negative output"
                print(f"  [PASSED]: Handled gracefully ({tag}). Forecast range: [{min(forecast):.2f}, {max(forecast):.2f}]")
                print(f"     Mean Forecast: {[round(x, 2) for x in forecast[:3]]}...")

        except (ValueError, TypeError) as e:
            print(f"  [PASSED] (Caught Gracefully via Domain Validation): {e}")
        except Exception as e:
            print(f"  [FAILED] (Unhandled Exception): {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("ROBUSTNESS BATTERY COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_robustness_battery()