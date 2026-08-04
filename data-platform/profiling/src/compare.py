import pandas as pd


def compare(df_old, df_new):
    print("\n========== DATA DRIFT REPORT ==========\n")

    drift_report = {}

    # Store drift information for every column
    column_drift = {}

    # -----------------------------
    # Shape Comparison
    # -----------------------------
    print("Dataset Shape")
    print(f"Old : {df_old.shape}")
    print(f"New : {df_new.shape}")

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
    # Data Type Comparison
    # -----------------------------
    print("\nDatatype Changes")

    dtype_changes = []

    for col in df_old.columns:

        if col not in df_new.columns:
            column_drift[col]["status"] = "major_drift"
            column_drift[col]["reasons"].append(
                "Column missing from new dataset"
            )
            continue

        if df_old[col].dtype != df_new[col].dtype:

            print(
                f"{col}: "
                f"{df_old[col].dtype} -> {df_new[col].dtype}"
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
        print("No datatype changes")

    drift_report["dtype_changes"] = dtype_changes


    # Null Percentage Comparison

    print("\nNull Percentage Changes")

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

        # Minor drift: 5 to less than 10 percentage points
        if 5 <= null_difference < 10:

            print(
                f"{col}: "
                f"{old_null}% -> {new_null}% "
                f"(Minor Drift)"
            )

            null_changes.append({
                "column": col,
                "old": old_null,
                "new": new_null,
                "difference": round(null_difference, 2),
                "status": "minor_drift"
            })

            # Don't downgrade an existing major drift
            if column_drift[col]["status"] != "major_drift":
                column_drift[col]["status"] = "minor_drift"

            column_drift[col]["reasons"].append(
                f"Null rate changed by {round(null_difference, 2)} percentage points"
            )


        # Major drift: 10 or more percentage points
        elif null_difference >= 10:

            print(
                f"{col}: "
                f"{old_null}% -> {new_null}% "
                f"(Major Drift)"
            )

            null_changes.append({
                "column": col,
                "old": old_null,
                "new": new_null,
                "difference": round(null_difference, 2),
                "status": "major_drift"
            })

            column_drift[col]["status"] = "major_drift"

            column_drift[col]["reasons"].append(
                f"Null rate changed by {round(null_difference, 2)} percentage points"
            )

    drift_report["null_changes"] = null_changes



    # Numeric Mean Comparison

    print("\nNumeric Mean Changes")

    mean_changes = []

    numeric_cols = df_old.select_dtypes(
        include="number"
    ).columns

    for col in numeric_cols:

        if col not in df_new.columns:
            continue

        old_mean = df_old[col].mean()
        new_mean = df_new[col].mean()
        old_std = df_old[col].std()

        mean_difference = abs(
            new_mean - old_mean
        )

        # PDF requirement:
        # mean shifted by more than 1 standard deviation
        if (
            pd.notna(old_std)
            and old_std > 0
            and mean_difference > old_std
        ):

            print(
                f"{col}: Major mean shift"
            )

            mean_changes.append({
                "column": col,
                "old_mean": round(old_mean, 2),
                "new_mean": round(new_mean, 2),
                "old_std": round(old_std, 2),
                "difference": round(mean_difference, 2)
            })

            column_drift[col]["status"] = "major_drift"

            column_drift[col]["reasons"].append(
                "Mean shifted by more than 1 standard deviation"
            )

    drift_report["mean_changes"] = mean_changes

    # New Categorical Values

    print("\nNew Categorical Values")

    new_categories = {}

    object_cols = [
        col
        for col in df_old.select_dtypes(
            include="object"
        ).columns
        if col != "date"
    ]

    for col in object_cols:

        if col not in df_new.columns:
            continue

        old_values = set(
            df_old[col].dropna()
        )

        new_values = set(
            df_new[col].dropna()
        )

        added = new_values - old_values

        if added:

            added_list = list(added)

            print(
                f"{col}: {added}"
            )

            new_categories[col] = added_list

            # Our grading rule:
            # 1-2 new categories = minor
            # 3+ new categories = major

            if len(added) <= 2:

                if column_drift[col]["status"] != "major_drift":
                    column_drift[col]["status"] = "minor_drift"

                column_drift[col]["reasons"].append(
                    f"{len(added)} new categorical value(s)"
                )

            else:

                column_drift[col]["status"] = "major_drift"

                column_drift[col]["reasons"].append(
                    f"{len(added)} new categorical values"
                )

    drift_report["new_categories"] = new_categories


    # Print Per-Column Drift

    print("\nColumn Drift Status")

    for col, details in column_drift.items():

        print(
            f"{col}: {details['status']}"
        )

        for reason in details["reasons"]:
            print(f"  - {reason}")

    drift_report["column_drift"] = column_drift


    # Overall Drift Decision

    print("\nOverall Drift")

    statuses = [
        details["status"]
        for details in column_drift.values()
    ]

    # Any major column makes overall drift major
    if "major_drift" in statuses:

        drift_status = "Major Drift"

    # Otherwise, any minor column makes overall drift minor
    elif "minor_drift" in statuses:

        drift_status = "Minor Drift"

    # Shape changed but columns themselves have no detected drift
    elif df_old.shape != df_new.shape:

        drift_status = "Minor Drift"

    else:

        drift_status = "No Drift"

    print(drift_status)

    drift_report["status"] = drift_status


    return drift_report