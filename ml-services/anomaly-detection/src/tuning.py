import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0,str(project_root))

from src.isolation_forest_model import IsolationForestModel

from src.lof_model import LOFModel

from src.one_class_svm_model import OneClassSVMModel


output_dir = project_root / "output"


def load_data():
    """
    Load the training dataset and all test datasets.
    """

    train_df = pd.read_csv(output_dir / "train_normal.csv")

    test_datasets = {
        "temperature_spike": pd.read_csv(output_dir/ "test_temperature_spike.csv"),
        "temperature_drift": pd.read_csv(output_dir/ "test_temperature_drift.csv"),
        "stock_anomaly": pd.read_csv(output_dir/ "test_stock_anomaly.csv"),
        "combined_anomaly": pd.read_csv(output_dir/ "test_combined_anomaly.csv")
    }

    return (train_df,test_datasets)


def run_tuning(
    model,
    train_features,
    test_datasets,
    name,
):
    print(
        f"\n{name}"
    )

    return model.tune(
        train_features=train_features,
        test_datasets=test_datasets,
    )


def main():

    print("=" * 70)

    print("ANOMALY DETECTION HYPERPARAMETER TUNING")

    print("=" * 70)

    train_df, test_datasets = (load_data())

    train_features = train_df[["temperature","humidity","stock_count"]]

    # Run tuning for all three models.

    results = pd.concat(
        [
            run_tuning(
                IsolationForestModel(),
                train_features,
                test_datasets,
                "[1/3] Isolation Forest",
            ),

            run_tuning(
                LOFModel(),
                train_features,
                test_datasets,
                "[2/3] Local Outlier Factor",
            ),

            run_tuning(
                OneClassSVMModel(),
                train_features,
                test_datasets,
                "[3/3] One-Class SVM",
            ),
        ],
        ignore_index=True,
    )

    print("\nCombining all tuning results...")

    # Keep OVERALL rows first for each model,
    # followed by the per-dataset rankings.

    results.sort_values(by=["Model","Test Dataset","Rank"],inplace=True)

    results.reset_index(drop=True,inplace=True)

    # Save complete tuning results.

    output_file = (output_dir/ "hyperparameter_tuning_results.csv")

    results.to_csv(output_file,index=False)

    print("\n"+ "=" * 70)

    print("Hyperparameter tuning completed successfully!")

    print("=" * 70)

    print(f"\nSaved to:\n{output_file}")

    # Overall best configurations

    print("\n"+ "=" * 70)

    print("OVERALL BEST CONFIGURATIONS")

    print("=" * 70)

    overall = results[results["Test Dataset"] == "OVERALL"].copy()

    if overall.empty:

        print("\nNo overall ranking results found.")

        print("Check that rank_results() in tuning_utils.py is the updated version.")

    else:

        for model_name in (overall["Model"].unique()):

            model_results = (overall[overall["Model"]== model_name].sort_values(by="Rank"))

            best = model_results.iloc[0]

            print()
            print(model_name)

            print("-" * 70)

            print(f"Rank         : "f"{int(best['Rank'])}")

            print(f"Avg PR Score : "f"{best['PR Score']:.4f}")

            print(f"Avg F1       : "f"{best['F1']:.4f}")

            print(f"Avg Precision: "f"{best['Precision']:.4f}")

            print(f"Avg Recall   : "f"{best['Recall']:.4f}")

            print(f"Total TP     : "f"{int(best['TP'])}")

            print(f"Total TN     : "f"{int(best['TN'])}")

            print(f"Total FP     : "f"{int(best['FP'])}")

            print(f"Total FN     : "f"{int(best['FN'])}")

            print("\nParameters:")

            parameter_columns = [
                "Contamination",
                "n_estimators",
                "max_samples",
                "n_neighbors",
                "Metric",
                "Kernel",
                "nu",
                "gamma",
                "degree",
            ]

            for parameter in parameter_columns:

                if parameter not in best.index:
                    continue

                value = best[
                    parameter
                ]

                # Don't print empty/unused
                # parameters.

                if pd.isna(value):
                    continue

                print(f"  {parameter}: "f"{value}")

    # Summary

    print("\n" + "=" * 70)
    print("TUNING SUMMARY")
    print("=" * 70)

    summary = (results.groupby(["Model","Test Dataset"]).size().reset_index(name="Configurations"))

    print(summary.to_string(index=False))

    # Preview

    print("\n" + "=" * 70)

    print("RESULT PREVIEW")

    print("=" * 70)

    print(results.head(20).to_string(index=False))


if __name__ == "__main__":
    main()