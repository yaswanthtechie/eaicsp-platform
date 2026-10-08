"""
R9-11 M5: a fast, always-on guard for profiling performance.

The full 500k / 750k / 1M benchmark lives in
examples/scale_performance_demo.py (too slow for every test run).
This test uses the same data generator at 50,000 rows, adds real mess
(nulls), and checks that profiling stays vectorised-fast and still
counts every problem correctly.
"""

import time

import numpy as np

from examples.scale_performance_demo import create_dataset
from src.profiler import Profiler

ROWS = 50_000

# Generous on purpose: the real time is about 0.1-0.2 s. A limit this
# loose only fails if someone reintroduces a row-by-row Python loop.
MAX_SECONDS = 10.0


def test_profiles_50k_messy_rows_quickly_and_correctly():
    df = create_dataset(ROWS)

    # Blank out 5% of prices so the benchmark exercises null handling,
    # not just perfectly clean data.
    missing = df.sample(frac=0.05, random_state=1).index
    df.loc[missing, "unit_price"] = np.nan

    start = time.perf_counter()
    report = Profiler().profile(df)
    elapsed = time.perf_counter() - start

    assert elapsed < MAX_SECONDS, (
        f"Profiling {ROWS:,} rows took {elapsed:.2f}s "
        f"(limit {MAX_SECONDS}s): check for row-by-row loops"
    )
    assert report["shape"] == [ROWS, 4]
    assert report["quality_score"]["missing_values"] == len(missing)
    assert report["quality_score"]["score"] < 100


def test_benchmark_dataset_is_reproducible():
    """Same seed, same data: benchmark numbers can be re-run."""
    first = create_dataset(1_000)
    second = create_dataset(1_000)

    assert first.equals(second)