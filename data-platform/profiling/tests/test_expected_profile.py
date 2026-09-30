from src.expected_profile import (
    create_expected_profile,
    save_expected_profile,
    load_expected_profile,
    benchmark_profile,
)
def test_create_expected_profile():
    profile_report = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "sku_id",
                "dtype": "object",
                "role": "identifier",
                "cardinality": 50,
                "null_percent": 0.0,
            },
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            },
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    result = create_expected_profile(
        profile_report
    )

    assert result["version"] == "1.0"
    assert result["source"] == "trusted_profile"

    assert (
        result["baseline"]["row_count"]["expected"]
        == 5000
    )

    assert (
        result["baseline"]["row_count"]["tolerance_percent"]
        == 5.0
    )

    assert (
        result["baseline"]["quality_score"]["baseline"]
        == 92.0
    )

    assert (
        result["baseline"]["quality_score"]["minimum"]
        == 87.0
    )

    assert (
        result["baseline"]["columns"]["quantity_sold"]
        ["null_percent"]["expected"]
        == 3.0
    )

    assert (
        result["baseline"]["columns"]["quantity_sold"]
        ["null_percent"]["maximum"]
        == 5.0
    )

    assert (
        result["baseline"]["columns"]["quantity_sold"]
        ["mean"]["expected"]
        == 50.0
    )

    assert (
        result["baseline"]["columns"]["quantity_sold"]
        ["mean"]["tolerance_percent"]
        == 10.0
    )

def test_save_and_load_expected_profile(tmp_path):
    profile_report = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    expected_profile = create_expected_profile(
        profile_report
    )

    profile_path = tmp_path / "expected_profile.json"

    save_expected_profile(
        expected_profile,
        profile_path,
    )

    loaded_profile = load_expected_profile(
        profile_path
    )

    assert loaded_profile == expected_profile

def test_benchmark_profile_passes_when_current_run_is_within_expectations():
    profile_report = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    expected_profile = create_expected_profile(
        profile_report
    )

    current_profile = {
        "shape": [4980, 5],
        "quality_score": {
            "score": 90
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 4.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 53.0
            }
        },
    }

    result = benchmark_profile(
        expected_profile,
        current_profile,
    )

    assert result["status"] == "pass"
    assert result["deviations"] == []

def test_benchmark_profile_fails_when_current_run_exceeds_expectations():
    profile_report = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    expected_profile = create_expected_profile(
        profile_report
    )

    current_profile = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 80
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 8.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 70.0
            }
        },
    }

    result = benchmark_profile(
        expected_profile,
        current_profile,
    )

    assert result["status"] == "fail"

    metrics = {
        deviation["metric"]
        for deviation in result["deviations"]
    }

    assert "quality_score" in metrics
    assert "quantity_sold.null_percent" in metrics
    assert "quantity_sold.mean" in metrics

def test_benchmark_profile_fails_on_dtype_change():
    profile_report = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "int64",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    expected_profile = create_expected_profile(
        profile_report
    )

    current_profile = {
        "shape": [5000, 5],
        "quality_score": {
            "score": 92
        },
        "column_summary": [
            {
                "column": "quantity_sold",
                "dtype": "object",
                "role": "numeric",
                "cardinality": 100,
                "null_percent": 3.0,
            }
        ],
        "statistics": {
            "quantity_sold": {
                "mean": 50.0
            }
        },
    }

    result = benchmark_profile(
        expected_profile,
        current_profile,
    )

    assert result["status"] == "fail"

    metrics = {
        deviation["metric"]
        for deviation in result["deviations"]
    }

    assert "quantity_sold.dtype" in metrics