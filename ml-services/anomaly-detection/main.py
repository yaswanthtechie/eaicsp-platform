from pathlib import Path

import pandas as pd

from src.data import generate_all_datasets
from src.evaluate import evaluate_models
from src.plot import generate_plot
from src.train import (
    save_models,
    train_models,
)

project_root = Path(__file__).resolve().parent
output_dir = project_root / "output"


def main():
    print("=" * 60)
    print("Starting Anomaly Detection Pipeline")
    print("=" * 60)

    # Generate all datasets
    generate_all_datasets()

    # Load training data
    train_df = pd.read_csv(
        output_dir / "train_normal.csv"
    )

    # Train candidate models
    models = train_models(train_df)

    # Deploy models
    save_models(models)

    # Test datasets
    test_datasets = {
        "Temperature Spike": "test_temperature_spike.csv",
        "Temperature Drift": "test_temperature_drift.csv",
        "Stock Anomaly": "test_stock_anomaly.csv",
        "Combined Anomaly": "test_combined_anomaly.csv",
    }

    all_results = []

    for dataset_name, filename in test_datasets.items():

        print(f"\nEvaluating {dataset_name}...")

        df = pd.read_csv(
            output_dir / filename
        )

        results = evaluate_models(df)

        results.insert(
            0,
            "Dataset",
            dataset_name,
        )

        all_results.append(results)

        # Optional: generate plot
        # generate_plot(df)

    final_results = pd.concat(
        all_results,
        ignore_index=True,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_results.to_csv(
        output_dir / "precision_recall.csv",
        index=False,
    )

    print("\nFinal Results")
    print("=" * 60)
    print(final_results)

    print("=" * 60)
    print("Pipeline completed successfully.")
    print("=" * 60)

    return final_results


if __name__ == "__main__":
    main()