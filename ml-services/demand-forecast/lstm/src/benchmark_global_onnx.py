"""Benchmark GlobalDemandLSTM ONNX FP32 vs dynamic INT8 on real test windows."""

import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.quantization import quantize_dynamic, QuantType

from src.config import GLOBAL_DATA_PATH, GLOBAL_LOOKBACK, GLOBAL_HORIZON
from src.global_data import load_global_data


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
DATA_PATH = ROOT / GLOBAL_DATA_PATH

FP32_MODEL = OUTPUT / "global_best_model.onnx"
INT8_MODEL = OUTPUT / "global_best_model_int8.onnx"
REPORT_PATH = OUTPUT / "global_onnx_benchmark_report.json"

BATCH_SIZES = [1, 32, 256]
WARMUP_RUNS = 10
ROUNDS = 5
RUNS_PER_ROUND = 40

INPUT_NAMES = [
    "input_sequence",
    "sku_id",
    "category_id",
    "warehouse_id",
]


def create_int8_model():
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
    options.intra_op_num_threads = 1

    return ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


def make_feed(tensors, start, end):
    x, sku, category, warehouse, _ = tensors
    return {
        "input_sequence": x[start:end].numpy(),
        "sku_id": sku[start:end].numpy(),
        "category_id": category[start:end].numpy(),
        "warehouse_id": warehouse[start:end].numpy(),
    }


def predict_all(session, tensors, batch_size):
    x = tensors[0]
    outputs = []

    for start in range(0, len(x), batch_size):
        end = min(start + batch_size, len(x))
        feed = make_feed(tensors, start, end)
        outputs.append(session.run(["forecast"], feed)[0])

    return np.concatenate(outputs, axis=0)


def inverse_scale(values, scaler):
    shape = values.shape
    return scaler.inverse_transform(
        values.reshape(-1, 1)
    ).reshape(shape)


def accuracy_metrics(actual, predicted):
    error = predicted - actual
    nonzero = np.abs(actual) > 1e-8

    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "MAPE_percent": (
            float(
                np.mean(np.abs(error[nonzero] / actual[nonzero])) * 100
            )
            if np.any(nonzero)
            else None
        ),
    }


def benchmark_session(session, tensors, batch_size):
    x = tensors[0]
    sample_count = len(x)

    # Select actual test windows. Wrap around only if needed.
    indices = np.arange(batch_size) % sample_count
    x_all, sku_all, category_all, warehouse_all, _ = tensors

    feed = {
        "input_sequence": x_all[indices].numpy(),
        "sku_id": sku_all[indices].numpy(),
        "category_id": category_all[indices].numpy(),
        "warehouse_id": warehouse_all[indices].numpy(),
    }

    for _ in range(WARMUP_RUNS):
        session.run(["forecast"], feed)

    round_means = []
    all_timings = []

    for _ in range(ROUNDS):
        timings = []

        for _ in range(RUNS_PER_ROUND):
            start = time.perf_counter()
            session.run(["forecast"], feed)
            timings.append((time.perf_counter() - start) * 1000)

        round_means.append(float(np.mean(timings)))
        all_timings.extend(timings)

    values = np.asarray(all_timings, dtype=float)
    total_seconds = float(np.sum(values) / 1000)

    return {
        "batch_size": batch_size,
        "rounds": ROUNDS,
        "runs_per_round": RUNS_PER_ROUND,
        "total_measured_calls": len(values),
        "mean_batch_latency_ms": float(np.mean(values)),
        "std_batch_latency_ms": float(np.std(values)),
        "min_batch_latency_ms": float(np.min(values)),
        "max_batch_latency_ms": float(np.max(values)),
        "p50_batch_latency_ms": float(np.percentile(values, 50)),
        "p95_batch_latency_ms": float(np.percentile(values, 95)),
        "round_mean_latency_ms": round_means,
        "throughput_samples_per_sec": float(
            batch_size * len(values) / total_seconds
        ),
    }


def graph_node_summary(path):
    graph = onnx.load(str(path)).graph
    counts = {}

    for node in graph.node:
        counts[node.op_type] = counts.get(node.op_type, 0) + 1

    quantized_types = {
        "MatMulInteger",
        "DynamicQuantizeLinear",
        "QLinearMatMul",
        "MatMulNBits",
        "ConvInteger",
    }

    return {
        "node_count": len(graph.node),
        "operator_counts": counts,
        "quantized_operator_count": sum(
            count
            for op, count in counts.items()
            if op in quantized_types
        ),
    }


def main():
    if not FP32_MODEL.exists():
        raise FileNotFoundError(
            f"{FP32_MODEL} missing. Run python -m src.global_onnx_export first."
        )

    data = load_global_data(
        DATA_PATH,
        lookback=GLOBAL_LOOKBACK,
        horizon=GLOBAL_HORIZON,
    )
    tensors = data.test.tensors

    if len(tensors[0]) == 0:
        raise ValueError("No actual global test windows found.")

    OUTPUT.mkdir(parents=True, exist_ok=True)

    print("Creating dynamic INT8 model...")
    create_int8_model()

    fp32_session = make_session(FP32_MODEL)
    int8_session = make_session(INT8_MODEL)

    # Accuracy is evaluated over every held-out test window.
    y_scaled = tensors[4].numpy()
    y_true = inverse_scale(y_scaled, data.scaler)

    fp32_scaled = predict_all(fp32_session, tensors, 256)
    int8_scaled = predict_all(int8_session, tensors, 256)

    fp32_actual = inverse_scale(fp32_scaled, data.scaler)
    int8_actual = inverse_scale(int8_scaled, data.scaler)

    report = {
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "test_windows": len(tensors[0]),
        "lookback": GLOBAL_LOOKBACK,
        "horizon": GLOBAL_HORIZON,
        "device": "CPUExecutionProvider",
        "warmup_runs": WARMUP_RUNS,
        "rounds": ROUNDS,
        "runs_per_round": RUNS_PER_ROUND,
        "model_size_bytes": {
            "fp32": FP32_MODEL.stat().st_size,
            "int8": INT8_MODEL.stat().st_size,
        },
        "graph": {
            "fp32": graph_node_summary(FP32_MODEL),
            "int8": graph_node_summary(INT8_MODEL),
        },
        "accuracy_original_sales_units": {
            "fp32": accuracy_metrics(y_true, fp32_actual),
            "int8": accuracy_metrics(y_true, int8_actual),
            "int8_vs_fp32_prediction_difference": accuracy_metrics(
                fp32_actual, int8_actual
            ),
        },
        "benchmark": {},
    }

    fp32_size = report["model_size_bytes"]["fp32"]
    int8_size = report["model_size_bytes"]["int8"]

    report["size_reduction_percent"] = (
        (fp32_size - int8_size) / fp32_size * 100
        if fp32_size
        else None
    )

    for batch_size in BATCH_SIZES:
        print(f"Benchmarking batch size {batch_size}...")

        fp32_result = benchmark_session(
            fp32_session, tensors, batch_size
        )
        int8_result = benchmark_session(
            int8_session, tensors, batch_size
        )

        fp32_rate = fp32_result["throughput_samples_per_sec"]
        int8_rate = int8_result["throughput_samples_per_sec"]

        int8_result["throughput_speedup_vs_fp32"] = (
            int8_rate / fp32_rate if fp32_rate else None
        )

        report["benchmark"][str(batch_size)] = {
            "fp32": fp32_result,
            "int8": int8_result,
        }

    REPORT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\n=== Global ONNX FP32 vs Dynamic INT8 ===")
    print(f"Actual test windows: {len(tensors[0])}")
    print(
        f"FP32 size: {fp32_size / 1024:.2f} KB | "
        f"INT8 size: {int8_size / 1024:.2f} KB"
    )
    print(
        "INT8 graph quantized operators: "
        f"{report['graph']['int8']['quantized_operator_count']}"
    )

    for batch, versions in report["benchmark"].items():
        print(f"\nBatch {batch}")
        for version, result in versions.items():
            print(
                f"{version.upper():4s} | "
                f"mean={result['mean_batch_latency_ms']:.3f} ms | "
                f"std={result['std_batch_latency_ms']:.3f} ms | "
                f"p50={result['p50_batch_latency_ms']:.3f} ms | "
                f"p95={result['p95_batch_latency_ms']:.3f} ms | "
                f"throughput={result['throughput_samples_per_sec']:.2f} samples/s"
            )

    print("\nAccuracy in original sales units:")
    print(json.dumps(report["accuracy_original_sales_units"], indent=2))
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
