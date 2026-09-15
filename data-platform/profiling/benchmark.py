import time
import statistics
import pandas as pd
import numpy as np
from pathlib import Path


from src.profile import profile


def create_test_data(rows):
    """Create synthetic sales-shaped data for benchmarking."""

    np.random.seed(42)

    return pd.DataFrame({
        "date": pd.date_range(
            start="2024-01-01",
            periods=rows,
            freq="min"
        ),
        "sku_id": np.random.choice(
            [f"SKU{i:03d}" for i in range(1, 51)],
            size=rows
        ),
        "warehouse_id": np.random.choice(
            ["WH1", "WH2", "WH3", "WH4", "WH5"],
            size=rows
        ),
        "quantity_sold": np.random.randint(
            1, 100,
            size=rows
        ),
        "unit_price": np.random.uniform(
            10, 1000,
            size=rows
        )
    })



def benchmark(rows, runs=3):
    """Run the real profiling library multiple times and return average time."""

    timings = []

    df = create_test_data(rows)

    for _ in range(runs):
        start = time.perf_counter()

        profile(df)

        elapsed = time.perf_counter() - start
        timings.append(elapsed)

    average_time = statistics.mean(timings)

    print(
        f"{rows:,} rows -> "
        f"average {average_time:.2f} seconds "
        f"({runs} runs)"
    )

    return average_time

def find_knee_point(results):
    """Find the row size where profiling time increases most sharply."""

    if len(results) < 2:
        return None

    growth_rates = []

    for previous, current in zip(results, results[1:]):
        row_growth = current["rows"] / previous["rows"]
        time_growth = current["seconds"] / previous["seconds"]

        slowdown_ratio = time_growth / row_growth

        growth_rates.append({
            "rows": current["rows"],
            "slowdown_ratio": slowdown_ratio
        })

    knee = max(
        growth_rates,
        key=lambda item: item["slowdown_ratio"]
    )

    return knee["rows"]



if __name__ == "__main__":

    row_sizes = [
        100_000,
        250_000,
        500_000,
        750_000,
        1_000_000
    ]

    results = []

    for rows in row_sizes:
        elapsed = benchmark(rows)

        results.append({
            "rows": rows,
            "seconds": round(elapsed, 2)
        })

    print("\n========== PERFORMANCE RESULTS ==========")

    for result in results:
        print(
            f"{result['rows']:,} rows -> "
            f"{result['seconds']:.2f} seconds"
        )

    knee_point = find_knee_point(results)

    print(
        f"\nObserved knee point: "
        f"{knee_point:,} rows"
    )

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    benchmark_df = pd.DataFrame(results)

benchmark_df["observed_knee_point"] = ""

if knee_point is not None:
    benchmark_df.loc[
        benchmark_df["rows"] == knee_point,
        "observed_knee_point"
    ] = "YES"

    output_path = reports_dir / "performance_benchmark.csv"
    benchmark_df.to_csv(output_path, index=False)

    print(f"\nBenchmark results saved to: {output_path}")