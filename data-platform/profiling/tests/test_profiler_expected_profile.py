from src.profiler import Profiler


def test_profiler_expected_profile_benchmarking():
    profiler = Profiler()

    trusted_profile = {
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

    expected_profile = profiler.create_expected_profile(
        trusted_profile
    )

    result = profiler.benchmark_profile(
        expected_profile,
        current_profile,
    )

    assert expected_profile["version"] == "1.0"
    assert result["status"] == "pass"
    assert result["deviations"] == []

import pandas as pd

from src.profiler import Profiler


def test_profiler_expected_profile_end_to_end():
    profiler = Profiler()

    trusted_df = pd.DataFrame(
        {
            "sku_id": ["A", "B", "C", "D"],
            "quantity_sold": [10, 20, 30, 40],
            "unit_price": [100, 110, 120, 130],
        }
    )

    current_df = pd.DataFrame(
        {
            "sku_id": ["A", "B", "C", "D"],
            "quantity_sold": [10, None, 30, 40],
            "unit_price": [100, 110, 120, 130],
        }
    )

    # Create the trusted baseline from an actual
    # profiling result.
    trusted_profile = profiler.profile(
        trusted_df
    )

    expected_profile = profiler.create_expected_profile(
        trusted_profile
    )

    # Profile the new run.
    current_profile = profiler.profile(
        current_df
    )

    result = profiler.benchmark_profile(
        expected_profile,
        current_profile,
    )

    assert expected_profile["version"] == "1.0"
    assert result["status"] == "fail"

    metrics = {
        deviation["metric"]
        for deviation in result["deviations"]
    }

    assert "quality_score" in metrics

def test_profiler_executive_summary():
    profiler = Profiler()

    profiling_report = {
        "quality_score": {
            "score": 88
        },
        "missing_values": 5,
        "duplicate_rows": 1,
        "total_outliers": 2,
    }

    etl_output = {
        "status": "success",
        "warnings": 0,
        "errors": 0,
        "sla_status": "met",
    }

    validation_output = {
        "status": "pass",
        "invalid_rows": 0,
        "validation_failures": 0,
        "errors": 0,
        "warnings": 0,
    }

    summary = profiler.executive_summary(
        profiling_report=profiling_report,
        etl_output=etl_output,
        validation_output=validation_output,
    )

    assert isinstance(summary, str)
    assert "quality score" in summary
    assert "The ETL pipeline status" in summary
    assert "Validation status" in summary