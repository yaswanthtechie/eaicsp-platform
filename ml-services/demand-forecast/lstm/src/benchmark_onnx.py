
from pathlib import Path
import json
import time

import numpy as np
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType
import joblib

from config import LOOKBACK, HORIZON, DATASET_DAYS
from data import generate_data


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"

FP32_MODEL = OUTPUT / "best_model.onnx"
INT8_MODEL = OUTPUT / "best_model_int8.onnx"
SCALER_PATH = OUTPUT / "scaler.pkl"
REPORT_PATH = OUTPUT / "onnx_benchmark_report.json"

BATCH_SIZES = [1, 32, 256]
WARMUP_RUNS = 20
BENCHMARK_RUNS = 200


def make_test_windows():
    """Build chronological test windows using the existing scaler."""
    df = generate_data(days=DATASET_DAYS)
    scaler = joblib.load(SCALER_PATH)

    # Keep the final 15% of timestamps for the test targets.
    values = df["Demand"].to_numpy(dtype=np.float32).reshape(-1, 1)
    scaled = scaler.transform(values).astype(np.float32).ravel()

    test_start = int(len(scaled) * 0.85)
    X, y = [], []

    for target_start in range(test_start, len(scaled) - HORIZON + 1):
        history_start = target_start - LOOKBACK
        if history_start < 0:
            continue

        X.append(scaled[history_start:target_start])
        y.append(scaled[target_start:target_start + HORIZON])

    if not X:
        raise ValueError("Not enough data to create test windows.")

    # Expected LSTM input shape: (samples, lookback, 1).
    return (
        np.asarray(X, dtype=np.float32)[..., np.newaxis],
        np.asarray(y, dtype=np.float32),
        scaler,
    )


def create_int8_model():
    """Quantize model weights dynamically; activations remain runtime-computed."""
    quantize_dynamic(
        model_input=str(FP32_MODEL),
        model_output=str(INT8_MODEL),
        weight_type=QuantType.QInt8,
    )


def make_session(path):
    options = ort.SessionOptions()
    options.graph_optimization_level = (
        ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    )
    session = ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    input_name = session.get_inputs()[0].name
    return session, input_name


def predict(session, input_name, X):
    return session.run(None, {input_name: X})[0]


def benchmark_session(session, input_name, X, batch_size):
    """Measure batch-call latency and processed samples per second."""
    # Reuse real test windows; repeat them when batch size exceeds test count.
    repeats = (batch_size + len(X) - 1) // len(X)
    batch = np.concatenate([X] * repeats, axis=0)[:batch_size]

    for _ in range(WARMUP_RUNS):
        predict(session, input_name, batch)

    timings = []
    for _ in range(BENCHMARK_RUNS):
        start = time.perf_counter()
        predict(session, input_name, batch)
        timings.append(time.perf_counter() - start)

    timings = np.asarray(timings)
    total_seconds = timings.sum()

    return {
        "batch_size": batch_size,
        "p50_batch_latency_ms": float(np.percentile(timings, 50) * 1000),
        "p95_batch_latency_ms": float(np.percentile(timings, 95) * 1000),
        "throughput_samples_per_sec": float(
            batch_size * BENCHMARK_RUNS / total_seconds
        ),
    }


def inverse_scale(values, scaler):
    original_shape = values.shape
    return scaler.inverse_transform(
        values.reshape(-1, 1)
    ).reshape(original_shape)


def accuracy_metrics(y_true, y_pred):
    error = y_pred - y_true
    nonzero = np.abs(y_true) > 1e-8

    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE_percent": (
            float(np.mean(np.abs(error[nonzero] / y_true[nonzero])) * 100)
            if np.any(nonzero)
            else None
        ),
    }


def main():
    for path in [FP32_MODEL, SCALER_PATH]:
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Train/export the model first."
            )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    X_test, y_test_scaled, scaler = make_test_windows()

    # Create INT8 model from the original FP32 ONNX model.
    create_int8_model()

    fp32_session, fp32_input = make_session(FP32_MODEL)
    int8_session, int8_input = make_session(INT8_MODEL)

    fp32_predictions = predict(fp32_session, fp32_input, X_test)
    int8_predictions = predict(int8_session, int8_input, X_test)

    # Forecast accuracy must be calculated in original demand units.
    y_true = inverse_scale(y_test_scaled, scaler)
    fp32_actual = inverse_scale(fp32_predictions, scaler)
    int8_actual = inverse_scale(int8_predictions, scaler)

    report = {
        "device": "CPUExecutionProvider",
        "test_windows": int(len(X_test)),
        "benchmark_runs_per_batch": BENCHMARK_RUNS,
        "warmup_runs": WARMUP_RUNS,
        "model_size_bytes": {
            "fp32": FP32_MODEL.stat().st_size,
            "int8": INT8_MODEL.stat().st_size,
        },
        "benchmark": {},
        "accuracy": {
            "fp32": accuracy_metrics(y_true, fp32_actual),
            "int8": accuracy_metrics(y_true, int8_actual),
            "quantization_prediction_difference": accuracy_metrics(
                fp32_actual, int8_actual
            ),
        },
    }

    fp32_size = report["model_size_bytes"]["fp32"]
    int8_size = report["model_size_bytes"]["int8"]

    report["size_reduction_percent"] = (
        (fp32_size - int8_size) / fp32_size * 100
    )

    for batch_size in BATCH_SIZES:
        fp32_result = benchmark_session(
            fp32_session, fp32_input, X_test, batch_size
        )
        int8_result = benchmark_session(
            int8_session, int8_input, X_test, batch_size
        )

        fp32_result["speedup_vs_fp32"] = 1.0
        int8_result["speedup_vs_fp32"] = (
            int8_result["throughput_samples_per_sec"]
            / fp32_result["throughput_samples_per_sec"]
        )

        report["benchmark"][str(batch_size)] = {
            "fp32": fp32_result,
            "int8": int8_result,
        }

    fp32_mae = report["accuracy"]["fp32"]["MAE"]
    int8_mae = report["accuracy"]["int8"]["MAE"]
    report["accuracy"]["MAE_change_percent_vs_fp32"] = (
        (int8_mae - fp32_mae) / fp32_mae * 100
        if fp32_mae != 0
        else None
    )

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== ONNX FP32 vs Dynamic INT8 ===")
    print(f"Test windows: {len(X_test)}")
    print(
        f"FP32 size: {fp32_size / 1024:.2f} KB | "
        f"INT8 size: {int8_size / 1024:.2f} KB"
    )
    print(f"Size reduction: {report['size_reduction_percent']:.2f}%")
    print("\nBenchmark:")
    for batch_size, results in report["benchmark"].items():
        print(f"\nBatch {batch_size}:")
        for version, metrics in results.items():
            print(
                f"  {version:4s} | "
                f"p50={metrics['p50_batch_latency_ms']:.3f} ms | "
                f"p95={metrics['p95_batch_latency_ms']:.3f} ms | "
                f"throughput={metrics['throughput_samples_per_sec']:.2f} samples/s"
            )

    print("\nAccuracy:")
    print(json.dumps(report["accuracy"], indent=2))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
