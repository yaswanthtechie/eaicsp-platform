import pandas as pd
from .compare import compare

# A correlation needs enough keys to mean anything. With 2 keys it is
# always exactly +1 or -1, so any two keys that happen to move would be
# reported as a "perfect" root cause. Below this many matched keys we
# make no suggestion at all.
MIN_MATCHED_KEYS = 5

def suggest_root_causes(
    downstream_old,
    downstream_new,
    upstream_old,
    upstream_new,
    relationships,
):
    """
    Suggest plausible upstream causes for detected drift.
    """

    # -----------------------------
    # Input validation
    # -----------------------------
    if not isinstance(downstream_old, pd.DataFrame):
        raise TypeError(
            "downstream_old must be a pandas DataFrame"
        )

    if not isinstance(downstream_new, pd.DataFrame):
        raise TypeError(
            "downstream_new must be a pandas DataFrame"
        )

    if not isinstance(upstream_old, pd.DataFrame):
        raise TypeError(
            "upstream_old must be a pandas DataFrame"
        )

    if not isinstance(upstream_new, pd.DataFrame):
        raise TypeError(
            "upstream_new must be a pandas DataFrame"
        )

    if not isinstance(relationships, list):
        raise TypeError(
            "relationships must be a list"
        )

    # -----------------------------
    # Detect downstream drift
    # -----------------------------
    downstream_report = compare(
        downstream_old,
        downstream_new,
    )

    downstream_drifts = []

    for column, details in downstream_report[
        "column_drift"
    ].items():

        if details["status"] in {
            "minor_drift",
            "major_drift",
        }:
            downstream_drifts.append(column)

    # -----------------------------
    # Find relationship keys
    # -----------------------------
    relationship_keys = _find_relationship_keys(
        relationships,
        downstream_new.columns,
    )

    # -----------------------------
    # Detect upstream drift
    # -----------------------------
    upstream_drifts = _find_upstream_drifts(
        upstream_old,
        upstream_new,
    )

    candidates = []

    # -----------------------------
    # Analyze each downstream metric
    # -----------------------------
    for downstream_metric in downstream_drifts:

        # Skip columns that are not present
        # in both old and new datasets.
        if (
            downstream_metric not in downstream_old.columns
            or downstream_metric not in downstream_new.columns
        ):
            continue

        # Root-cause analysis currently works
        # with numeric metrics only.
        if not pd.api.types.is_numeric_dtype(
            downstream_old[downstream_metric]
        ):
            continue

        if not pd.api.types.is_numeric_dtype(
            downstream_new[downstream_metric]
        ):
            continue

        # -----------------------------
        # Analyze each relationship
        # -----------------------------
        for relationship in relationship_keys:

            downstream_key = relationship[
                "downstream_key"
            ]

            upstream_key = relationship[
                "upstream_key"
            ]

            # Don't treat the relationship key
            # itself as the downstream metric.
            if downstream_metric == downstream_key:
                continue

            # -----------------------------
            # Analyze each upstream drift
            # -----------------------------
            for upstream_metric in upstream_drifts:

                # Skip the upstream relationship key.
                if upstream_metric == upstream_key:
                    continue

                # Skip columns that are not present
                # in both upstream datasets.
                if (
                    upstream_metric not in upstream_old.columns
                    or upstream_metric not in upstream_new.columns
                ):
                    continue

                # Upstream metric must be numeric.
                if not pd.api.types.is_numeric_dtype(
                    upstream_old[upstream_metric]
                ):
                    continue

                if not pd.api.types.is_numeric_dtype(
                    upstream_new[upstream_metric]
                ):
                    continue

                # -----------------------------
                # Calculate key-level changes
                # -----------------------------
                changes = _calculate_key_changes(
                    downstream_old,
                    downstream_new,
                    upstream_old,
                    upstream_new,
                    downstream_key,
                    upstream_key,
                    downstream_metric,
                    upstream_metric,
                )

                # -----------------------------
                # Calculate association
                # -----------------------------
                correlation = _calculate_association(
                    changes
                )

                # -----------------------------
                # Build candidate
                # -----------------------------
                candidate = _build_root_cause_candidate(
                    downstream_metric,
                    upstream_metric,
                    relationship,
                    changes,
                    correlation,
                )

                if candidate is not None:
                    candidates.append(candidate)

    # -----------------------------
    # Rank strongest candidates first
    # -----------------------------
    candidates.sort(
        key=lambda candidate: (
            abs(candidate["correlation"]),
            candidate["relationship"][
                "overlap_percentage"
            ],
            candidate["matched_keys"],
        ),
        reverse=True,
    )

    return candidates
def _find_relationship_keys(
    relationships,
    downstream_columns,
):
    """
    Find relationship keys connected to the downstream dataset.
    """

    relationship_keys = []

    for relationship in relationships:
        left_column = relationship["left_column"]
        right_column = relationship["right_column"]

        if left_column in downstream_columns:
            relationship_keys.append(
                {
                    "downstream_key": left_column,
                    "upstream_key": right_column,
                    "overlap_percentage": relationship[
                        "overlap_percentage"
                    ],
                    "classification": relationship[
                        "classification"
                    ],
                }

            )

        elif right_column in downstream_columns:
            relationship_keys.append(
                {
                    "downstream_key": right_column,
                    "upstream_key": left_column,
                    "overlap_percentage": relationship[
                        "overlap_percentage"
                    ],
                    "classification": relationship[
                        "classification"
                    ],
                }
            )

    return relationship_keys

def _find_upstream_drifts(
    upstream_old,
    upstream_new,
):
    """
    Find columns that show drift in the upstream dataset.
    """

    upstream_report = compare(
        upstream_old,
        upstream_new,
    )

    upstream_drifts = []

    for column, details in upstream_report["column_drift"].items():
        if details["status"] in {"minor_drift", "major_drift"}:
            upstream_drifts.append(column)

    return upstream_drifts


def _calculate_key_changes(
    downstream_old,
    downstream_new,
    upstream_old,
    upstream_new,
    downstream_key,
    upstream_key,
    downstream_metric,
    upstream_metric,
):
    """
    Calculate percentage changes for the same relationship keys.
    """

    downstream_old_values = (
        downstream_old[
            [downstream_key, downstream_metric]
        ]
        .dropna()
        .groupby(downstream_key)[downstream_metric]
        .mean()
    )

    downstream_new_values = (
        downstream_new[
            [downstream_key, downstream_metric]
        ]
        .dropna()
        .groupby(downstream_key)[downstream_metric]
        .mean()
    )

    upstream_old_values = (
        upstream_old[
            [upstream_key, upstream_metric]
        ]
        .dropna()
        .groupby(upstream_key)[upstream_metric]
        .mean()
    )

    upstream_new_values = (
        upstream_new[
            [upstream_key, upstream_metric]
        ]
        .dropna()
        .groupby(upstream_key)[upstream_metric]
        .mean()
    )

    common_keys = (
        set(downstream_old_values.index)
        & set(downstream_new_values.index)
        & set(upstream_old_values.index)
        & set(upstream_new_values.index)
    )

    changes = []

    for key in common_keys:
        downstream_old_value = downstream_old_values[key]
        downstream_new_value = downstream_new_values[key]

        upstream_old_value = upstream_old_values[key]
        upstream_new_value = upstream_new_values[key]

        if downstream_old_value == 0 or upstream_old_value == 0:
            continue

        downstream_change = (
            (downstream_new_value - downstream_old_value)
            / abs(downstream_old_value)
        ) * 100

        upstream_change = (
            (upstream_new_value - upstream_old_value)
            / abs(upstream_old_value)
        ) * 100

        changes.append(
            {
                "key": key,
                "downstream_change": round(
                    downstream_change,
                    2,
                ),
                "upstream_change": round(
                    upstream_change,
                    2,
                ),
            }
        )

    return changes

def _calculate_association(changes):
    """
    Calculate the correlation between upstream and downstream changes.
    """

    if len(changes) < MIN_MATCHED_KEYS:
        return None

    changes_df = pd.DataFrame(changes)

    correlation = changes_df[
        "downstream_change"
    ].corr(
        changes_df["upstream_change"]
    )

    if pd.isna(correlation):
        return None

    return round(correlation, 3)

def _build_root_cause_candidate(
    downstream_metric,
    upstream_metric,
    relationship,
    changes,
    correlation,
):
    """
    Build a plausible root-cause candidate from observed evidence.
    """

    if correlation is None:
        return None

    if abs(correlation) < 0.5:
        return None

    return {
        "downstream_metric": downstream_metric,
        "upstream_metric": upstream_metric,
        "relationship": {
            "downstream_key": relationship["downstream_key"],
            "upstream_key": relationship["upstream_key"],
            "overlap_percentage": relationship[
                "overlap_percentage"
            ],
            "classification": relationship[
                "classification"
            ],
        },
        "correlation": correlation,
        "matched_keys": len(changes),
        "suggestion": (
            f"{upstream_metric} is a plausible contributing "
            f"factor for the drift in {downstream_metric}. "
            "The observed relationship and key-level changes "
            "show an association, but do not prove causation."
        ),
        "evidence": changes,
    }