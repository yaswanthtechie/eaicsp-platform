import math
import json
from pathlib import Path


EXPECTED_PROFILE_VERSION = "1.0"


def create_expected_profile(
    profile_report,
    row_count_tolerance_percent=5.0,
    quality_score_tolerance=5.0,
    null_rate_tolerance_points=2.0,
    numeric_tolerance_percent=10.0,
):
    """
    Create an expected profile from a trusted profiling result.

    The expected profile is a baseline used to evaluate
    future profiling runs.
    """

    if not isinstance(profile_report, dict):
        raise TypeError(
            "profile_report must be a dictionary"
        )

    shape = profile_report.get("shape")

    if (
        not isinstance(shape, (list, tuple))
        or len(shape) != 2
    ):
        raise ValueError(
            "profile_report must contain a valid shape"
        )

    quality_score = profile_report.get(
        "quality_score"
    )

    if not isinstance(quality_score, dict):
        raise ValueError(
            "profile_report must contain quality_score"
        )

    score = quality_score.get("score")

    if score is None:
        raise ValueError(
            "profile_report must contain quality_score.score"
        )

    column_summary = profile_report.get(
        "column_summary",
        [],
    )

    statistics = profile_report.get(
        "statistics",
        {},
    )

    expected_columns = {}

    for column in column_summary:
        column_name = column.get("column")

        if not column_name:
            continue

        null_percent = column.get(
            "null_percent",
            0.0,
        )

        if null_percent is None:
            null_percent = 0.0

        expected_column = {
            "dtype": column.get("dtype"),
            "role": column.get("role"),
            "cardinality": column.get("cardinality"),
            "null_percent": {
                "expected": float(null_percent),
                "maximum": round(
                    float(null_percent)
                    + null_rate_tolerance_points,
                    2,
                ),
            },
        }

        column_stats = statistics.get(
            column_name,
            {},
        )

        mean = column_stats.get("mean")

        if mean is not None:
            mean_value = float(mean)

            if math.isfinite(mean_value):
                expected_column["mean"] = {
                    "expected": mean_value,
                    "tolerance_percent": (
                        numeric_tolerance_percent
                    ),
                }

        expected_columns[column_name] = expected_column

    expected_profile = {
        "version": EXPECTED_PROFILE_VERSION,
        "source": "trusted_profile",
        "baseline": {
            "row_count": {
                "expected": int(shape[0]),
                "tolerance_percent": (
                    row_count_tolerance_percent
                ),
            },
            "quality_score": {
                "baseline": float(score),
                "minimum": max(
                    0.0,
                    float(score)
                    - quality_score_tolerance,
                ),
            },
            "columns": expected_columns,
        },
    }

    return expected_profile


def save_expected_profile(
    expected_profile,
    path,
):
    """
    Save an expected profile to a JSON file.
    """

    if not isinstance(expected_profile, dict):
        raise TypeError(
            "expected_profile must be a dictionary"
        )

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            expected_profile,
            file,
            indent=2,
        )


def load_expected_profile(path):
    """
    Load an expected profile from a JSON file.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Expected profile not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        expected_profile = json.load(file)

    if not isinstance(expected_profile, dict):
        raise ValueError(
            "Expected profile JSON must contain an object"
        )

    return expected_profile

def benchmark_profile(
    expected_profile,
    current_profile,
):
    """
    Compare a current profiling result against
    an expected profile baseline.
    """

    if not isinstance(expected_profile, dict):
        raise TypeError(
            "expected_profile must be a dictionary"
        )

    if not isinstance(current_profile, dict):
        raise TypeError(
            "current_profile must be a dictionary"
        )

    baseline = expected_profile.get("baseline")

    if not isinstance(baseline, dict):
        raise ValueError(
            "expected_profile must contain baseline"
        )

    deviations = []

    # ---------------------------------
    # Row-count benchmark
    # ---------------------------------
    row_count_config = baseline.get(
        "row_count",
        {},
    )

    expected_rows = row_count_config.get(
        "expected"
    )

    tolerance_percent = row_count_config.get(
        "tolerance_percent",
        0.0,
    )

    current_shape = current_profile.get("shape")

    if (
        expected_rows is not None
        and isinstance(current_shape, (list, tuple))
        and len(current_shape) == 2
    ):
        current_rows = current_shape[0]

        allowed_difference = (
            expected_rows
            * tolerance_percent
            / 100
        )

        minimum_rows = (
            expected_rows - allowed_difference
        )

        maximum_rows = (
            expected_rows + allowed_difference
        )

        if not (
            minimum_rows
            <= current_rows
            <= maximum_rows
        ):
            deviations.append(
                {
                    "metric": "row_count",
                    "expected": expected_rows,
                    "current": current_rows,
                    "status": "fail",
                    "reason": (
                        "Current row count is outside "
                        "the expected tolerance"
                    ),
                }
            )

    # ---------------------------------
    # Quality-score benchmark
    # ---------------------------------
    quality_config = baseline.get(
        "quality_score",
        {},
    )

    minimum_quality = quality_config.get(
        "minimum"
    )

    current_quality = (
        current_profile.get(
            "quality_score",
            {},
        ).get("score")
    )

    # A run with no quality score cannot be checked, so it must not
    # quietly count as meeting the minimum.
    if (
        minimum_quality is not None
        and current_quality is None
    ):
        deviations.append(
            {
                "metric": "quality_score",
                "expected_minimum": minimum_quality,
                "current": None,
                "status": "fail",
                "reason": (
                    "Current profile has no quality score, so it "
                    "cannot be checked against the expected minimum"
                ),
            }
        )

    elif (
        minimum_quality is not None
        and current_quality is not None
        and current_quality < minimum_quality
    ):
        deviations.append(
            {
                "metric": "quality_score",
                "expected_minimum": minimum_quality,
                "current": current_quality,
                "status": "fail",
                "reason": (
                    "Current quality score is below "
                    "the expected minimum"
                ),
            }
        )

    # ---------------------------------
    # Column-level benchmarks
    # ---------------------------------
    expected_columns = baseline.get(
        "columns",
        {},
    )

    current_columns = {}

    for column in current_profile.get(
        "column_summary",
        [],
    ):
        column_name = column.get("column")

        if column_name:
            current_columns[column_name] = column

    current_statistics = current_profile.get(
        "statistics",
        {},
    )

    # IMPORTANT:
    # expected_column is created here.
    # All column-level checks must stay
    # inside this loop.
    for column_name, expected_column in (
        expected_columns.items()
    ):
        current_column = current_columns.get(
            column_name
        )

        # -----------------------------
        # Missing column benchmark
        # -----------------------------
        if current_column is None:
            deviations.append(
                {
                    "metric": column_name,
                    "status": "fail",
                    "reason": (
                        "Expected column is missing "
                        "from the current profile"
                    ),
                }
            )
            continue

        # -----------------------------
        # Data type benchmark
        # -----------------------------
        expected_dtype = expected_column.get(
            "dtype"
        )

        current_dtype = current_column.get(
            "dtype"
        )

        if (
            expected_dtype is not None
            and current_dtype is not None
            and expected_dtype != current_dtype
        ):
            deviations.append(
                {
                    "metric": f"{column_name}.dtype",
                    "expected": expected_dtype,
                    "current": current_dtype,
                    "status": "fail",
                    "reason": (
                        "Current data type does not "
                        "match the expected profile"
                    ),
                }
            )

        # -----------------------------
        # Null-rate benchmark
        # -----------------------------
        null_config = expected_column.get(
            "null_percent",
            {},
        )

        maximum_null = null_config.get(
            "maximum"
        )

        current_null = current_column.get(
            "null_percent"
        )

        if (
            maximum_null is not None
            and current_null is not None
            and current_null > maximum_null
        ):
            deviations.append(
                {
                    "metric": (
                        f"{column_name}.null_percent"
                    ),
                    "expected_maximum": maximum_null,
                    "current": current_null,
                    "status": "fail",
                    "reason": (
                        "Current null rate exceeds "
                        "the expected maximum"
                    ),
                }
            )

        # -----------------------------
        # Numeric mean benchmark
        # -----------------------------
        mean_config = expected_column.get(
            "mean"
        )

        if mean_config:
            expected_mean = mean_config.get(
                "expected"
            )

            mean_tolerance = mean_config.get(
                "tolerance_percent",
                0.0,
            )

            current_mean = (
                current_statistics.get(
                    column_name,
                    {},
                ).get("mean")
            )

            if (
                expected_mean is not None
                and current_mean is not None
            ):
                if expected_mean == 0:
                    mean_deviation = (
                        current_mean != 0
                    )
                else:
                    allowed_mean_difference = (
                        abs(expected_mean)
                        * mean_tolerance
                        / 100
                    )

                    mean_deviation = (
                        abs(
                            current_mean
                            - expected_mean
                        )
                        > allowed_mean_difference
                    )

                if mean_deviation:
                    deviations.append(
                        {
                            "metric": (
                                f"{column_name}.mean"
                            ),
                            "expected": expected_mean,
                            "current": current_mean,
                            "tolerance_percent": (
                                mean_tolerance
                            ),
                            "status": "fail",
                            "reason": (
                                "Current mean is "
                                "outside the expected "
                                "tolerance"
                            ),
                        }
                    )

    # ---------------------------------
# Unexpected new columns
# ---------------------------------
# A column nobody expected is a schema change; it breaks downstream
# consumers just as often as a missing column does. Only checked when
# the expected profile actually lists its columns.
    if expected_columns:
        for column_name in sorted(
            set(current_columns) - set(expected_columns)
        ):
            deviations.append(
                {
                    "metric": column_name,
                    "status": "fail",
                    "reason": (
                        "Unexpected column is not in "
                        "the expected profile"
                    ),
                }
            )
    # ---------------------------------
    # Final benchmark result
    # ---------------------------------
    return {
        "status": (
            "fail"
            if deviations
            else "pass"
        ),
        "deviations": deviations,
        "expected_profile_version": (
            expected_profile.get("version")
        ),
    }