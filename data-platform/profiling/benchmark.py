import time
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


def benchmark(rows):
    """Run the real profiling library and measure execution time."""

    print(f"\nProfiling {rows:,} rows...")

    df = create_test_data(rows)

    start = time.perf_counter()

    profile(df)

    elapsed = time.perf_counter() - start

    print(f"{rows:,} rows -> {elapsed:.2f} seconds")

    return elapsed


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

    # Save benchmark results
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    benchmark_df = pd.DataFrame(results)

    output_path = reports_dir / "performance_benchmark.csv"
    benchmark_df.to_csv(output_path, index=False)

    print(f"\nBenchmark results saved to: {output_path}")