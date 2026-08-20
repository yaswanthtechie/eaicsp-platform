import numpy as np
import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


SEASONAL_DATASET = (
    "output/test_seasonal_normal.csv"
)

BLOCK_SIZE = 100


def describe_block(
    scores,
    temperatures,
):
    """
    Return summary statistics for one chronological block.
    """

    return {
        "count": len(scores),

        "temperature_mean": np.mean(
            temperatures
        ),

        "temperature_min": np.min(
            temperatures
        ),

        "temperature_max": np.max(
            temperatures
        ),

        "score_mean": np.mean(
            scores
        ),

        "score_median": np.median(
            scores
        ),

        "score_p95": np.percentile(
            scores,
            95,
        ),

        "score_p99": np.percentile(
            scores,
            99,
        ),

        "score_min": np.min(
            scores
        ),

        "score_max": np.max(
            scores
        ),
    }


def main():

    print("=" * 110)
    print(
        "SEASONAL DATA — CHRONOLOGICAL BLOCK ANALYSIS"
    )
    print("=" * 110)

    # --------------------------------------------------------
    # Load seasonal normal dataset
    # --------------------------------------------------------

    df = pd.read_csv(
        SEASONAL_DATASET
    )

    print()
    print(
        f"Dataset rows : {len(df)}"
    )

    print(
        f"Block size   : {BLOCK_SIZE}"
    )

    print(
        f"Temperature mean : "
        f"{df['temperature'].mean():.2f}°C"
    )

    print(
        f"Temperature std  : "
        f"{df['temperature'].std():.2f}°C"
    )

    models = get_models()

    # --------------------------------------------------------
    # Prepare model input
    # --------------------------------------------------------

    X = (
        df[
            feature_names
        ].to_numpy()
    )

    temperatures = (
        df["temperature"]
        .to_numpy()
    )

    # --------------------------------------------------------
    # Evaluate each model
    # --------------------------------------------------------

    for model_name, model in models.items():

        print()
        print("=" * 110)
        print(
            model_name.upper()
        )
        print("=" * 110)

        # Higher score = more anomalous
        scores = (
            -model.score(X)
        )

        # ----------------------------------------------------
        # Overall statistics
        # ----------------------------------------------------

        print()
        print(
            "OVERALL"
        )
        print("-" * 110)

        print(
            f"Temperature mean : "
            f"{temperatures.mean():.4f}°C"
        )

        print(
            f"Temperature std  : "
            f"{temperatures.std():.4f}°C"
        )

        print(
            f"Score mean       : "
            f"{scores.mean():.6f}"
        )

        print(
            f"Score median     : "
            f"{np.median(scores):.6f}"
        )

        print(
            f"Score P95        : "
            f"{np.percentile(scores, 95):.6f}"
        )

        print(
            f"Score P99        : "
            f"{np.percentile(scores, 99):.6f}"
        )

        # ----------------------------------------------------
        # Chronological blocks
        # ----------------------------------------------------

        print()
        print(
            "CHRONOLOGICAL BLOCKS"
        )
        print("-" * 110)

        print(
            f"{'Block':<8}"
            f"{'Rows':<12}"
            f"{'Temp Mean':<14}"
            f"{'Temp Min':<13}"
            f"{'Temp Max':<13}"
            f"{'Score Mean':<15}"
            f"{'Score Median':<15}"
            f"{'Score P95':<15}"
            f"{'Score P99':<15}"
        )

        print("-" * 110)

        block_results = []

        for start in range(
            0,
            len(df),
            BLOCK_SIZE,
        ):

            end = min(
                start + BLOCK_SIZE,
                len(df),
            )

            block_scores = scores[
                start:end
            ]

            block_temperatures = temperatures[
                start:end
            ]

            result = describe_block(
                block_scores,
                block_temperatures,
            )

            block_results.append(
                result
            )

            block_number = (
                start // BLOCK_SIZE
            ) + 1

            print(
                f"{block_number:<8}"
                f"{start}-{end - 1:<7}"
                f"{result['temperature_mean']:<14.3f}"
                f"{result['temperature_min']:<13.3f}"
                f"{result['temperature_max']:<13.3f}"
                f"{result['score_mean']:<15.6f}"
                f"{result['score_median']:<15.6f}"
                f"{result['score_p95']:<15.6f}"
                f"{result['score_p99']:<15.6f}"
            )

        # ----------------------------------------------------
        # Compare first block vs last block
        # ----------------------------------------------------

        first = block_results[0]
        last = block_results[-1]

        print()
        print(
            "FIRST BLOCK VS LAST BLOCK"
        )
        print("-" * 110)

        print(
            f"Temperature mean:"
        )

        print(
            f"  First : "
            f"{first['temperature_mean']:.6f}°C"
        )

        print(
            f"  Last  : "
            f"{last['temperature_mean']:.6f}°C"
        )

        print(
            f"  Change: "
            f"{last['temperature_mean'] - first['temperature_mean']:.6f}°C"
        )

        print()

        print(
            "Score median:"
        )

        print(
            f"  First : "
            f"{first['score_median']:.6f}"
        )

        print(
            f"  Last  : "
            f"{last['score_median']:.6f}"
        )

        print(
            f"  Change: "
            f"{last['score_median'] - first['score_median']:.6f}"
        )

        print()

        print(
            "Score P99:"
        )

        print(
            f"  First : "
            f"{first['score_p99']:.6f}"
        )

        print(
            f"  Last  : "
            f"{last['score_p99']:.6f}"
        )

        print(
            f"  Change: "
            f"{last['score_p99'] - first['score_p99']:.6f}"
        )

        # ----------------------------------------------------
        # Detect whether the regime is approximately stable
        # toward the end.
        # ----------------------------------------------------

        tail_blocks = block_results[
            -5:
        ]

        tail_temperature_means = [
            x["temperature_mean"]
            for x in tail_blocks
        ]

        tail_score_medians = [
            x["score_median"]
            for x in tail_blocks
        ]

        print()
        print(
            "LAST 5 BLOCK STABILITY"
        )
        print("-" * 110)

        print(
            f"Temperature mean range : "
            f"{min(tail_temperature_means):.4f} "
            f"to "
            f"{max(tail_temperature_means):.4f}°C"
        )

        print(
            f"Score median range     : "
            f"{min(tail_score_medians):.6f} "
            f"to "
            f"{max(tail_score_medians):.6f}"
        )

        print()

        print(
            "INTERPRETATION DATA"
        )
        print("-" * 110)

        print(
            "The important question is whether the score "
            "distribution moves from the calibration regime "
            "and then becomes reasonably stable."
        )

        print(
            "If the later blocks are stable, that supports "
            "treating the change as a sustained operating-regime "
            "shift rather than isolated anomalies."
        )

    print()
    print("=" * 110)
    print(
        "TEST COMPLETED"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()