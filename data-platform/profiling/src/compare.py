import logging
import pandas as pd

logger = logging.getLogger(__name__)


class DriftReport(dict):

    @property
    def has_major_drift(self):
        return self["status"] == "Major Drift"


def compare(df_old, df_new):
    logger.info("\n========== DATA DRIFT REPORT ==========\n")

    drift_report = {}

    # -----------------------------
    # Structural Compatibility
    # -----------------------------
    old_columns = set(df_old.columns)
    new_columns = set(df_new.columns)

    shared_columns = sorted(old_columns & new_columns)
    only_in_old = sorted(old_columns - new_columns)
    only_in_new = sorted(new_columns - old_columns)

    compatible_types = []
    incompatible_types = []

    for col in shared_columns:
        old_dtype = df_old[col].dtype
        new_dtype = df_new[col].dtype

        if old_dtype == new_dtype:
            compatible_types.append({
                "column": col,
                "dtype": str(old_dtype)
            })
        else:
            incompatible_types.append({
                "column": col,
                "old_dtype": str(old_dtype),
                "new_dtype": str(new_dtype)
            })

    drift_report["schema_compatibility"] = {
        "shared_columns": shared_columns,
        "only_in_old": only_in_old,
        "only_in_new": only_in_new,
        "compatible_types": compatible_types,
        "incompatible_types": incompatible_types
    }

    # -----------------------------
    # Store drift information
    # for every column
    # -----------------------------
    column_drift = {}

    # -----------------------------
    # Shape Comparison
    # -----------------------------
    logger.info("Dataset Shape")
    logger.info("Old : %s", df_old.shape)
    logger.info("New : %s", df_new.shape)

    drift_report["old_shape"] = df_old.shape
    drift_report["new_shape"] = df_new.shape

    # -----------------------------
    # Initialize Column Drift
    # -----------------------------
    for col in df_old.columns:
        column_drift[col] = {
            "status": "no_drift",
            "reasons": []
        }

    # -----------------------------
    # Detect New Columns
    # -----------------------------
    new_columns = [
        col for col in df_new.columns
        if col not in df_old.columns
    ]

    for col in new_columns:
        column_drift[col] = {
            "status": "major_drift",
            "reasons": [
                "New column added to new dataset"
            ]
        }

    drift_report["new_columns"] = new_columns

    # -----------------------------
    # Data Type Comparison
    # -----------------------------
    logger.info("\nDatatype Changes")

    dtype_changes = []

    for col in df_old.columns:

        if col not in df_new.columns:
            column_drift[col]["status"] = "major_drift"
            column_drift[col]["reasons"].append(
                "Column missing from new dataset"
            )
            continue

        if df_old[col].dtype != df_new[col].dtype:

            logger.info(
                "%s: %s -> %s",
                col,
                df_old[col].dtype,
                df_new[col].dtype
            )

            dtype_changes.append({
                "column": col,
                "old": str(df_old[col].dtype),
                "new": str(df_new[col].dtype)
            })

            column_drift[col]["status"] = "major_drift"
            column_drift[col]["reasons"].append(
                "Datatype changed"
            )

    if len(dtype_changes) == 0:
        logger.info("No datatype changes")

    drift_report["dtype_changes"] = dtype_changes

    # -----------------------------
    # Null Percentage Comparison
    # -----------------------------
    logger.info("\nNull Percentage Changes")

    null_changes = []

    for col in df_old.columns:

        if col not in df_new.columns:
            continue

        old_null = round(
            df_old[col].isnull().mean() * 100, 2
        )

        new_null = round(
            df_new[col].isnull().mean() * 100, 2
        )

        null_difference = abs(
            new_null - old_null
        )

        # Minor drift:
        # 5 to less than 10 percentage points
        if 5 <= null_difference < 10:

            logger.info(
                "%s: %s%% -> %s%% (Minor Drift)",
                col,
                old_null,
                new_null
            )

            null_changes.append({
                "column": col,
                "old": old_null,
                "new": new_null,
                "difference": round(
                    null_difference, 2
                ),
                "status": "minor_drift"
            })

            # Don't downgrade existing major drift
            if column_drift[col]["status"] != "major_drift":
                column_drift[col]["status"] = "minor_drift"

            column_drift[col]["reasons"].append(
                f"Null rate changed by "
                f"{round(null_difference, 2)} "
                f"percentage points"
            )

        # Major drift:
        # 10 or more percentage points
        elif null_difference >= 10:

            logger.info(
                "%s: %s%% -> %s%% (Major Drift)",
                col,
                old_null,
                new_null
            )

            null_changes.append({
                "column": col,
                "old": old_null,
                "new": new_null,
                "difference": round(
                    null_difference, 2
                ),
                "status": "major_drift"
            })

            column_drift[col]["status"] = "major_drift"

            column_drift[col]["reasons"].append(
                f"Null rate changed by "
                f"{round(null_difference, 2)} "
                f"percentage points"
            )

    drift_report["null_changes"] = null_changes

    # -----------------------------
    # Numeric Mean Comparison
    # -----------------------------
    logger.info("\nNumeric Mean Changes")

    mean_changes = []

    numeric_cols = df_old.select_dtypes(
        include="number"
    ).columns

    for col in numeric_cols:

        if col not in df_new.columns:
            continue

        # If the column is no longer numeric
        # in the new dataset, skip mean comparison.
        # The datatype change is already reported.
        if not pd.api.types.is_numeric_dtype(
            df_new[col]
        ):
            continue

        old_mean = df_old[col].mean()
        new_mean = df_new[col].mean()
        old_std = df_old[col].std()

        mean_difference = abs(
            new_mean - old_mean
        )

        # Mean shifted by more than
        # 1 standard deviation
        if (
            pd.notna(old_std)
            and old_std > 0
            and mean_difference > old_std
        ):

            logger.info("%s: Major mean shift", col)

            mean_changes.append({
                "column": col,
                "old_mean": round(old_mean, 2),
                "new_mean": round(new_mean, 2),
                "old_std": round(old_std, 2),
                "difference": round(
                    mean_difference, 2
                )
            })

            column_drift[col]["status"] = "major_drift"

            column_drift[col]["reasons"].append(
                "Mean shifted by more than "
                "1 standard deviation"
            )

    drift_report["mean_changes"] = mean_changes

    # -----------------------------
    # Categorical Drift Detail
    # -----------------------------
    logger.info("\nCategorical Drift Details")

    categorical_drift = {}

    object_cols = list(
    df_old.select_dtypes(include=["object", "category"]).columns
    )

    # Threshold for significant proportion change
    PROPORTION_THRESHOLD = 0.10

    for col in object_cols:

        if col not in df_new.columns:
            continue

        old_series = df_old[col].dropna()
        new_series = df_new[col].dropna()

        old_values = set(old_series)
        new_values = set(new_series)

        # -----------------------------
        # Appeared categories
        # -----------------------------
        added = sorted(new_values - old_values)

        # -----------------------------
        # Disappeared categories
        # -----------------------------
        removed = sorted(old_values - new_values)

        # -----------------------------
        # Category proportion changes
        # -----------------------------
        old_proportions = old_series.value_counts(
            normalize=True
        )

        new_proportions = new_series.value_counts(
            normalize=True
        )

        all_categories = old_values | new_values

        proportion_changes = []

        for category in sorted(all_categories):

            old_percentage = (
                old_proportions.get(category, 0) * 100
            )

            new_percentage = (
                new_proportions.get(category, 0) * 100
            )

            difference = abs(
                new_percentage - old_percentage
            )

            if difference >= PROPORTION_THRESHOLD * 100:

                proportion_changes.append({
                    "category": category,
                    "old_percentage": round(
                        old_percentage, 2
                    ),
                    "new_percentage": round(
                        new_percentage, 2
                    ),
                    "difference": round(
                        difference, 2
                    )
                })

        # -----------------------------
        # Store results
        # -----------------------------
        if added or removed or proportion_changes:

            categorical_drift[col] = {
                "appeared": added,
                "disappeared": removed,
                "proportion_changes": proportion_changes
            }

            logger.info("\n%s", col)

            if added:
                logger.info("  Appeared: %s", added)

            if removed:
                logger.info("  Disappeared: %s", removed)

            if proportion_changes:
                logger.info("  Significant proportion changes:")

                for change in proportion_changes:
                    logger.info(
                        "    %s: %s%% -> %s%%",
                        change["category"],
                        change["old_percentage"],
                        change["new_percentage"]
                    )
            # -----------------------------
            # Update column drift status
            # -----------------------------

            # New or removed categories are meaningful drift
            if added or removed:

                if len(added) + len(removed) >= 3:
                    column_drift[col]["status"] = "major_drift"

                elif column_drift[col]["status"] != "major_drift":
                    column_drift[col]["status"] = "minor_drift"

                column_drift[col]["reasons"].append(
                    "Categorical values appeared or disappeared"
                )

            # Significant proportion changes
            if proportion_changes:

                if column_drift[col]["status"] != "major_drift":
                    column_drift[col]["status"] = "minor_drift"

                column_drift[col]["reasons"].append(
                    "Significant categorical proportion change"
                )

    drift_report["categorical_drift"] = categorical_drift
    # -----------------------------
    # Print Per-Column Drift
    # -----------------------------
    logger.info("\nColumn Drift Status")

    for col, details in column_drift.items():

        logger.info("%s: %s", col, details["status"])

        for reason in details["reasons"]:
            logger.info("  - %s", reason)

    drift_report["column_drift"] = column_drift

    # -----------------------------
    # Overall Drift Decision
    # -----------------------------
    logger.info("\nOverall Drift")

    statuses = [
        details["status"]
        for details in column_drift.values()
    ]

    # Any major column makes
    # overall drift major
    if "major_drift" in statuses:

        drift_status = "Major Drift"

    # Otherwise, any minor column
    # makes overall drift minor
    elif "minor_drift" in statuses:

        drift_status = "Minor Drift"

    # Shape changed but columns themselves
    # have no detected drift
    elif df_old.shape != df_new.shape:

        drift_status = "Minor Drift"

    else:

        drift_status = "No Drift"

    logger.info(drift_status)

    drift_report["status"] = drift_status

    return DriftReport(drift_report)