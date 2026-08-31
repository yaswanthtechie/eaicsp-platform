"""
Adversarial & Corrupted Input Robustness Test Suite
"""

import pickle
import numpy as np
import torch

from config import LOOKBACK, SCALER_PATH
from predict import forecast_demand


def run_robustness_battery():
    print("=" * 70)
    print("RUNNING ADVERSARIAL & CORRUPTED DATA ROBUSTNESS BATTERY")
    print("=" * 70)

    # Base valid series
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

            # Validate prediction validity
            has_nan = np.isnan(forecast).any()
            has_inf = np.isinf(forecast).any()

            if has_nan or has_inf:
                print(f"  ❌ FAILED: Returned NaN/Inf predictions -> {forecast}")
            else:
                print(f"  ✅ PASSED: Handled gracefully. Forecast range: [{min(forecast):.2f}, {max(forecast):.2f}]")
                print(f"     Mean Forecast: {[round(x, 2) for x in forecast[:3]]}...")

        except (ValueError, TypeError) as e:
            print(f"  ✅ PASSED (Caught Gracefully via Domain Validation): {e}")
        except Exception as e:
            print(f"  ❌ FAILED (Unhandled Exception): {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("ROBUSTNESS BATTERY COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_robustness_battery()