# regressor_ablation.py

from pathlib import Path

import pandas as pd

from src.data import load_sales_data
from src.external_regressors import (
    add_external_regressors,
    validate_external_regressors,
)
from src.evaluate import evaluate
from src.train_prophet import (
    EXTERNAL_REGRESSORS,
    predict_prophet,
    train_prophet,
)


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

RESULTS_DIR = (
    PROJECT_ROOT
    / "models"
    / "regressor_ablation"
)

RESULTS_PATH = (
    RESULTS_DIR
    / "ablation_results.csv"
)

TRAIN_END_DATE = "2015-01-01"


# ============================================================
# Build Experiment Configurations
# ============================================================

def build_ablation_experiments():
    """
    Create baseline and leave-one-regressor-out experiments.

    Returns
    -------
    list[dict]
        Experiment definitions.
    """

    experiments = []

    # --------------------------------------------------------
    # Baseline
    # --------------------------------------------------------

    experiments.append(
        {
            "experiment": "baseline",
            "removed_regressor": None,
            "regressors": EXTERNAL_REGRESSORS.copy(),
        }
    )

    # --------------------------------------------------------
    # Leave-one-regressor-out experiments
    # --------------------------------------------------------

    for removed_regressor in EXTERNAL_REGRESSORS:

        selected_regressors = [
            regressor
            for regressor in EXTERNAL_REGRESSORS
            if regressor != removed_regressor
        ]

        experiments.append(
            {
                "experiment": (
                    f"remove_{removed_regressor}"
                ),
                "removed_regressor": (
                    removed_regressor
                ),
                "regressors": selected_regressors,
            }
        )

    return experiments


# ============================================================
# Prepare Dataset
# ============================================================

def prepare_dataset():
    """
    Load sales data and add external regressors.

    Returns
    -------
    pd.DataFrame
        Prophet-compatible dataframe.
    """

    df = load_sales_data()

    df = add_external_regressors(
        df
    )

    validate_external_regressors(
        df
    )

    prophet_df = df.rename(
        columns={
            "date": "ds",
            "quantity_sold": "y",
        }
    ).copy()

    prophet_df["ds"] = pd.to_datetime(
        prophet_df["ds"]
    )

    prophet_df = (
        prophet_df
        .sort_values("ds")
        .reset_index(drop=True)
    )

    return prophet_df


# ============================================================
# Train/Test Split
# ============================================================

def split_train_test(
    df,
    train_end_date=TRAIN_END_DATE,
):
    """
    Apply the same time-based train/test split used
    by the existing forecasting pipeline.
    """

    train_df = df[
        df["ds"] < train_end_date
    ].copy()

    test_df = df[
        df["ds"] >= train_end_date
    ].copy()

    if train_df.empty:

        raise ValueError(
            "Training dataframe is empty."
        )

    if test_df.empty:

        raise ValueError(
            "Test dataframe is empty."
        )

    return train_df, test_df


# ============================================================
# Calculate Delta
# ============================================================

def calculate_delta(
    baseline_value,
    experiment_value,
):
    """
    Calculate experiment metric delta relative to baseline.

    Positive delta means the metric increased.
    Negative delta means the metric decreased.
    """

    return float(
        experiment_value
        - baseline_value
    )


# ============================================================
# Run Ablation Study
# ============================================================

def run_ablation_study():
    """
    Run baseline + leave-one-regressor-out experiments.

    Returns
    -------
    pd.DataFrame
        Ablation results.
    """

    print("=" * 70)
    print("PROPHET REGRESSOR ABLATION STUDY")
    print("=" * 70)

    # --------------------------------------------------------
    # Load and prepare data
    # --------------------------------------------------------

    df = prepare_dataset()

    print(
        f"Total rows: {len(df)}"
    )

    # --------------------------------------------------------
    # Same train/test split for every experiment
    # --------------------------------------------------------

    train_df, test_df = split_train_test(
        df
    )

    print(
        f"Training rows: {len(train_df)}"
    )

    print(
        f"Testing rows: {len(test_df)}"
    )

    print(
        f"Train end date: {TRAIN_END_DATE}"
    )

    # --------------------------------------------------------
    # Build experiments
    # --------------------------------------------------------

    experiments = (
        build_ablation_experiments()
    )

    raw_results = []

    # --------------------------------------------------------
    # Run every experiment
    # --------------------------------------------------------

    for experiment in experiments:

        experiment_name = (
            experiment["experiment"]
        )

        removed_regressor = (
            experiment["removed_regressor"]
        )

        selected_regressors = (
            experiment["regressors"]
        )

        print("\n")
        print("-" * 70)

        print(
            f"Experiment: {experiment_name}"
        )

        if removed_regressor is None:

            print(
                "Removed regressor: None"
            )

        else:

            print(
                "Removed regressor:",
                removed_regressor,
            )

        print(
            "Using regressors:",
            selected_regressors,
        )

        print("-" * 70)

        # ----------------------------------------------------
        # Train model
        #
        # save_model=False is important because otherwise
        # every ablation experiment would overwrite
        # output/prophet_model.json.
        # ----------------------------------------------------

        model = train_prophet(
            train_df,
            regressors=selected_regressors,
            save_model=False,
        )

        # ----------------------------------------------------
        # Predict using the same selected regressors
        # ----------------------------------------------------

        forecast = predict_prophet(
            model,
            test_df,
            regressors=selected_regressors,
        )

        # ----------------------------------------------------
        # Align predictions with actual values by date
        # ----------------------------------------------------

        actual_df = test_df[
            [
                "ds",
                "y",
            ]
        ].copy()

        merged = actual_df.merge(
            forecast,
            on="ds",
            how="inner",
        )

        if merged.empty:

            raise ValueError(
                f"No matching dates found for "
                f"experiment '{experiment_name}'."
            )

        # ----------------------------------------------------
        # Evaluate
        # ----------------------------------------------------

        metrics = evaluate(
            merged["y"].to_numpy(),
            merged["yhat"].to_numpy(),
        )

        raw_results.append(
            {
                "experiment": experiment_name,
                "removed_regressor": (
                    removed_regressor
                ),
                "regressors_used": (
                    ", ".join(
                        selected_regressors
                    )
                    if selected_regressors
                    else "none"
                ),
                "MAPE": metrics["MAPE"],
                "RMSE": metrics["RMSE"],
            }
        )

    # --------------------------------------------------------
    # Create result dataframe
    # --------------------------------------------------------

    results = pd.DataFrame(
        raw_results
    )

    # --------------------------------------------------------
    # Baseline metrics
    # --------------------------------------------------------

    baseline_row = results[
        results["experiment"]
        == "baseline"
    ]

    if baseline_row.empty:

        raise ValueError(
            "Baseline experiment result not found."
        )

    baseline_mape = float(
        baseline_row.iloc[0]["MAPE"]
    )

    baseline_rmse = float(
        baseline_row.iloc[0]["RMSE"]
    )

    # --------------------------------------------------------
    # Calculate metric deltas
    # --------------------------------------------------------

    results["delta_MAPE"] = (
        results["MAPE"]
        .apply(
            lambda value:
            calculate_delta(
                baseline_mape,
                value,
            )
        )
    )

    results["delta_RMSE"] = (
        results["RMSE"]
        .apply(
            lambda value:
            calculate_delta(
                baseline_rmse,
                value,
            )
        )
    )

    # --------------------------------------------------------
    # Add interpretation
    # --------------------------------------------------------

    results["interpretation"] = (
        results.apply(
            interpret_result,
            axis=1,
        )
    )

    # --------------------------------------------------------
    # Save results
    # --------------------------------------------------------

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results.to_csv(
        RESULTS_PATH,
        index=False,
    )

    print("\n")
    print("=" * 70)
    print("ABLATION RESULTS")
    print("=" * 70)

    print(
        results.to_string(
            index=False
        )
    )

    print("\n")
    print(
        f"Results saved to: {RESULTS_PATH}"
    )

    print("=" * 70)

    return results


# ============================================================
# Result Interpretation
# ============================================================

def interpret_result(row):
    """
    Interpret a regressor ablation result relative to baseline.

    This does NOT claim causality.
    It only describes the measured change in this experiment.
    """

    if row["experiment"] == "baseline":

        return "Baseline with all regressors."

    delta_mape = row["delta_MAPE"]
    delta_rmse = row["delta_RMSE"]

    if (
        delta_mape > 0
        and delta_rmse > 0
    ):

        return (
            "Removing this regressor worsened "
            "both MAPE and RMSE in this experiment."
        )

    if (
        delta_mape < 0
        and delta_rmse < 0
    ):

        return (
            "Removing this regressor improved "
            "both MAPE and RMSE in this experiment."
        )

    if (
        delta_mape > 0
        and delta_rmse < 0
    ):

        return (
            "Removing this regressor increased MAPE "
            "but reduced RMSE."
        )

    if (
        delta_mape < 0
        and delta_rmse > 0
    ):

        return (
            "Removing this regressor reduced MAPE "
            "but increased RMSE."
        )

    return (
        "Removing this regressor produced "
        "no change in one or both metrics."
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    run_ablation_study()