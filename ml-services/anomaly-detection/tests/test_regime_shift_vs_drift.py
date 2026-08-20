import numpy as np
import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


CALIBRATION = (
    "output/calibration_normal.csv"
)

SEASONAL = (
    "output/test_seasonal_normal.csv"
)

DRIFT = (
    "output/test_temperature_drift.csv"
)

SPIKES = (
    "output/test_temperature_spike.csv"
)

BLOCK_SIZE = 100


def summarize_block(
    temperatures,
    scores,
):
    """
    Calculate statistics for one chronological block.
    """

    temperatures = np.asarray(
        temperatures,
        dtype=float,
    )

    scores = np.asarray(
        scores,
        dtype=float,
    )

    return {
        "temperature_mean": float(
            np.mean(temperatures)
        ),
        "temperature_std": float(
            np.std(temperatures)
        ),
        "temperature_min": float(
            np.min(temperatures)
        ),
        "temperature_max": float(
            np.max(temperatures)
        ),
        "score_mean": float(
            np.mean(scores)
        ),
        "score_median": float(
            np.median(scores)
        ),
        "score_std": float(
            np.std(scores)
        ),
    }


def analyze_dataset(
    name,
    df,
    model,
):
    """
    Analyze chronological behavior of a dataset.
    """

    X = (
        df[
            feature_names
        ].to_numpy()
    )

    temperatures = (
        df["temperature"]
        .to_numpy()
    )

    # Higher score = more anomalous.
    scores = (
        -model.score(X)
    )

    blocks = []

    for start in range(
        0,
        len(df),
        BLOCK_SIZE,
    ):

        end = min(
            start + BLOCK_SIZE,
            len(df),
        )

        block = summarize_block(
            temperatures[start:end],
            scores[start:end],
        )

        block["start"] = start
        block["end"] = end - 1

        blocks.append(block)

    return scores, blocks


def print_blocks(
    blocks,
):
    """
    Print chronological block statistics.
    """

    print(
        f"{'Block':<8}"
        f"{'Temp Mean':<13}"
        f"{'Temp Std':<12}"
        f"{'Temp Min':<12}"
        f"{'Temp Max':<12}"
        f"{'Score Mean':<15}"
        f"{'Score Median':<15}"
        f"{'Score Std':<14}"
    )

    print("-" * 100)

    for index, block in enumerate(
        blocks,
        start=1,
    ):

        print(
            f"{index:<8}"
            f"{block['temperature_mean']:<13.3f}"
            f"{block['temperature_std']:<12.3f}"
            f"{block['temperature_min']:<12.3f}"
            f"{block['temperature_max']:<12.3f}"
            f"{block['score_mean']:<15.6f}"
            f"{block['score_median']:<15.6f}"
            f"{block['score_std']:<14.6f}"
        )


def calculate_regime_stability(
    blocks,
):
    """
    Compare the first half of the blocks against
    the second half.

    A stable regime should have relatively small
    changes between later blocks.

    A drift should continue moving.
    """

    if len(blocks) < 4:

        return {
            "temperature_progression": 0.0,
            "score_progression": 0.0,
        }

    midpoint = len(blocks) // 2

    first_half = blocks[
        :midpoint
    ]

    second_half = blocks[
        midpoint:
    ]

    first_temperature = np.mean(
        [
            block[
                "temperature_mean"
            ]
            for block in first_half
        ]
    )

    second_temperature = np.mean(
        [
            block[
                "temperature_mean"
            ]
            for block in second_half
        ]
    )

    first_score = np.mean(
        [
            block[
                "score_median"
            ]
            for block in first_half
        ]
    )

    second_score = np.mean(
        [
            block[
                "score_median"
            ]
            for block in second_half
        ]
    )

    return {
        "temperature_progression": (
            second_temperature
            - first_temperature
        ),
        "score_progression": (
            second_score
            - first_score
        ),
    }


def main():

    print("=" * 100)
    print(
        "REGIME SHIFT VS SLOW DRIFT TEST"
    )
    print("=" * 100)

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    calibration_df = pd.read_csv(
        CALIBRATION
    )

    seasonal_df = pd.read_csv(
        SEASONAL
    )

    drift_df = pd.read_csv(
        DRIFT
    )

    spike_df = pd.read_csv(
        SPIKES
    )

    print()
    print(
        f"Calibration rows : "
        f"{len(calibration_df)}"
    )

    print(
        f"Seasonal rows    : "
        f"{len(seasonal_df)}"
    )

    print(
        f"Drift rows       : "
        f"{len(drift_df)}"
    )

    print(
        f"Spike rows       : "
        f"{len(spike_df)}"
    )

    models = get_models()

    # --------------------------------------------------------
    # Analyze each model
    # --------------------------------------------------------

    for model_name, model in models.items():

        print()
        print("=" * 100)
        print(
            model_name.upper()
        )
        print("=" * 100)

        # ----------------------------------------------------
        # Calibration
        # ----------------------------------------------------

        calibration_X = (
            calibration_df[
                feature_names
            ].to_numpy()
        )

        calibration_scores = (
            -model.score(
                calibration_X
            )
        )

        calibration_p99 = float(
            np.percentile(
                calibration_scores,
                99,
            )
        )

        print()
        print(
            "CALIBRATION"
        )
        print("-" * 100)

        print(
            f"P99 threshold : "
            f"{calibration_p99:.6f}"
        )

        # ----------------------------------------------------
        # Seasonal
        # ----------------------------------------------------

        print()
        print(
            "STABLE SEASONAL REGIME"
        )
        print("-" * 100)

        seasonal_scores, seasonal_blocks = (
            analyze_dataset(
                "seasonal",
                seasonal_df,
                model,
            )
        )

        print_blocks(
            seasonal_blocks
        )

        seasonal_stability = (
            calculate_regime_stability(
                seasonal_blocks
            )
        )

        print()
        print(
            "Seasonal progression"
        )

        print(
            f"Temperature change : "
            f"{seasonal_stability['temperature_progression']:.4f}°C"
        )

        print(
            f"Score change       : "
            f"{seasonal_stability['score_progression']:.6f}"
        )

        # ----------------------------------------------------
        # Drift
        # ----------------------------------------------------

        print()
        print(
            "SLOW TEMPERATURE DRIFT"
        )
        print("-" * 100)

        drift_scores, drift_blocks = (
            analyze_dataset(
                "drift",
                drift_df,
                model,
            )
        )

        print_blocks(
            drift_blocks
        )

        drift_stability = (
            calculate_regime_stability(
                drift_blocks
            )
        )

        print()
        print(
            "Drift progression"
        )

        print(
            f"Temperature change : "
            f"{drift_stability['temperature_progression']:.4f}°C"
        )

        print(
            f"Score change       : "
            f"{drift_stability['score_progression']:.6f}"
        )

        # ----------------------------------------------------
        # Spike dataset
        # ----------------------------------------------------

        print()
        print(
            "TEMPERATURE SPIKES"
        )
        print("-" * 100)

        spike_X = (
            spike_df[
                feature_names
            ].to_numpy()
        )

        spike_scores = (
            -model.score(
                spike_X
            )
        )

        spike_labels = (
            spike_df["is_anomaly"]
            .astype(int)
            .to_numpy()
        )

        spike_predictions = (
            spike_scores
            > calibration_p99
        ).astype(int)

        spike_tp = int(
            (
                (spike_predictions == 1)
                & (spike_labels == 1)
            ).sum()
        )

        spike_fn = int(
            (
                (spike_predictions == 0)
                & (spike_labels == 1)
            ).sum()
        )

        print(
            f"Actual spike anomalies : "
            f"{spike_labels.sum()}"
        )

        print(
            f"Detected using fixed P99: "
            f"{spike_tp}"
        )

        print(
            f"Missed using fixed P99   : "
            f"{spike_fn}"
        )

        # ----------------------------------------------------
        # Final diagnostic
        # ----------------------------------------------------

        print()
        print(
            "REGIME VS DRIFT DIAGNOSTIC"
        )
        print("-" * 100)

        seasonal_temp_change = abs(
            seasonal_stability[
                "temperature_progression"
            ]
        )

        drift_temp_change = abs(
            drift_stability[
                "temperature_progression"
            ]
        )

        print(
            f"Seasonal temperature progression : "
            f"{seasonal_temp_change:.4f}°C"
        )

        print(
            f"Drift temperature progression    : "
            f"{drift_temp_change:.4f}°C"
        )

        if (
            seasonal_temp_change
            < drift_temp_change
        ):

            print(
                "[PASS] Seasonal regime is more "
                "stable than the drift sequence."
            )

        else:

            print(
                "[INFO] Seasonal and drift behavior "
                "need further investigation."
            )

    print()
    print("=" * 100)
    print(
        "TEST COMPLETED"
    )
    print("=" * 100)


if __name__ == "__main__":
    main()