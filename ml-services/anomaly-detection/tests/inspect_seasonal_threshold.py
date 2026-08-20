import pandas as pd
import numpy as np

from src.adaptive_threshold import AdaptiveThreshold
from src.model_loader import (
    feature_names,
    get_models,
)


BACKGROUND = (
    "models/background_sample.csv"
)

SEASONAL = (
    "output/test_seasonal_normal.csv"
)

SPIKE = (
    "output/test_temperature_spike.csv"
)


def describe_scores(
    label,
    scores,
):
    scores = np.asarray(
        scores,
        dtype=float,
    )

    print()
    print(label)
    print("-" * 80)

    print(
        f"Minimum : {scores.min():.6f}"
    )

    print(
        f"Median  : {np.median(scores):.6f}"
    )

    print(
        f"P95     : {np.percentile(scores, 95):.6f}"
    )

    print(
        f"P99     : {np.percentile(scores, 99):.6f}"
    )

    print(
        f"Maximum : {scores.max():.6f}"
    )


def main():

    print("=" * 80)
    print(
        "CALIBRATION VS SEASONAL VS SPIKE "
        "SCORE DISTRIBUTION"
    )
    print("=" * 80)

    background_df = pd.read_csv(
        BACKGROUND
    )

    seasonal_df = pd.read_csv(
        SEASONAL
    )

    spike_df = pd.read_csv(
        SPIKE
    )

    background_X = (
        background_df[
            feature_names
        ].to_numpy()
    )

    seasonal_X = (
        seasonal_df[
            feature_names
        ].to_numpy()
    )

    spike_X = (
        spike_df[
            feature_names
        ].to_numpy()
    )

    models = get_models()

    for model_name, model in models.items():

        print()
        print("=" * 80)
        print(
            model_name.upper()
        )
        print("=" * 80)

        calibration_scores = (
            -model.score(
                background_X
            )
        )

        seasonal_scores = (
            -model.score(
                seasonal_X
            )
        )

        spike_scores = (
            -model.score(
                spike_X
            )
        )

        describe_scores(
            "CALIBRATION NORMAL",
            calibration_scores,
        )

        describe_scores(
            "SEASONAL NORMAL",
            seasonal_scores,
        )

        describe_scores(
            "TEMPERATURE SPIKES",
            spike_scores,
        )

        # ----------------------------------------------------
        # Fixed calibration P99
        # ----------------------------------------------------

        calibration_threshold = (
            np.percentile(
                calibration_scores,
                99,
            )
        )

        # ----------------------------------------------------
        # Ideal seasonal P99
        #
        # This is NOT a production algorithm.
        #
        # It answers:
        #
        # "If we already knew the seasonal data was
        # normal, what threshold would we get?"
        # ----------------------------------------------------

        seasonal_threshold = (
            np.percentile(
                seasonal_scores,
                99,
            )
        )

        print()
        print(
            "THRESHOLD COMPARISON"
        )
        print("-" * 80)

        print(
            f"Calibration P99 : "
            f"{calibration_threshold:.6f}"
        )

        print(
            f"Seasonal P99    : "
            f"{seasonal_threshold:.6f}"
        )

        # ----------------------------------------------------
        # How many seasonal normals would each threshold
        # classify as anomalous?
        # ----------------------------------------------------

        calibration_fp = (
            seasonal_scores
            > calibration_threshold
        ).sum()

        seasonal_fp = (
            seasonal_scores
            > seasonal_threshold
        ).sum()

        print()
        print(
            "SEASONAL NORMAL CLASSIFICATION"
        )
        print("-" * 80)

        print(
            f"Using calibration P99 : "
            f"{calibration_fp} / "
            f"{len(seasonal_scores)}"
        )

        print(
            f"Using seasonal P99    : "
            f"{seasonal_fp} / "
            f"{len(seasonal_scores)}"
        )

        # ----------------------------------------------------
        # Spike detection using ideal seasonal threshold
        # ----------------------------------------------------

        spike_detected = (
            spike_scores
            > seasonal_threshold
        ).sum()

        print()
        print(
            "SPIKE DETECTION USING "
            "IDEAL SEASONAL THRESHOLD"
        )
        print("-" * 80)

        print(
            f"Detected : "
            f"{spike_detected} / "
            f"{len(spike_scores)}"
        )

        # ----------------------------------------------------
        # Simulate initializing directly with seasonal
        # normal scores.
        #
        # Diagnostic only.
        # ----------------------------------------------------

        manager = AdaptiveThreshold(
            window_size=100,
            percentile=99.0,
        )

        manager.initialize(
            seasonal_scores
        )

        manager_threshold = (
            manager.get_threshold()
        )

        print()
        print(
            "ADAPTIVE MANAGER INITIALIZED "
            "WITH SEASONAL NORMAL"
        )
        print("-" * 80)

        print(
            f"Threshold : "
            f"{manager_threshold:.6f}"
        )

        print()

    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()