import pytest
from src.parity import compare_reports


def test_compare_reports_perfect_match():
    """Test when both reports match perfectly, returning an empty list."""
    pandas_report = {
        "shape": [100, 2],
        "column_summary": [{"column": "col1", "null_count": 0, "unique_count": 10}],
        "statistics": {
            "col1": {"count": 100, "mean": 5.0, "std": 1.2, "min": 0, "25%": 2, "50%": 5, "75%": 8, "max": 10}
        },
        "outliers": {"col1": {"outlier_count": 2}}
    }

    sql_report = {
        "shape": [100, 2],
        "column_summary": [{"column": "col1", "null_count": 0, "unique_count": 10}],
        "statistics": {
            "col1": {"count": 100, "mean": 5.0, "std": 1.2, "min": 0, "25%": 2, "50%": 5, "75%": 8, "max": 10}
        },
        "outliers": {"col1": {"outlier_count": 2}}
    }

    mismatches = compare_reports(pandas_report, sql_report)
    assert mismatches == []


def test_compare_reports_all_mismatches():
    """Test all mismatch branches (shape, missing columns, differing values, outliers)."""
    pandas_report = {
        "shape": [100, 2],
        "column_summary": [
            {"column": "col1", "null_count": 0, "unique_count": 10},
            {"column": "col2", "null_count": 5, "unique_count": 20}  # Missing in SQL
        ],
        "statistics": {
            "col1": {"count": 100, "mean": 5.0, "std": 1.2, "min": 0, "25%": 2, "50%": 5, "75%": 8, "max": 10},
            "col3": {"count": 50, "mean": 1.0, "std": 0.5, "min": 0, "25%": 0, "50%": 1, "75%": 1, "max": 2}
            # Missing in SQL
        },
        "outliers": {"col1": {"outlier_count": 2}}
    }

    sql_report = {
        "shape": [99, 2],  # Shape mismatch
        "column_summary": [
            {"column": "col1", "null_count": 1, "unique_count": 9}  # Value mismatch
        ],
        "statistics": {
            "col1": {"count": 99, "mean": 4.5, "std": 1.2, "min": 0, "25%": 2, "50%": 5, "75%": 8, "max": 10}
            # Value mismatch on count and mean
        },
        "outliers": {"col1": {"outlier_count": 5}}  # Outlier mismatch
    }

    mismatches = compare_reports(pandas_report, sql_report)

    # Assert specific error messages were captured
    assert "shape: pandas=[100, 2] sql=[99, 2]" in mismatches
    assert "col2: missing from SQL report" in mismatches
    assert "col1.null_count: pandas=0 sql=1" in mismatches
    assert "col1.unique_count: pandas=10 sql=9" in mismatches
    assert "col3: no SQL statistics" in mismatches
    assert "col1.count: pandas=100 sql=99" in mismatches
    assert "col1.mean: pandas=5.0 sql=4.5" in mismatches
    assert "col1.outlier_count: pandas=2 sql=5" in mismatches