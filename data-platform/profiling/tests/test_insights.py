import pandas as pd

from src.insights import generate_insights


def test_missing_value_insight():
    df = pd.DataFrame({
        "name": ["A", "B", None, "D"]
    })

    report = {
        "column_summary": [
            {
                "column": "name",
                "null_percent": 25.0
            }
        ],
        "outliers": {},
        "quality_scorecard": {
            "overall_score": 75.0
        }
    }

    insights = generate_insights(df, report)

    assert "name has 25.0% missing values." in insights


def test_outlier_insight():
    df = pd.DataFrame({
        "amount": [10, 20, 30, 999]
    })

    report = {
        "column_summary": [],
        "outliers": {
            "amount": {
                "outlier_count": 1
            }
        },
        "quality_scorecard": {
            "overall_score": 90.0
        }
    }

    insights = generate_insights(df, report)

    assert "amount contains 1 detected outliers." in insights


def test_quality_score_not_repeated_as_insight():
    df = pd.DataFrame({
        "id": [1, 2, 3]
    })

    report = {
        "column_summary": [],
        "outliers": {},
        "quality_scorecard": {
            "overall_score": 99.65
        }
    }

    insights = generate_insights(df, report)

    assert "Overall data quality score is 99.65 out of 100." not in insights

def test_no_missing_values_no_missing_insight():
    df = pd.DataFrame({
        "name": ["A", "B", "C"]
    })

    report = {
        "column_summary": [
            {
                "column": "name",
                "null_percent": 0.0
            }
        ],
        "outliers": {},
        "quality_scorecard": {
            "overall_score": 100.0
        }
    }

    insights = generate_insights(df, report)

    assert "name has 0.0% missing values." not in insights


def test_empty_report():
    df = pd.DataFrame({
        "id": [1, 2, 3]
    })

    report = {}

    insights = generate_insights(df, report)

    assert insights == []

def test_dominant_category_insight():
    df = pd.DataFrame({
        "warehouse": [
            "WH1", "WH1", "WH1", "WH1",
            "WH2", "WH2",
            "WH3", "WH4"
        ]
    })

    report = {
        "column_summary": [],
        "outliers": {},
        "quality_scorecard": {
            "overall_score": 90.0
        }
    }

    insights = generate_insights(df, report)

    assert "WH1 accounts for 50.0% of all records in warehouse." in insights


def test_strong_correlation_insight():
    df = pd.DataFrame({
        "quantity_sold": [10, 20, 30, 40],
        "total_amount": [100, 200, 300, 400]
    })

    report = {
        "column_summary": [],
        "outliers": {},
        "top_correlations": [
            {
                "column1": "quantity_sold",
                "column2": "total_amount",
                "correlation": 0.95
            }
        ],
        "quality_scorecard": {
            "overall_score": 90.0
        }
    }

    insights = generate_insights(df, report)

    assert (
        "quantity_sold and total_amount have a strong "
        "positive correlation of 0.95."
    ) in insights


def test_weak_correlation_no_insight():
    df = pd.DataFrame({
        "quantity_sold": [10, 20, 30, 40],
        "total_amount": [100, 150, 300, 250]
    })

    report = {
        "column_summary": [],
        "outliers": {},
        "top_correlations": [
            {
                "column1": "quantity_sold",
                "column2": "total_amount",
                "correlation": 0.4
            }
        ],
        "quality_scorecard": {
            "overall_score": 90.0
        }
    }

    insights = generate_insights(df, report)

    assert not any(
        "strong" in insight and "correlation" in insight
        for insight in insights
    )


def test_cumulative_concentration_insight():
    # 3 of 6 warehouses hold 80% of records
    df = pd.DataFrame({
        "warehouse_id": ["WH1"] * 30
        + ["WH2"] * 30
        + ["WH3"] * 20
        + ["WH4"] * 10
        + ["WH5"] * 5
        + ["WH6"] * 5
    })

    insights = generate_insights(df, {})

    assert (
        "3 categories in warehouse_id account for at least 80% of all records."
        in insights
    )