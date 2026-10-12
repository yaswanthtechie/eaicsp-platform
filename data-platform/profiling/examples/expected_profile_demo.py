from pathlib import Path

import pandas as pd

from src.profile import profile
from src.expected_profile import (
    create_expected_profile,
    save_expected_profile,
    load_expected_profile,
    benchmark_profile,
)


BASE_DIR = Path(__file__).resolve().parents[1]

DATA_PATH = BASE_DIR / "data" / "sales_data.csv"
EXPECTED_PATH = (
    BASE_DIR / "reports" / "expected_profile.json"
)


def main():
    # ---------------------------------
    # Load the trusted dataset
    # ---------------------------------
    trusted_df = pd.read_csv(DATA_PATH)

    # ---------------------------------
    # Create trusted profile
    # ---------------------------------
    trusted_profile = profile(trusted_df)

    # ---------------------------------
    # Create expected baseline
    # ---------------------------------
    expected_profile = create_expected_profile(
        trusted_profile
    )

    # ---------------------------------
    # Save expected baseline
    # ---------------------------------
    save_expected_profile(
        expected_profile,
        EXPECTED_PATH,
    )

    print("\n=== EXPECTED PROFILE CREATED ===")
    print(f"Saved to: {EXPECTED_PATH}")

    # ---------------------------------
    # Load expected baseline
    # ---------------------------------
    expected_profile = load_expected_profile(
        EXPECTED_PATH
    )

    # ---------------------------------
    # Create a new run
    # ---------------------------------
    current_df = trusted_df.copy()

    # Deliberately introduce a large increase
    # in missing values to demonstrate
    # expected-profile benchmarking.
    quantity_sold_missing_count = int(
        len(current_df) * 0.20
    )

    current_df.loc[
        current_df.index[:quantity_sold_missing_count],
        "quantity_sold",
    ] = None

    # ---------------------------------
    # Profile the new run
    # ---------------------------------
    current_profile = profile(current_df)

    # ---------------------------------
    # Benchmark against expectation
    # ---------------------------------
    result = benchmark_profile(
        expected_profile,
        current_profile,
    )

    print("\n=== BENCHMARK RESULT ===")
    print(f"Status: {result['status']}")

    if not result["deviations"]:
        print("No deviations found.")
        return

    print("\n=== DEVIATIONS ===")

    for deviation in result["deviations"]:
        print(
            f"\nMetric: {deviation['metric']}"
        )

        print(
            f"Status: {deviation['status']}"
        )

        if "expected_maximum" in deviation:
            print(
                f"Expected maximum: "
                f"{deviation['expected_maximum']}"
            )

        if "expected_minimum" in deviation:
            print(
                f"Expected minimum: "
                f"{deviation['expected_minimum']}"
            )

        if "expected" in deviation:
            print(
                f"Expected: "
                f"{deviation['expected']}"
            )

        print(
            f"Current: {deviation['current']}"
        )

        print(
            f"Reason: {deviation['reason']}"
        )


if __name__ == "__main__":
    main()