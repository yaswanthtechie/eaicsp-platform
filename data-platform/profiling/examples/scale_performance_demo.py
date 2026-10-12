import time
from pathlib import Path
import numpy as np
import pandas as pd

from src.profiler import Profiler


def create_dataset(row_count):
    rng = np.random.default_rng(42)

    return pd.DataFrame(
        {
            "sku_id": rng.choice(
                [f"SKU{i:03d}" for i in range(1, 51)],
                size=row_count,
            ),
            "warehouse": rng.choice(
                ["WH1", "WH2", "WH3", "WH4", "WH5"],
                size=row_count,
            ),
            "quantity_sold": rng.integers(
                1,
                500,
                size=row_count,
            ),
            "unit_price": rng.uniform(
                10,
                1000,
                size=row_count,
            ),
        }
    )


def benchmark(row_count):
    df = create_dataset(row_count)

    profiler = Profiler()

    start = time.perf_counter()

    report = profiler.profile(df)

    elapsed = time.perf_counter() - start

    return elapsed, report

def main():
    results = []

    for row_count in [500_000, 750_000, 1_000_000]:
        timings = []

        for run_number in range(1, 4):
            elapsed, report = benchmark(row_count)
            timings.append(elapsed)

            print(
                f"{row_count:,} rows "
                f"-> Run {run_number}: "
                f"{elapsed:.4f} seconds"
            )

        average_time = sum(timings) / len(timings)

        results.append(
            {
                "rows": row_count,
                "run_1_seconds": round(timings[0], 4),
                "run_2_seconds": round(timings[1], 4),
                "run_3_seconds": round(timings[2], 4),
                "average_seconds": round(average_time, 4),
                "quality_score": report["quality_score"]["score"],
            }
        )

        print(
            f"{row_count:,} rows "
            f"-> Average: {average_time:.4f} seconds\n"
        )

    # reports/ is gitignored, so it does not exist on a fresh clone.
    output_path = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "scale_performance_results.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(results).to_csv(
        output_path,
        index=False,
    )

    print(f"Results saved to: {output_path}")

if __name__ == "__main__":
    main()