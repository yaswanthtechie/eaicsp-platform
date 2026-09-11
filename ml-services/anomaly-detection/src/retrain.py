import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import sys

project_root = Path(__file__).resolve().parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data import generate_normal_data
from src.evaluate import evaluate_models
from src.train import (
    save_models,
    train_models,
)

project_root = Path(__file__).resolve().parent.parent

output_dir = project_root / "output"
models_dir = project_root / "models"

output_dir.mkdir(
    parents=True,
    exist_ok=True,
)

FEATURE_COLUMNS = [
    "temperature",
    "humidity",
    "stock_count",
]

METADATA_FILE = (
    models_dir /
    "model_metadata.json"
)

RETRAIN_LOG = (
    output_dir /
    "retrain_log.csv"
)

PERFORMANCE_HISTORY = (
    output_dir /
    "model_performance_history.csv"
)

READINGS_PER_DAY = 24 * 12

WINDOW_DAYS = 30

TOTAL_DAYS = 35

WINDOW_SIZE = (
    WINDOW_DAYS *
    READINGS_PER_DAY
)

TOTAL_READINGS = (
    TOTAL_DAYS *
    READINGS_PER_DAY
)


def load_test_datasets():
    """
    Load benchmark datasets.
    """

    return {
        "Temperature Spike": pd.read_csv(
            output_dir /
            "test_temperature_spike.csv"
        ),
        "Temperature Drift": pd.read_csv(
            output_dir /
            "test_temperature_drift.csv"
        ),
        "Stock Anomaly": pd.read_csv(
            output_dir /
            "test_stock_anomaly.csv"
        ),
        "Combined Anomaly": pd.read_csv(
            output_dir /
            "test_combined_anomaly.csv"
        ),
    }


def load_metadata():

    if not METADATA_FILE.exists():

        metadata = {
            "model_version": "1.0.0",
            "last_retrained": None,
        }

        with open(
            METADATA_FILE,
            "w",
        ) as file:

            json.dump(
                metadata,
                file,
                indent=4,
            )

        return metadata

    with open(
        METADATA_FILE,
        "r",
    ) as file:

        return json.load(file)


def save_metadata(metadata):

    with open(
        METADATA_FILE,
        "w",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
        )


def increment_version(version):

    major, minor, patch = map(
        int,
        version.split("."),
    )

    patch += 1

    return (
        f"{major}."
        f"{minor}."
        f"{patch}"
    )


def append_csv(
    rows,
    file_path,
):
    """
    Append rows into a csv.
    """

    if not rows:
        return

    df = pd.DataFrame(rows)

    if file_path.exists():

        existing = pd.read_csv(
            file_path
        )

        df = pd.concat(
            [
                existing,
                df,
            ],
            ignore_index=True,
        )

    df.to_csv(
        file_path,
        index=False,
    )

    # ==========================================================
# Evaluation Helpers
# ==========================================================

def evaluate_all_datasets(models=None):
    """
    Evaluate either the deployed models or the supplied
    candidate models on every benchmark dataset.
    """

    test_datasets = load_test_datasets()

    results = []

    for dataset_name, dataset in test_datasets.items():

        metrics = evaluate_models(
            dataset,
            models=models,
        )

        metrics.insert(
            0,
            "Dataset",
            dataset_name,
        )

        results.append(metrics)

    return pd.concat(
        results,
        ignore_index=True,
    )


# ==========================================================
# Rolling Window Generation
# ==========================================================

def generate_rolling_windows():
    """
    Generate 35 days of normal sensor data and
    create six rolling 30-day windows.

    Returns
    -------
    list
        Each element is

        (
            window_number,
            start_day,
            end_day,
            dataframe
        )
    """

    normal_df = generate_normal_data(
        n=TOTAL_READINGS,
        seed=42,
    )

    windows = []

    total_windows = (
        TOTAL_DAYS -
        WINDOW_DAYS +
        1
    )

    for window_number in range(total_windows):

        start_reading = (
            window_number *
            READINGS_PER_DAY
        )

        end_reading = (
            start_reading +
            WINDOW_SIZE
        )

        start_day = (
            window_number + 1
        )

        end_day = (
            start_day +
            WINDOW_DAYS -
            1
        )

        window_df = (
            normal_df
            .iloc[
                start_reading:
                end_reading
            ]
            .reset_index(
                drop=True
            )
        )

        windows.append(
            (
                window_number + 1,
                start_day,
                end_day,
                window_df,
            )
        )

    return windows


# ==========================================================
# Model Comparison
# ==========================================================

def compare_models(
    deployed_metrics,
    candidate_metrics,
):
    """
    Compare average precision of each model
    across all benchmark datasets.

    Returns
    -------
    dict

    {
        "Isolation Forest": True,
        "One-Class SVM": False,
        ...
    }
    """

    comparison = {}

    deployed_avg = (
        deployed_metrics
        .groupby("Model")[
            "Precision"
        ]
        .mean()
    )

    candidate_avg = (
        candidate_metrics
        .groupby("Model")[
            "Precision"
        ]
        .mean()
    )

    for model in deployed_avg.index:

        comparison[model] = (
            candidate_avg[model]
            >=
            deployed_avg[model]
        )

    return comparison

# ==========================================================
# Retraining Loop
# ==========================================================

def run_retraining(
    deploy_on_improvement=True,
):
    """
    Simulate nightly retraining using a
    rolling 30-day window.
    """

    metadata = load_metadata()

    current_version = metadata["model_version"]

    windows = generate_rolling_windows()

    deployment_rows = []

    performance_rows = []

    deployed_metrics = evaluate_all_datasets()

    for (
        window_number,
        start_day,
        end_day,
        window_df,
    ) in windows:

        print("=" * 60)
        print(
            f"Window {window_number} "
            f"(Day {start_day} - {end_day})"
        )
        print("=" * 60)

        # -----------------------------------------
        # Train candidate models
        # -----------------------------------------

        candidate_models = train_models(
            window_df
        )

        candidate_metrics = evaluate_all_datasets(
            models=candidate_models
        )

        deployment = compare_models(
            deployed_metrics,
            candidate_metrics,
        )

        candidate_version = increment_version(
            current_version
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # -----------------------------------------
        # Save complete performance history
        # -----------------------------------------

        for _, row in candidate_metrics.iterrows():

            performance_rows.append(
                {
                    "Timestamp": timestamp,
                    "Window": window_number,
                    "Window Start": start_day,
                    "Window End": end_day,
                    "Version": candidate_version,
                    "Dataset": row["Dataset"],
                    "Model": row["Model"],
                    "Precision": row["Precision"],
                    "Recall": row["Recall"],
                    "Caught": row["Caught"],
                    "False Alarms": row["False Alarms"],
                    "Predicted": row["Predicted"],
                }
            )

        # -----------------------------------------
        # Deployment decision
        # -----------------------------------------

        old_avg = (
            deployed_metrics
            .groupby("Model")["Precision"]
            .mean()
        )

        new_avg = (
            candidate_metrics
            .groupby("Model")["Precision"]
            .mean()
        )

        deployed = False

        for model in deployment:

            improved = deployment[model]

            deployment_rows.append(
                {
                    "Timestamp": timestamp,
                    "Window": window_number,
                    "Window Start": start_day,
                    "Window End": end_day,
                    "Model": model,
                    "Old Version": current_version,
                    "Candidate Version": candidate_version,
                    "Old Precision": round(
                        old_avg[model],
                        4,
                    ),
                    "New Precision": round(
                        new_avg[model],
                        4,
                    ),
                    "Decision": (
                        "DEPLOYED"
                        if improved
                        else "REJECTED"
                    ),
                    "Reason": (
                        "Average precision improved"
                        if improved
                        else "Average precision decreased"
                    ),
                }
            )

            if improved:
                deployed = True

        # -----------------------------------------
        # Deploy candidate models
        # -----------------------------------------

        if deployed and deploy_on_improvement:

            print(
                "Deploying candidate models..."
            )

            save_models(
                candidate_models
            )

            current_version = (
                candidate_version
            )

            metadata[
                "model_version"
            ] = current_version

            metadata[
                "last_retrained"
            ] = timestamp

            save_metadata(
                metadata
            )

            deployed_metrics = (
                candidate_metrics
            )

        else:

            print(
                "Deployment rejected."
            )

    append_csv(
        deployment_rows,
        RETRAIN_LOG,
    )

    append_csv(
        performance_rows,
        PERFORMANCE_HISTORY,
    )

    return (
        deployment_rows,
        performance_rows,
    )

# ==========================================================
# Summary
# ==========================================================

def print_summary(
    deployment_rows,
    performance_rows,
):
    """
    Print a summary of the retraining run.
    """

    print("\n")
    print("=" * 70)
    print("Rolling Window Retraining Summary")
    print("=" * 70)

    deployed = sum(
        row["Decision"] == "DEPLOYED"
        for row in deployment_rows
    )

    rejected = sum(
        row["Decision"] == "REJECTED"
        for row in deployment_rows
    )

    print(f"Deployment Decisions : {len(deployment_rows)}")
    print(f"Models Deployed      : {deployed}")
    print(f"Models Rejected      : {rejected}")

    print()

    if performance_rows:

        history = pd.DataFrame(
            performance_rows
        )

        print("Average Precision")

        print(
            history.groupby("Model")["Precision"]
            .mean()
            .sort_values(
                ascending=False,
            )
            .round(4)
        )

        print()

        print("Average Recall")

        print(
            history.groupby("Model")["Recall"]
            .mean()
            .sort_values(
                ascending=False,
            )
            .round(4)
        )

    print()

    print(
        f"Deployment log saved to:\n"
        f"{RETRAIN_LOG}"
    )

    print()

    print(
        f"Performance history saved to:\n"
        f"{PERFORMANCE_HISTORY}"
    )

    print("=" * 70)


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    deployment_rows, performance_rows = run_retraining()

    print_summary(
        deployment_rows,
        performance_rows,
    )