import argparse
import json
from pathlib import Path


def load_profile(path):
    """Load a profile JSON snapshot."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def compare_profiles(old, new):
    """Compare two profile snapshots and return their differences."""

    changes = {
        "quality_score": None,
        "dataset_shape": None,
        "added_columns": [],
        "removed_columns": [],
        "changed_columns": [],
    }

    # -----------------------------
    # Quality score
    # -----------------------------
    old_quality = old.get("quality_score", {})
    new_quality = new.get("quality_score", {})

    old_score = old_quality.get("score")
    new_score = new_quality.get("score")

    if old_score != new_score:
        changes["quality_score"] = {
            "old": old_score,
            "new": new_score,
            "change": new_score - old_score
            if old_score is not None and new_score is not None
            else None,
        }

    # -----------------------------
    # Dataset shape
    # -----------------------------
    old_shape = old.get("shape")
    new_shape = new.get("shape")

    if old_shape != new_shape:
        changes["dataset_shape"] = {
            "old": old_shape,
            "new": new_shape,
        }

    # -----------------------------
    # Column summaries
    # -----------------------------
    old_columns = {
        item["column"]: item
        for item in old.get("column_summary", [])
        if "column" in item
    }

    new_columns = {
        item["column"]: item
        for item in new.get("column_summary", [])
        if "column" in item
    }

    old_names = set(old_columns)
    new_names = set(new_columns)

    changes["added_columns"] = sorted(
        new_names - old_names
    )

    changes["removed_columns"] = sorted(
        old_names - new_names
    )

    # -----------------------------
    # Column-level changes
    # -----------------------------
    shared_columns = old_names & new_names

    old_statistics = old.get("statistics", {})
    new_statistics = new.get("statistics", {})

    old_outliers = old.get("outliers", {})
    new_outliers = new.get("outliers", {})

    for column in sorted(shared_columns):

        old_info = old_columns[column]
        new_info = new_columns[column]

        column_changes = {}

        # Summary fields
        for field in [
            "dtype",
            "null_count",
            "null_percent",
            "unique_count",
            "role",
            "cardinality",
        ]:

            old_value = old_info.get(field)
            new_value = new_info.get(field)

            if old_value != new_value:
                column_changes[field] = {
                    "old": old_value,
                    "new": new_value,
                }

        # Numeric statistics
        old_stats = old_statistics.get(column, {})
        new_stats = new_statistics.get(column, {})

        for field in [
            "count",
            "mean",
            "std",
            "min",
            "25%",
            "50%",
            "75%",
            "max",
        ]:

            old_value = old_stats.get(field)
            new_value = new_stats.get(field)

            if old_value != new_value:
                column_changes[f"stat_{field}"] = {
                    "old": old_value,
                    "new": new_value,
                }

        # Outlier information
        old_outlier = old_outliers.get(column, {})
        new_outlier = new_outliers.get(column, {})

        for field in [
            "lower_limit",
            "upper_limit",
            "outlier_count",
        ]:

            old_value = old_outlier.get(field)
            new_value = new_outlier.get(field)

            if old_value != new_value:
                column_changes[f"outlier_{field}"] = {
                    "old": old_value,
                    "new": new_value,
                }

        if column_changes:
            changes["changed_columns"].append({
                "column": column,
                "changes": column_changes,
            })

    return changes


def print_diff(changes):
    """Print a human-readable profile difference."""

    print("\n========== PROFILE DIFF ==========")

    if changes["quality_score"]:
        score = changes["quality_score"]

        print("\nQuality Score:")
        print(
            f"  {score['old']} -> {score['new']} "
            f"({score['change']:+})"
        )

    if changes["dataset_shape"]:
        shape = changes["dataset_shape"]

        print("\nDataset Shape:")
        print(f"  {shape['old']} -> {shape['new']}")

    if changes["added_columns"]:
        print("\nAdded Columns:")

        for column in changes["added_columns"]:
            print(f"  + {column}")

    if changes["removed_columns"]:
        print("\nRemoved Columns:")

        for column in changes["removed_columns"]:
            print(f"  - {column}")

    if changes["changed_columns"]:
        print("\nChanged Columns:")

        for item in changes["changed_columns"]:

            print(f"  {item['column']}:")

            for field, values in item["changes"].items():

                print(
                    f"    {field}: "
                    f"{values['old']} -> "
                    f"{values['new']}"
                )

    if not any([
        changes["quality_score"],
        changes["dataset_shape"],
        changes["added_columns"],
        changes["removed_columns"],
        changes["changed_columns"],
    ]):
        print("\nNo profile changes detected.")

    print("\n==================================")


def main():

    parser = argparse.ArgumentParser(
        description="Compare two profiling JSON snapshots."
    )

    parser.add_argument(
        "--old",
        required=True,
        help="Path to the older profile JSON."
    )

    parser.add_argument(
        "--new",
        required=True,
        help="Path to the newer profile JSON."
    )

    args = parser.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)

    if not old_path.exists():
        parser.error(
            f"Old profile not found: {old_path}"
        )

    if not new_path.exists():
        parser.error(
            f"New profile not found: {new_path}"
        )

    old_profile = load_profile(old_path)
    new_profile = load_profile(new_path)

    changes = compare_profiles(
        old_profile,
        new_profile
    )

    print_diff(changes)


if __name__ == "__main__":
    main()