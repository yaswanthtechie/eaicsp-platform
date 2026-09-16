import json

from profile_diff import compare_profiles


def make_profile(
    score=90,
    columns=None,
    statistics=None,
    outliers=None,
):
    if columns is None:
        columns = []

    if statistics is None:
        statistics = {}

    if outliers is None:
        outliers = {}

    return {
        "shape": [100, len(columns)],
        "columns": [item["column"] for item in columns],
        "column_summary": columns,
        "statistics": statistics,
        "outliers": outliers,
        "quality_score": {
            "score": score,
        },
    }


def test_quality_score_change():

    old = make_profile(score=95)
    new = make_profile(score=82)

    result = compare_profiles(old, new)

    assert result["quality_score"]["old"] == 95
    assert result["quality_score"]["new"] == 82
    assert result["quality_score"]["change"] == -13


def test_added_column():

    old = make_profile(
        columns=[
            {
                "column": "sku_id",
                "dtype": "object",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 10,
                "role": "ID",
                "cardinality": "High Cardinality",
            }
        ]
    )

    new = make_profile(
        columns=[
            {
                "column": "sku_id",
                "dtype": "object",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 10,
                "role": "ID",
                "cardinality": "High Cardinality",
            },
            {
                "column": "unit_price",
                "dtype": "float64",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 50,
                "role": "Measure",
                "cardinality": "High Cardinality",
            },
        ]
    )

    result = compare_profiles(old, new)

    assert result["added_columns"] == ["unit_price"]
    assert result["removed_columns"] == []


def test_removed_column():

    old = make_profile(
        columns=[
            {
                "column": "sku_id",
                "dtype": "object",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 10,
                "role": "ID",
                "cardinality": "High Cardinality",
            },
            {
                "column": "unit_price",
                "dtype": "float64",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 50,
                "role": "Measure",
                "cardinality": "High Cardinality",
            },
        ]
    )

    new = make_profile(
        columns=[
            {
                "column": "sku_id",
                "dtype": "object",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 10,
                "role": "ID",
                "cardinality": "High Cardinality",
            }
        ]
    )

    result = compare_profiles(old, new)

    assert result["added_columns"] == []
    assert result["removed_columns"] == ["unit_price"]


def test_changed_numeric_statistics():

    columns = [
        {
            "column": "quantity_sold",
            "dtype": "float64",
            "null_count": 0,
            "null_percent": 0.0,
            "unique_count": 50,
            "role": "Measure",
            "cardinality": "High Cardinality",
        }
    ]

    old = make_profile(
        columns=columns,
        statistics={
            "quantity_sold": {
                "count": "100",
                "mean": 50.0,
                "std": 10.0,
                "min": 1.0,
                "25%": 25.0,
                "50%": 50.0,
                "75%": 75.0,
                "max": 100.0,
            }
        },
        outliers={
            "quantity_sold": {
                "lower_limit": -50.0,
                "upper_limit": 150.0,
                "outlier_count": 2,
            }
        },
    )

    new = make_profile(
        columns=columns,
        statistics={
            "quantity_sold": {
                "count": "100",
                "mean": 75.0,
                "std": 20.0,
                "min": 1.0,
                "25%": 30.0,
                "50%": 70.0,
                "75%": 90.0,
                "max": 200.0,
            }
        },
        outliers={
            "quantity_sold": {
                "lower_limit": -60.0,
                "upper_limit": 180.0,
                "outlier_count": 8,
            }
        },
    )

    result = compare_profiles(old, new)

    changed = result["changed_columns"][0]

    assert changed["column"] == "quantity_sold"

    assert changed["changes"]["stat_mean"]["old"] == 50.0
    assert changed["changes"]["stat_mean"]["new"] == 75.0

    assert (
        changed["changes"]["outlier_outlier_count"]["old"]
        == 2
    )

    assert (
        changed["changes"]["outlier_outlier_count"]["new"]
        == 8
    )


def test_no_profile_changes():

    profile = make_profile(
        score=90,
        columns=[
            {
                "column": "sku_id",
                "dtype": "object",
                "null_count": 0,
                "null_percent": 0.0,
                "unique_count": 10,
                "role": "ID",
                "cardinality": "High Cardinality",
            }
        ]
    )

    result = compare_profiles(profile, profile)

    assert result["quality_score"] is None
    assert result["dataset_shape"] is None
    assert result["added_columns"] == []
    assert result["removed_columns"] == []
    assert result["changed_columns"] == []