"""Round 14 one-at-a-time ablation of the historical ETA features."""

import json

from sklearn.metrics import mean_absolute_error

from src.data import load_dataset
from src.features import build_eta_features
from src.paths import PROJECT_ROOT
from src.pipeline import create_eta_history_pipeline
from src.preprocess import (
    CATEGORICAL_FEATURES,
    ETA_HISTORY_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    preprocess_features,
)
from src.split import chronological_split


def main():
    datasets = load_dataset()

    features = preprocess_features(
        build_eta_features(datasets)
    )

    split = chronological_split(
        features=features,
        orders=datasets["orders"],
        test_size=0.20,
    )

    results = {}

    for removed in [
        None,
        *ETA_HISTORY_FEATURES,
    ]:
        kept = [
            feature
            for feature in ETA_HISTORY_FEATURES
            if feature != removed
        ]

        columns = (
            NUMERIC_FEATURES
            + kept
            + CATEGORICAL_FEATURES
        )

        pipeline = create_eta_history_pipeline(
            historical_features=kept
        )

        pipeline.fit(
            split.train[columns],
            split.train[TARGET_COLUMN],
        )

        mae = float(
            mean_absolute_error(
                split.test[TARGET_COLUMN],
                pipeline.predict(
                    split.test[columns]
                ),
            )
        )

        label = (
            "all_six"
            if removed is None
            else f"without_{removed}"
        )

        results[label] = mae

        print(
            f"{label:<55}{mae:.4f}"
        )

    output_path = (
        PROJECT_ROOT
        / "results"
        / "round14_ablation.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            results,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()