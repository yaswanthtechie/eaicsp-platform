import csv
import json
import time
import statistics
from pathlib import Path

import numpy as np
import torch
import onnxruntime as ort

from src.global_model import GlobalDemandLSTM

CHECKPOINT = Path("output/global_best_model.pt")
ONNX_MODEL = Path("output/global_best_model.onnx")
REPORT_JSON = Path("output/global_onnx_benchmark_report.json")
REPORT_CSV = Path("output/global_onnx_benchmark_results.csv")

BATCH_SIZES = [1, 8, 32, 64]
WARMUP_RUNS = 20
BENCHMARK_RUNS = 200


def percentile(values, p):
    return float(np.percentile(values, p))


def main():
    torch.set_num_threads(1)

    checkpoint = torch.load(
        CHECKPOINT, map_location="cpu", weights_only=False
    )
    config = checkpoint["config"]

    model = GlobalDemandLSTM(**config)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session_options.inter_op_num_threads = 1

    session = ort.InferenceSession(
        str(ONNX_MODEL),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )

    rng = np.random.default_rng(42)
    results = []
    parity_results = []

    for batch_size in BATCH_SIZES:
        x = rng.standard_normal(
            (batch_size, checkpoint["lookback"],
             config["num_numeric_features"])
        ).astype(np.float32)

        sku_id = rng.integers(
            0, config["num_skus"], size=batch_size, dtype=np.int64
        )
        category_id = rng.integers(
            0, config["num_categories"], size=batch_size, dtype=np.int64
        )
        warehouse_id = rng.integers(
            0, config["num_warehouses"], size=batch_size, dtype=np.int64
        )

        inputs = {
            "x": x,
            "sku_id": sku_id,
            "category_id": category_id,
            "warehouse_id": warehouse_id,
        }

        tx = torch.from_numpy(x)
        tsku = torch.from_numpy(sku_id)
        tcategory = torch.from_numpy(category_id)
        twarehouse = torch.from_numpy(warehouse_id)

        with torch.inference_mode():
            torch_output = model(tx, tsku, tcategory, twarehouse).numpy()

        ort_output = session.run(["forecast"], inputs)[0]
        max_diff = float(np.max(np.abs(torch_output - ort_output)))
        parity_passed = bool(
            np.allclose(torch_output, ort_output, rtol=1e-4, atol=1e-5)
        )

        parity_results.append({
            "batch_size": batch_size,
            "max_absolute_difference": max_diff,
            "parity_passed": parity_passed,
        })

        # Warm up both runtimes before measuring.
        with torch.inference_mode():
            for _ in range(WARMUP_RUNS):
                model(tx, tsku, tcategory, twarehouse)

        for _ in range(WARMUP_RUNS):
            session.run(["forecast"], inputs)

        torch_times = []
        onnx_times = []

        with torch.inference_mode():
            for _ in range(BENCHMARK_RUNS):
                start = time.perf_counter()
                model(tx, tsku, tcategory, twarehouse)
                torch_times.append((time.perf_counter() - start) * 1000)

        for _ in range(BENCHMARK_RUNS):
            start = time.perf_counter()
            session.run(["forecast"], inputs)
            onnx_times.append((time.perf_counter() - start) * 1000)

        for runtime, times in [
            ("pytorch_cpu", torch_times),
            ("onnxruntime_cpu", onnx_times),
        ]:
            median_ms = percentile(times, 50)
            p95_ms = percentile(times, 95)
            throughput = batch_size / (statistics.mean(times) / 1000)

            results.append({
                "batch_size": batch_size,
                "runtime": runtime,
                "runs": BENCHMARK_RUNS,
                "p50_latency_ms": round(median_ms, 4),
                "p95_latency_ms": round(p95_ms, 4),
                "mean_latency_ms": round(statistics.mean(times), 4),
                "throughput_samples_per_second": round(throughput, 2),
            })

        print(
            f"Batch {batch_size}: parity={'PASS' if parity_passed else 'FAIL'}, "
            f"max_abs_diff={max_diff:.8g}"
        )

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "model": "GlobalDemandLSTM",
        "checkpoint": str(CHECKPOINT),
        "onnx_model": str(ONNX_MODEL),
        "provider": "CPUExecutionProvider",
        "warmup_runs": WARMUP_RUNS,
        "benchmark_runs": BENCHMARK_RUNS,
        "batch_sizes": BATCH_SIZES,
        "parity_results": parity_results,
        "all_parity_passed": all(r["parity_passed"] for r in parity_results),
        "benchmark_results": results,
    }

    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with REPORT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print("\n========== BENCHMARK RESULTS ==========")
    for row in results:
        print(
            f"batch={row['batch_size']:>2} | {row['runtime']:<15} | "
            f"p50={row['p50_latency_ms']:>8.4f} ms | "
            f"p95={row['p95_latency_ms']:>8.4f} ms | "
            f"throughput={row['throughput_samples_per_second']:>10.2f} samples/s"
        )

    print("\nJSON report:", REPORT_JSON)
    print("CSV report:", REPORT_CSV)
    print("All batch parity passed:", report["all_parity_passed"])

    if not report["all_parity_passed"]:
        raise RuntimeError(
            "Parity failed for at least one batch size. Check ONNX export."
        )


if __name__ == "__main__":
    main()
